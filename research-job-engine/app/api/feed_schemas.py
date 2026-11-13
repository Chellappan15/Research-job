import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import ContentType, JobStatus, SourceType


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class FeedItemOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    type: ContentType
    title: str
    url: str
    summary: str | None
    thumbnail_url: str | None
    published_at: datetime | None
    fetched_at: datetime
    external_id: str


class SourceOut(BaseModel):
    id: uuid.UUID
    name: str
    source_type: SourceType
    feed_url: str | None
    channel_id: str | None
    enabled: bool
    fetch_interval_seconds: int
    last_success_at: datetime | None
    last_error: str | None
    item_count: int


class IngestionRunOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    status: JobStatus
    scheduled_for: datetime
    attempt_count: int
    max_attempts: int
    items_seen: int | None
    items_inserted: int | None
    last_error: str | None
    next_attempt_at: datetime
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class StatsOut(BaseModel):
    total_items: int
    items_by_type: dict[str, int]
    items_fetched_last_24h: int
    newest_item_at: datetime | None
    sources_total: int
    sources_enabled: int
    sources_with_errors: int
    ingestion_runs_by_status: dict[str, int]
