from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 3009
    POSTGRES_DSN: str = "postgresql://postgres:postgres@postgres:5432/brooker"
    PAPERCLIP_URL: str = "http://paperclip:3100"
    CONFIG_PATH: str = "/app/config/departments.json"

    model_config = {"env_prefix": "HEARTBEAT_", "env_file": ".env"}


settings = Settings()
