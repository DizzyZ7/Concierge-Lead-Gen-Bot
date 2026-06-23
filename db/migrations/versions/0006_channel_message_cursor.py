from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_channel_message_cursor"
down_revision = "0005_unique_lead_source_post"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("target_channels", sa.Column("last_seen_message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("target_channels", "last_seen_message_id")
