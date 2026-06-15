from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_channel_filters"
down_revision = "0003_post_analytics_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("target_channels", sa.Column("min_score", sa.Numeric(4, 2), nullable=True))
    op.add_column("target_channels", sa.Column("allowed_intents", sa.Text(), nullable=True))
    op.add_column("target_channels", sa.Column("blocked_keywords", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("target_channels", "blocked_keywords")
    op.drop_column("target_channels", "allowed_intents")
    op.drop_column("target_channels", "min_score")
