"""Unit tests for gateway post-decision hooks."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from services.gateway.src.hooks import (
    on_proposal_approved,
    on_proposal_rejected,
)
from services.gateway.src.main import app

# ---------------------------------------------------------------------------
# Helpers shared across hook unit tests
# ---------------------------------------------------------------------------


def _make_token(
    private_pem: bytes,
    *,
    sub: str = "hod-cac-01",
    dept: str = "cac",
    role: str = "hod",
    permissions: list[str] | None = None,
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
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


# ---------------------------------------------------------------------------
# Pure hook unit tests (no HTTP server)
# ---------------------------------------------------------------------------


class TestOnProposalApproved:
    """on_proposal_approved — must POST to both sync-back and email-notifier."""

    @pytest.mark.asyncio
    async def test_on_proposal_approved_calls_sync_back_and_email(self) -> None:
        """Approval hook fires two POSTs: sync-back + email-notifier."""
        posted_calls: list[tuple[str, dict]] = []

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.gateway.src.hooks.httpx.AsyncClient", return_value=mock_client):
            await on_proposal_approved("chg_0001", "cac")

        assert mock_client.post.call_count == 2

        first_url = mock_client.post.call_args_list[0][0][0]
        second_url = mock_client.post.call_args_list[1][0][0]

        assert "sync-back" in first_url or "process-approved" in first_url
        assert "email-notifier" in second_url or "notify/confirmed" in second_url

        # Second call body must carry the proposal_id and decision
        second_json = mock_client.post.call_args_list[1][1]["json"]
        assert second_json["proposal_id"] == "chg_0001"
        assert second_json["decision"] == "approved"
        assert second_json["dept"] == "cac"


class TestOnProposalRejected:
    """on_proposal_rejected — must POST only to email-notifier, no sync-back."""

    @pytest.mark.asyncio
    async def test_on_proposal_rejected_calls_email_only(self) -> None:
        """Rejection hook fires one POST: email-notifier only (no sync-back)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.gateway.src.hooks.httpx.AsyncClient", return_value=mock_client):
            await on_proposal_rejected("chg_0001", "cac", reason="Not valid")

        # Only one POST — no sync-back for rejections
        assert mock_client.post.call_count == 1

        url = mock_client.post.call_args_list[0][0][0]
        assert "email-notifier" in url or "notify/confirmed" in url

        json_body = mock_client.post.call_args_list[0][1]["json"]
        assert json_body["proposal_id"] == "chg_0001"
        assert json_body["decision"] == "rejected"
        assert json_body["dept"] == "cac"


class TestHookFailureSafety:
    """Downstream failures must never propagate — fire-and-forget contract."""

    @pytest.mark.asyncio
    async def test_hook_failure_does_not_raise(self) -> None:
        """When httpx raises, on_proposal_approved must swallow the error silently."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Must not raise regardless of httpx failure
        with patch("services.gateway.src.hooks.httpx.AsyncClient", return_value=mock_client):
            await on_proposal_approved("chg_0001", "cac")  # no exception expected

    @pytest.mark.asyncio
    async def test_rejection_hook_failure_does_not_raise(self) -> None:
        """When httpx raises during rejection hook, error is swallowed silently."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ConnectionError("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.gateway.src.hooks.httpx.AsyncClient", return_value=mock_client):
            await on_proposal_rejected("chg_0001", "cac")  # no exception expected

    @pytest.mark.asyncio
    async def test_http_error_status_does_not_raise(self) -> None:
        """When the downstream service returns 500, raise_for_status raises — must be swallowed."""
        import httpx as _httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=_httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(),
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.gateway.src.hooks.httpx.AsyncClient", return_value=mock_client):
            await on_proposal_approved("chg_0001", "cac")  # no exception expected


# ---------------------------------------------------------------------------
# Integration test: approve endpoint calls on_proposal_approved
# ---------------------------------------------------------------------------


class TestApproveEndpointTriggersHooks:
    """Full ASGI integration: approve endpoint must invoke on_proposal_approved."""

    @pytest.mark.asyncio
    async def test_approve_endpoint_triggers_hooks(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """POST /approve -> on_proposal_approved called with correct proposal_id + dept."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        app.state.db_pool = pool

        hook_calls: list[tuple[str, str]] = []

        async def _fake_on_approved(proposal_id: str, dept: str) -> None:
            hook_calls.append((proposal_id, dept))

        from services.gateway.src.auth import JWTClaims

        claims = JWTClaims(
            sub="hod-cac-01",
            dept="cac",
            role="hod",
            permissions=["read", "approve"],
            proposal_id=None,
        )

        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=claims),
            patch(
                "services.gateway.src.proposals.on_proposal_approved",
                side_effect=_fake_on_approved,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/approve",
                    headers=_auth_header(token),
                )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # Hook was called exactly once with the right arguments
        assert len(hook_calls) == 1
        assert hook_calls[0] == ("chg_0001", "cac")

    @pytest.mark.asyncio
    async def test_reject_endpoint_triggers_hooks(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """POST /reject -> on_proposal_rejected called with correct args."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        app.state.db_pool = pool

        hook_calls: list[tuple[str, str, str | None]] = []

        async def _fake_on_rejected(
            proposal_id: str, dept: str, reason: str | None = None
        ) -> None:
            hook_calls.append((proposal_id, dept, reason))

        from services.gateway.src.auth import JWTClaims

        claims = JWTClaims(
            sub="hod-cac-01",
            dept="cac",
            role="hod",
            permissions=["read", "approve"],
            proposal_id=None,
        )

        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=claims),
            patch(
                "services.gateway.src.proposals.on_proposal_rejected",
                side_effect=_fake_on_rejected,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/reject",
                    headers=_auth_header(token),
                    json={"reason": "Unverified source"},
                )

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        assert len(hook_calls) == 1
        assert hook_calls[0][0] == "chg_0001"
        assert hook_calls[0][1] == "cac"
        assert hook_calls[0][2] == "Unverified source"

    @pytest.mark.asyncio
    async def test_edit_endpoint_triggers_approved_hook(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """POST /edit -> on_proposal_approved called (edit is an approve variant)."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem, dept="cac")
        pool, conn = _mock_pool()

        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        app.state.db_pool = pool

        hook_calls: list[tuple[str, str]] = []

        async def _fake_on_approved(proposal_id: str, dept: str) -> None:
            hook_calls.append((proposal_id, dept))

        from services.gateway.src.auth import JWTClaims

        claims = JWTClaims(
            sub="hod-cac-01",
            dept="cac",
            role="hod",
            permissions=["read", "approve"],
            proposal_id=None,
        )

        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=claims),
            patch(
                "services.gateway.src.proposals.on_proposal_approved",
                side_effect=_fake_on_approved,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/edit",
                    headers=_auth_header(token),
                    json={"edited_value": "3.20"},
                )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        assert len(hook_calls) == 1
        assert hook_calls[0] == ("chg_0001", "cac")
