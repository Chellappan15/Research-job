import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.api.main import create_app
from app.config import Settings
from app.jobs.repository import JobRepository
from app.research.base import ResearchResult, Source


@pytest.fixture
async def client(repo: JobRepository, settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    app.state.settings = settings  # lifespan is not run by ASGITransport; wire state directly
    app.state.repo = repo
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_create_job_persists_pending(client: httpx.AsyncClient, db) -> None:
    r = await client.post("/api/v1/jobs", json={"topic": "  Solid-state batteries  "})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    row = await db.job(uuid.UUID(body["job_id"]))
    assert row["topic"] == "Solid-state batteries"
    assert row["status"] == "pending"
    assert row["attempt_count"] == 0 and row["worker_version"] == 0
    assert await db.events(row["id"]) == ["created"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"topic": ""},
        {"topic": "   "},
        {"topic": None},
        {"topic": 123},
        {"topic": "x" * 501},
        {"topic": "ok", "unexpected": True},
    ],
)
async def test_invalid_requests_rejected(client: httpx.AsyncClient, payload: dict) -> None:
    r = await client.post("/api/v1/jobs", json=payload)
    assert r.status_code == 422


async def test_get_job_status(client: httpx.AsyncClient) -> None:
    job_id = (await client.post("/api/v1/jobs", json={"topic": "graph databases"})).json()["job_id"]
    r = await client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["stage"] is None
    assert body["report_available"] is False
    assert body["created_at"] and body["updated_at"]


async def test_get_unknown_job_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"/api/v1/jobs/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"/api/v1/jobs/{uuid.uuid4()}/report")).status_code == 404
    assert (await client.get("/api/v1/jobs/not-a-uuid")).status_code == 422


async def test_report_unavailable_until_completed(
    client: httpx.AsyncClient, repo: JobRepository
) -> None:
    job_id = (await client.post("/api/v1/jobs", json={"topic": "quantum"})).json()["job_id"]
    r = await client.get(f"/api/v1/jobs/{job_id}/report")
    assert r.status_code == 409

    lease = await repo.claim("w1", 30)
    assert lease is not None
    await repo.save_checkpoint(lease, "planning", {}, 30)
    status = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert status["status"] == "running" and status["stage"] == "planning"

    await repo.complete(lease, ResearchResult("report body", [Source("https://a.example", "A")]))
    body = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert body["status"] == "completed" and body["report_available"] is True
    assert body["stage"] == "completed" and body["completed_at"]

    report = (await client.get(f"/api/v1/jobs/{job_id}/report")).json()
    assert report["content"] == "report body"
    assert report["sources"] == [{"url": "https://a.example", "title": "A"}]
