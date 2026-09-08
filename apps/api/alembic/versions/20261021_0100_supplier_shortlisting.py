"""supplier shortlisting and sourcing recommendation ledger"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261021_0100"
down_revision = "20261020_0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    dt = sa.DateTime(timezone=True)

    def owner():
        return sa.Column(
            "owner_id", uid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )

    def ctx():
        return sa.Column(
            "context_id",
            uid,
            sa.ForeignKey("intelligence_supplier_shortlist_contexts.id", ondelete="CASCADE"),
            nullable=False,
        )

    def sup():
        return sa.Column(
            "supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        )

    op.create_table(
        "intelligence_supplier_shortlist_contexts",
        sa.Column("id", uid, primary_key=True),
        owner(),
        sa.Column("product_id", uid),
        sa.Column("opportunity_id", uid),
        sa.Column("requirement_id", uid),
        sa.Column("current_version", sa.Integer, nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("target_market", sa.String(120)),
        sa.Column("budget_currency", sa.String(3)),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_shortlist_context_idempotency"),
    )
    op.create_table(
        "intelligence_supplier_shortlist_context_versions",
        sa.Column("id", uid, primary_key=True),
        owner(),
        ctx(),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint("context_id", "version", name="uq_shortlist_context_version"),
    )
    op.create_table(
        "intelligence_supplier_shortlist_score_versions",
        sa.Column("id", uid, primary_key=True),
        owner(),
        ctx(),
        sup(),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("weights", jsonb, nullable=False),
        sa.Column("dimensions", jsonb, nullable=False),
        sa.Column("score", sa.Numeric(8, 4), nullable=False),
        sa.Column("eligibility", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "supplier_id",
            "model_version",
            name="uq_shortlist_score_version",
        ),
    )
    op.create_table(
        "intelligence_supplier_shortlist_versions",
        sa.Column("id", uid, primary_key=True),
        owner(),
        ctx(),
        sa.Column("context_version", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint("context_id", "version", name="uq_shortlist_version"),
    )
    op.create_table(
        "intelligence_supplier_shortlist_decisions",
        sa.Column("id", uid, primary_key=True),
        owner(),
        ctx(),
        sa.Column(
            "shortlist_version_id",
            uid,
            sa.ForeignKey("intelligence_supplier_shortlist_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sup(),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("decision_key", sa.String(180), nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "supplier_id",
            "decision_key",
            name="uq_shortlist_decision_identity",
        ),
    )
    op.create_table(
        "intelligence_supplier_shortlist_handoffs",
        sa.Column("id", uid, primary_key=True),
        owner(),
        ctx(),
        sup(),
        sa.Column(
            "decision_id",
            uid,
            sa.ForeignKey("intelligence_supplier_shortlist_decisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requirement_id", uid),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "supplier_id", name="uq_shortlist_handoff_identity"
        ),
    )
    op.create_table(
        "intelligence_supplier_shortlist_events",
        sa.Column("id", uid, primary_key=True),
        owner(),
        ctx(),
        sa.Column("supplier_id", uid),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("event_key", sa.String(240), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint("owner_id", "event_key", name="uq_shortlist_event_key"),
    )


def downgrade() -> None:
    for name in (
        "intelligence_supplier_shortlist_events",
        "intelligence_supplier_shortlist_handoffs",
        "intelligence_supplier_shortlist_decisions",
        "intelligence_supplier_shortlist_versions",
        "intelligence_supplier_shortlist_score_versions",
        "intelligence_supplier_shortlist_context_versions",
        "intelligence_supplier_shortlist_contexts",
    ):
        op.drop_table(name)
