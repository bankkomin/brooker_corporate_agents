"""Integration test: staging proposal -> HOD email notification.

Tests the /notify/proposal and related email-notifier endpoints with mocked
SMTP. Verifies correct HOD resolution, JWT token generation, and HTTP response
codes without making real network calls.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from services.email_notifier.src.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PAYLOAD = {
    "proposal_id": "chg_0001",
    "agent_name": "funding-agent",
    "file": "ALCO_Tracker.xlsx",
    "tab": "Funding Facilities",
    "cell": "E8",
    "new_value": "3.15",
    "confidence": 0.91,
    "dept": "cac",
}

# A minimal departments.json that resolves "cac" HOD to a literal address,
# bypassing the ${ENV_VAR} indirection used in the real config.
_MOCK_DEPARTMENTS = {
    "departments": {
        "cac": {
            "escalation": {
                "hodEmails": ["cac.hod@brooker.co.th"],
            }
        }
    }
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProposalNotification:
    """POST /notify/proposal — HOD email sent on valid proposal."""

    @pytest.mark.asyncio
    async def test_proposal_notification_sends_email(self) -> None:
        """POST /notify/proposal with valid cac dept -> 200 {"status": "sent"}."""
        # Patch departments loader so HOD email resolves without env vars, and
        # patch send_proposal_notification to avoid real SMTP.
        with (
            patch(
                "services.email_notifier.src.main._load_departments",
                return_value=_MOCK_DEPARTMENTS,
            ),
            patch(
                "services.email_notifier.src.main.send_proposal_notification",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "services.email_notifier.src.main.generate_proposal_token",
                return_value="fake.jwt.token",
            ),
        ):
            # Disable real DB pool — lifespan won't run in ASGI transport
            app.state.db_pool = None

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/notify/proposal", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "sent"
        assert "notification_id" in body

        # Verify send_proposal_notification was called with the resolved HOD email
        mock_send.assert_awaited_once()
        call_kwargs = mock_send.call_args
        assert call_kwargs.kwargs["hod_email"] == "cac.hod@brooker.co.th"
        assert call_kwargs.kwargs["token"] == "fake.jwt.token"

    @pytest.mark.asyncio
    async def test_proposal_notification_no_hod_returns_422(self) -> None:
        """POST /notify/proposal with dept that has no HOD -> 422."""
        # Return a departments config that has no HOD emails for "unknown_dept"
        empty_departments: dict = {"departments": {}}

        with patch(
            "services.email_notifier.src.main._load_departments",
            return_value=empty_departments,
        ):
            app.state.db_pool = None

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                payload = dict(_VALID_PAYLOAD, dept="unknown_dept")
                resp = await client.post("/notify/proposal", json=payload)

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "unknown_dept" in detail

    @pytest.mark.asyncio
    async def test_proposal_notification_logs_to_db_when_pool_available(self) -> None:
        """When db_pool is available, send_proposal_notification receives it."""
        from unittest.mock import MagicMock

        # Build a lightweight mock pool — just needs to be truthy
        mock_pool = MagicMock()

        with (
            patch(
                "services.email_notifier.src.main._load_departments",
                return_value=_MOCK_DEPARTMENTS,
            ),
            patch(
                "services.email_notifier.src.main.send_proposal_notification",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "services.email_notifier.src.main.generate_proposal_token",
                return_value="fake.jwt.token",
            ),
        ):
            app.state.db_pool = mock_pool

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/notify/proposal", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        # Confirm pool was forwarded so DB logging can occur
        mock_send.assert_awaited_once()
        assert mock_send.call_args.kwargs["pool"] is mock_pool

    @pytest.mark.asyncio
    async def test_proposal_notification_env_var_hod_resolved(self) -> None:
        """HOD email from ${ENV_VAR} placeholder is resolved via os.environ."""
        env_departments = {
            "departments": {
                "cac": {
                    "escalation": {
                        "hodEmails": ["${CAC_HOD_EMAIL}"],
                    }
                }
            }
        }

        with (
            patch(
                "services.email_notifier.src.main._load_departments",
                return_value=env_departments,
            ),
            patch.dict(os.environ, {"CAC_HOD_EMAIL": "resolved.hod@brooker.co.th"}),
            patch(
                "services.email_notifier.src.main.send_proposal_notification",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "services.email_notifier.src.main.generate_proposal_token",
                return_value="fake.jwt.token",
            ),
        ):
            app.state.db_pool = None

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/notify/proposal", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        mock_send.assert_awaited_once()
        assert mock_send.call_args.kwargs["hod_email"] == "resolved.hod@brooker.co.th"

    @pytest.mark.asyncio
    async def test_confirmed_notification_sends_email(self) -> None:
        """POST /notify/confirmed with explicit recipient -> 200 {"status": "sent"}."""
        confirmed_payload = {
            "proposal_id": "chg_0001",
            "decision": "approved",
            "dept": "cac",
            "recipient": "cac.hod@brooker.co.th",
        }

        with (
            patch(
                "services.email_notifier.src.main.send_confirmed",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            app.state.db_pool = None

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/notify/confirmed", json=confirmed_payload)

        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_confirmed_notification_no_recipient_no_hod_returns_422(
        self,
    ) -> None:
        """POST /notify/confirmed with no recipient and unknown dept -> 422."""
        confirmed_payload = {
            "proposal_id": "chg_0001",
            "decision": "approved",
            "dept": "unknown_dept",
        }

        empty_departments: dict = {"departments": {}}

        with patch(
            "services.email_notifier.src.main._load_departments",
            return_value=empty_departments,
        ):
            app.state.db_pool = None

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/notify/confirmed", json=confirmed_payload)

        assert resp.status_code == 422
