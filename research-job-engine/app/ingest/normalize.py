"""Turn raw feed entries into one consistent, safe schema. Never invents metadata."""

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models import ContentType, SourceType

MAX_TITLE = 500
MAX_SUMMARY = 2000
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid"}
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizedItem:
    external_id: str
    content_type: ContentType
    title: str
    url: str
    canonical_url: str
    summary: str | None
    thumbnail_url: str | None
    published_at: datetime | None
    fetched_at: datetime


def _http_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    return value


def canonicalize_url(url: str) -> str:
    """Lowercase scheme/host, drop default ports, fragments, tracking params, trailing slash."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    netloc = (
        host
        if port is None or (scheme, port) in (("http", 80), ("https", 443))
        else (f"{host}:{port}")
    )
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    )
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit(
        ("https" if scheme in ("http", "https") else scheme, netloc, path, urlencode(query), "")
    )


def clean_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _published(entry: dict[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=UTC)
            except (TypeError, ValueError):
                continue
    return None


def _thumbnail(entry: dict[str, Any]) -> str | None:
    for key in ("media_thumbnail", "media_content"):
        for media in entry.get(key) or []:
            if isinstance(media, dict) and (
                key == "media_thumbnail" or str(media.get("medium", "")).startswith("image")
            ):
                if url := _http_url(media.get("url")):
                    return url
    for enc in entry.get("enclosures") or []:
        if isinstance(enc, dict) and str(enc.get("type", "")).startswith("image/"):
            if url := _http_url(enc.get("href")):
                return url
    return None


def normalize_entry(
    entry: dict[str, Any], source_type: SourceType, fetched_at: datetime
) -> NormalizedItem | None:
    """Return None for entries that cannot be linked to (no usable URL)."""
    if source_type == SourceType.YOUTUBE:
        video_id = entry.get("yt_videoid")
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
            return None
        url = f"https://www.youtube.com/watch?v={video_id}"
        external_id = f"yt:{video_id}"
        content_type = ContentType.VIDEO
        summary_raw = entry.get("media_description") or entry.get("summary")
        thumbnail = _thumbnail(entry) or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    else:
        url = _http_url(entry.get("link"))
        if url is None:
            return None
        content_type = ContentType.ARTICLE
        summary_raw = entry.get("summary") or entry.get("description")
        thumbnail = _thumbnail(entry)
        raw_id = entry.get("id") or entry.get("guid")
        external_id = (
            str(raw_id).strip()[:1000] if isinstance(raw_id, str) and raw_id.strip() else None
        ) or canonicalize_url(url)

    canonical = canonicalize_url(url)
    title = clean_text(entry.get("title"), MAX_TITLE) or canonical
    return NormalizedItem(
        external_id=external_id,
        content_type=content_type,
        title=title,
        url=url,
        canonical_url=canonical,
        summary=clean_text(summary_raw, MAX_SUMMARY),
        thumbnail_url=thumbnail,
        published_at=_published(entry),
        fetched_at=fetched_at,
    )


def dedupe(items: list[NormalizedItem]) -> list[NormalizedItem]:
    """Drop in-batch duplicates (same external id or canonical URL); first occurrence wins."""
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    out = []
    for item in items:
        if item.external_id in seen_ids or item.canonical_url in seen_urls:
            continue
        seen_ids.add(item.external_id)
        seen_urls.add(item.canonical_url)
        out.append(item)
    return out
