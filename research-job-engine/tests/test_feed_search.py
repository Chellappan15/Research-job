from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.api.main import create_app
from app.feed.repository import FeedRepository
from app.scheduler.scheduler import Scheduler
from tests.test_feed_api import client  # noqa: F401 - shared fixture

BASE = datetime(2026, 11, 1, tzinfo=UTC)


async def _item(db, source_id, n, title, summary=None, ctype="article") -> None:
    async with db.engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO content_items (id, source_id, content_type, title, url, "
                "canonical_url, summary, published_at, fetched_at, external_id) VALUES "
                "(gen_random_uuid(), :s, :t, :title, :u, :u, :summary, :p, now(), :e)"
            ),
            {
                "s": source_id,
                "t": ctype,
                "title": title,
                "summary": summary,
                "u": f"https://s.example/{source_id}/{n}",
                "p": BASE + timedelta(hours=n),
                "e": str(n),
            },
        )


@pytest.fixture
async def corpus(make_source, db) -> dict:
    news = await make_source("News")
    vids = await make_source("Vids", source_type="youtube")
    await _item(db, news, 1, "Diffusion models explained", "Image generation basics")
    await _item(db, news, 2, "New open-weights LLM released", "A transformer model with 70B")
    await _item(db, news, 3, "Kubernetes 2.0", "Nothing about AI here")
    await _item(db, vids, 4, "Transformers in 10 minutes", None, "video")
    for n in range(10, 40):  # filler so matches span beyond one page
        await _item(db, news, n, f"Weekly model roundup {n}", "links")
    return {"news": news, "vids": vids}


async def test_search_covers_whole_database(client, corpus) -> None:  # noqa: F811
    r = await client.get("/api/v1/feed", params={"q": "model", "limit": 5})
    body = r.json()
    assert r.status_code == 200
    # stemming: "model" matches "models"/"model"; 30 roundups + 2 others, not just page 1
    assert body["total"] == 32
    assert len(body["items"]) == 5
    assert body["items"][0]["title"] == "Weekly model roundup 39"  # still newest-first


async def test_search_matches_summary_and_phrases(client, corpus) -> None:  # noqa: F811
    hits = (await client.get("/api/v1/feed", params={"q": "image generation"})).json()
    assert [i["title"] for i in hits["items"]] == ["Diffusion models explained"]
    phrase = (await client.get("/api/v1/feed", params={"q": '"open-weights"'})).json()
    assert phrase["total"] == 1
    excluded = (await client.get("/api/v1/feed", params={"q": "model -weekly"})).json()
    assert excluded["total"] == 2


async def test_search_combines_with_filters(client, corpus) -> None:  # noqa: F811
    r = await client.get("/api/v1/feed", params={"q": "transformer", "type": "video"})
    assert [i["title"] for i in r.json()["items"]] == ["Transformers in 10 minutes"]
    r = await client.get(
        "/api/v1/feed", params={"q": "transformer", "source_id": str(corpus["news"])}
    )
    assert [i["title"] for i in r.json()["items"]] == ["New open-weights LLM released"]


async def test_search_edge_cases(client, corpus) -> None:  # noqa: F811
    assert (await client.get("/api/v1/feed", params={"q": "   "})).json()["total"] == 34
    assert (await client.get("/api/v1/feed", params={"q": "zzzqqq"})).json()["total"] == 0
    assert (await client.get("/api/v1/feed", params={"q": "&|!():*"})).status_code == 200
    assert (await client.get("/api/v1/feed", params={"q": "x" * 201})).status_code == 422


async def test_runs_expose_started_at(client, make_source, sessionmaker, repo) -> None:  # noqa: F811
    await make_source("Runs")
    await Scheduler(sessionmaker, 3).enqueue_due()
    run = (await client.get("/api/v1/ingestion-runs")).json()["items"][0]
    assert run["started_at"] is None  # not picked up yet
    lease = await repo.claim("w1", 30)
    assert lease is not None
    run = (await client.get("/api/v1/ingestion-runs")).json()["items"][0]
    assert run["status"] == "running" and run["started_at"] is not None


async def test_cors_only_when_configured(repo, sessionmaker, settings) -> None:
    for origins, expected in (("", None), ("http://localhost:5173", "http://localhost:5173")):
        app = create_app(settings.model_copy(update={"cors_origins": origins}))
        app.state.settings, app.state.repo = settings, repo
        app.state.feed_repo = FeedRepository(sessionmaker)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            r = await c.get("/api/v1/stats", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("access-control-allow-origin") == expected
