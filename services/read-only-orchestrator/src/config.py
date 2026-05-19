from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 3040
    POSTGRES_DSN: str = "postgresql://postgres:postgres@postgres:5432/brooker"
    QDRANT_URL: str = "http://qdrant:6333"
    LLM_BASE_URL: str = "http://nginx:8080/v1"
    LLM_MODEL: str = "qwen-122b"
    VAULT_ROOT: str = "/vault"
    DEPARTMENTS_CONFIG: str = "/app/config/departments.json"
    SKILLS_ROOT: str = "/skills"

    model_config = {"env_file": ".env"}

settings = Settings()
