"""Add durable metadata to website claims."""

import sqlalchemy as sa

from alembic import op

revision = "20261008_0087"
down_revision = "20261007_0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_website_claims",
        sa.Column("source_reference", sa.String(1000), nullable=False, server_default=""),
    )
    op.add_column(
        "intelligence_website_claims",
        sa.Column("freshness", sa.String(24), nullable=False, server_default="FRESH"),
    )
    op.add_column(
        "intelligence_website_claims",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "intelligence_website_claims",
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_website_claims",
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_website_claims", sa.Column("current_observation_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_website_claim_observation",
        "intelligence_website_claims",
        "intelligence_website_observations",
        ["current_observation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_website_claim_observation", "intelligence_website_claims", type_="foreignkey"
    )
    for column in (
        "current_observation_id",
        "last_seen",
        "first_seen",
        "confidence",
        "freshness",
        "source_reference",
    ):
        op.drop_column("intelligence_website_claims", column)
