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

    model_config = {"env_prefix": "REFLECTION_", "env_file": ".env"}


settings = Settings()
