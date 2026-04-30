from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 3030
    POSTGRES_DSN: str = "postgresql://brook:brook@postgres:5432/brook_agents"
    EVAL_DATASET_PATH: str = "/app/config/eval"
    CAC_ORCHESTRATOR_URL: str = "http://localhost:3001"
    HR_ORCHESTRATOR_URL: str = "http://localhost:3002"

    model_config = {"env_prefix": "EVAL_"}


settings = Settings()
