"""cac-orchestrator service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class OrchestratorSettings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # vLLM large model (via nginx load balancer)
    vllm_large_url: str = "http://nginx:8080/v1"
    vllm_large_model: str = "qwen-122b"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_rest_port: int = 6333

    # Postgres
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "corporate_agents"
    postgres_user: str = "agents"
    postgres_password: str = "changeme"

    # Data paths
    staging_path: str = "/data/staging"
    mirror_path: str = "/data/mirror"

    # RAG settings
    confidence_threshold: float = 0.85
    rag_top_k: int = 8
    rag_min_relevance: float = 0.70

    # Config file paths
    escalation_rules_path: str = "/app/config/escalation_rules.json"
    excel_schema_path: str = "/app/config/excel_schema/alco_tracker.json"
    skills_path: str = "/app/skills"

    # Email notifier
    email_notifier_url: str = "http://email-notifier:3005"

    # Logging
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = OrchestratorSettings()
