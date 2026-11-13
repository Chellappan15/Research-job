import asyncio
from collections import Counter

from app.jobs.repository import JobRepository


async def test_concurrent_workers_claim_different_jobs(repo: JobRepository) -> None:
    jobs = {(await repo.create_job(f"topic {i}", 3)).id for i in range(25)}

    async def claimer(worker: str) -> list:
        got = []
        while (lease := await repo.claim(worker, 30)) is not None:
            got.append(lease.job_id)
        return got

    results = await asyncio.gather(*[claimer(f"w{i}") for i in range(8)])
    claimed = [j for r in results for j in r]
    assert Counter(claimed).most_common(1)[0][1] == 1  # no job claimed twice
    assert set(claimed) == jobs
    assert sum(1 for r in results if r) > 1  # work was actually spread across workers


async def test_single_job_claimed_once_under_contention(repo: JobRepository, db) -> None:
    job = await repo.create_job("only one", 3)
    leases = await asyncio.gather(*[repo.claim(f"w{i}", 30) for i in range(12)])
    winners = [lease for lease in leases if lease is not None]
    assert len(winners) == 1
    row = await db.job(job.id)
    assert row["worker_version"] == 1 and row["attempt_count"] == 1
