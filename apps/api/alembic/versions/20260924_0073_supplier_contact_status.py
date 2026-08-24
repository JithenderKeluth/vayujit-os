"""Persist supplier contact communication status."""

import sqlalchemy as sa

from alembic import op

revision = "20260924_0073"
down_revision = "20260923_0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_supplier_contacts",
        sa.Column(
            "communication_status", sa.String(32), nullable=False, server_default="not_contacted"
        ),
    )
    op.alter_column("intelligence_supplier_contacts", "communication_status", server_default=None)


def downgrade() -> None:
    op.drop_column("intelligence_supplier_contacts", "communication_status")
