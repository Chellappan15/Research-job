"""content full-text search: generated tsvector column + GIN index

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Weighted: title (A) ranks above summary (B). Generated, so writers never maintain it.
    op.execute(
        """
        ALTER TABLE content_items ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A')
            || setweight(to_tsvector('english', coalesce(summary, '')), 'B')
        ) STORED
        """
    )
    op.create_index("ix_content_search", "content_items", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_content_search", table_name="content_items")
    op.drop_column("content_items", "search_vector")
