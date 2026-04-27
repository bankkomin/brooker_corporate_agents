"""Wiki compiler service configuration."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class WikiSettings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}

    # LLM
    vllm_base_url: str = "http://host.docker.internal:8000/v1"
    vllm_model: str = "qwen-large"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    # Vault
    vault_path: str = "/mnt/obsidian-vault"

    # Config paths
    wiki_schema_path: str = "/app/config/wiki_schema.json"
    departments_config: str = "/app/config/departments.json"

    # Service
    wiki_compiler_port: int = 3007
    log_level: str = "INFO"

    # Paperclip
    paperclip_url: str = "http://paperclip:3100"


settings = WikiSettings()
