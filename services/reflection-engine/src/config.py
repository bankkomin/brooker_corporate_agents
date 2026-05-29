from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 3008
    POSTGRES_DSN: str = "postgresql://postgres:postgres@postgres:5432/brooker"

    # LLM — accepts both VLLM_LARGE_URL (canonical) and legacy LLM_BASE_URL
    VLLM_LARGE_URL: str = "http://host.docker.internal:8000/v1"
    VLLM_LARGE_MODEL: str = "qwen-122b"

    # Legacy aliases — ignored if the VLLM_* vars are set
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""

    VAULT_ROOT: str = "/vault"
    STAGING_PENDING_DIR: str = "/data/staging/pending"
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

    model_config = {"env_prefix": "REFLECTION_", "env_file": ".env", "extra": "ignore"}

    @property
    def llm_base_url(self) -> str:
        return self.VLLM_LARGE_URL or self.LLM_BASE_URL or "http://host.docker.internal:8000/v1"

    @property
    def llm_model(self) -> str:
        return self.VLLM_LARGE_MODEL or self.LLM_MODEL or "qwen-122b"


settings = Settings()
