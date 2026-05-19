"""Unit tests for gateway proposal CRUD endpoints with RBAC dept scoping."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from services.gateway.src.main import app


def _make_token(
    private_pem: bytes,
    *,
    sub: str = "hod-cac-01",
    dept: str = "cac",
    role: str = "hod",
    permissions: list[str] | None = None,
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    """Create a signed JWT for testing."""
    payload: dict = {
        "sub": sub,
        "dept": dept,
        "role": role,
        "permissions": permissions or ["read", "approve"],
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + exp_delta,
    }
    return jwt.encode(payload, private_pem, algorithm="RS256")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _FakeAcquire:
    """Async context manager that mimics asyncpg pool.acquire()."""

    def __init__(self, conn: AsyncMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Create a mock asyncpg pool with connection context manager."""
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquire(conn)
    return pool, conn


_SAMPLE_ROW = {
    "id": "chg_0001",
    "created_at": datetime(2026, 3, 1, 12, 0, 0),
    "agent": "funding-agent",
    "file": "ALCO_Tracker.xlsx",
    "tab": "Funding Facilities",
    "cell": "E8",
    "old_value": "3.10",
    "new_value": "3.15",
    "source": "Slack #cac-committee",
    "confidence": 0.91,
    "reasoning": "Rate updated per discussion",
    "status": "pending",
    "interaction_id": 1,
    "dept": "cac",
}


class TestListProposals:
    """GET /api/proposals — list dept-scoped proposals."""

    @pytest.mark.asyncio
    async def test_list_proposals_returns_dept_scoped_results(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """List returns only proposals matching the JWT dept claim."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        rows = [dict(_SAMPLE_ROW)]
        conn.fetch = AsyncMock(return_value=rows)

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/proposals", headers=_auth_header(token))

        assert resp.status_code == 200
        body = resp.json()
        assert "proposals" in body
        assert body["total"] == 1
        assert body["proposals"][0]["id"] == "chg_0001"

        # Verify the query included dept filtering
        call_args = conn.fetch.call_args
        assert "dept" in call_args[0][0].lower() or "$1" in call_args[0][0]


class TestGetProposal:
    """GET /api/proposals/{proposal_id} — single proposal detail."""

    @pytest.mark.asyncio
    async def test_proposal_not_found_returns_404(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Requesting a non-existent proposal returns 404."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=None)

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/proposals/chg_9999", headers=_auth_header(token)
                )

        assert resp.status_code == 404
        assert resp.json()["code"] == "PROPOSAL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_dept_mismatch_returns_403(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """HR token cannot access CAC proposal — 403 DEPT_MISMATCH."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="hr")
        pool, conn = _mock_pool()

        # Proposal exists but belongs to cac
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-hr-01", dept="hr", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/proposals/chg_0001", headers=_auth_header(token)
                )

        assert resp.status_code == 403
        assert resp.json()["code"] == "DEPT_MISMATCH"


class TestApproveProposal:
    """POST /api/proposals/{proposal_id}/approve."""

    @pytest.mark.asyncio
    async def test_approve_updates_status_and_creates_decision(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Approving a pending proposal updates status and inserts approval_decisions row."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        # Atomic UPDATE RETURNING returns the row on success
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/approve", headers=_auth_header(token)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["proposal_id"] == "chg_0001"

        # Atomic UPDATE via fetchrow + INSERT via execute
        assert conn.fetchrow.call_count >= 1
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_approve_already_approved_returns_409(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Approving an already-approved proposal returns 409 PROPOSAL_NOT_PENDING."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        already_approved = dict(_SAMPLE_ROW, status="approved")
        # First fetchrow (atomic UPDATE) returns None (not pending),
        # second fetchrow (SELECT for error detail) returns existing row.
        conn.fetchrow = AsyncMock(side_effect=[None, already_approved])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/approve", headers=_auth_header(token)
                )

        assert resp.status_code == 409
        assert resp.json()["code"] == "PROPOSAL_NOT_PENDING"


class TestRejectProposal:
    """POST /api/proposals/{proposal_id}/reject."""

    @pytest.mark.asyncio
    async def test_reject_without_reason_returns_422(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Rejecting without a reason returns 422 REJECTION_REASON_REQUIRED."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/reject",
                    headers=_auth_header(token),
                    json={},  # no reason
                )

        assert resp.status_code == 422
        assert resp.json()["code"] == "REJECTION_REASON_REQUIRED"

    @pytest.mark.asyncio
    async def test_reject_already_rejected_returns_409(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Rejecting an already-rejected proposal returns 409."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        already_rejected = dict(_SAMPLE_ROW, status="rejected")
        # The reject endpoint pre-reads the row first (SELECT), checks dept,
        # then checks status. With status="rejected" it returns 409 immediately
        # without a second fetchrow call.
        conn.fetchrow = AsyncMock(return_value=already_rejected)

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/reject",
                    headers=_auth_header(token),
                    json={"reason": "Not relevant"},
                )

        assert resp.status_code == 409
        assert resp.json()["code"] == "PROPOSAL_NOT_PENDING"


class TestEditProposal:
    """POST /api/proposals/{proposal_id}/edit."""

    @pytest.mark.asyncio
    async def test_edit_updates_value_and_approves(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Editing a proposal updates value and sets status to approved."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        # Atomic UPDATE RETURNING returns the row on success
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01", dept="cac", role="hod",
                permissions=["read", "approve"], proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/edit",
                    headers=_auth_header(token),
                    json={"edited_value": "3.20"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["proposal_id"] == "chg_0001"

        # Atomic UPDATE via fetchrow + INSERT via execute
        assert conn.fetchrow.call_count >= 1
        assert conn.execute.call_count >= 1
