"""Deployment-related behaviour: legacy endpoints off by default, readiness check."""

import httpx

from app.api.main import create_app
from app.config import Settings
from app.feed.repository import FeedRepository
from app.jobs.repository import JobRepository


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_legacy_jobs_api_disabled_by_default(repo: JobRepository, sessionmaker) -> None:
    settings = Settings()  # production defaults
    assert settings.enable_legacy_jobs_api is False
    app = create_app(settings)
    app.state.settings, app.state.repo = settings, repo
    app.state.feed_repo = FeedRepository(sessionmaker)
    async with _client(app) as c:
        assert (await c.post("/api/v1/jobs", json={"topic": "x"})).status_code == 404
        assert (await c.get("/api/v1/stats")).status_code == 200


def test_default_database_url_has_no_real_credentials() -> None:
    assert "change-me" in Settings.model_fields["database_url"].default


async def test_readiness_reports_database_state(engine, settings) -> None:
    app = create_app(settings)
    app.state.engine = engine
    async with _client(app) as c:
        r = await c.get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ok"}

    from app.db import make_engine

    dead = make_engine("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none")
    app.state.engine = dead
    async with _client(app) as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503
    await dead.dispose()
