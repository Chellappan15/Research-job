"""Scheduler process: `python -m app.scheduler.main`. Safe to run multiple instances."""

import asyncio
import contextlib
import logging
import signal

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import make_engine, make_sessionmaker
from app.logging import configure_logging
from app.scheduler.scheduler import Scheduler

log = logging.getLogger(__name__)


async def run(scheduler: Scheduler, poll_seconds: float, stop: asyncio.Event) -> None:
    log.info("scheduler started", extra={"poll_seconds": poll_seconds})
    while not stop.is_set():
        try:
            await scheduler.enqueue_due()
        except (SQLAlchemyError, OSError):
            log.exception("scheduling pass failed; will retry")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
    log.info("scheduler stopped")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows
            loop.add_signal_handler(sig, stop.set)
    try:
        await run(
            Scheduler(make_sessionmaker(engine), settings.ingest_max_attempts),
            settings.scheduler_poll_seconds,
            stop,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
