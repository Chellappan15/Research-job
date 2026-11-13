import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


job_status_enum = Enum(
    JobStatus,
    name="job_status",
    values_callable=lambda e: [m.value for m in e],
)


class ResearchJob(Base):
    __tablename__ = "research_jobs"
    __table_args__ = (
        CheckConstraint("length(btrim(topic)) > 0", name="ck_jobs_topic_nonempty"),
        CheckConstraint("worker_version >= 0", name="ck_jobs_worker_version_nonneg"),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count_nonneg"),
        CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts_pos"),
        CheckConstraint(
            "status <> 'running' OR "
            "(assigned_worker_id IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_jobs_running_has_owner",
        ),
        Index(
            "ix_jobs_pending_eligible",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint("kind IN ('research', 'ingest')", name="ck_jobs_kind"),
        CheckConstraint(
            "kind <> 'ingest' OR (source_id IS NOT NULL AND scheduled_for IS NOT NULL)",
            name="ck_jobs_ingest_has_slot",
        ),
        Index(
            "uq_jobs_source_slot",
            "source_id",
            "scheduled_for",
            unique=True,
            postgresql_where=text("kind = 'ingest'"),
        ),
        Index(
            "ix_jobs_ingest_source_created",
            "source_id",
            "created_at",
            postgresql_where=text("kind = 'ingest'"),
        ),
        Index(
            "ix_jobs_running_lease",
            "lease_expires_at",
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, nullable=False, server_default=JobStatus.PENDING.value
    )
    assigned_worker_id: Mapped[str | None] = mapped_column(String(255))
    worker_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default="research")
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE")
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job_id", "job_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchReport(Base):
    __tablename__ = "research_reports"
    __table_args__ = (UniqueConstraint("job_id", name="uq_research_reports_job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchSource(Base):
    __tablename__ = "research_sources"
    __table_args__ = (Index("ix_research_sources_job_id", "job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceType(enum.StrEnum):
    RSS = "rss"
    YOUTUBE = "youtube"
    GITHUB = "github"


class ContentType(enum.StrEnum):
    ARTICLE = "article"
    VIDEO = "video"


source_type_enum = Enum(
    SourceType, name="source_type", values_callable=lambda e: [m.value for m in e]
)
content_type_enum = Enum(
    ContentType, name="content_type", values_callable=lambda e: [m.value for m in e]
)


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_sources_name_nonempty"),
        CheckConstraint("fetch_interval_seconds >= 60", name="ck_sources_interval_min"),
        CheckConstraint(
            "(source_type = 'youtube' AND channel_id IS NOT NULL) "
            "OR (source_type IN ('rss', 'github') AND feed_url IS NOT NULL)",
            name="ck_sources_locator",
        ),
        UniqueConstraint("name", name="uq_sources_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(source_type_enum, nullable=False)
    feed_url: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    fetch_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3600"
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_content_source_external"),
        UniqueConstraint("canonical_url", name="uq_content_canonical_url"),
        CheckConstraint("length(btrim(title)) > 0", name="ck_content_title_nonempty"),
        Index("ix_content_sort", text("coalesce(published_at, fetched_at) DESC"), "id"),
        Index("ix_content_source", "source_id"),
        Index("ix_content_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    content_type: Mapped[ContentType] = mapped_column(content_type_enum, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(summary, '')), 'B')",
            persisted=True,
        ),
        deferred=True,
    )
