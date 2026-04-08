"""Tests for slack-bot FastAPI app and health endpoint."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_slack_env(monkeypatch):
    """Set required env vars so SlackBotSettings doesn't raise at import."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
    monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
    monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")


def test_health_endpoint_returns_200():
    """GET /health returns 200 with service name."""
    with patch("services.slack_bot.src.main.AsyncApp"):
        from fastapi.testclient import TestClient
        from services.slack_bot.src.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "slack-bot"


def test_health_response_has_timestamp():
    """Health response includes ISO timestamp."""
    with patch("services.slack_bot.src.main.AsyncApp"):
        from fastapi.testclient import TestClient
        from services.slack_bot.src.main import app

        client = TestClient(app)
        data = client.get("/health").json()
        assert "timestamp" in data


def test_slack_events_route_exists():
    """POST /slack/events route is registered."""
    with patch("services.slack_bot.src.main.AsyncApp"):
        from services.slack_bot.src.main import app

        routes = [r.path for r in app.routes]
        assert "/slack/events" in routes
