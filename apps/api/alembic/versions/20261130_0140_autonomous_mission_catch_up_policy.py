"""Add the mission catch-up policy column required by the ORM."""

import sqlalchemy as sa

from alembic import op

revision = "20261130_0140"
down_revision = "20261130_0139"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_autonomous_missions",
        sa.Column("catch_up_policy", sa.String(24), nullable=False, server_default="SKIP"),
    )


def downgrade() -> None:
    op.drop_column("intelligence_autonomous_missions", "catch_up_policy")
