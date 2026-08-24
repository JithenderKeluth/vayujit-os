"""Add supplier certification and evidence concurrency safeguards."""

import sqlalchemy as sa

from alembic import op

revision = "20260925_0074"
down_revision = "20260924_0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_supplier_evidence",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE intelligence_supplier_evidence "
        "SET updated_at = retrieved_at WHERE updated_at IS NULL"
    )
    op.alter_column("intelligence_supplier_evidence", "updated_at", nullable=False)
    op.create_unique_constraint(
        "uq_supplier_certification_version",
        "intelligence_supplier_certification_claims",
        ["owner_id", "supplier_id", "claim", "version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_supplier_certification_version",
        "intelligence_supplier_certification_claims",
        type_="unique",
    )
    op.drop_column("intelligence_supplier_evidence", "updated_at")
