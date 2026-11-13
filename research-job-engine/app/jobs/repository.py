"""All job state transitions. Each public method is exactly one database transaction.

Ownership-sensitive writes are fenced: they only touch a row when
    status = 'running' AND assigned_worker_id = :worker AND worker_version = :version
    AND lease_expires_at > now()
`now()` is the database clock, so worker clock skew never affects lease decisions.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, case, func, insert, literal, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    JobEvent,
    JobStatus,
    ResearchJob,
    ResearchReport,
    ResearchSource,
    job_status_enum,
)
from app.research.base import ResearchResult

log = logging.getLogger(__name__)

J = ResearchJob


class LeaseLost(Exception):
    """This worker no longer owns the job (lease expired or job re-claimed)."""

    def __init__(self, job_id: uuid.UUID, version: int) -> None:
        super().__init__(f"lease lost for job {job_id} (version {version})")
        self.job_id = job_id
        self.version = version


@dataclass(frozen=True)
class Lease:
    job_id: uuid.UUID
    worker_id: str
    version: int
    attempt: int
    max_attempts: int
    topic: str
    checkpoint: dict[str, Any] | None
    kind: str = "research"
    source_id: uuid.UUID | None = None
    scheduled_for: datetime | None = None


@dataclass(frozen=True)
class RetryPolicy:
    base_seconds: float
    max_seconds: float

    def delay(self, attempt: int) -> float:
        """Bounded exponential backoff: base * 2^(attempt-1), capped at max."""
        return min(self.base_seconds * (2 ** max(attempt - 1, 0)), self.max_seconds)


def _secs(seconds: float | ColumnElement[Any]) -> ColumnElement[Any]:
    return func.make_interval(0, 0, 0, 0, 0, 0, seconds)


def _backoff_sql(policy: RetryPolicy) -> ColumnElement[Any]:
    """Same formula as RetryPolicy.delay, evaluated per row in SQL (used by recovery)."""
    raw = literal(policy.base_seconds) * func.power(2, func.greatest(J.attempt_count - 1, 0))
    return _secs(func.least(raw, literal(policy.max_seconds)))


def _owned_by(lease: Lease) -> ColumnElement[bool]:
    return and_(
        J.id == lease.job_id,
        J.status == JobStatus.RUNNING,
        J.assigned_worker_id == lease.worker_id,
        J.worker_version == lease.version,
        J.lease_expires_at > func.now(),
    )


async def _event(
    session: AsyncSession, job_id: uuid.UUID, event_type: str, payload: dict[str, Any]
) -> None:
    await session.execute(
        insert(JobEvent).values(job_id=job_id, event_type=event_type, payload=payload)
    )


class JobRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = sessionmaker

    # ---------- API side ----------

    async def create_job(self, topic: str, max_attempts: int) -> ResearchJob:
        async with self._sm.begin() as s:
            job = ResearchJob(id=uuid.uuid4(), topic=topic, max_attempts=max_attempts)
            s.add(job)
            await s.flush()
            await _event(s, job.id, "created", {"topic": topic})
        async with self._sm() as s:
            return await s.get_one(ResearchJob, job.id)

    async def get_job(self, job_id: uuid.UUID) -> tuple[ResearchJob, bool] | None:
        """Return (job, report_available) or None."""
        async with self._sm() as s:
            row = (
                await s.execute(
                    select(J, ResearchReport.id.is_not(None))
                    .outerjoin(ResearchReport, ResearchReport.job_id == J.id)
                    .where(J.id == job_id)
                )
            ).first()
            return (row[0], bool(row[1])) if row else None

    async def get_report(
        self, job_id: uuid.UUID
    ) -> tuple[ResearchReport, list[ResearchSource]] | None:
        async with self._sm() as s:
            report = (
                await s.execute(select(ResearchReport).where(ResearchReport.job_id == job_id))
            ).scalar_one_or_none()
            if report is None:
                return None
            sources = (
                await s.execute(
                    select(ResearchSource)
                    .where(ResearchSource.job_id == job_id)
                    .order_by(ResearchSource.created_at, ResearchSource.url)
                )
            ).scalars()
            return report, list(sources)

    # ---------- worker side ----------

    async def claim(self, worker_id: str, lease_seconds: float) -> Lease | None:
        """Atomically claim the oldest eligible pending job (FOR UPDATE SKIP LOCKED)."""
        eligible = (
            select(J.id)
            .where(
                J.status == JobStatus.PENDING,
                J.next_attempt_at <= func.now(),
                J.attempt_count < J.max_attempts,
            )
            .order_by(J.next_attempt_at, J.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(J)
            .where(J.id == eligible)
            .values(
                status=JobStatus.RUNNING,
                assigned_worker_id=worker_id,
                worker_version=J.worker_version + 1,
                attempt_count=J.attempt_count + 1,
                lease_expires_at=func.now() + _secs(lease_seconds),
                updated_at=func.now(),
            )
            .returning(
                J.id,
                J.worker_version,
                J.attempt_count,
                J.max_attempts,
                J.topic,
                J.checkpoint,
                J.kind,
                J.source_id,
                J.scheduled_for,
            )
        )
        async with self._sm.begin() as s:
            row = (await s.execute(stmt)).first()
            if row is None:
                return None
            lease = Lease(
                job_id=row.id,
                worker_id=worker_id,
                version=row.worker_version,
                attempt=row.attempt_count,
                max_attempts=row.max_attempts,
                topic=row.topic,
                checkpoint=row.checkpoint,
                kind=row.kind,
                source_id=row.source_id,
                scheduled_for=row.scheduled_for,
            )
            await _event(
                s,
                lease.job_id,
                "claimed",
                {"worker_id": worker_id, "version": lease.version, "attempt": lease.attempt},
            )
        log.info(
            "job claimed",
            extra={
                "job_id": str(lease.job_id),
                "version": lease.version,
                "attempt": lease.attempt,
                "worker_id": worker_id,
            },
        )
        return lease

    async def heartbeat(self, lease: Lease, lease_seconds: float) -> bool:
        """Extend the lease. False means ownership is lost and work must stop."""
        stmt = (
            update(J)
            .where(_owned_by(lease))
            .values(lease_expires_at=func.now() + _secs(lease_seconds), updated_at=func.now())
            .returning(J.id)
        )
        async with self._sm.begin() as s:
            return (await s.execute(stmt)).first() is not None

    async def save_checkpoint(
        self, lease: Lease, stage: str, data: dict[str, Any], lease_seconds: float
    ) -> None:
        """Persist a stage checkpoint (also extends the lease). Raises LeaseLost."""
        stmt = (
            update(J)
            .where(_owned_by(lease))
            .values(
                checkpoint={"stage": stage, "data": data},
                lease_expires_at=func.now() + _secs(lease_seconds),
                updated_at=func.now(),
            )
            .returning(J.id)
        )
        async with self._sm.begin() as s:
            if (await s.execute(stmt)).first() is None:
                raise LeaseLost(lease.job_id, lease.version)
            await _event(s, lease.job_id, "checkpoint", {"stage": stage, "version": lease.version})

    async def complete(self, lease: Lease, result: ResearchResult) -> None:
        """Lock + validate ownership, insert report + sources, mark completed. Raises LeaseLost."""
        async with self._sm.begin() as s:
            locked = (
                await s.execute(select(J.id).where(_owned_by(lease)).with_for_update())
            ).first()
            if locked is None:
                raise LeaseLost(lease.job_id, lease.version)
            await s.execute(
                insert(ResearchReport).values(
                    id=uuid.uuid4(), job_id=lease.job_id, content=result.content
                )
            )
            if result.sources:
                await s.execute(
                    insert(ResearchSource),
                    [
                        {
                            "id": uuid.uuid4(),
                            "job_id": lease.job_id,
                            "url": src.url,
                            "title": src.title,
                        }
                        for src in result.sources
                    ],
                )
            await s.execute(
                update(J)
                .where(J.id == lease.job_id)
                .values(
                    status=JobStatus.COMPLETED,
                    assigned_worker_id=None,
                    lease_expires_at=None,
                    last_error=None,
                    checkpoint=func.jsonb_set(
                        func.coalesce(J.checkpoint, text("'{}'::jsonb")),
                        text("'{stage}'"),
                        text("'\"completed\"'::jsonb"),
                    ),
                    completed_at=func.now(),
                    updated_at=func.now(),
                )
            )
            await _event(
                s,
                lease.job_id,
                "completed",
                {"version": lease.version, "sources": len(result.sources)},
            )
        log.info("job completed", extra={"job_id": str(lease.job_id), "version": lease.version})

    async def fail_attempt(
        self,
        lease: Lease,
        error: str,
        policy: RetryPolicy,
        retryable: bool = True,
        min_delay_seconds: float = 0.0,
    ) -> JobStatus:
        """Record a failed attempt: back to pending with backoff, or failed. Raises LeaseLost."""
        exhausted = (not retryable) or lease.attempt >= lease.max_attempts
        new_status = JobStatus.FAILED if exhausted else JobStatus.PENDING
        values: dict[str, Any] = {
            "status": new_status,
            "assigned_worker_id": None,
            "lease_expires_at": None,
            "last_error": error,
            "updated_at": func.now(),
        }
        if not exhausted:
            delay = max(policy.delay(lease.attempt), min_delay_seconds)  # e.g. Retry-After
            values["next_attempt_at"] = func.now() + _secs(delay)
        async with self._sm.begin() as s:
            row = (
                await s.execute(update(J).where(_owned_by(lease)).values(**values).returning(J.id))
            ).first()
            if row is None:
                raise LeaseLost(lease.job_id, lease.version)
            await _event(
                s,
                lease.job_id,
                "failed" if exhausted else "retry_scheduled",
                {"version": lease.version, "attempt": lease.attempt, "error": error},
            )
        log.warning(
            "job attempt failed",
            extra={
                "job_id": str(lease.job_id),
                "attempt": lease.attempt,
                "new_status": new_status.value,
                "error": error,
            },
        )
        return new_status

    async def release(self, lease: Lease, reason: str) -> bool:
        """Graceful shutdown: hand the job back immediately without spending an attempt.

        Returns False if ownership was already lost (nothing to release).
        """
        stmt = (
            update(J)
            .where(_owned_by(lease))
            .values(
                status=JobStatus.PENDING,
                assigned_worker_id=None,
                lease_expires_at=None,
                attempt_count=func.greatest(J.attempt_count - 1, 0),
                next_attempt_at=func.now(),
                updated_at=func.now(),
            )
            .returning(J.id)
        )
        async with self._sm.begin() as s:
            if (await s.execute(stmt)).first() is None:
                return False
            await _event(s, lease.job_id, "released", {"version": lease.version, "reason": reason})
        log.info("job released", extra={"job_id": str(lease.job_id), "reason": reason})
        return True

    async def recover_expired(self, policy: RetryPolicy, limit: int = 100) -> int:
        """Return expired running jobs to pending (with backoff) or fail them if out of attempts.

        Safe to run concurrently from many processes: rows are locked with SKIP LOCKED and
        the expiry predicate is re-checked against the locked row.
        """
        expired = (
            select(J.id)
            .where(J.status == JobStatus.RUNNING, J.lease_expires_at <= func.now())
            .order_by(J.lease_expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        exhausted = J.attempt_count >= J.max_attempts
        stmt = (
            update(J)
            .where(
                J.id.in_(expired), J.status == JobStatus.RUNNING, J.lease_expires_at <= func.now()
            )
            .values(
                status=case(
                    (exhausted, literal(JobStatus.FAILED, job_status_enum)),
                    else_=literal(JobStatus.PENDING, job_status_enum),
                ),
                next_attempt_at=case(
                    (exhausted, J.next_attempt_at), else_=func.now() + _backoff_sql(policy)
                ),
                last_error=func.concat(
                    "lease expired (worker ",
                    J.assigned_worker_id,
                    ", attempt ",
                    J.attempt_count,
                    ")",
                ),
                assigned_worker_id=None,
                lease_expires_at=None,
                updated_at=func.now(),
            )
            .returning(J.id, J.status, J.attempt_count, J.worker_version)
        )
        async with self._sm.begin() as s:
            rows = (await s.execute(stmt)).all()
            for r in rows:
                await _event(
                    s,
                    r.id,
                    "lease_expired",
                    {
                        "version": r.worker_version,
                        "attempt": r.attempt_count,
                        "new_status": r.status.value,
                    },
                )
        if rows:
            log.warning("recovered expired leases", extra={"count": len(rows)})
        return len(rows)
