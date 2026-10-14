"""Add immutable PR-8C procurement-readiness assessments and HUMAN acknowledgements."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20261012_0153"
down_revision = "20261011_0152"
branch_labels = None
depends_on = None


def _json(default: str = "{}") -> sa.TextClause:
    return sa.text(f"'{default}'::jsonb")


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    op.create_table(
        "intelligence_supplier_procurement_readiness_assessments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=False),
        sa.Column("assessment_id", uuid, nullable=False),
        sa.Column("canonical_supplier_id", uuid, nullable=False),
        sa.Column("supplier_id", uuid, nullable=True),
        sa.Column("supplier_product_id", uuid, nullable=True),
        sa.Column("shortlist_context_id", uuid, nullable=True),
        sa.Column("shortlist_version_id", uuid, nullable=True),
        sa.Column("shortlist_decision_id", uuid, nullable=True),
        sa.Column("due_diligence_context_id", uuid, nullable=True),
        sa.Column("commercial_readiness_id", uuid, nullable=True),
        sa.Column("reassessment_id", uuid, nullable=True),
        sa.Column("comparison_id", uuid, nullable=True),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEEDS_EVIDENCE"),
        sa.Column("policy_version", sa.String(80), nullable=False, server_default="pr8c-readiness-v1"),
        sa.Column("calculation_versions", js, nullable=False, server_default=_json("[]")),
        sa.Column("dimensions", js, nullable=False, server_default=_json()),
        sa.Column("blockers", js, nullable=False, server_default=_json("[]")),
        sa.Column("unknowns", js, nullable=False, server_default=_json("[]")),
        sa.Column("contradictions", js, nullable=False, server_default=_json("[]")),
        sa.Column("evidence_lineage", js, nullable=False, server_default=_json()),
        sa.Column("provenance", js, nullable=False, server_default=_json()),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("actor_provenance", sa.String(16), nullable=False, server_default="HUMAN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["intelligence_product_opportunity_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["canonical_supplier_id"], ["intelligence_cross_marketplace_suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_product_id"], ["intelligence_supplier_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shortlist_context_id"], ["intelligence_supplier_shortlist_contexts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shortlist_version_id"], ["intelligence_supplier_shortlist_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shortlist_decision_id"], ["intelligence_supplier_shortlist_decisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["due_diligence_context_id"], ["intelligence_supplier_due_diligence_contexts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["commercial_readiness_id"], ["intelligence_commercial_readiness_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reassessment_id"], ["intelligence_commercial_reassessments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["comparison_id"], ["intelligence_supplier_comparison_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr8c_assessment_fingerprint"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8c_assessment_idempotency"),
    )
    for name, cols in {
        "owner": ["owner_id"],
        "goal": ["goal_id"],
        "opportunity": ["opportunity_id"],
        "assessment": ["assessment_id"],
        "canonical_supplier": ["canonical_supplier_id"],
        "supplier": ["supplier_id"],
        "supplier_product": ["supplier_product_id"],
        "shortlist_context": ["shortlist_context_id"],
        "shortlist_version": ["shortlist_version_id"],
        "shortlist_decision": ["shortlist_decision_id"],
        "due_context": ["due_diligence_context_id"],
        "commercial": ["commercial_readiness_id"],
        "reassessment": ["reassessment_id"],
        "comparison": ["comparison_id"],
        "fingerprint": ["input_fingerprint"],
        "status": ["status"],
    }.items():
        op.create_index(f"ix_pr8c_assessment_{name}", "intelligence_supplier_procurement_readiness_assessments", cols)

    op.create_table(
        "intelligence_supplier_procurement_readiness_acknowledgements",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("assessment_id", uuid, nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False, server_default="HUMAN"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("assessment_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["intelligence_supplier_procurement_readiness_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8c_ack_idempotency"),
    )
    op.create_index("ix_pr8c_ack_assessment", "intelligence_supplier_procurement_readiness_acknowledgements", ["owner_id", "assessment_id"])


def downgrade() -> None:
    op.drop_index("ix_pr8c_ack_assessment", table_name="intelligence_supplier_procurement_readiness_acknowledgements")
    op.drop_table("intelligence_supplier_procurement_readiness_acknowledgements")
    for name in (
        "owner", "goal", "opportunity", "assessment", "canonical_supplier", "supplier",
        "supplier_product", "shortlist_context", "shortlist_version", "shortlist_decision",
        "due_context", "commercial", "reassessment", "comparison", "fingerprint", "status",
    ):
        op.drop_index(f"ix_pr8c_assessment_{name}", table_name="intelligence_supplier_procurement_readiness_assessments")
    op.drop_table("intelligence_supplier_procurement_readiness_assessments")

