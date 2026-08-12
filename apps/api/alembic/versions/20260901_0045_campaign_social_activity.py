"""Link Social posts to Campaign Activity projections."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_0045"
down_revision: str | None = "20260831_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaign_activities", sa.Column("social_post_id", sa.UUID(), nullable=True))
    op.create_index(
        "ix_campaign_activities_social_post_id", "campaign_activities", ["social_post_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_activities_social_post_id", table_name="campaign_activities")
    op.drop_column("campaign_activities", "social_post_id")
