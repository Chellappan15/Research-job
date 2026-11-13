"""Ingestion persistence. Completion is fenced exactly like research completion."""

import logging
import uuid
from dataclasses import asdict

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingest.normalize import NormalizedItem
from app.jobs.repository import Lease, LeaseLost, _event, _owned_by
from app.models import ContentItem, JobStatus, ResearchJob, Source

log = logging.getLogger(__name__)


class IngestRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = sessionmaker

    async def get_source(self, source_id: uuid.UUID) -> Source | None:
        async with self._sm() as s:
            return await s.get(Source, source_id)

    async def complete_ingestion(self, lease: Lease, items: list[NormalizedItem]) -> int:
        """One transaction: validate ownership, insert new items (dedup by constraints),
        mark source fetched and job completed. Returns number of newly inserted items."""
        if lease.source_id is None:
            raise ValueError("ingest lease without source_id")
        async with self._sm.begin() as s:
            locked = (
                await s.execute(select(ResearchJob.id).where(_owned_by(lease)).with_for_update())
            ).first()
            if locked is None:
                raise LeaseLost(lease.job_id, lease.version)
            inserted = 0
            if items:
                rows = [
                    {**asdict(item), "id": uuid.uuid4(), "source_id": lease.source_id}
                    for item in items
                ]
                result = await s.execute(
                    pg_insert(ContentItem)
                    .values(rows)
                    .on_conflict_do_nothing()
                    .returning(ContentItem.id)
                )
                inserted = len(result.all())
            await s.execute(
                update(Source)
                .where(Source.id == lease.source_id)
                .values(last_success_at=func.now(), last_error=None, updated_at=func.now())
            )
            await s.execute(
                update(ResearchJob)
                .where(ResearchJob.id == lease.job_id)
                .values(
                    status=JobStatus.COMPLETED,
                    assigned_worker_id=None,
                    lease_expires_at=None,
                    last_error=None,
                    checkpoint={
                        "stage": "completed",
                        "items_seen": len(items),
                        "items_inserted": inserted,
                    },
                    completed_at=func.now(),
                    updated_at=func.now(),
                )
            )
            await _event(
                s,
                lease.job_id,
                "ingested",
                {"version": lease.version, "items_seen": len(items), "items_inserted": inserted},
            )
        log.info(
            "ingestion completed",
            extra={
                "job_id": str(lease.job_id),
                "source_id": str(lease.source_id),
                "seen": len(items),
                "inserted": inserted,
            },
        )
        return inserted

    async def record_source_error(self, source_id: uuid.UUID, error: str) -> None:
        """Informational only (does not affect job state), so it is not fenced."""
        async with self._sm.begin() as s:
            await s.execute(
                update(Source)
                .where(Source.id == source_id)
                .values(last_error=error[:2000], updated_at=func.now())
            )
