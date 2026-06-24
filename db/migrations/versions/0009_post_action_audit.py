from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_post_action_audit"
down_revision = "0008_channel_validation_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("parsed_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("previous_status", sa.Text(), nullable=True),
        sa.Column("new_status", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_username", sa.String(length=128), nullable=True),
        sa.Column("actor_name", sa.String(length=256), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_post_actions_post_id", "post_actions", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_post_actions_post_id", table_name="post_actions")
    op.drop_table("post_actions")
