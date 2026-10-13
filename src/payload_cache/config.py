from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://cache:cache@localhost:5432/cache"
    transform_delay: float = 0.5


@lru_cache
def get_settings() -> Settings:
    return Settings()
