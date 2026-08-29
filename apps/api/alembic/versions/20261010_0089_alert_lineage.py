"""Persist alert lineage metadata."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261010_0089"
down_revision = "20261009_0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_autonomous_alerts", sa.Column("lineage", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("intelligence_autonomous_alerts", "lineage")
