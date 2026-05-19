"""Tests for /notify/confirmed and /notify/escalation recipient resolution logic."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport
from services.email_notifier.src.main import app


@pytest.fixture
def mock_db_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set app.state.db_pool to None so no real DB is needed."""
    app.state.db_pool = None


@pytest.mark.asyncio
@patch("services.email_notifier.src.main.send_confirmed", new_callable=AsyncMock)
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value="hod@test.com",
)
async def test_confirmed_resolves_hod_from_dept(
    mock_resolve: object,
    mock_send: AsyncMock,
    mock_db_pool: None,
) -> None:
    """POST /notify/confirmed with dept and no recipient resolves HOD from departments.json."""
    payload = {
        "proposal_id": "chg_0042",
        "decision": "approved",
        "dept": "cac",
    }
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/notify/confirmed", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert "notification_id" in data

    mock_send.assert_awaited_once_with(
        proposal_id="chg_0042",
        decision="approved",
        recipient="hod@test.com",
        pool=None,
    )


@pytest.mark.asyncio
@patch("services.email_notifier.src.main.send_confirmed", new_callable=AsyncMock)
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value="hod@test.com",
)
async def test_confirmed_uses_explicit_recipient(
    mock_resolve: object,
    mock_send: AsyncMock,
    mock_db_pool: None,
) -> None:
    """POST /notify/confirmed with an explicit recipient uses that address, not the HOD."""
    payload = {
        "proposal_id": "chg_0043",
        "decision": "rejected",
        "dept": "cac",
        "recipient": "custom@test.com",
    }
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/notify/confirmed", json=payload)

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"

    mock_send.assert_awaited_once_with(
        proposal_id="chg_0043",
        decision="rejected",
        recipient="custom@test.com",
        pool=None,
    )


@pytest.mark.asyncio
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value=None,
)
async def test_confirmed_no_recipient_returns_422(
    mock_resolve: object,
    mock_db_pool: None,
) -> None:
    """POST /notify/confirmed with no explicit recipient and no HOD configured returns 422."""
    payload = {
        "proposal_id": "chg_0044",
        "decision": "approved",
        "dept": "unknown-dept",
    }
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/notify/confirmed", json=payload)

    assert resp.status_code == 422
    assert "No recipient configured" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /notify/escalation — recipient resolution tests
# ---------------------------------------------------------------------------


@pytest.fixture
def sync_client() -> TestClient:
    return TestClient(app)


@patch("services.email_notifier.src.main.send_escalation", new_callable=AsyncMock)
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value="hod@test.com",
)
def test_escalation_sends_to_hod_and_ceo(
    mock_resolve: object,
    mock_send: AsyncMock,
    sync_client: TestClient,
) -> None:
    """Escalation endpoint calls send_escalation with both HOD and CEO recipients."""
    payload = {
        "escalation_detail": "Covenant ratio 4.2x exceeds 4.0x limit",
        "agent_name": "funding-agent",
        "query": "check covenants",
        "user_id": "U123",
        "channel": "C-cac",
        "severity": "high",
        "dept": "cac",
    }

    with patch.dict(os.environ, {"CEO_EMAIL": "ceo@test.com"}):
        resp = sync_client.post("/notify/escalation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert "notification_id" in data
    assert data["recipients"] == 2

    mock_send.assert_awaited_once()
    call_kwargs = mock_send.call_args.kwargs
    assert set(call_kwargs["recipients"]) == {"hod@test.com", "ceo@test.com"}


@patch("services.email_notifier.src.main.send_escalation", new_callable=AsyncMock)
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value="hod@test.com",
)
def test_escalation_no_ceo_email_sends_to_hod_only(
    mock_resolve: object,
    mock_send: AsyncMock,
    sync_client: TestClient,
) -> None:
    """When CEO_EMAIL is unset, escalation is still sent to HOD only."""
    payload = {
        "escalation_detail": "LCR ratio below 110% threshold",
        "agent_name": "liquidity-agent",
        "query": "check LCR",
        "user_id": "U456",
        "channel": "C-cac",
        "severity": "critical",
        "dept": "cac",
    }

    env = {k: v for k, v in os.environ.items() if k != "CEO_EMAIL"}
    with patch.dict(os.environ, env, clear=True):
        resp = sync_client.post("/notify/escalation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert data["recipients"] == 1

    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["recipients"] == ["hod@test.com"]


@patch("services.email_notifier.src.main._resolve_hod_email", return_value=None)
def test_escalation_no_recipients_returns_422(
    mock_resolve: object,
    sync_client: TestClient,
) -> None:
    """When neither HOD nor CEO email is available, return 422."""
    payload = {
        "escalation_detail": "Unknown breach",
        "agent_name": "risk-agent",
        "query": "check risk",
        "user_id": "U789",
        "channel": "C-cac",
        "dept": "unknown_dept",
    }

    env = {k: v for k, v in os.environ.items() if k != "CEO_EMAIL"}
    with patch.dict(os.environ, env, clear=True):
        resp = sync_client.post("/notify/escalation", json=payload)

    assert resp.status_code == 422
    assert "No escalation recipients" in resp.json()["detail"]


@patch("services.email_notifier.src.main.send_escalation", new_callable=AsyncMock)
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value="hod@test.com",
)
def test_escalation_deduplicates_when_hod_equals_ceo(
    mock_resolve: object,
    mock_send: AsyncMock,
    sync_client: TestClient,
) -> None:
    """When HOD and CEO email are identical, only one recipient is used."""
    payload = {
        "escalation_detail": "Duplicate recipient test",
        "agent_name": "test-agent",
        "query": "test query",
        "user_id": "U000",
        "channel": "C-test",
        "dept": "cac",
    }

    with patch.dict(os.environ, {"CEO_EMAIL": "hod@test.com"}):
        resp = sync_client.post("/notify/escalation", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["recipients"] == 1

    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["recipients"] == ["hod@test.com"]
