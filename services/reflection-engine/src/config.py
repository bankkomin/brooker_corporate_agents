from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 3008
    POSTGRES_DSN: str = "postgresql://postgres:postgres@postgres:5432/brooker"
    LLM_BASE_URL: str = "http://nginx:8080/v1"
    LLM_MODEL: str = "qwen-122b"
    PAPERCLIP_URL: str = "http://paperclip:3100"
    VAULT_ROOT: str = "/vault"
    REFLECTION_CRON_HOUR: int = 2
    REFLECTION_CRON_MINUTE: int = 0
    SIGNAL_THRESHOLD: float = 0.5
    MIN_PATTERN_COUNT: int = 5
    VAULT_HEALTH_CHECK_CRON_HOUR: int = 3
    VAULT_HEALTH_CHECK_CRON_MINUTE: int = 0
    VAULT_HEALTH_CHECK_ENABLED: bool = True
    STAGING_PATH: str = "/data/staging"
    DAILY_LOG_DRAFTING_ENABLED: bool = True
    SYNTHESIS_SCAN_CRON_HOUR: int = 4
    SYNTHESIS_SCAN_CRON_MINUTE: int = 0
    SYNTHESIS_SCAN_ENABLED: bool = True
    RAG_INGESTION_URL: str = "http://rag-ingestion:3004"
    SYNTHESIS_SCAN_TIMEOUT: float = 300.0  # synthesis can be slow; 5min cap

    model_config = {"env_prefix": "REFLECTION_", "env_file": ".env"}


settings = Settings()
