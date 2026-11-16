from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+psycopg://encurtador:encurtador@localhost:5433/encurtador"
    base_url: str = "http://localhost:8000"
    code_length: int = 7


settings = Settings()
