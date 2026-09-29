"""Add the additive GP-7.5 Product Intelligence profile."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261130_0141"
down_revision = "20261130_0140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_product_opportunities",
        sa.Column(
            "intelligence_profile",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("intelligence_product_opportunities", "intelligence_profile")
