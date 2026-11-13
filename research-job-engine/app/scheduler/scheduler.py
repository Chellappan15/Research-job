"""Enqueue ingestion jobs for due sources. Never runs ingestion itself.

A source's slot is `floor(epoch(now) / interval) * interval`. The partial unique index
`uq_jobs_source_slot (source_id, scheduled_for) WHERE kind = 'ingest'` makes enqueueing
idempotent, so any number of scheduler instances can run concurrently.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = logging.getLogger(__name__)

_ENQUEUE_SQL = text(
    """
    WITH clock AS (SELECT coalesce(CAST(:now AS timestamptz), now()) AS ts),
    due AS (
        SELECT s.id, s.name,
               to_timestamp(
                   floor(extract(epoch FROM clock.ts) / s.fetch_interval_seconds)
                   * s.fetch_interval_seconds
               ) AS slot
        FROM sources s, clock
        WHERE s.enabled
          -- don't pile up slots while a previous run is still queued or running
          AND NOT EXISTS (
              SELECT 1 FROM research_jobs j
              WHERE j.kind = 'ingest' AND j.source_id = s.id
                AND j.status IN ('pending', 'running')
          )
    ),
    inserted AS (
        INSERT INTO research_jobs (id, kind, topic, source_id, scheduled_for, max_attempts)
        SELECT gen_random_uuid(), 'ingest', 'ingest: ' || due.name, due.id, due.slot,
               :max_attempts
        FROM due
        ON CONFLICT (source_id, scheduled_for) WHERE kind = 'ingest' DO NOTHING
        RETURNING id, source_id, scheduled_for
    ),
    events AS (
        INSERT INTO job_events (job_id, event_type, payload)
        SELECT id, 'scheduled',
               jsonb_build_object('source_id', source_id, 'scheduled_for', scheduled_for)
        FROM inserted
    )
    SELECT id, source_id, scheduled_for FROM inserted
    """
)


@dataclass(frozen=True)
class ScheduledJob:
    job_id: str
    source_id: str
    scheduled_for: datetime


class Scheduler:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], max_attempts: int) -> None:
        self._sm = sessionmaker
        self.max_attempts = max_attempts

    async def enqueue_due(self, now: datetime | None = None) -> list[ScheduledJob]:
        """One idempotent statement; `now` is only overridden in tests (default: DB clock)."""
        async with self._sm.begin() as s:
            rows = (
                await s.execute(_ENQUEUE_SQL, {"now": now, "max_attempts": self.max_attempts})
            ).all()
        jobs = [ScheduledJob(str(r.id), str(r.source_id), r.scheduled_for) for r in rows]
        if jobs:
            log.info("scheduled ingestion jobs", extra={"count": len(jobs)})
        return jobs
