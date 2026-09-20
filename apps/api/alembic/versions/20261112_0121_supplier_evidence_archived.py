"""Add the missing SupplierEvidence archive state column."""

import sqlalchemy as sa

from alembic import op

revision = "20261112_0121"
down_revision = "20261111_0120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_supplier_evidence",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_intelligence_supplier_evidence_archived",
        "intelligence_supplier_evidence",
        ["archived"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_intelligence_supplier_evidence_archived",
        table_name="intelligence_supplier_evidence",
    )
    op.drop_column("intelligence_supplier_evidence", "archived")
