"""E2E-style tests for the complete approval flow.

Tests endpoint orchestration with mocked DB — verifies the full
approve/reject/edit lifecycle, department isolation, and decision tracking.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from services.gateway.src.auth import JWTClaims
from services.gateway.src.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rsa_keypair() -> tuple[bytes, bytes]:
    """Generate a 2048-bit RSA key pair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(
    private_pem: bytes,
    *,
    dept: str = "cac",
    role: str = "hod",
    sub: str | None = None,
) -> str:
    """Create a signed JWT for integration testing."""
    if sub is None:
        sub = f"{dept}.hod@brooker.co.th"
    return pyjwt.encode(
        {
            "sub": sub,
            "dept": dept,
            "role": role,
            "permissions": [f"read:{dept}", f"approve:{dept}"],
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=24),
        },
        private_pem,
        algorithm="RS256",
    )


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _FakeAcquire:
    """Async context manager mimicking asyncpg pool.acquire()."""

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


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestFullApprovalFlow:
    """End-to-end: create proposal in mock DB -> GET -> approve -> verify."""

    @pytest.mark.asyncio
    async def test_full_approval_flow(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """GET proposal -> POST approve -> status changed + decision inserted."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        pending_row = dict(_SAMPLE_ROW)
        conn.fetchrow = AsyncMock(return_value=pending_row)
        conn.execute = AsyncMock(return_value="UPDATE 1")

        claims = JWTClaims(
            sub="cac.hod@brooker.co.th",
            dept="cac",
            role="hod",
            permissions=["read:cac", "approve:cac"],
            proposal_id=None,
        )

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt", return_value=claims):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Step 1: GET the proposal
                get_resp = await client.get(
                    "/api/proposals/chg_0001", headers=_auth_header(token)
                )
                assert get_resp.status_code == 200
                assert get_resp.json()["id"] == "chg_0001"
                assert get_resp.json()["status"] == "pending"

                # Step 2: Approve
                approve_resp = await client.post(
                    "/api/proposals/chg_0001/approve",
                    headers=_auth_header(token),
                )

        assert approve_resp.status_code == 200
        body = approve_resp.json()
        assert body["status"] == "approved"
        assert body["proposal_id"] == "chg_0001"

        # Verify DB calls: atomic UPDATE via fetchrow + INSERT via execute
        # The UPDATE RETURNING is done via fetchrow, INSERT via execute
        assert conn.execute.call_count >= 1
        insert_sql = conn.execute.call_args_list[0][0][0]
        assert "approval_decisions" in insert_sql.lower()


class TestDeptIsolation:
    """Department isolation: cross-department access must be blocked."""

    @pytest.mark.asyncio
    async def test_dept_isolation_blocks_cross_access(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """CAC proposal + HR token -> 403 DEPT_MISMATCH."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="hr")
        pool, conn = _mock_pool()

        # Proposal belongs to cac
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))

        hr_claims = JWTClaims(
            sub="hr.hod@brooker.co.th",
            dept="hr",
            role="hod",
            permissions=["read:hr", "approve:hr"],
            proposal_id=None,
        )

        app.state.db_pool = pool
        with patch(
            "services.gateway.src.auth.validate_jwt",
            return_value=hr_claims,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/proposals/chg_0001", headers=_auth_header(token)
                )

        assert resp.status_code == 403
        assert resp.json()["code"] == "DEPT_MISMATCH"


class TestRejectionFlow:
    """Rejection with reason: pending -> rejected + reason stored."""

    @pytest.mark.asyncio
    async def test_rejection_flow_with_reason(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Create pending -> reject with reason -> verify status + reason."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        claims = JWTClaims(
            sub="cac.hod@brooker.co.th",
            dept="cac",
            role="hod",
            permissions=["read:cac", "approve:cac"],
            proposal_id=None,
        )

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt", return_value=claims):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/reject",
                    headers=_auth_header(token),
                    json={"reason": "Rate source unverified"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["proposal_id"] == "chg_0001"

        # Verify DB calls: atomic UPDATE via fetchrow + INSERT via execute
        assert conn.execute.call_count >= 1
        insert_sql = conn.execute.call_args_list[0][0][0]
        assert "rejection_reason" in insert_sql.lower()
        insert_args = conn.execute.call_args_list[0][0]
        assert "Rate source unverified" in insert_args


class TestEditFlow:
    """Edit flow: pending -> edit with new value -> approved + edited_value stored."""

    @pytest.mark.asyncio
    async def test_edit_flow(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Create pending -> edit with new value -> verify approved + edited_value."""
        private_pem, public_pem = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        claims = JWTClaims(
            sub="cac.hod@brooker.co.th",
            dept="cac",
            role="hod",
            permissions=["read:cac", "approve:cac"],
            proposal_id=None,
        )

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt", return_value=claims):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/edit",
                    headers=_auth_header(token),
                    json={"edited_value": "3.20"},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["proposal_id"] == "chg_0001"

        # Verify DB calls: atomic UPDATE via fetchrow + INSERT via execute
        assert conn.execute.call_count >= 1
        insert_sql = conn.execute.call_args_list[0][0][0]
        assert "edited_value" in insert_sql.lower()
        insert_args = conn.execute.call_args_list[0][0]
        assert "3.20" in insert_args
