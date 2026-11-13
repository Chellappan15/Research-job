"""HTTP fetching + feed parsing for RSS/Atom, GitHub Atom and YouTube channel feeds."""

import asyncio
import email.utils
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urlsplit

import feedparser
import httpx

from app.ingest.normalize import NormalizedItem, dedupe, normalize_entry
from app.models import SourceType

log = logging.getLogger(__name__)

YOUTUBE_FEED = "https://www.youtube.com/feeds/videos.xml"
MAX_RETRY_AFTER_SECONDS = 3600
ACCEPT_HEADER = "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.5"
_ACCEPTED_TYPES = ("xml", "rss", "atom", "text/plain", "text/html")


class FetchError(Exception):
    """A source could not be fetched/parsed. `retryable` and `retry_after` drive the job retry."""

    def __init__(self, message: str, *, retryable: bool, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def feed_url_for(source_type: SourceType, feed_url: str | None, channel_id: str | None) -> str:
    if source_type == SourceType.YOUTUBE:
        if not channel_id:
            raise FetchError("youtube source has no channel_id", retryable=False)
        return f"{YOUTUBE_FEED}?{urlencode({'channel_id': channel_id})}"
    if not feed_url:
        raise FetchError(f"{source_type.value} source has no feed_url", retryable=False)
    return feed_url


def parse_retry_after(value: str | None) -> float:
    if not value:
        return 0.0
    value = value.strip()
    if value.isdigit():
        seconds = float(value)
    else:
        try:
            when = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return 0.0
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    return max(0.0, min(seconds, MAX_RETRY_AFTER_SECONDS))


class FeedFetcher:
    """Shared HTTP client with timeouts, a response-size cap and per-host concurrency limits."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_bytes: int = 5_000_000,
        per_host_concurrency: int = 2,
    ) -> None:
        self.client = client
        self.max_bytes = max_bytes
        self._host_limits: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(per_host_concurrency)
        )

    @classmethod
    def create(cls, timeout_seconds: float, user_agent: str, **kw: Any) -> "FeedFetcher":
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0)),
            follow_redirects=True,
            max_redirects=5,
            headers={
                "User-Agent": user_agent,
                "Accept": ACCEPT_HEADER,
            },
        )
        return cls(client, **kw)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def get_bytes(self, url: str) -> bytes:
        host = urlsplit(url).hostname or ""
        async with self._host_limits[host]:
            try:
                async with self.client.stream("GET", url) as resp:
                    self._check_status(resp)
                    ctype = resp.headers.get("content-type", "").lower()
                    if ctype and not any(t in ctype for t in _ACCEPTED_TYPES):
                        raise FetchError(f"unexpected content-type {ctype!r}", retryable=False)
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in resp.aiter_bytes():
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise FetchError(
                                f"response larger than {self.max_bytes} bytes", retryable=False
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.TimeoutException as exc:
                raise FetchError(
                    f"timeout fetching {url}: {type(exc).__name__}", retryable=True
                ) from exc
            except httpx.TransportError as exc:
                raise FetchError(f"network error fetching {url}: {exc}", retryable=True) from exc

    @staticmethod
    def _check_status(resp: httpx.Response) -> None:
        code = resp.status_code
        if code < 400:
            return
        if code in (429, 503):
            raise FetchError(
                f"rate limited / unavailable (HTTP {code})",
                retryable=True,
                retry_after=parse_retry_after(resp.headers.get("retry-after")),
            )
        if code >= 500 or code == 408:
            raise FetchError(f"server error (HTTP {code})", retryable=True)
        raise FetchError(f"client error (HTTP {code})", retryable=False)

    async def fetch_items(
        self,
        source_type: SourceType,
        feed_url: str | None,
        channel_id: str | None,
        fetched_at: datetime,
    ) -> list[NormalizedItem]:
        url = feed_url_for(source_type, feed_url, channel_id)
        body = await self.get_bytes(url)
        # feedparser is CPU-bound; keep the event loop (and heartbeats) responsive.
        return await asyncio.to_thread(parse_feed, body, source_type, fetched_at)


def parse_feed(body: bytes, source_type: SourceType, fetched_at: datetime) -> list[NormalizedItem]:
    parsed = feedparser.parse(body)
    entries = parsed.get("entries") or []
    if parsed.get("bozo") and not entries:
        exc = parsed.get("bozo_exception")
        raise FetchError(f"unparseable feed: {exc}", retryable=False)
    items = []
    skipped = 0
    for entry in entries:
        item = normalize_entry(entry, source_type, fetched_at)
        if item is None:
            skipped += 1
        else:
            items.append(item)
    if skipped:
        log.info("skipped feed entries without usable URL", extra={"skipped": skipped})
    return dedupe(items)
