import contextlib
from collections.abc import AsyncIterator, Callable
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import text

from app.config import Settings
from app.ingest.fetchers import FeedFetcher
from app.ingest.ingestor import Ingestor
from app.ingest.repository import IngestRepository
from app.jobs.repository import JobRepository, LeaseLost
from app.research.mock import MockResearchExecutor
from app.scheduler.scheduler import Scheduler
from app.worker.runner import Worker
from tests import feeds
from tests.test_worker import running, wait_for

Handler = Callable[[httpx.Request], httpx.Response]


def routes(table: dict[str, httpx.Response | Callable[[], httpx.Response]]) -> Handler:
    calls: dict[str, int] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        key = req.url.host
        calls[key] = calls.get(key, 0) + 1
        resp = table[key]
        return resp() if callable(resp) else resp

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


def xml(body: bytes) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "application/xml"})


@pytest.fixture
def ingest_repo(sessionmaker) -> IngestRepository:
    return IngestRepository(sessionmaker)


@contextlib.asynccontextmanager
async def worker_with(
    repo: JobRepository, ingest_repo: IngestRepository, settings: Settings, handler: Handler
) -> AsyncIterator[None]:
    fetcher = FeedFetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    worker = Worker(
        repo, MockResearchExecutor(), settings, "w-ingest", ingestor=Ingestor(ingest_repo, fetcher)
    )
    async with running(worker):
        yield
    await fetcher.aclose()


async def _job_for(db, source_id) -> dict:
    async with db.engine.connect() as c:
        row = (
            (
                await c.execute(
                    text(
                        "SELECT * FROM research_jobs WHERE source_id = :s "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"s": source_id},
                )
            )
            .mappings()
            .one()
        )
        return dict(row)


async def _items(db, source_id=None) -> list[dict]:
    async with db.engine.connect() as c:
        q = "SELECT * FROM content_items" + (" WHERE source_id = :s" if source_id else "")
        return [dict(r) for r in (await c.execute(text(q), {"s": source_id})).mappings()]


async def _source(db, source_id) -> dict:
    async with db.engine.connect() as c:
        return dict(
            (await c.execute(text("SELECT * FROM sources WHERE id = :s"), {"s": source_id}))
            .mappings()
            .one()
        )


def done(db, source_id, *statuses: str):
    async def check() -> bool:
        return (await _job_for(db, source_id))["status"] in statuses

    return check


async def test_rss_and_youtube_end_to_end(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    rss = await make_source("AI Weekly", feed_url="https://news.example.com/feed")
    yt = await make_source("AI Explained", source_type="youtube")
    await Scheduler(sessionmaker, 3).enqueue_due()
    handler = routes({"news.example.com": xml(feeds.RSS), "www.youtube.com": xml(feeds.YOUTUBE)})
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, rss, "completed", "failed"))
        await wait_for(done(db, yt, "completed", "failed"))

    rss_job, yt_job = await _job_for(db, rss), await _job_for(db, yt)
    assert rss_job["status"] == "completed" and yt_job["status"] == "completed"
    assert rss_job["checkpoint"] == {"stage": "completed", "items_seen": 3, "items_inserted": 3}
    assert yt_job["checkpoint"]["items_inserted"] == 2
    videos = await _items(db, yt)
    assert {v["content_type"] for v in videos} == {"video"}
    assert {v["external_id"] for v in videos} == {"yt:abcDEF12345", "yt:zzzZZZ99999"}
    assert (await _source(db, rss))["last_success_at"] is not None
    assert "ingested" in await db.events(rss_job["id"])


async def test_duplicate_prevention_across_runs_and_sources(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    a = await make_source("Feed A", feed_url="https://a.example/feed", fetch_interval_seconds=60)
    b = await make_source("Feed B", feed_url="https://b.example/feed", fetch_interval_seconds=60)
    sched = Scheduler(sessionmaker, 3)
    handler = routes({"a.example": xml(feeds.RSS), "b.example": xml(feeds.RSS)})
    await sched.enqueue_due()
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, a, "completed", "failed"))
        await wait_for(done(db, b, "completed", "failed"))
    # Same articles syndicated by two sources: canonical URL is unique -> stored once.
    assert len(await _items(db)) == 3
    inserted = [(await _job_for(db, s))["checkpoint"]["items_inserted"] for s in (a, b)]
    assert sorted(inserted) == [0, 3]

    # Next slot re-fetches the same feed: nothing new is inserted.
    from datetime import UTC, datetime

    await sched.enqueue_due(datetime.now(UTC) + timedelta(minutes=2))
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, a, "completed", "failed"))
    assert (await _job_for(db, a))["checkpoint"]["items_inserted"] == 0
    assert len(await _items(db)) == 3


