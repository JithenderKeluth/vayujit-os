"""Add durable Campaign replacement and checkpoint release metadata.

Revision ID: 20260810_0020
Revises: 20260808_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0020"
down_revision: str | None = "20260808_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaign_activities",
        sa.Column("replaces_activity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "campaign_activities",
        sa.Column("replaced_by_activity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "campaign_activities", sa.Column("replacement_reason", sa.String(500), nullable=True)
    )
    op.add_column(
        "campaign_activities",
        sa.Column("replacement_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaign_activities",
        sa.Column("released_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "campaign_activities",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_campaign_activity_replaces",
        "campaign_activities",
        "campaign_activities",
        ["replaces_activity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_campaign_activity_replaced_by",
        "campaign_activities",
        "campaign_activities",
        ["replaced_by_activity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_campaign_activity_released_by",
        "campaign_activities",
        "users",
        ["released_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_campaign_activities_replaces_activity_id",
        "campaign_activities",
        ["replaces_activity_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_activities_replaces_activity_id", table_name="campaign_activities")
    op.drop_constraint(
        "fk_campaign_activity_released_by", "campaign_activities", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_campaign_activity_replaced_by", "campaign_activities", type_="foreignkey"
    )
    op.drop_constraint("fk_campaign_activity_replaces", "campaign_activities", type_="foreignkey")
    op.drop_column("campaign_activities", "released_at")
    op.drop_column("campaign_activities", "released_by")
    op.drop_column("campaign_activities", "replacement_created_at")
    op.drop_column("campaign_activities", "replacement_reason")
    op.drop_column("campaign_activities", "replaced_by_activity_id")
    op.drop_column("campaign_activities", "replaces_activity_id")
