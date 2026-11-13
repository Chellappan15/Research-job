import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.scheduler.scheduler import Scheduler

T0 = datetime(2026, 11, 13, 10, 7, 30, tzinfo=UTC)


async def _jobs(db) -> list[dict]:
    async with db.engine.connect() as c:
        rows = await c.execute(
            text(
                "SELECT id, source_id, scheduled_for, status, kind, max_attempts "
                "FROM research_jobs WHERE kind = 'ingest' ORDER BY scheduled_for"
            )
        )
        return [dict(r) for r in rows.mappings()]


async def _finish_all(db) -> None:
    async with db.engine.begin() as c:
        await c.execute(text("UPDATE research_jobs SET status = 'completed' WHERE kind = 'ingest'"))


async def test_schedules_due_source_on_aligned_slot(sessionmaker, make_source, db) -> None:
    sid = await make_source("Hourly", fetch_interval_seconds=3600)
    created = await Scheduler(sessionmaker, 3).enqueue_due(T0)
    assert len(created) == 1
    (job,) = await _jobs(db)
    assert job["source_id"] == sid
    assert job["scheduled_for"] == datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
    assert job["status"] == "pending" and job["max_attempts"] == 3
    assert await db.events(job["id"]) == ["scheduled"]


async def test_scheduler_is_idempotent_within_slot(sessionmaker, make_source, db) -> None:
    await make_source("Hourly", fetch_interval_seconds=3600)
    sched = Scheduler(sessionmaker, 3)
    assert len(await sched.enqueue_due(T0)) == 1
    await _finish_all(db)  # even after the run completes, the same slot is not re-queued
    assert await sched.enqueue_due(T0 + timedelta(minutes=10)) == []
    assert len(await _jobs(db)) == 1
    # next slot -> new job
    assert len(await sched.enqueue_due(T0 + timedelta(hours=1))) == 1
    assert len(await _jobs(db)) == 2


async def test_no_pile_up_while_previous_run_pending(sessionmaker, make_source, db) -> None:
    await make_source("Fast", fetch_interval_seconds=60)
    sched = Scheduler(sessionmaker, 3)
    await sched.enqueue_due(T0)
    for minutes in range(1, 6):
        assert await sched.enqueue_due(T0 + timedelta(minutes=minutes)) == []
    assert len(await _jobs(db)) == 1


async def test_disabled_sources_not_scheduled(sessionmaker, make_source, db) -> None:
    await make_source("Off", enabled=False)
    await make_source("On")
    created = await Scheduler(sessionmaker, 3).enqueue_due(T0)
    assert len(created) == 1


async def test_concurrent_scheduler_instances(sessionmaker, make_source, db) -> None:
    ids = [await make_source(f"Source {i}", fetch_interval_seconds=900) for i in range(5)]
    schedulers = [Scheduler(sessionmaker, 3) for _ in range(8)]
    results = await asyncio.gather(*[s.enqueue_due(T0) for s in schedulers])
    assert sum(len(r) for r in results) == 5
    jobs = await _jobs(db)
    assert sorted(j["source_id"] for j in jobs) == sorted(ids)
    for job in jobs:
        assert await db.events(job["id"]) == ["scheduled"]


async def test_scheduler_uses_db_clock_by_default(sessionmaker, make_source, db) -> None:
    await make_source("Now")
    assert len(await Scheduler(sessionmaker, 3).enqueue_due()) == 1
