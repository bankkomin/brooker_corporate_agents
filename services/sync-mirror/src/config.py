"""sync-mirror service configuration."""

from pydantic_settings import BaseSettings


class SyncMirrorSettings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # Mirror source
    mirror_source: str = "smb"
    mirror_sync_interval_minutes: int = 15
    mirror_path: str = "/data/mirror"

    # SMB
    smb_host: str = ""
    smb_share: str = ""
    smb_username: str = ""
    smb_password: str = ""

    # Postgres
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "corporate_agents"
    postgres_user: str = "agents"
    postgres_password: str = "changeme"

    # Logging
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = SyncMirrorSettings()
