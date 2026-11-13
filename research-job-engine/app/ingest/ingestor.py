"""Job handler for `kind='ingest'` jobs, used by the existing worker."""

import logging
from datetime import UTC, datetime

from app.ingest.fetchers import FeedFetcher, FetchError
from app.ingest.normalize import NormalizedItem
from app.ingest.repository import IngestRepository
from app.jobs.repository import Lease

log = logging.getLogger(__name__)


class Ingestor:
    def __init__(self, repo: IngestRepository, fetcher: FeedFetcher) -> None:
        self.repo = repo
        self.fetcher = fetcher

    async def fetch(self, lease: Lease) -> list[NormalizedItem]:
        """Read-only network step; safe to repeat after a crash (at-least-once)."""
        if lease.source_id is None:
            raise FetchError("ingest job has no source_id", retryable=False)
        source = await self.repo.get_source(lease.source_id)
        if source is None:
            raise FetchError("source no longer exists", retryable=False)
        if not source.enabled:
            raise FetchError("source is disabled", retryable=False)
        return await self.fetcher.fetch_items(
            source.source_type, source.feed_url, source.channel_id, datetime.now(UTC)
        )

    async def complete(self, lease: Lease, items: list[NormalizedItem]) -> None:
        await self.repo.complete_ingestion(lease, items)

    async def record_failure(self, lease: Lease, error: str) -> None:
        if lease.source_id is not None:
            await self.repo.record_source_error(lease.source_id, error)
