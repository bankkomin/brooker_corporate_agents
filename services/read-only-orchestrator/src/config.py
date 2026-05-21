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
    # Minimum cosine similarity score for a retrieved chunk to count as
    # "grounded" evidence.  Matches the repo-wide RAG_MIN_RELEVANCE convention
    # (deck-writer, docker-compose defaults).  Set lower in dev if needed.
    RAG_MIN_RELEVANCE: float = 0.50

    model_config = {"env_file": ".env"}


settings = Settings()
