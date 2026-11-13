"""Standalone worker process: `python -m app.worker.main`."""

import asyncio
import logging
import os
import signal
import socket
import uuid

from app.config import get_settings
from app.db import make_engine, make_sessionmaker
from app.ingest.fetchers import FeedFetcher
from app.ingest.ingestor import Ingestor
from app.ingest.repository import IngestRepository
from app.jobs.repository import JobRepository
from app.logging import configure_logging
from app.research.mock import MockResearchExecutor
from app.worker.runner import Worker

log = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    fetcher = FeedFetcher.create(
        settings.fetch_timeout_seconds,
        settings.http_user_agent,
        max_bytes=settings.fetch_max_bytes,
        per_host_concurrency=settings.fetch_per_host_concurrency,
    )
    worker = Worker(
        JobRepository(sessionmaker),
        MockResearchExecutor(settings.mock_stage_delay_seconds),
        settings,
        worker_id,
        ingestor=Ingestor(IngestRepository(sessionmaker), fetcher),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows: Ctrl+C raises KeyboardInterrupt instead
            pass
    try:
        await worker.run(stop)
    finally:
        await fetcher.aclose()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
