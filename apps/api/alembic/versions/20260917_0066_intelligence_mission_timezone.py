"""Persist Intelligence mission timezone for durable scheduling."""

import sqlalchemy as sa

from alembic import op

revision = "20260917_0066"
down_revision = "20260916_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_research_missions",
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    op.drop_column("intelligence_research_missions", "timezone")
