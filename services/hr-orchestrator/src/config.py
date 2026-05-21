"""hr-orchestrator service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class HROrchestratorSettings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # LLM -- OpenAI-compatible vLLM endpoint serving Qwen.
    vllm_large_url: str = "http://nginx:8080/v1"
    vllm_large_model: str = "qwen-large"
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

    # Data paths (read-only -- HR has no staging)
    mirror_path: str = "/data/mirror"

    # RAG settings
    rag_top_k: int = 8
    rag_min_relevance: float = 0.70

    # Config file paths
    escalation_rules_path: str = "/app/config/escalation_rules.json"
    skills_path: str = "/app/skills"

    # Email notifier
    email_notifier_url: str = "http://email-notifier:3005"

    # Paperclip
    paperclip_url: str = "http://paperclip:3100"
    paperclip_api_key: str = "dev-paperclip-key"

    # Vault
    vault_root: str = "/vault/hr"

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


settings = HROrchestratorSettings()
