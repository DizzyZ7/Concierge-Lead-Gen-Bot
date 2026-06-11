from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_post_analytics_fields"
down_revision = "0002_relevance_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parsed_posts", sa.Column("text_hash", sa.String(length=64), nullable=True))
    op.add_column("parsed_posts", sa.Column("content_summary", sa.Text(), nullable=True))
    op.add_column("parsed_posts", sa.Column("suggested_angle", sa.Text(), nullable=True))
    op.create_index("ix_parsed_posts_text_hash", "parsed_posts", ["text_hash"])


def downgrade() -> None:
    op.drop_index("ix_parsed_posts_text_hash", table_name="parsed_posts")
    op.drop_column("parsed_posts", "suggested_angle")
    op.drop_column("parsed_posts", "content_summary")
    op.drop_column("parsed_posts", "text_hash")
