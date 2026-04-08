"""Tests for email-notifier service endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from services.email_notifier.src.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
    assert resp.json()["service"] == "email-notifier"


@patch("services.email_notifier.src.main.send_escalation", new_callable=AsyncMock)
@patch(
    "services.email_notifier.src.main._resolve_hod_email",
    return_value="hod@brooker.test",
)
def test_notify_escalation(
    mock_resolve: object, mock_send: object, client: TestClient
) -> None:
    payload = {
        "escalation_detail": "Covenant ratio 4.2x > 4.0x threshold",
        "agent_name": "funding-agent",
        "query": "check covenants",
        "user_id": "U123",
        "channel": "C-cac",
    }
    resp = client.post("/notify/escalation", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert "notification_id" in data
    assert data["recipients"] >= 1


@patch("services.email_notifier.src.main.send_proposal_notification", new_callable=AsyncMock)
@patch("services.email_notifier.src.main.generate_proposal_token", return_value="mock-jwt")
@patch("services.email_notifier.src.main._resolve_hod_email", return_value="hod@brooker.test")
def test_notify_proposal(
    mock_resolve: object, mock_jwt: object, mock_send: object, client: TestClient
) -> None:
    payload = {
        "proposal_id": "chg_0001",
        "agent_name": "liquidity-agent",
        "file": "ALCO_Tracker.xlsx",
        "tab": "Liquidity",
        "cell": "D10",
        "new_value": "1.18",
        "confidence": 0.91,
        "dept": "cac",
    }
    resp = client.post("/notify/proposal", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert "notification_id" in data


def test_notify_proposal_missing_dept(client: TestClient) -> None:
    """Proposal without dept field should return 422 validation error."""
    payload = {
        "proposal_id": "chg_0001",
        "agent_name": "liquidity-agent",
        "file": "ALCO_Tracker.xlsx",
        "tab": "Liquidity",
        "cell": "D10",
        "new_value": "1.18",
        "confidence": 0.91,
    }
    resp = client.post("/notify/proposal", json=payload)
    assert resp.status_code == 422


def test_notify_proposal_no_hod_email(client: TestClient) -> None:
    """When no HOD email is configured for the dept, return 422."""
    payload = {
        "proposal_id": "chg_0001",
        "agent_name": "liquidity-agent",
        "file": "ALCO_Tracker.xlsx",
        "tab": "Liquidity",
        "cell": "D10",
        "new_value": "1.18",
        "confidence": 0.91,
        "dept": "nonexistent",
    }
    resp = client.post("/notify/proposal", json=payload)
    assert resp.status_code == 422
    assert "No HOD email" in resp.json()["detail"]


@patch("services.email_notifier.src.main.send_reminder", new_callable=AsyncMock)
@patch("services.email_notifier.src.main.generate_proposal_token", return_value="reminder-jwt")
def test_notify_reminder(mock_jwt: object, mock_send: object, client: TestClient) -> None:
    payload = {"proposal_id": "chg_0001", "recipient": "hod@example.com", "dept": "cac"}
    resp = client.post("/notify/reminder", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


def test_notify_reminder_missing_dept(client: TestClient) -> None:
    """Reminder without dept field should return 422 validation error."""
    payload = {"proposal_id": "chg_0001", "recipient": "hod@example.com"}
    resp = client.post("/notify/reminder", json=payload)
    assert resp.status_code == 422


def test_notify_confirmed_missing_dept(client: TestClient) -> None:
    """Confirmed without dept field should return 422 validation error."""
    payload = {"proposal_id": "chg_0001", "decision": "approved"}
    resp = client.post("/notify/confirmed", json=payload)
    assert resp.status_code == 422
