"""Complete local Supplier Intelligence closure persistence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260922_0071"
down_revision = "20260921_0070"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.add_column(
        "intelligence_supplier_searches",
        sa.Column("provider_execution_id", sa.String(180), nullable=True),
    )
    op.create_unique_constraint(
        "uq_supplier_search_provider_execution",
        "intelligence_supplier_searches",
        ["provider_execution_id"],
    )
    op.add_column(
        "intelligence_supplier_searches", sa.Column("lease_token", sa.String(180), nullable=True)
    )
    op.add_column(
        "intelligence_supplier_searches",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_searches",
        sa.Column("checkpoint_state", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "intelligence_supplier_decisions",
        sa.Column("idempotency_key", sa.String(180), nullable=True),
    )
    op.create_unique_constraint(
        "uq_supplier_decision_idempotency",
        "intelligence_supplier_decisions",
        ["owner_id", "idempotency_key"],
    )
    op.add_column(
        "intelligence_supplier_contacts",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "intelligence_supplier_contacts",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_commercial_terms",
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "intelligence_supplier_commercial_terms",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "intelligence_supplier_certification_claims",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "intelligence_supplier_certification_claims",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "intelligence_supplier_document_references",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reference_id", sa.String(180), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("content_hash", sa.String(128)),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "supplier_id", "reference_id", name="uq_supplier_document_ref"
        ),
    )
    op.create_table(
        "intelligence_supplier_history",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "supplier_id",
            UUID,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "intelligence_supplier_recovery",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "search_id",
            UUID,
            sa.ForeignKey("intelligence_supplier_searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="accepted"),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_supplier_recovery_idempotency"),
    )


def downgrade() -> None:
    op.drop_table("intelligence_supplier_recovery")
    op.drop_table("intelligence_supplier_history")
    op.drop_table("intelligence_supplier_document_references")
    op.drop_column("intelligence_supplier_certification_claims", "is_current")
    op.drop_column("intelligence_supplier_certification_claims", "version")
    op.drop_column("intelligence_supplier_commercial_terms", "is_current")
    op.drop_column("intelligence_supplier_commercial_terms", "lead_time_days")
    op.drop_column("intelligence_supplier_contacts", "updated_at")
    op.drop_column("intelligence_supplier_contacts", "archived")
    op.drop_constraint(
        "uq_supplier_decision_idempotency", "intelligence_supplier_decisions", type_="unique"
    )
    op.drop_column("intelligence_supplier_decisions", "idempotency_key")
    op.drop_column("intelligence_supplier_searches", "checkpoint_state")
    op.drop_column("intelligence_supplier_searches", "lease_expires_at")
    op.drop_column("intelligence_supplier_searches", "lease_token")
    op.drop_constraint(
        "uq_supplier_search_provider_execution", "intelligence_supplier_searches", type_="unique"
    )
    op.drop_column("intelligence_supplier_searches", "provider_execution_id")
