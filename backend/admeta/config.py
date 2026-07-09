"""설정 — 환경변수 기반. .env 자동 로드."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    extract_model: str = Field("claude-haiku-4-5-20251001", alias="EXTRACT_MODEL")
    embed_model: str = Field("voyage-3", alias="EMBED_MODEL")

    # DB
    database_url: str = Field(
        "postgresql://admeta:admeta@localhost:5432/admeta",
        alias="DATABASE_URL",
    )

    # paths
    raw_dir: str = Field("data/raw", alias="RAW_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
