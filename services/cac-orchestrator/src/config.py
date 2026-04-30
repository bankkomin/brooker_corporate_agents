"""cac-orchestrator service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class OrchestratorSettings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # LLM — OpenAI-compatible endpoint (vLLM, Gemini, etc.)
    vllm_large_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    vllm_large_model: str = "gemini-3.1-flash-lite-preview"
    llm_api_key: str = ""

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

    # Paperclip
    paperclip_url: str = "http://paperclip:3100"
    paperclip_api_key: str = "dev-paperclip-key"

    # Vault
    vault_root: str = "/vault/cac"

    # Departments config
    departments_config_path: str = "/app/config/departments.json"

    # Logging
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = OrchestratorSettings()
