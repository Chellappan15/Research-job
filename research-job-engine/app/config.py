from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Real credentials belong in .env (git-ignored) or the host's secret settings, never here.
    database_url: str = "postgresql+asyncpg://techpulse:change-me@localhost:5432/techpulse"

    worker_concurrency: int = Field(default=4, ge=1)
    lease_seconds: int = Field(default=30, ge=1)
    heartbeat_seconds: float = Field(default=10, gt=0)
    poll_interval_seconds: float = Field(default=1.0, gt=0)
    recovery_interval_seconds: float = Field(default=5.0, gt=0)
    retry_base_seconds: float = Field(default=5, ge=0)
    retry_max_seconds: float = Field(default=300, ge=0)
    default_max_attempts: int = Field(default=3, ge=1)
    mock_stage_delay_seconds: float = Field(default=0.5, ge=0)

    # TechPulse ingestion
    scheduler_poll_seconds: float = Field(default=30, gt=0)
    ingest_max_attempts: int = Field(default=3, ge=1)
    fetch_timeout_seconds: float = Field(default=15, gt=0)
    fetch_max_bytes: int = Field(default=5_000_000, ge=1024)
    fetch_per_host_concurrency: int = Field(default=2, ge=1)
    http_user_agent: str = "TechPulse/0.2 (feed aggregator)"

    # Comma-separated browser origins allowed to call the API (production frontend).
    # Not needed in development: the Vite dev server proxies /api to the backend.
    cors_origins: str = ""

    # Legacy Milestone 1 endpoints (POST/GET /api/v1/jobs, mock research only). Off by default:
    # POST is unauthenticated, so anyone could enqueue jobs on a public deployment.
    enable_legacy_jobs_api: bool = False

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
