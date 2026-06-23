from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_lead_activity_timestamp"
down_revision = "0006_channel_message_cursor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("leads", "updated_at")
