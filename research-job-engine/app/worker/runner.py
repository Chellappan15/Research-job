"""Worker loop: claim -> execute (with heartbeats + checkpoints) -> complete / retry."""

import asyncio
import contextlib
import logging
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.jobs.repository import JobRepository, Lease, LeaseLost, RetryPolicy
from app.research.base import ResearchExecutor

if TYPE_CHECKING:
    from app.ingest.ingestor import Ingestor

log = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        repo: JobRepository,
        executor: ResearchExecutor,
        settings: Settings,
        worker_id: str,
        ingestor: "Ingestor | None" = None,
    ) -> None:
        self.repo = repo
        self.executor = executor
        self.ingestor = ingestor
        self.settings = settings
        self.worker_id = worker_id
        self.policy = RetryPolicy(settings.retry_base_seconds, settings.retry_max_seconds)
        self._tasks: set[asyncio.Task[None]] = set()

    async def run(self, stop: asyncio.Event) -> None:
        """Run until `stop` is set, then stop claiming and release in-flight jobs."""
        log.info(
            "worker started",
            extra={"worker_id": self.worker_id, "concurrency": self.settings.worker_concurrency},
        )
        loop = asyncio.get_running_loop()
        next_recovery = 0.0
        try:
            while not stop.is_set():
                if loop.time() >= next_recovery:
                    await self._safe_db(self.repo.recover_expired(self.policy), "recovery")
                    next_recovery = loop.time() + self.settings.recovery_interval_seconds

                claimed = False
                if len(self._tasks) < self.settings.worker_concurrency:
                    lease = await self._safe_db(
                        self.repo.claim(self.worker_id, self.settings.lease_seconds), "claim"
                    )
                    if lease is not None:
                        claimed = True
                        task = asyncio.create_task(self._run_job(lease))
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)

                if not claimed:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(
                            stop.wait(), timeout=self.settings.poll_interval_seconds
                        )
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        log.info(
            "worker stopping", extra={"worker_id": self.worker_id, "in_flight": len(self._tasks)}
        )
        tasks = list(self._tasks)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("worker stopped", extra={"worker_id": self.worker_id})

    async def _safe_db(self, coro: Any, what: str) -> Any:
        """Run a DB call from the main loop; log (not crash) on transient DB errors."""
        try:
            return await coro
        except (SQLAlchemyError, OSError):
            log.exception("database call failed", extra={"op": what})
            return None

    async def _heartbeat_loop(self, lease: Lease) -> None:
        """Returns only when ownership is lost."""
        while True:
            await asyncio.sleep(self.settings.heartbeat_seconds)
            try:
                ok = await self.repo.heartbeat(lease, self.settings.lease_seconds)
            except (SQLAlchemyError, OSError):
                log.exception("heartbeat failed, will retry", extra={"job_id": str(lease.job_id)})
                continue
            if not ok:
                log.warning(
                    "heartbeat rejected: lease lost",
                    extra={"job_id": str(lease.job_id), "version": lease.version},
                )
                return

    async def _run_job(self, lease: Lease) -> None:
        ctx = {"job_id": str(lease.job_id), "version": lease.version, "attempt": lease.attempt}

        async def save_checkpoint(stage: str, data: dict[str, Any]) -> None:
            await self.repo.save_checkpoint(lease, stage, data, self.settings.lease_seconds)
            log.info("checkpoint saved", extra={**ctx, "stage": stage})

        work: Coroutine[Any, Any, Any]
        if lease.kind == "ingest":
            if self.ingestor is None:
                log.error("no ingestor configured; releasing ingest job", extra=ctx)
                await self.repo.release(lease, "worker cannot run ingest jobs")
                return
            work = self.ingestor.fetch(lease)
        else:
            work = self.executor.run(lease.topic, lease.checkpoint, save_checkpoint)
        exec_task = asyncio.create_task(work)
        hb_task = asyncio.create_task(self._heartbeat_loop(lease))
        try:
            done, _ = await asyncio.wait({exec_task, hb_task}, return_when=asyncio.FIRST_COMPLETED)
            if exec_task not in done:
                # Heartbeat lost ownership: abandon the work, never write results.
                exec_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, LeaseLost):
                    await exec_task
                return
            result = exec_task.result()  # re-raises executor exceptions
            if lease.kind == "ingest" and self.ingestor is not None:
                await self.ingestor.complete(lease, result)
            else:
                await self.repo.complete(lease, result)
        except LeaseLost:
            log.warning("lease lost; abandoning job", extra=ctx)
        except asyncio.CancelledError:
            # Graceful shutdown: stop work and hand the job back.
            exec_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, LeaseLost):
                await exec_task
            with contextlib.suppress(SQLAlchemyError, OSError):
                await asyncio.shield(self.repo.release(lease, "worker shutdown"))
            raise
        except Exception as exc:  # executor failure -> recorded in DB, retried if budget remains
            log.exception("job attempt raised", extra=ctx)
            error = f"{type(exc).__name__}: {exc}"[:2000]
            # Errors may declare retry semantics (e.g. ingest FetchError: 4xx is permanent,
            # 429 carries Retry-After). Anything else is retried with the normal backoff.
            retryable = bool(getattr(exc, "retryable", True))
            min_delay = float(getattr(exc, "retry_after", 0.0) or 0.0)
            try:
                await self.repo.fail_attempt(
                    lease, error, self.policy, retryable=retryable, min_delay_seconds=min_delay
                )
            except LeaseLost:
                log.warning("lease lost before failure could be recorded", extra=ctx)
                return
            if lease.kind == "ingest" and self.ingestor is not None:
                try:
                    await self.ingestor.record_failure(lease, error)
                except (SQLAlchemyError, OSError):
                    log.exception("could not record source error", extra=ctx)
        finally:
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task
