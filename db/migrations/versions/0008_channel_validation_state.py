from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_channel_validation_state"
down_revision = "0007_lead_activity_timestamp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "target_channels",
        sa.Column("last_validation_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "target_channels",
        sa.Column("last_validation_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("target_channels", "last_validation_error")
    op.drop_column("target_channels", "last_validation_at")