async def test_db_constraints_enforce_dedup(make_source, db) -> None:
    sid = await make_source("X")
    insert = text(
        "INSERT INTO content_items (id, source_id, content_type, title, url, canonical_url, "
        "fetched_at, external_id) VALUES (gen_random_uuid(), :s, 'article', 't', :u, :c, now(), :e)"
    )
    from sqlalchemy.exc import IntegrityError

    async with db.engine.begin() as c:
        await c.execute(insert, {"s": sid, "u": "https://x/1", "c": "https://x/1", "e": "1"})
    for params in (
        {"s": sid, "u": "https://x/2", "c": "https://x/2", "e": "1"},  # same external id
        {"s": sid, "u": "https://x/1?a", "c": "https://x/1", "e": "2"},  # same canonical url
    ):
        with pytest.raises(IntegrityError):
            async with db.engine.begin() as c:
                await c.execute(insert, params)


async def test_source_failure_is_isolated_and_retried(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    good = await make_source("Good", feed_url="https://good.example/feed")
    bad = await make_source("Bad", feed_url="https://bad.example/feed")
    await Scheduler(sessionmaker, 3).enqueue_due()
    handler = routes({"good.example": xml(feeds.RSS), "bad.example": httpx.Response(502)})
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, good, "completed", "failed"))
        await wait_for(done(db, bad, "failed"))
    bad_job = await _job_for(db, bad)
    assert bad_job["attempt_count"] == 3  # retried up to the budget
    assert "HTTP 502" in bad_job["last_error"]
    assert "HTTP 502" in (await _source(db, bad))["last_error"]
    assert handler.calls["bad.example"] == 3
    assert (await _job_for(db, good))["status"] == "completed"
    assert await _items(db, bad) == []


async def test_transient_failure_then_success(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    sid = await make_source("Flaky", feed_url="https://flaky.example/feed")
    responses = iter([httpx.Response(503), xml(feeds.RSS)])
    await Scheduler(sessionmaker, 3).enqueue_due()
    handler = routes({"flaky.example": lambda: next(responses)})
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, sid, "completed", "failed"))
    job = await _job_for(db, sid)
    assert job["status"] == "completed" and job["attempt_count"] == 2
    src = await _source(db, sid)
    assert src["last_error"] is None and src["last_success_at"] is not None


async def test_permanent_error_not_retried(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    sid = await make_source("Gone", feed_url="https://gone.example/feed")
    await Scheduler(sessionmaker, 3).enqueue_due()
    handler = routes({"gone.example": httpx.Response(404)})
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, sid, "failed"))
    job = await _job_for(db, sid)
    assert job["attempt_count"] == 1 and "HTTP 404" in job["last_error"]


async def test_rate_limit_honours_retry_after(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    sid = await make_source("Limited", feed_url="https://limited.example/feed")
    await Scheduler(sessionmaker, 3).enqueue_due()
    handler = routes({"limited.example": httpx.Response(429, headers={"retry-after": "600"})})
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(lambda: _attempted(db, sid))
    job = await _job_for(db, sid)
    assert job["status"] == "pending"
    assert job["next_attempt_at"] >= job["updated_at"] + timedelta(seconds=599)
    assert handler.calls["limited.example"] == 1


async def _attempted(db, sid) -> bool:
    job = await _job_for(db, sid)
    return job["attempt_count"] >= 1 and job["status"] == "pending"


async def test_worker_recovery_after_crash(
    repo, ingest_repo, sessionmaker, make_source, db, settings
) -> None:
    sid = await make_source("Orphan", feed_url="https://orphan.example/feed")
    await Scheduler(sessionmaker, 3).enqueue_due()
    crashed = await repo.claim("w-crashed", 30)  # claimed, then the process dies
    assert crashed is not None and crashed.kind == "ingest" and crashed.source_id == sid
    await db.expire_lease(crashed.job_id)
    handler = routes({"orphan.example": xml(feeds.RSS)})
    async with worker_with(repo, ingest_repo, settings, handler):
        await wait_for(done(db, sid, "completed", "failed"))
    job = await _job_for(db, sid)
    assert job["status"] == "completed" and job["attempt_count"] == 2
    events = await db.events(job["id"])
    assert events.index("lease_expired") < events.index("ingested")


async def test_stale_worker_cannot_store_items(
    repo, ingest_repo, sessionmaker, make_source, db
) -> None:
    from app.ingest.fetchers import parse_feed
    from app.jobs.repository import RetryPolicy
    from app.models import SourceType

    await make_source("Stale", feed_url="https://stale.example/feed")
    await Scheduler(sessionmaker, 3).enqueue_due()
    stale = await repo.claim("w-old", 30)
    assert stale is not None
    await db.expire_lease(stale.job_id)
    await repo.recover_expired(RetryPolicy(0, 0))
    current = await repo.claim("w-new", 30)
    assert current is not None

    from datetime import UTC, datetime

    items = parse_feed(feeds.RSS, SourceType.RSS, datetime.now(UTC))
    with pytest.raises(LeaseLost):
        await ingest_repo.complete_ingestion(stale, items)
    assert await _items(db) == []
    assert await ingest_repo.complete_ingestion(current, items) == 3
