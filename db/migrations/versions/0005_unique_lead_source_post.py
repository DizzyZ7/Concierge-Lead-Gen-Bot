from __future__ import annotations

from alembic import op

revision = "0005_unique_lead_source_post"
down_revision = "0004_channel_filters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_leads_source_post_id", "leads", ["source_post_id"])


def downgrade() -> None:
    op.drop_constraint("uq_leads_source_post_id", "leads", type_="unique")
