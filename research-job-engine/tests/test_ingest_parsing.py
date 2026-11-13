from datetime import UTC, datetime

import pytest

from app.ingest.fetchers import FetchError, parse_feed
from app.ingest.normalize import canonicalize_url, clean_text
from app.models import ContentType, SourceType
from tests import feeds

NOW = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)


def test_rss_parsing_and_normalization() -> None:
    items = parse_feed(feeds.RSS, SourceType.RSS, NOW)
    by_id = {i.external_id: i for i in items}
    # no-link and javascript: entries skipped; tracking-URL duplicate dropped
    assert len(items) == 3
    first = by_id["post-1"]
    assert first.content_type == ContentType.ARTICLE
    assert first.title == "New open model released"  # HTML stripped
    assert first.summary == "A new open-weights model."
    assert first.canonical_url == "https://news.example.com/posts/open-model?id=7"
    assert first.thumbnail_url == "https://news.example.com/img/1.jpg"
    assert first.published_at == datetime(2026, 11, 11, 9, 30, tzinfo=UTC)
    assert first.fetched_at == NOW


def test_missing_metadata_handled_safely() -> None:
    items = parse_feed(feeds.RSS, SourceType.RSS, NOW)
    no_date = next(i for i in items if i.title == "No date, no guid")
    assert no_date.published_at is None  # never fabricated
    assert no_date.summary is None and no_date.thumbnail_url is None
    assert no_date.external_id == "https://news.example.com/posts/no-date"  # falls back to URL
    untitled = next(i for i in items if i.external_id == "post-3")
    assert untitled.title == "https://news.example.com/posts/untitled"


def test_github_atom_releases() -> None:
    (item,) = parse_feed(feeds.ATOM_GITHUB, SourceType.GITHUB, NOW)
    assert item.title == "v5.0.0"
    assert item.url == "https://github.com/acme/transformers/releases/tag/v5.0.0"
    assert item.published_at == datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    assert item.summary == "Major release"


def test_youtube_feed_parsing() -> None:
    items = parse_feed(feeds.YOUTUBE, SourceType.YOUTUBE, NOW)
    assert [i.external_id for i in items] == ["yt:abcDEF12345", "yt:zzzZZZ99999"]
    v = items[0]
    assert v.content_type == ContentType.VIDEO
    assert v.url == "https://www.youtube.com/watch?v=abcDEF12345"
    assert v.summary == "Attention, explained."
    assert v.thumbnail_url == "https://i1.ytimg.com/vi/abcDEF12345/hqdefault.jpg"
    assert v.published_at == datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
    assert items[1].thumbnail_url == "https://i.ytimg.com/vi/zzzZZZ99999/hqdefault.jpg"
    assert items[1].summary is None


def test_unparseable_feed_is_permanent_error() -> None:
    with pytest.raises(FetchError) as err:
        parse_feed(feeds.NOT_A_FEED, SourceType.RSS, NOW)
    assert err.value.retryable is False


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        (
            "HTTP://WWW.Example.COM:80/a/b/?utm_source=x&b=2&a=1#frag",
            "https://example.com/a/b?a=1&b=2",
        ),
        ("https://example.com", "https://example.com/"),
        ("https://example.com:8443/x?fbclid=1", "https://example.com:8443/x"),
    ],
)
def test_canonicalize_url(raw: str, canonical: str) -> None:
    assert canonicalize_url(raw) == canonical


def test_clean_text_truncates() -> None:
    assert clean_text("<p>" + "a" * 50 + "</p>", 10) == "a" * 9 + "…"
    assert clean_text("   ", 10) is None
    assert clean_text(None, 10) is None
