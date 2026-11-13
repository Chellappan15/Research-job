"""Read-only queries backing the TechPulse REST API."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ContentItem, ContentType, JobEvent, JobStatus, ResearchJob, Source

C = ContentItem
J = ResearchJob
SORT_TS = func.coalesce(C.published_at, C.fetched_at)
DAY = func.make_interval(0, 0, 0, 1)
# Start of the latest attempt = most recent 'claimed' event (no extra column needed).
STARTED_AT = (
    select(func.max(JobEvent.created_at))
    .where(JobEvent.job_id == J.id, JobEvent.event_type == "claimed")
    .correlate(J)
    .scalar_subquery()
)


@dataclass(frozen=True)
class FeedFilter:
    content_type: ContentType | None = None
    source_ids: tuple[uuid.UUID, ...] = ()
    since: datetime | None = None
    until: datetime | None = None
    q: str | None = None


def _apply(stmt: Select[Any], f: FeedFilter) -> Select[Any]:
    if f.content_type is not None:
        stmt = stmt.where(C.content_type == f.content_type)
    if f.source_ids:
        stmt = stmt.where(C.source_id.in_(f.source_ids))
    if f.since is not None:
        stmt = stmt.where(SORT_TS >= f.since)
    if f.until is not None:
        stmt = stmt.where(SORT_TS < f.until)
    if f.q:
        # Full-text search over the whole table (GIN index); websearch syntax supports
        # "quoted phrases", OR and -exclusion. Results stay newest-first.
        stmt = stmt.where(C.search_vector.op("@@")(func.websearch_to_tsquery("english", f.q)))
    return stmt


class FeedRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = sessionmaker

    async def list_feed(
        self, f: FeedFilter, limit: int, offset: int
    ) -> tuple[list[tuple[ContentItem, str]], int]:
        async with self._sm() as s:
            total = (await s.execute(_apply(select(func.count()).select_from(C), f))).scalar_one()
            rows = (
                await s.execute(
                    _apply(select(C, Source.name).join(Source, Source.id == C.source_id), f)
                    .order_by(SORT_TS.desc(), C.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return [(r[0], r[1]) for r in rows], total

    async def get_item(self, item_id: uuid.UUID) -> tuple[ContentItem, str] | None:
        async with self._sm() as s:
            row = (
                await s.execute(
                    select(C, Source.name)
                    .join(Source, Source.id == C.source_id)
                    .where(C.id == item_id)
                )
            ).first()
            return (row[0], row[1]) if row else None

    async def list_sources(self, enabled: bool | None) -> list[tuple[Source, int]]:
        counts = select(C.source_id, func.count().label("n")).group_by(C.source_id).subquery()
        stmt = (
            select(Source, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.source_id == Source.id)
            .order_by(Source.name)
        )
        if enabled is not None:
            stmt = stmt.where(Source.enabled == enabled)
        async with self._sm() as s:
            return [(r[0], int(r[1])) for r in (await s.execute(stmt)).all()]

    async def list_runs(
        self,
        source_id: uuid.UUID | None,
        status: JobStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[ResearchJob, str, datetime | None]], int]:
        cond = [J.kind == "ingest"]
        if source_id is not None:
            cond.append(J.source_id == source_id)
        if status is not None:
            cond.append(J.status == status)
        async with self._sm() as s:
            total = (
                await s.execute(select(func.count()).select_from(J).where(and_(*cond)))
            ).scalar_one()
            rows = (
                await s.execute(
                    select(J, Source.name, STARTED_AT)
                    .join(Source, Source.id == J.source_id)
                    .where(and_(*cond))
                    .order_by(J.created_at.desc(), J.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return [(r[0], r[1], r[2]) for r in rows], total

    async def stats(self) -> dict[str, Any]:
        async with self._sm() as s:
            by_type = dict(
                (
                    await s.execute(select(C.content_type, func.count()).group_by(C.content_type))
                ).all()
            )
            last_24h = (
                await s.execute(select(func.count()).where(C.fetched_at >= func.now() - DAY))
            ).scalar_one()
            runs = dict(
                (
                    await s.execute(
                        select(J.status, func.count()).where(J.kind == "ingest").group_by(J.status)
                    )
                ).all()
            )
            src = (
                await s.execute(
                    select(
                        func.count(),
                        func.count().filter(Source.enabled),
                        func.count().filter(Source.last_error.is_not(None)),
                    ).select_from(Source)
                )
            ).one()
            newest = (await s.execute(select(func.max(SORT_TS)))).scalar_one()
        return {
            "total_items": sum(by_type.values()),
            "items_by_type": {t.value: by_type.get(t, 0) for t in ContentType},
            "items_fetched_last_24h": last_24h,
            "newest_item_at": newest,
            "sources_total": src[0],
            "sources_enabled": src[1],
            "sources_with_errors": src[2],
            "ingestion_runs_by_status": {st.value: runs.get(st, 0) for st in JobStatus},
        }
