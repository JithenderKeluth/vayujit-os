"""Add immutable PR-6A decision evidence/readiness snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261006_0145"
down_revision = "20261006_0144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_decision_evidence_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shortlist_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_diligence_context_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_diligence_assessment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("commercial_readiness_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("landed_cost_calculation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_economics_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_target", sa.String(length=40), nullable=False),
        sa.Column("decision_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("input_references", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trust_environment", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("blockers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("unknowns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("contradictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("freshness_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("readiness_state", sa.String(length=24), nullable=False),
        sa.Column("safe_next_action", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_decision_id"], ["intelligence_product_opportunity_decisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_cross_marketplace_suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shortlist_decision_id"], ["intelligence_supplier_shortlist_decisions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["due_diligence_context_id"], ["intelligence_supplier_due_diligence_contexts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["due_diligence_assessment_id"], ["intelligence_supplier_due_diligence_assessments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["commercial_readiness_snapshot_id"], ["intelligence_commercial_readiness_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["landed_cost_calculation_id"], ["intelligence_economic_calculations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unit_economics_id"], ["intelligence_product_opportunity_unit_economics.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "input_fingerprint", name="uq_decision_evidence_fingerprint"),
    )
    op.create_index(
        "ix_decision_evidence_context",
        "intelligence_decision_evidence_snapshots",
        ["owner_id", "opportunity_id", "decision_target", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_decision_evidence_context", table_name="intelligence_decision_evidence_snapshots")
    op.drop_table("intelligence_decision_evidence_snapshots")
