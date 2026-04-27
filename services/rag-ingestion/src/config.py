"""rag-ingestion service configuration."""

from pydantic_settings import BaseSettings


class RAGSettings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # Embedder
    embedder_type: str = "gemini"  # "gemini" or "vllm"
    vllm_embed_url: str = "http://host.docker.internal:8002/v1"
    vllm_embed_model: str = "qwen-embed"
    gemini_api_key: str = ""
    gemini_embed_model: str = "gemini-embedding-001"

    # Qdrant
    qdrant_mode: str = "local"  # "local" (file-based persistent), "memory", or "server" (Docker)
    qdrant_local_path: str = "./data/qdrant_local"
    qdrant_host: str = "qdrant"
    qdrant_rest_port: int = 6333

    # Postgres
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "corporate_agents"
    postgres_user: str = "agents"
    postgres_password: str = "changeme"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "changeme"
    minio_bucket: str = "raw-documents"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 128

    # Obsidian
    obsidian_vault_path: str = "/mnt/obsidian-vault"
    obsidian_watch_enabled: bool = False
    obsidian_qdrant_collection: str = "cac_knowledge"
    obsidian_ingest_delay_seconds: int = 5
    obsidian_watch_config: str = "/app/config/obsidian_watch.json"

    # Mirror
    mirror_path: str = "/data/mirror"

    # Logging
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = RAGSettings()
