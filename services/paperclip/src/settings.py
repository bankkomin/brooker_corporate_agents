"""Paperclip service configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paperclip configuration loaded from environment variables."""

    database_url: str = "postgresql://cac_user:cac_pass@postgres:5432/cac_db"
    paperclip_api_key: str = "dev-paperclip-key"
    sync_back_url: str = "http://sync-back:3006"
    email_notifier_url: str = "http://email-notifier:3005"
    slack_bot_url: str = "http://slack-bot:3003"
    wiki_compiler_url: str = "http://wiki-compiler:3007"
    log_level: str = "info"
    heartbeat_stale_seconds: int = 120

    model_config = {"env_prefix": ""}


settings = Settings()
