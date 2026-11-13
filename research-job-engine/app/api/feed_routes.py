import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.feed_schemas import FeedItemOut, IngestionRunOut, Page, SourceOut, StatsOut
from app.feed.repository import FeedFilter, FeedRepository
from app.models import ContentItem, ContentType, JobStatus

router = APIRouter(prefix="/api/v1")

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100_000)]


def _repo(request: Request) -> FeedRepository:
    return request.app.state.feed_repo


def _item(item: ContentItem, source_name: str) -> FeedItemOut:
    return FeedItemOut(
        id=item.id,
        source_id=item.source_id,
        source_name=source_name,
        type=item.content_type,
        title=item.title,
        url=item.url,
        summary=item.summary,
        thumbnail_url=item.thumbnail_url,
        published_at=item.published_at,
        fetched_at=item.fetched_at,
        external_id=item.external_id,
    )


def _aware(name: str, value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise HTTPException(
            422,
            f"{name} must include a timezone (e.g. 2026-11-13T00:00:00Z)",
        )
    return value


@router.get("/feed", response_model=Page[FeedItemOut])
async def list_feed(
    request: Request,
    limit: Limit = 20,
    offset: Offset = 0,
    type: ContentType | None = None,  # noqa: A002 - public query parameter name
    source_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[FeedItemOut]:
    since, until = _aware("since", since), _aware("until", until)
    if since and until and since >= until:
        raise HTTPException(422, "since must be before until")
    f = FeedFilter(type, tuple(source_id or ()), since, until, (q or "").strip() or None)
    rows, total = await _repo(request).list_feed(f, limit, offset)
    return Page(items=[_item(i, n) for i, n in rows], total=total, limit=limit, offset=offset)


@router.get("/feed/{item_id}", response_model=FeedItemOut)
async def get_feed_item(item_id: uuid.UUID, request: Request) -> FeedItemOut:
    found = await _repo(request).get_item(item_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item not found")
    return _item(*found)


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(request: Request, enabled: bool | None = None) -> list[SourceOut]:
    return [
        SourceOut(
            id=s.id,
            name=s.name,
            source_type=s.source_type,
            feed_url=s.feed_url,
            channel_id=s.channel_id,
            enabled=s.enabled,
            fetch_interval_seconds=s.fetch_interval_seconds,
            last_success_at=s.last_success_at,
            last_error=s.last_error,
            item_count=n,
        )
        for s, n in await _repo(request).list_sources(enabled)
    ]


@router.get("/ingestion-runs", response_model=Page[IngestionRunOut])
async def list_runs(
    request: Request,
    limit: Limit = 20,
    offset: Offset = 0,
    source_id: uuid.UUID | None = None,
    status_: Annotated[JobStatus | None, Query(alias="status")] = None,
) -> Page[IngestionRunOut]:
    rows, total = await _repo(request).list_runs(source_id, status_, limit, offset)
    items = []
    for job, name, started_at in rows:
        cp = job.checkpoint or {}
        items.append(
            IngestionRunOut(
                id=job.id,
                source_id=job.source_id,
                source_name=name,
                status=job.status,
                scheduled_for=job.scheduled_for,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                items_seen=cp.get("items_seen"),
                items_inserted=cp.get("items_inserted"),
                last_error=job.last_error,
                next_attempt_at=job.next_attempt_at,
                created_at=job.created_at,
                started_at=started_at,
                completed_at=job.completed_at,
            )
        )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/stats", response_model=StatsOut)
async def stats(request: Request) -> StatsOut:
    return StatsOut(**await _repo(request).stats())
