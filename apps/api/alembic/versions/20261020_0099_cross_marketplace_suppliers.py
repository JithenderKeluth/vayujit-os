"""add provider-independent cross-marketplace supplier projection"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261020_0099"
down_revision = "20261019_0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    op.create_table(
        "intelligence_cross_marketplace_suppliers",
        sa.Column("id", uid, primary_key=True),
        sa.Column("owner_id", uid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_key", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("identity_state", sa.String(24), nullable=False),
        sa.Column("aliases", jsonb, nullable=False),
        sa.Column("view_json", jsonb, nullable=False),
        sa.Column("confidence_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("source_diversity_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("freshness_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "canonical_key", name="uq_cross_marketplace_supplier_key"),
    )
    op.create_index(
        "ix_cross_marketplace_suppliers_owner_id",
        "intelligence_cross_marketplace_suppliers",
        ["owner_id"],
    )
    op.create_index(
        "ix_cross_marketplace_suppliers_canonical_key",
        "intelligence_cross_marketplace_suppliers",
        ["canonical_key"],
    )
    op.create_index(
        "ix_cross_marketplace_suppliers_identity_state",
        "intelligence_cross_marketplace_suppliers",
        ["identity_state"],
    )
    op.create_index(
        "ix_cross_marketplace_suppliers_updated_at",
        "intelligence_cross_marketplace_suppliers",
        ["updated_at"],
    )

    op.create_table(
        "intelligence_cross_marketplace_supplier_links",
        sa.Column("id", uid, primary_key=True),
        sa.Column("owner_id", uid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "canonical_supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            uid,
            sa.ForeignKey("intelligence_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_state", sa.String(24), nullable=False),
        sa.Column("rationale", sa.String(500), nullable=False),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canonical_supplier_id", "supplier_id", name="uq_cross_supplier_link"),
    )
    op.create_index(
        "ix_cross_marketplace_supplier_links_owner_id",
        "intelligence_cross_marketplace_supplier_links",
        ["owner_id"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_links_canonical_supplier_id",
        "intelligence_cross_marketplace_supplier_links",
        ["canonical_supplier_id"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_links_supplier_id",
        "intelligence_cross_marketplace_supplier_links",
        ["supplier_id"],
    )

    op.create_table(
        "intelligence_cross_marketplace_supplier_evaluations",
        sa.Column("id", uid, primary_key=True),
        sa.Column("owner_id", uid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "canonical_supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("weights", jsonb, nullable=False),
        sa.Column("dimensions", jsonb, nullable=False),
        sa.Column("explanation", jsonb, nullable=False),
        sa.Column("final_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "canonical_supplier_id",
            "model_version",
            "idempotency_key",
            name="uq_cross_supplier_evaluation_idempotency",
        ),
    )
    op.create_index(
        "ix_cross_marketplace_supplier_evaluations_owner_id",
        "intelligence_cross_marketplace_supplier_evaluations",
        ["owner_id"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_evaluations_canonical_supplier_id",
        "intelligence_cross_marketplace_supplier_evaluations",
        ["canonical_supplier_id"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_evaluations_created_at",
        "intelligence_cross_marketplace_supplier_evaluations",
        ["created_at"],
    )

    op.create_table(
        "intelligence_cross_marketplace_supplier_events",
        sa.Column("id", uid, primary_key=True),
        sa.Column("owner_id", uid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "canonical_supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("event_key", sa.String(240), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "event_key", name="uq_cross_supplier_event_key"),
    )
    op.create_index(
        "ix_cross_marketplace_supplier_events_owner_id",
        "intelligence_cross_marketplace_supplier_events",
        ["owner_id"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_events_canonical_supplier_id",
        "intelligence_cross_marketplace_supplier_events",
        ["canonical_supplier_id"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_events_event_type",
        "intelligence_cross_marketplace_supplier_events",
        ["event_type"],
    )
    op.create_index(
        "ix_cross_marketplace_supplier_events_created_at",
        "intelligence_cross_marketplace_supplier_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_cross_marketplace_supplier_events")
    op.drop_table("intelligence_cross_marketplace_supplier_evaluations")
    op.drop_table("intelligence_cross_marketplace_supplier_links")
    op.drop_table("intelligence_cross_marketplace_suppliers")
