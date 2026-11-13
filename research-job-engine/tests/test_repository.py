import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError

from app.jobs.repository import JobRepository, LeaseLost, RetryPolicy
from app.models import ResearchReport
from app.research.base import ResearchResult, Source

RESULT = ResearchResult(
    "final report", [Source("https://s1.example", "S1"), Source("https://s2.example")]
)


async def test_claim_sets_ownership(repo: JobRepository, db) -> None:
    job = await repo.create_job("topic", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None and lease.job_id == job.id
    assert (lease.version, lease.attempt, lease.worker_id) == (1, 1, "w1")
    row = await db.job(job.id)
    assert row["status"] == "running"
    assert row["assigned_worker_id"] == "w1"
    assert row["worker_version"] == 1 and row["attempt_count"] == 1
    assert row["lease_expires_at"] is not None
    assert await db.events(job.id) == ["created", "claimed"]


async def test_claim_nothing_eligible(repo: JobRepository, db) -> None:
    assert await repo.claim("w1", 30) is None
    job = await repo.create_job("later", 3)
    async with db.engine.begin() as c:
        await c.execute(
            text("UPDATE research_jobs SET next_attempt_at = now() + interval '1 hour'")
        )
    assert await repo.claim("w1", 30) is None
    await db.make_due(job.id)
    assert await repo.claim("w1", 30) is not None


async def test_claim_order_is_fifo(repo: JobRepository) -> None:
    first = await repo.create_job("first", 3)
    await repo.create_job("second", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None and lease.job_id == first.id


async def test_heartbeat_extends_lease(repo: JobRepository, db) -> None:
    await repo.create_job("t", 3)
    lease = await repo.claim("w1", 5)
    assert lease is not None
    before = (await db.job(lease.job_id))["lease_expires_at"]
    assert await repo.heartbeat(lease, 60) is True
    after = (await db.job(lease.job_id))["lease_expires_at"]
    assert after - before > timedelta(seconds=50)


async def test_heartbeat_rejected_after_expiry(repo: JobRepository, db) -> None:
    await repo.create_job("t", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None
    await db.expire_lease(lease.job_id)
    assert await repo.heartbeat(lease, 30) is False


async def test_heartbeat_rejected_for_wrong_worker(repo: JobRepository) -> None:
    await repo.create_job("t", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None
    from dataclasses import replace

    assert await repo.heartbeat(replace(lease, worker_id="intruder"), 30) is False


async def test_stale_fencing_token_rejected(repo: JobRepository, db, policy: RetryPolicy) -> None:
    job = await repo.create_job("t", 3)
    stale = await repo.claim("w-old", 30)
    assert stale is not None
    await db.expire_lease(job.id)
    assert await repo.recover_expired(RetryPolicy(0, 0)) == 1
    current = await repo.claim("w-new", 30)
    assert current is not None and current.version == stale.version + 1

    # Even with the same worker id, a stale version is fenced off.
    from dataclasses import replace

    same_id_stale = replace(stale, worker_id="w-new")
    for lease in (stale, same_id_stale):
        assert await repo.heartbeat(lease, 30) is False
        with pytest.raises(LeaseLost):
            await repo.save_checkpoint(lease, "planning", {"x": 1}, 30)
        with pytest.raises(LeaseLost):
            await repo.complete(lease, RESULT)
        with pytest.raises(LeaseLost):
            await repo.fail_attempt(lease, "boom", policy)
        assert await repo.release(lease, "shutdown") is False

    row = await db.job(job.id)
    assert row["status"] == "running" and row["assigned_worker_id"] == "w-new"
    assert row["checkpoint"] is None
    assert await db.count("research_reports", job.id) == 0

    await repo.complete(current, RESULT)
    assert (await db.job(job.id))["status"] == "completed"


async def test_atomic_completion(repo: JobRepository, db) -> None:
    job = await repo.create_job("t", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None
    await repo.save_checkpoint(lease, "reporting", {"k": "v"}, 30)
    await repo.complete(lease, RESULT)
    row = await db.job(job.id)
    assert row["status"] == "completed"
    assert row["completed_at"] is not None
    assert row["assigned_worker_id"] is None and row["lease_expires_at"] is None
    assert row["checkpoint"] == {"stage": "completed", "data": {"k": "v"}}
    assert await db.count("research_reports", job.id) == 1
    assert await db.count("research_sources", job.id) == 2
    assert (await db.events(job.id))[-1] == "completed"
    # A second completion by the same (now finished) lease is rejected.
    with pytest.raises(LeaseLost):
        await repo.complete(lease, RESULT)
    assert await db.count("research_reports", job.id) == 1


async def test_completion_rolls_back_on_failure(repo: JobRepository, db, sessionmaker) -> None:
    job = await repo.create_job("t", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None
    # Plant a conflicting report so the report INSERT violates the unique constraint.
    async with sessionmaker.begin() as s:
        await s.execute(insert(ResearchReport).values(job_id=job.id, content="planted"))
    with pytest.raises(IntegrityError):
        await repo.complete(lease, RESULT)
    row = await db.job(job.id)
    assert row["status"] == "running"  # status update rolled back
    assert row["completed_at"] is None
    assert await db.count("research_sources", job.id) == 0
    assert "completed" not in await db.events(job.id)


async def test_constraints_reject_invalid_rows(db) -> None:
    with pytest.raises(IntegrityError):
        async with db.engine.begin() as c:
            await c.execute(
                text("INSERT INTO research_jobs (id, topic) VALUES (gen_random_uuid(), '  ')")
            )
    with pytest.raises(IntegrityError):
        async with db.engine.begin() as c:
            await c.execute(
                text(
                    "INSERT INTO research_jobs (id, topic, max_attempts) "
                    "VALUES (gen_random_uuid(), 'x', 0)"
                )
            )


async def test_expired_lease_recovery_schedules_retry(
    repo: JobRepository, db, policy: RetryPolicy
) -> None:
    job = await repo.create_job("t", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None
    await db.expire_lease(job.id)
    assert await repo.recover_expired(policy) == 1
    row = await db.job(job.id)
    assert row["status"] == "pending"
    assert row["assigned_worker_id"] is None and row["lease_expires_at"] is None
    assert "lease expired" in row["last_error"]
    assert row["next_attempt_at"] > row["updated_at"] + timedelta(seconds=9)  # 10s backoff
    assert await repo.claim("w2", 30) is None  # not yet due
    await db.make_due(job.id)
    again = await repo.claim("w2", 30)
    assert again is not None and again.attempt == 2 and again.version == 2


async def test_expired_lease_recovery_fails_when_exhausted(repo: JobRepository, db) -> None:
    job = await repo.create_job("t", 1)
    assert await repo.claim("w1", 30) is not None
    await db.expire_lease(job.id)
    assert await repo.recover_expired(RetryPolicy(0, 0)) == 1
    row = await db.job(job.id)
    assert row["status"] == "failed"
    assert "lease expired" in row["last_error"]
    assert await repo.claim("w2", 30) is None


async def test_unexpired_leases_not_recovered(repo: JobRepository) -> None:
    await repo.create_job("t", 3)
    assert await repo.claim("w1", 30) is not None
    assert await repo.recover_expired(RetryPolicy(0, 0)) == 0


async def test_concurrent_recovery_is_safe(repo: JobRepository, db) -> None:
    jobs = [await repo.create_job(f"t{i}", 3) for i in range(10)]
    for _ in jobs:
        assert await repo.claim("w1", 30) is not None
    async with db.engine.begin() as c:
        await c.execute(
            text("UPDATE research_jobs SET lease_expires_at = now() - interval '1 second'")
        )
    counts = await asyncio.gather(*[repo.recover_expired(RetryPolicy(0, 0)) for _ in range(6)])
    assert sum(counts) == 10
    for job in jobs:
        assert (await db.events(job.id)).count("lease_expired") == 1


async def test_fail_attempt_retries_with_backoff_then_fails(repo: JobRepository, db) -> None:
    policy = RetryPolicy(base_seconds=10, max_seconds=15)
    assert [policy.delay(a) for a in (1, 2, 3, 4)] == [10, 15, 15, 15]
    job = await repo.create_job("t", 2)

    lease = await repo.claim("w1", 30)
    assert lease is not None
    assert (await repo.fail_attempt(lease, "boom 1", policy)).value == "pending"
    row = await db.job(job.id)
    assert row["last_error"] == "boom 1"
    assert row["next_attempt_at"] > row["updated_at"] + timedelta(seconds=9)

    await db.make_due(job.id)
    lease = await repo.claim("w1", 30)
    assert lease is not None and lease.attempt == 2
    assert (await repo.fail_attempt(lease, "boom 2", policy)).value == "failed"
    row = await db.job(job.id)
    assert row["status"] == "failed" and row["last_error"] == "boom 2"
    assert await db.events(job.id) == [
        "created",
        "claimed",
        "retry_scheduled",
        "claimed",
        "failed",
    ]


async def test_release_refunds_attempt(repo: JobRepository, db) -> None:
    job = await repo.create_job("t", 3)
    lease = await repo.claim("w1", 30)
    assert lease is not None
    await repo.save_checkpoint(lease, "planning", {"q": 1}, 30)
    assert await repo.release(lease, "shutdown") is True
    row = await db.job(job.id)
    assert row["status"] == "pending" and row["attempt_count"] == 0
    assert row["checkpoint"] == {"stage": "planning", "data": {"q": 1}}  # kept for resume
    nxt = await repo.claim("w2", 30)
    assert nxt is not None and nxt.version == 2 and nxt.checkpoint["stage"] == "planning"
