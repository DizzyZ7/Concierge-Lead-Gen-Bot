from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_relevance_reason"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parsed_posts", sa.Column("relevance_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("parsed_posts", "relevance_reason")
