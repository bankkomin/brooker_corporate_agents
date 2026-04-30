from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = {PORT}
    DEPT_ID: str = "{DEPT_ID}"
    DEPT_NAME: str = "{DEPT_NAME}"
    POSTGRES_DSN: str = "postgresql://postgres:postgres@postgres:5432/brooker"
    QDRANT_URL: str = "http://qdrant:6333"
    PAPERCLIP_URL: str = "http://paperclip:3100"
    LLM_BASE_URL: str = "http://nginx:8080/v1"
    LLM_MODEL: str = "qwen-122b"
    VAULT_ROOT: str = "/vault"

    model_config = {"env_file": ".env"}


settings = Settings()
