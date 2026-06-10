from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "target_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_username", sa.Text(), nullable=False, unique=True),
        sa.Column("channel_title", sa.Text(), nullable=True),
        sa.Column("geo", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("daily_draft_limit", sa.Integer(), server_default="5", nullable=False),
        sa.Column("review_delay_min", sa.Integer(), server_default="3", nullable=False),
        sa.Column("review_delay_max", sa.Integer(), server_default="15", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "parsed_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("target_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tg_message_id", sa.BigInteger(), nullable=False),
        sa.Column("post_text", sa.Text(), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("intent", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel_id", "tg_message_id", name="uq_parsed_post_channel_message"),
    )
    op.create_table(
        "review_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("parsed_posts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("draft_source", sa.Text(), server_default="ai", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to_reviewer_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_message_id", sa.BigInteger(), nullable=True),
        sa.Column("marked_done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("tg_username", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("source_post_id", sa.Integer(), sa.ForeignKey("parsed_posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("geo", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="new", nullable=False),
        sa.Column("deal_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "draft_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("geo", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_table(
        "daily_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), server_default=sa.func.current_date(), nullable=False),
        sa.Column("posts_parsed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("drafts_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reviewer_done", sa.Integer(), server_default="0", nullable=False),
        sa.Column("leads_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deals_closed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revenue", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("ai_drafts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("template_drafts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ai_failures", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("date", name="uq_daily_stats_date"),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("daily_stats")
    op.drop_table("draft_templates")
    op.drop_table("leads")
    op.drop_table("review_drafts")
    op.drop_table("parsed_posts")
    op.drop_table("target_channels")
