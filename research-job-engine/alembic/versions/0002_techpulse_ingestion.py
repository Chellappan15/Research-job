"""TechPulse ingestion: sources, content_items, ingest job kind + scheduling slot

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_type = postgresql.ENUM("rss", "youtube", "github", name="source_type", create_type=False)
content_type = postgresql.ENUM("article", "video", name="content_type", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    source_type.create(bind, checkfirst=True)
    content_type.create(bind, checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("feed_url", sa.Text()),
        sa.Column("channel_id", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fetch_interval_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_sources_name_nonempty"),
        sa.CheckConstraint("fetch_interval_seconds >= 60", name="ck_sources_interval_min"),
        sa.CheckConstraint(
            "(source_type = 'youtube' AND channel_id IS NOT NULL) "
            "OR (source_type IN ('rss', 'github') AND feed_url IS NOT NULL)",
            name="ck_sources_locator",
        ),
        sa.UniqueConstraint("name", name="uq_sources_name"),
    )

    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_type", content_type, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("source_id", "external_id", name="uq_content_source_external"),
        sa.UniqueConstraint("canonical_url", name="uq_content_canonical_url"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_content_title_nonempty"),
    )
    op.create_index(
        "ix_content_sort",
        "content_items",
        [sa.text("coalesce(published_at, fetched_at) DESC"), "id"],
    )
    op.create_index("ix_content_source", "content_items", ["source_id"])

    op.add_column(
        "research_jobs",
        sa.Column("kind", sa.String(32), nullable=False, server_default="research"),
    )
    op.add_column(
        "research_jobs",
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
        ),
    )
    op.add_column("research_jobs", sa.Column("scheduled_for", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_jobs_kind", "research_jobs", "kind IN ('research', 'ingest')")
    op.create_check_constraint(
        "ck_jobs_ingest_has_slot",
        "research_jobs",
        "kind <> 'ingest' OR (source_id IS NOT NULL AND scheduled_for IS NOT NULL)",
    )
    op.create_index(
        "uq_jobs_source_slot",
        "research_jobs",
        ["source_id", "scheduled_for"],
        unique=True,
        postgresql_where=sa.text("kind = 'ingest'"),
    )
    op.create_index(
        "ix_jobs_ingest_source_created",
        "research_jobs",
        ["source_id", "created_at"],
        postgresql_where=sa.text("kind = 'ingest'"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_ingest_source_created", table_name="research_jobs")
    op.drop_index("uq_jobs_source_slot", table_name="research_jobs")
    op.drop_constraint("ck_jobs_ingest_has_slot", "research_jobs", type_="check")
    op.drop_constraint("ck_jobs_kind", "research_jobs", type_="check")
    op.drop_column("research_jobs", "scheduled_for")
    op.drop_column("research_jobs", "source_id")
    op.drop_column("research_jobs", "kind")
    op.drop_table("content_items")
    op.drop_table("sources")
    content_type.drop(op.get_bind(), checkfirst=True)
    source_type.drop(op.get_bind(), checkfirst=True)
