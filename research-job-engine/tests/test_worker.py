import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from sqlalchemy import text

from app.config import Settings
from app.jobs.repository import JobRepository
from app.research.base import ResearchResult, SaveCheckpoint
from app.research.mock import STAGES, MockResearchExecutor
from app.worker.runner import Worker


@contextlib.asynccontextmanager
async def running(worker: Worker) -> AsyncIterator[asyncio.Event]:
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run(stop))
    try:
        yield stop
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=10)


async def wait_for(predicate: Callable[[], Any], limit: float = 10.0) -> None:
    async with asyncio.timeout(limit):
        while not await predicate():  # noqa: ASYNC110 - polling the database
            await asyncio.sleep(0.05)


def status_is(db, job_id, *statuses: str):
    async def check() -> bool:
        return (await db.job(job_id))["status"] in statuses

    return check


class RecordingExecutor(MockResearchExecutor):
    """Mock executor that records which stages actually ran."""

    def __init__(self, delay: float = 0.0) -> None:
        super().__init__(delay)
        self.ran: list[str] = []

    async def run(self, topic: str, checkpoint, save_checkpoint: SaveCheckpoint) -> ResearchResult:
        async def recording(stage: str, data: dict[str, Any]) -> None:
            self.ran.append(stage)
            await save_checkpoint(stage, data)

        return await super().run(topic, checkpoint, recording)


async def test_end_to_end_with_mock_executor(repo: JobRepository, db, settings: Settings) -> None:
    job = await repo.create_job("Retrieval augmented generation", 3)
    worker = Worker(repo, MockResearchExecutor(), settings, "w-e2e")
    async with running(worker):
        await wait_for(status_is(db, job.id, "completed", "failed"))
    row = await db.job(job.id)
    assert row["status"] == "completed" and row["attempt_count"] == 1
    events = await db.events(job.id)
    assert events == ["created", "claimed", *["checkpoint"] * len(STAGES), "completed"]
    report = await repo.get_report(job.id)
    assert report is not None
    content, sources = report[0].content, report[1]
    assert content.startswith("# Research report: Retrieval augmented generation")
    assert [s.url for s in sources] == [
        f"https://example.com/retrieval-augmented-generation/{i}" for i in (1, 2, 3)
    ]


async def test_mock_executor_is_deterministic() -> None:
    async def noop(stage: str, data: dict[str, Any]) -> None:
        return None

    a = await MockResearchExecutor().run("Same topic", None, noop)
    b = await MockResearchExecutor().run("Same topic", None, noop)
    assert a == b


class AlwaysFails:
    async def run(self, topic, checkpoint, save_checkpoint) -> ResearchResult:
        await save_checkpoint("planning", {})
        raise RuntimeError("search provider down")


async def test_worker_exceptions_respect_retry_limit(
    repo: JobRepository, db, settings: Settings
) -> None:
    job = await repo.create_job("doomed", 3)
    async with running(Worker(repo, AlwaysFails(), settings, "w-fail")):
        await wait_for(status_is(db, job.id, "failed"))
    row = await db.job(job.id)
    assert row["attempt_count"] == 3
    assert row["last_error"] == "RuntimeError: search provider down"
    events = await db.events(job.id)
    assert events.count("retry_scheduled") == 2 and events.count("failed") == 1
    assert await db.count("research_reports", job.id) == 0


class FailsOnce(MockResearchExecutor):
    def __init__(self) -> None:
        super().__init__(0)
        self.calls = 0

    async def run(self, topic, checkpoint, save_checkpoint) -> ResearchResult:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("transient")
        return await super().run(topic, checkpoint, save_checkpoint)


async def test_transient_failure_is_retried(repo: JobRepository, db, settings: Settings) -> None:
    job = await repo.create_job("flaky", 3)
    async with running(Worker(repo, FailsOnce(), settings, "w-flaky")):
        await wait_for(status_is(db, job.id, "completed", "failed"))
    row = await db.job(job.id)
    assert row["status"] == "completed" and row["attempt_count"] == 2
    assert row["last_error"] is None


