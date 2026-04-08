"""Tests for slack-bot service configuration."""

import pytest
from pydantic import ValidationError


class TestSlackBotSettings:
    def test_required_fields_load_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings load successfully when all required env vars are set."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.slack_bot_token == "xoxb-test-token"
        assert s.slack_signing_secret == "test-secret"
        assert s.cac_channel_id == "C0123456789"

    def test_missing_slack_bot_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing SLACK_BOT_TOKEN must raise ValidationError."""
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

        from services.slack_bot.src.config import SlackBotSettings

        with pytest.raises(ValidationError):
            SlackBotSettings()

    def test_missing_signing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing SLACK_SIGNING_SECRET must raise ValidationError."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

        from services.slack_bot.src.config import SlackBotSettings

        with pytest.raises(ValidationError):
            SlackBotSettings()

    def test_default_service_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Downstream service URLs default to Docker DNS names."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.rag_ingestion_url == "http://rag-ingestion:3004"
        assert s.cac_orchestrator_url == "http://cac-orchestrator:3001"

    def test_orchestrator_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Orchestrator feature flag defaults to False (Stage 3 stub)."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.orchestrator_enabled is False

    def test_custom_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service URLs can be overridden via env vars."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")
        monkeypatch.setenv("RAG_INGESTION_URL", "http://localhost:3004")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.rag_ingestion_url == "http://localhost:3004"
