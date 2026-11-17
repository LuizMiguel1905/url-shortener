from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://encurtador:encurtador@localhost:5433/encurtador"
    base_url: str = "http://localhost:8000"
    redis_url: str = "redis://localhost:6380/0"
    cache_ttl_seconds: int = 3600
    clicks_flush_interval_seconds: float = 5.0
    code_length: int = 7


settings = Settings()
