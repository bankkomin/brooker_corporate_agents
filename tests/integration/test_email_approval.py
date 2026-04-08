"""Integration test: HOD approves/rejects via gateway -> hooks fire downstream.

Verifies that approve/reject/edit endpoints call on_proposal_approved /
on_proposal_rejected, which POST to sync-back and email-notifier.
Downstream HTTP calls are intercepted with httpx mock transport so no real
network connections are made.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from services.gateway.src.auth import JWTClaims
from services.gateway.src.main import app


# ---------------------------------------------------------------------------
# Fixtures & helpers (mirror the pattern from test_approval_flow.py)
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


def _make_token(
    private_pem: bytes,
    *,
    dept: str = "cac",
    role: str = "hod",
    sub: str | None = None,
) -> str:
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

_CAC_CLAIMS = JWTClaims(
    sub="cac.hod@brooker.co.th",
    dept="cac",
    role="hod",
    permissions=["read:cac", "approve:cac"],
    proposal_id=None,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApproveTriggersSyncAndEmail:
    """Approve endpoint -> on_proposal_approved -> both sync-back + email POSTs."""

    @pytest.mark.asyncio
    async def test_approve_triggers_sync_and_email(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Approving a proposal fires POST to sync-back AND email-notifier."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        posted_urls: list[str] = []

        async def _fake_post(
            url: str,
            json_body: dict,
            service_name: str,
            proposal_id: str,
        ) -> None:
            posted_urls.append(url)

        app.state.db_pool = pool
        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=_CAC_CLAIMS),
            patch(
                "services.gateway.src.hooks._post_fire_and_forget",
                side_effect=_fake_post,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/approve",
                    headers=_auth_header(token),
                )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # Both downstream hooks must have been called
        assert any("sync-back" in u or "process-approved" in u for u in posted_urls), (
            f"sync-back not called; posted_urls={posted_urls}"
        )
        assert any("notify/confirmed" in u for u in posted_urls), (
            f"email-notifier not called; posted_urls={posted_urls}"
        )

    @pytest.mark.asyncio
    async def test_approve_triggers_exactly_two_hooks(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Approve fires exactly 2 downstream POSTs: sync-back + email-notifier."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        hook_calls: list[tuple[str, dict]] = []

        async def _capture(url: str, json_body: dict, service_name: str, proposal_id: str) -> None:
            hook_calls.append((url, json_body))

        app.state.db_pool = pool
        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=_CAC_CLAIMS),
            patch(
                "services.gateway.src.hooks._post_fire_and_forget",
                side_effect=_capture,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                await client.post(
                    "/api/proposals/chg_0001/approve",
                    headers=_auth_header(token),
                )

        assert len(hook_calls) == 2


class TestRejectTriggersEmailOnly:
    """Reject endpoint -> on_proposal_rejected -> only email-notifier POST."""

    @pytest.mark.asyncio
    async def test_reject_triggers_email_only(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Rejecting a proposal fires email-notifier but NOT sync-back."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        posted_urls: list[str] = []

        async def _fake_post(url: str, json_body: dict, service_name: str, proposal_id: str) -> None:
            posted_urls.append(url)

        app.state.db_pool = pool
        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=_CAC_CLAIMS),
            patch(
                "services.gateway.src.hooks._post_fire_and_forget",
                side_effect=_fake_post,
            ),
        ):
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
        assert resp.json()["status"] == "rejected"

        # Email-notifier must be called
        assert any("notify/confirmed" in u for u in posted_urls), (
            f"email-notifier not called; posted_urls={posted_urls}"
        )
        # sync-back must NOT be called for rejections
        assert not any("process-approved" in u for u in posted_urls), (
            f"sync-back was wrongly called on rejection; posted_urls={posted_urls}"
        )

    @pytest.mark.asyncio
    async def test_reject_fires_exactly_one_hook(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Reject fires exactly 1 downstream POST (email-notifier only)."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        hook_calls: list[str] = []

        async def _capture(url: str, json_body: dict, service_name: str, proposal_id: str) -> None:
            hook_calls.append(url)

        app.state.db_pool = pool
        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=_CAC_CLAIMS),
            patch(
                "services.gateway.src.hooks._post_fire_and_forget",
                side_effect=_capture,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                await client.post(
                    "/api/proposals/chg_0001/reject",
                    headers=_auth_header(token),
                    json={"reason": "Needs more data"},
                )

        assert len(hook_calls) == 1


class TestEditTriggersHooks:
    """Edit endpoint -> on_proposal_approved -> both sync-back + email POSTs."""

    @pytest.mark.asyncio
    async def test_edit_triggers_sync_and_email(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Edit+approve fires both sync-back and email-notifier hooks."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        posted_urls: list[str] = []

        async def _fake_post(url: str, json_body: dict, service_name: str, proposal_id: str) -> None:
            posted_urls.append(url)

        app.state.db_pool = pool
        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=_CAC_CLAIMS),
            patch(
                "services.gateway.src.hooks._post_fire_and_forget",
                side_effect=_fake_post,
            ),
        ):
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
        assert resp.json()["status"] == "approved"

        # Edit re-uses the approval hook, so both downstream services are called
        assert any("process-approved" in u for u in posted_urls), (
            f"sync-back not called after edit; posted_urls={posted_urls}"
        )
        assert any("notify/confirmed" in u for u in posted_urls), (
            f"email-notifier not called after edit; posted_urls={posted_urls}"
        )

    @pytest.mark.asyncio
    async def test_hook_failure_does_not_block_gateway_response(
        self, rsa_keypair: tuple[bytes, bytes]
    ) -> None:
        """Hook errors are swallowed — gateway still returns 200 to caller."""
        private_pem, _ = rsa_keypair
        token = _make_token(private_pem)
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=dict(_SAMPLE_ROW))
        conn.execute = AsyncMock(return_value="UPDATE 1")

        async def _raise(*args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("sync-back is down")

        app.state.db_pool = pool
        with (
            patch("services.gateway.src.auth.validate_jwt", return_value=_CAC_CLAIMS),
            patch(
                "services.gateway.src.proposals.on_proposal_approved",
                side_effect=_raise,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/proposals/chg_0001/approve",
                    headers=_auth_header(token),
                )

        # Gateway must return 200 even when downstream hooks fail
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
