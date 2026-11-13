import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.api.main import create_app
from app.config import Settings
from app.feed.repository import FeedRepository
from app.jobs.repository import JobRepository
from app.scheduler.scheduler import Scheduler

BASE = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.fixture
async def client(
    repo: JobRepository, sessionmaker, settings: Settings
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    app.state.settings = settings
    app.state.repo = repo
    app.state.feed_repo = FeedRepository(sessionmaker)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _add_item(db, source_id, n: int, ctype: str = "article", published=True) -> uuid.UUID:
    item_id = uuid.uuid4()
    async with db.engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO content_items (id, source_id, content_type, title, url, "
                "canonical_url, published_at, fetched_at, external_id) VALUES "
                "(:id, :s, :t, :title, :u, :u, :p, :f, :e)"
            ),
            {
                "id": item_id,
                "s": source_id,
                "t": ctype,
                "title": f"item {n}",
                "u": f"https://ex.example/{source_id}/{n}",
                "p": BASE + timedelta(hours=n) if published else None,
                "f": BASE + timedelta(hours=n, minutes=5),
                "e": str(n),
            },
        )
    return item_id


@pytest.fixture
async def seeded(make_source, db) -> dict:
    news = await make_source("News")
    videos = await make_source("Videos", source_type="youtube")
    for n in range(1, 8):
        await _add_item(db, news, n)
    for n in range(10, 13):
        await _add_item(db, videos, n, "video")
    await _add_item(db, news, 20, published=False)  # sorts by fetched_at
    return {"news": news, "videos": videos}


async def test_feed_pagination_and_ordering(client, seeded) -> None:
    r = await client.get("/api/v1/feed", params={"limit": 4})
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 11 and body["limit"] == 4 and body["offset"] == 0
    assert [i["title"] for i in body["items"]] == ["item 20", "item 12", "item 11", "item 10"]
    assert body["items"][0]["published_at"] is None  # missing date is not invented
    page3 = (await client.get("/api/v1/feed", params={"limit": 4, "offset": 8})).json()
    assert [i["title"] for i in page3["items"]] == ["item 3", "item 2", "item 1"]


async def test_feed_filters(client, seeded) -> None:
    videos = (await client.get("/api/v1/feed", params={"type": "video"})).json()
    assert videos["total"] == 3 and {i["type"] for i in videos["items"]} == {"video"}
    assert videos["items"][0]["source_name"] == "Videos"

    by_source = (await client.get("/api/v1/feed", params={"source_id": str(seeded["news"])})).json()
    assert by_source["total"] == 8

    window = (
        await client.get(
            "/api/v1/feed",
            params={
                "since": (BASE + timedelta(hours=2)).isoformat(),
                "until": (BASE + timedelta(hours=5)).isoformat(),
            },
        )
    ).json()
    assert [i["title"] for i in window["items"]] == ["item 4", "item 3", "item 2"]

    combined = (
        await client.get(
            "/api/v1/feed",
            params=[("type", "article"), ("source_id", str(seeded["videos"]))],
        )
    ).json()
    assert combined["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"type": "podcast"},
        {"source_id": "nope"},
        {"since": "yesterday"},
        {"since": "2026-11-01T00:00:00"},  # naive datetime
        {"since": "2026-11-02T00:00:00Z", "until": "2026-11-01T00:00:00Z"},
    ],
)
async def test_feed_validation(client, params) -> None:
    assert (await client.get("/api/v1/feed", params=params)).status_code == 422


async def test_feed_item_detail(client, seeded, db) -> None:
    item_id = await _add_item(db, seeded["news"], 99)
    r = await client.get(f"/api/v1/feed/{item_id}")
    assert r.status_code == 200 and r.json()["title"] == "item 99"
    assert (await client.get(f"/api/v1/feed/{uuid.uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/feed/not-a-uuid")).status_code == 422


async def test_sources_endpoint(client, seeded, make_source) -> None:
    await make_source("Disabled", enabled=False)
    all_sources = (await client.get("/api/v1/sources")).json()
    assert [s["name"] for s in all_sources] == ["Disabled", "News", "Videos"]
    counts = {s["name"]: s["item_count"] for s in all_sources}
    assert counts == {"Disabled": 0, "News": 8, "Videos": 3}
    enabled = (await client.get("/api/v1/sources", params={"enabled": "true"})).json()
    assert [s["name"] for s in enabled] == ["News", "Videos"]


async def test_ingestion_runs_endpoint(client, seeded, sessionmaker, db) -> None:
    await Scheduler(sessionmaker, 3).enqueue_due()
    async with db.engine.begin() as c:
        await c.execute(
            text(
                "UPDATE research_jobs SET status = 'completed', completed_at = now(), "
                'checkpoint = \'{"items_seen": 5, "items_inserted": 2}\' WHERE source_id = :s'
            ),
            {"s": seeded["news"]},
        )
    runs = (await client.get("/api/v1/ingestion-runs")).json()
    assert runs["total"] == 2
    done = (await client.get("/api/v1/ingestion-runs", params={"status": "completed"})).json()
    assert done["total"] == 1
    run = done["items"][0]
    assert run["source_name"] == "News" and run["items_inserted"] == 2 and run["items_seen"] == 5
    by_source = (
        await client.get("/api/v1/ingestion-runs", params={"source_id": str(seeded["videos"])})
    ).json()
    assert by_source["total"] == 1 and by_source["items"][0]["status"] == "pending"
    assert (await client.get("/api/v1/ingestion-runs", params={"status": "x"})).status_code == 422


async def test_stats_endpoint(client, seeded, sessionmaker) -> None:
    await Scheduler(sessionmaker, 3).enqueue_due()
    stats = (await client.get("/api/v1/stats")).json()
    assert stats["total_items"] == 11
    assert stats["items_by_type"] == {"article": 8, "video": 3}
    assert stats["sources_total"] == 2 and stats["sources_enabled"] == 2
    assert stats["ingestion_runs_by_status"]["pending"] == 2
    assert stats["newest_item_at"] is not None


async def test_empty_feed(client) -> None:
    body = (await client.get("/api/v1/feed")).json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}
    stats = (await client.get("/api/v1/stats")).json()
    assert stats["total_items"] == 0 and stats["newest_item_at"] is None
