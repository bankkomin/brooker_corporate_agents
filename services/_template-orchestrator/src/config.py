"""Settings for a department orchestrator.

Copy this whole `_template-orchestrator/` directory to `services/<dept>-orchestrator/`
and replace every value tagged TODO with the dept's real values.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ---- Identity (replace per dept) -----------------------------------
    PORT: int = 3099  # TODO: assign a free port per docs/Implementation.md
    DEPT_ID: str = "template"  # TODO: e.g. "finance" / "cio" / "vcc"
    DEPT_NAME: str = "Template Department"  # TODO: human-readable name
    AGENT_ID: str = "template-orchestrator"  # TODO: <dept>-orchestrator

    # ---- Shared infra ---------------------------------------------------
    POSTGRES_DSN: str = "postgresql://postgres:postgres@postgres:5432/brooker"
    QDRANT_URL: str = "http://qdrant:6333"
    PAPERCLIP_URL: str = "http://paperclip:3100"
    LLM_BASE_URL: str = "http://nginx:8080/v1"
    LLM_MODEL: str = "qwen-122b"

    # ---- Filesystem -----------------------------------------------------
    VAULT_ROOT: str = "/vault"
    SKILLS_ROOT: str = "/skills"
    DEPARTMENTS_CONFIG: str = "/app/config/departments.json"

    # ---- Behaviour ------------------------------------------------------
    # Set False for read_only depts — they should use read-only-orchestrator
    # instead. Only flip to True for capabilityTier="write" departments
    # (e.g., finance / cio / vcc).
    WRITE_CAPABLE: bool = False

    model_config = {"env_file": ".env"}


settings = Settings()
