"""slack-bot service configuration."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SlackBotSettings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}

    # --- Slack credentials (REQUIRED) ---
    slack_bot_token: str = Field(..., description="xoxb-... bot OAuth token")
    slack_signing_secret: str = Field(..., description="Bolt request signature secret")

    # --- Channel IDs (REQUIRED) ---
    cac_channel_id: str = Field(..., description="Primary CAC committee channel")
    escalations_channel_id: str = Field(..., description="Escalations channel")
    approvals_channel_id: str = Field(..., description="Approvals channel")

    # --- Downstream services ---
    rag_ingestion_url: str = "http://rag-ingestion:3004"
    cac_orchestrator_url: str = "http://cac-orchestrator:3001"
    orchestrator_enabled: bool = False  # Flip to True in Stage 4

    # --- File handling ---
    max_file_size_mb: int = 50
    allowed_file_types: str = "pdf,xlsx,docx,txt,md"

    # --- HTTP client ---
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 3

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def allowed_types_set(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.allowed_file_types.split(","))
