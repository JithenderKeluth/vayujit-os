"""Persist exact Social identity on Campaign Activity projections."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260902_0046"
down_revision: str | None = "20260901_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaign_activities", sa.Column("social_platform", sa.String(length=24), nullable=True)
    )
    op.add_column("campaign_activities", sa.Column("social_account_id", sa.UUID(), nullable=True))
    op.add_column(
        "campaign_activities", sa.Column("social_content_type", sa.String(length=48), nullable=True)
    )
    op.add_column(
        "campaign_activities",
        sa.Column("social_media_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "campaign_activities",
        sa.Column("social_timezone_name", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_campaign_activities_social_platform", "campaign_activities", ["social_platform"]
    )
    op.create_index(
        "ix_campaign_activities_social_account_id", "campaign_activities", ["social_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_activities_social_account_id", table_name="campaign_activities")
    op.drop_index("ix_campaign_activities_social_platform", table_name="campaign_activities")
    op.drop_column("campaign_activities", "social_timezone_name")
    op.drop_column("campaign_activities", "social_media_ids")
    op.drop_column("campaign_activities", "social_content_type")
    op.drop_column("campaign_activities", "social_account_id")
    op.drop_column("campaign_activities", "social_platform")
