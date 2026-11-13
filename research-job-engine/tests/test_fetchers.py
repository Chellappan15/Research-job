from datetime import UTC, datetime

import httpx
import pytest

from app.ingest.fetchers import FeedFetcher, FetchError, feed_url_for, parse_retry_after
from app.models import SourceType
from tests import feeds

NOW = datetime(2026, 11, 13, tzinfo=UTC)


def fetcher_for(handler, **kw) -> FeedFetcher:
    return FeedFetcher(httpx.AsyncClient(transport=httpx.MockTransport(handler)), **kw)


async def test_fetch_and_parse_rss() -> None:
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(
            200, content=feeds.RSS, headers={"content-type": "application/rss+xml"}
        )

    items = await fetcher_for(handler).fetch_items(
        SourceType.RSS, "https://news.example.com/feed", None, NOW
    )
    assert len(items) == 3 and seen == ["https://news.example.com/feed"]


async def test_youtube_uses_channel_feed() -> None:
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url)
        return httpx.Response(200, content=feeds.YOUTUBE, headers={"content-type": "text/xml"})

    items = await fetcher_for(handler).fetch_items(
        SourceType.YOUTUBE, None, "UCaaaaaaaaaaaaaaaaaaaaaa", NOW
    )
    assert len(items) == 2
    assert seen[0].host == "www.youtube.com" and seen[0].path == "/feeds/videos.xml"
    assert seen[0].params["channel_id"] == "UCaaaaaaaaaaaaaaaaaaaaaa"


@pytest.mark.parametrize(
    ("status", "headers", "retryable", "retry_after"),
    [
        (429, {"retry-after": "120"}, True, 120),
        (503, {}, True, 0),
        (500, {}, True, 0),
        (404, {}, False, 0),
        (410, {}, False, 0),
        (403, {}, False, 0),
    ],
)
async def test_http_errors_classified(status, headers, retryable, retry_after) -> None:
    f = fetcher_for(lambda req: httpx.Response(status, headers=headers))
    with pytest.raises(FetchError) as err:
        await f.get_bytes("https://x.example/feed")
    assert err.value.retryable is retryable
    assert err.value.retry_after == retry_after


async def test_timeout_and_network_errors_are_retryable() -> None:
    def timeout(req):
        raise httpx.ReadTimeout("slow", request=req)

    def refused(req):
        raise httpx.ConnectError("refused", request=req)

    for handler in (timeout, refused):
        with pytest.raises(FetchError) as err:
            await fetcher_for(handler).get_bytes("https://x.example/feed")
        assert err.value.retryable is True


async def test_response_size_and_content_type_limits() -> None:
    big = fetcher_for(
        lambda req: httpx.Response(200, content=b"x" * 5000, headers={"content-type": "text/xml"}),
        max_bytes=1024,
    )
    with pytest.raises(FetchError, match="larger than"):
        await big.get_bytes("https://x.example/feed")

    binary = fetcher_for(
        lambda req: httpx.Response(200, content=b"PK", headers={"content-type": "application/zip"})
    )
    with pytest.raises(FetchError, match="content-type"):
        await binary.get_bytes("https://x.example/feed")


def test_retry_after_parsing() -> None:
    assert parse_retry_after("30") == 30
    assert parse_retry_after(None) == 0
    assert parse_retry_after("garbage") == 0
    assert parse_retry_after("999999") == 3600  # capped
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0  # in the past


def test_missing_locator_is_permanent() -> None:
    with pytest.raises(FetchError) as err:
        feed_url_for(SourceType.YOUTUBE, None, None)
    assert err.value.retryable is False
