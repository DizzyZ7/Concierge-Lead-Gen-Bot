from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_reviewer_claims"
down_revision = "0009_post_action_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_drafts", sa.Column("claimed_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("review_drafts", sa.Column("claimed_by_username", sa.String(length=128), nullable=True))
    op.add_column("review_drafts", sa.Column("claimed_by_name", sa.String(length=256), nullable=True))
    op.add_column("review_drafts", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("review_drafts", sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_review_drafts_claim_expires_at", "review_drafts", ["claim_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_review_drafts_claim_expires_at", table_name="review_drafts")
    op.drop_column("review_drafts", "claim_expires_at")
    op.drop_column("review_drafts", "claimed_at")
    op.drop_column("review_drafts", "claimed_by_name")
    op.drop_column("review_drafts", "claimed_by_username")
    op.drop_column("review_drafts", "claimed_by_user_id")
