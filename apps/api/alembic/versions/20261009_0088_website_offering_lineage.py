"""Complete durable website offering lineage."""

import sqlalchemy as sa

from alembic import op

revision = "20261009_0088"
down_revision = "20261008_0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "intelligence_website_offerings"
    op.add_column(table, sa.Column("source_profile_id", sa.UUID(), nullable=True))
    op.add_column(
        table, sa.Column("observation_ids", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(table, sa.Column("research_candidate_id", sa.UUID(), nullable=True))
    op.add_column(
        table, sa.Column("correlation_id", sa.String(80), nullable=False, server_default="")
    )
    op.create_foreign_key(
        "fk_website_offering_source_profile",
        table,
        "intelligence_website_source_profiles",
        ["source_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    table = "intelligence_website_offerings"
    op.drop_constraint("fk_website_offering_source_profile", table, type_="foreignkey")
    for column in (
        "correlation_id",
        "research_candidate_id",
        "observation_ids",
        "source_profile_id",
    ):
        op.drop_column(table, column)
