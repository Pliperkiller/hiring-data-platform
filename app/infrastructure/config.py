"""App configuration (env vars, settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://hiring:change-me@db:5432/hiring"


@lru_cache
def get_settings() -> Settings:
    return Settings()
