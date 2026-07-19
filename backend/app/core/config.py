"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "JobPilot API"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'jobpilot.db'}"
    secret_key: str = "change-this-secret-in-production"
    access_token_expire_minutes: int = 60 * 24
    google_client_id: str | None = None
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000"
    cors_origin_regex: str | None = None
    web_search_provider: str = "auto"
    firecrawl_api_key: str | None = None
    brave_search_api_key: str | None = None
    job_collection_interval_minutes: int = 60
    scheduler_poll_seconds: int = 30
    scheduler_batch_size: int = 5
    scheduler_lease_minutes: int = 15
    linkedin_enrichment_batch_size: int = 25
    llm_key_encryption_secret: str | None = None
    llm_request_timeout_seconds: int = 30
    resume_storage_provider: str = "database"
    resume_storage_path: str = str(BACKEND_DIR / "resume_artifacts")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
