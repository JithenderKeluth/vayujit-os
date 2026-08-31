# ruff: noqa: E501
"""Add canonical marketplace lineage projections."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261014_0093"
down_revision = "20261013_0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketplace_executions", sa.Column("lineage", postgresql.JSONB(), nullable=True))
    op.add_column(
        "marketplace_executions", sa.Column("counters", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "marketplace_executions", sa.Column("provider_payload", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("marketplace_executions", "counters")
    op.drop_column("marketplace_executions", "provider_payload")
    op.drop_column("marketplace_executions", "lineage")