async def test_pending_job_survives_worker_restart(
    repo: JobRepository, db, settings: Settings
) -> None:
    job = await repo.create_job("long job", 3)
    first = RecordingExecutor(delay=0.3)
    async with running(Worker(repo, first, settings, "w-first")):
        await wait_for(lambda: _has_checkpoint(db, job.id))
    # Graceful shutdown handed the job back with its checkpoint and refunded attempt.
    row = await db.job(job.id)
    assert row["status"] == "pending" and row["attempt_count"] == 0
    assert "released" in await db.events(job.id)
    done_before = list(first.ran)
    assert done_before and len(done_before) < len(STAGES)

    second = RecordingExecutor()
    async with running(Worker(repo, second, settings, "w-second")):
        await wait_for(status_is(db, job.id, "completed", "failed"))
    assert (await db.job(job.id))["status"] == "completed"
    assert second.ran == list(STAGES[len(done_before) :])  # resumed, not restarted


async def _has_checkpoint(db, job_id) -> bool:
    return (await db.job(job_id))["checkpoint"] is not None


async def test_heartbeats_keep_long_job_alive(repo: JobRepository, db, settings: Settings) -> None:
    fast_lease = settings.model_copy(update={"lease_seconds": 1, "heartbeat_seconds": 0.2})
    job = await repo.create_job("slow", 3)

    class Slow:
        async def run(self, topic, checkpoint, save_checkpoint) -> ResearchResult:
            await asyncio.sleep(2.5)  # longer than the lease; no checkpoints
            return ResearchResult("done")

    async with running(Worker(repo, Slow(), fast_lease, "w-slow")):
        await wait_for(status_is(db, job.id, "completed", "failed"))
    row = await db.job(job.id)
    assert row["status"] == "completed" and row["attempt_count"] == 1
    assert "lease_expired" not in await db.events(job.id)


async def test_worker_that_loses_lease_does_not_write_results(
    repo: JobRepository, db, settings: Settings
) -> None:
    job = await repo.create_job("stolen", 3)
    gate = asyncio.Event()

    class Blocks:
        async def run(self, topic, checkpoint, save_checkpoint) -> ResearchResult:
            await gate.wait()
            return ResearchResult("stale result")

    async with running(Worker(repo, Blocks(), settings, "w-zombie")):
        await wait_for(status_is(db, job.id, "running"))
        # Simulate a newer owner taking over (as recovery + re-claim would).
        async with db.engine.begin() as c:
            await c.execute(
                text(
                    "UPDATE research_jobs SET worker_version = worker_version + 1, "
                    "assigned_worker_id = 'w-new' WHERE id = :id"
                ),
                {"id": job.id},
            )
        gate.set()
        await asyncio.sleep(0.5)
    row = await db.job(job.id)
    assert row["status"] == "running" and row["assigned_worker_id"] == "w-new"
    assert await db.count("research_reports", job.id) == 0


async def test_crashed_worker_job_is_recovered(repo: JobRepository, db, settings: Settings) -> None:
    job = await repo.create_job("orphan", 3)
    crashed = await repo.claim("w-crashed", 30)  # claimed, then the process "dies"
    assert crashed is not None
    await db.expire_lease(job.id)
    async with running(Worker(repo, MockResearchExecutor(), settings, "w-rescuer")):
        await wait_for(status_is(db, job.id, "completed", "failed"))
    row = await db.job(job.id)
    assert row["status"] == "completed" and row["attempt_count"] == 2
    events = await db.events(job.id)
    assert events.index("lease_expired") < events.index("completed")


@pytest.mark.parametrize("concurrency", [1, 3])
async def test_worker_drains_queue(
    repo: JobRepository, db, settings: Settings, concurrency
) -> None:
    jobs = [await repo.create_job(f"batch {i}", 3) for i in range(6)]
    cfg = settings.model_copy(update={"worker_concurrency": concurrency})
    async with (
        running(Worker(repo, MockResearchExecutor(0.02), cfg, "w-a")),
        running(Worker(repo, MockResearchExecutor(0.02), cfg, "w-b")),
    ):
        for job in jobs:
            await wait_for(status_is(db, job.id, "completed", "failed"))
    for job in jobs:
        row = await db.job(job.id)
        assert row["status"] == "completed" and row["attempt_count"] == 1
