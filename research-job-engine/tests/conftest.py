"""Integration test fixtures. Requires a real PostgreSQL (see README).

TEST_DATABASE_URL must point at a disposable database: the schema is dropped and recreated.
"""

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from alembic import command
from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.jobs.repository import JobRepository, RetryPolicy

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/research_test",
)


@pytest.fixture(scope="session")
def migrated() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def engine(migrated: None) -> AsyncIterator[AsyncEngine]:
    eng = make_engine(TEST_DATABASE_URL)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(engine)


@pytest.fixture(autouse=True)
async def clean_db(request: pytest.FixtureRequest) -> None:
    if "engine" not in request.fixturenames and "repo" not in request.fixturenames:
        return
    eng: AsyncEngine = request.getfixturevalue("engine")
    async with eng.begin() as conn:
        await conn.execute(text("TRUNCATE research_jobs, sources CASCADE"))


@pytest.fixture
def repo(sessionmaker: async_sessionmaker[AsyncSession]) -> JobRepository:
    return JobRepository(sessionmaker)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        worker_concurrency=2,
        lease_seconds=5,
        heartbeat_seconds=0.2,
        poll_interval_seconds=0.05,
        recovery_interval_seconds=0.1,
        retry_base_seconds=0,
        retry_max_seconds=0,
        default_max_attempts=3,
        mock_stage_delay_seconds=0,
        enable_legacy_jobs_api=True,
    )


@pytest.fixture
def policy() -> RetryPolicy:
    return RetryPolicy(base_seconds=10, max_seconds=60)


class DB:
    """Small SQL helpers for arranging and asserting test state."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def job(self, job_id: uuid.UUID) -> dict[str, Any]:
        async with self.engine.connect() as c:
            row = (
                (
                    await c.execute(
                        text("SELECT * FROM research_jobs WHERE id = :id"), {"id": job_id}
                    )
                )
                .mappings()
                .one()
            )
            return dict(row)

    async def events(self, job_id: uuid.UUID) -> list[str]:
        async with self.engine.connect() as c:
            rows = await c.execute(
                text("SELECT event_type FROM job_events WHERE job_id = :id ORDER BY id"),
                {"id": job_id},
            )
            return [r[0] for r in rows]

    async def count(self, table: str, job_id: uuid.UUID) -> int:
        async with self.engine.connect() as c:
            return (
                await c.execute(
                    text(f"SELECT count(*) FROM {table} WHERE job_id = :id"), {"id": job_id}
                )
            ).scalar_one()

    async def expire_lease(self, job_id: uuid.UUID) -> None:
        async with self.engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE research_jobs SET lease_expires_at = now() - interval '1 second' "
                    "WHERE id = :id"
                ),
                {"id": job_id},
            )

    async def make_due(self, job_id: uuid.UUID) -> None:
        async with self.engine.begin() as c:
            await c.execute(
                text("UPDATE research_jobs SET next_attempt_at = now() WHERE id = :id"),
                {"id": job_id},
            )


@pytest.fixture
def db(engine: AsyncEngine) -> DB:
    return DB(engine)


@pytest.fixture
def make_source(sessionmaker: async_sessionmaker[AsyncSession]):
    """Register a source through the real sync code path and return its id."""
    from app.sources.sync import SourceSpec, upsert_sources

    async def _make(name: str = "AI Weekly", **kw: Any) -> uuid.UUID:
        kw.setdefault("source_type", "rss")
        if kw["source_type"] == "youtube":
            kw.setdefault("channel_id", "UC" + "a" * 22)
        else:
            kw.setdefault("feed_url", f"https://{name.lower().replace(' ', '-')}.example/feed")
        await upsert_sources(sessionmaker, [SourceSpec(name=name, **kw)])
        async with sessionmaker() as s:
            return (
                await s.execute(text("SELECT id FROM sources WHERE name = :n"), {"n": name})
            ).scalar_one()

    return _make
