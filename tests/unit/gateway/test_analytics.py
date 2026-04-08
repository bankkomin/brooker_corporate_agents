"""Unit tests for gateway analytics summary endpoint with dept RBAC."""
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


class TestAnalyticsSummary:
    """GET /api/analytics/summary — dept-scoped summary statistics."""

    @pytest.mark.asyncio
    async def test_summary_returns_correct_counts(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Summary returns pending, approved_today, escalations, avg_confidence."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        # fetchval returns different values for each sequential call
        conn.fetchval = AsyncMock(side_effect=[5, 2, 3, 0.87])

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
                    "/api/analytics/summary", headers=_auth_header(token)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending"] == 5
        assert body["approved_today"] == 2
        assert body["escalations"] == 3
        assert abs(body["avg_confidence"] - 0.87) < 0.001

    @pytest.mark.asyncio
    async def test_summary_all_zeros_when_no_data(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Summary returns zeros and null avg_confidence for empty department."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="hr")
        pool, conn = _mock_pool()

        # All counts are 0, AVG returns None from DB
        conn.fetchval = AsyncMock(side_effect=[0, 0, 0, None])

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
                    "/api/analytics/summary", headers=_auth_header(token)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending"] == 0
        assert body["approved_today"] == 0
        assert body["escalations"] == 0
        assert body["avg_confidence"] is None

    @pytest.mark.asyncio
    async def test_summary_executes_four_queries(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Summary endpoint executes exactly 4 fetchval queries."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchval = AsyncMock(side_effect=[10, 4, 1, 0.75])

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
                await client.get(
                    "/api/analytics/summary", headers=_auth_header(token)
                )

        assert conn.fetchval.call_count == 4

    @pytest.mark.asyncio
    async def test_summary_uses_dept_scoping_in_all_queries(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """All 4 analytics queries include dept as a parameter."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchval = AsyncMock(side_effect=[3, 1, 0, 0.9])

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
                await client.get(
                    "/api/analytics/summary", headers=_auth_header(token)
                )

        # Every query should pass dept ("cac") as a parameter
        for call in conn.fetchval.call_args_list:
            args = call[0]
            assert "cac" in args, (
                f"Query missing dept param: {args[0]!r} called with {args[1:]}"
            )


class TestAnalyticsAuth:
    """Authentication enforcement for analytics endpoints."""

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self) -> None:
        """Request without Authorization header returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/analytics/summary")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self) -> None:
        """Request with a garbage token returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/analytics/summary",
                headers={"Authorization": "Bearer garbage.token.here"},
            )

        assert resp.status_code == 401
