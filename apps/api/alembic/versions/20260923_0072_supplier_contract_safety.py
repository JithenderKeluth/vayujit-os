"""Complete supplier commercial and verification contract safety."""

import sqlalchemy as sa

from alembic import op

revision = "20260923_0072"
down_revision = "20260922_0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "intelligence_supplier_commercial_terms",
        sa.Column("sample_lead_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_commercial_terms",
        sa.Column("production_lead_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_commercial_terms",
        sa.Column("dispatch_lead_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_verifications",
        sa.Column("idempotency_key", sa.String(180), nullable=True),
    )
    op.create_unique_constraint(
        "uq_supplier_verification_idempotency",
        "intelligence_supplier_verifications",
        ["owner_id", "supplier_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_supplier_verification_idempotency",
        "intelligence_supplier_verifications",
        type_="unique",
    )
    op.drop_column("intelligence_supplier_verifications", "idempotency_key")
    op.drop_column("intelligence_supplier_commercial_terms", "dispatch_lead_days")
    op.drop_column("intelligence_supplier_commercial_terms", "production_lead_days")
    op.drop_column("intelligence_supplier_commercial_terms", "sample_lead_days")
