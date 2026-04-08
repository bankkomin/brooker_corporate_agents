"""Unit tests for gateway escalation endpoints with dept RBAC."""
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


_SAMPLE_ESCALATION = {
    "id": 1,
    "created_at": datetime(2026, 3, 1, 12, 0, 0),
    "interaction_id": 42,
    "severity": "high",
    "trigger_type": "confidence_threshold",
    "detail": "Confidence below 0.5 threshold",
    "paperclip_ticket_id": "TKT-001",
    "resolved_at": None,
    "resolved_by": None,
    "dept": "cac",
}


class TestListEscalations:
    """GET /api/escalations — list dept-scoped escalations."""

    @pytest.mark.asyncio
    async def test_list_returns_dept_scoped_results(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """List returns only escalations matching the JWT dept claim."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        rows = [dict(_SAMPLE_ESCALATION)]
        conn.fetch = AsyncMock(return_value=rows)

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01",
                dept="cac",
                role="hod",
                permissions=["read", "approve"],
                proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/escalations", headers=_auth_header(token)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert "escalations" in body
        assert "total" in body
        assert body["total"] == 1
        assert body["escalations"][0]["id"] == 1
        assert body["escalations"][0]["severity"] == "high"

        # Verify dept-scoped query was executed
        call_args = conn.fetch.call_args
        sql = call_args[0][0].lower()
        assert "dept" in sql or "$1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_orders_by_severity_then_created_at(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Results are ordered by severity ASC then created_at DESC."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        rows = [
            dict(_SAMPLE_ESCALATION, id=1, severity="critical"),
            dict(_SAMPLE_ESCALATION, id=2, severity="high"),
        ]
        conn.fetch = AsyncMock(return_value=rows)

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-cac-01",
                dept="cac",
                role="hod",
                permissions=["read", "approve"],
                proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/escalations", headers=_auth_header(token)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

        # Verify ORDER BY clause in query
        call_args = conn.fetch.call_args
        sql = call_args[0][0].lower()
        assert "order by" in sql
        assert "severity" in sql

    @pytest.mark.asyncio
    async def test_list_returns_empty_list_when_no_escalations(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Empty department returns empty escalations list with total=0."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="hr")
        pool, conn = _mock_pool()

        conn.fetch = AsyncMock(return_value=[])

        app.state.db_pool = pool
        with patch("services.gateway.src.auth.validate_jwt") as mock_validate:
            from services.gateway.src.auth import JWTClaims

            mock_validate.return_value = JWTClaims(
                sub="hod-hr-01",
                dept="hr",
                role="hod",
                permissions=["read"],
                proposal_id=None,
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/escalations", headers=_auth_header(token)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["escalations"] == []
        assert body["total"] == 0


class TestEscalationsAuth:
    """Authentication enforcement for escalation endpoints."""

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self) -> None:
        """Request without Authorization header returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/escalations")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self) -> None:
        """Request with a garbage token returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/escalations",
                headers={"Authorization": "Bearer not.a.valid.token"},
            )

        assert resp.status_code == 401
