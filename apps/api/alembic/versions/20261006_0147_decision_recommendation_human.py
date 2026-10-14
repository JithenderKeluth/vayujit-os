"""Add PR-6C recommendation assessments and explicit human decisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261006_0147"
down_revision = "20261006_0146"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_recommendation_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_evidence_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("synthesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_target", sa.String(length=40), nullable=False),
        sa.Column("recommendation_policy_version", sa.String(length=80), nullable=False),
        sa.Column("recommendation_state", sa.String(length=48), nullable=False),
        sa.Column("supporting_reasons", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("counter_reasons", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("unknowns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("contradictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("trust_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("economics_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("capital_fit_state", sa.String(length=24), nullable=False, server_default="UNKNOWN"),
        sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("input_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_cross_marketplace_suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decision_evidence_snapshot_id"], ["intelligence_decision_evidence_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["synthesis_id"], ["intelligence_decision_synthesis_snapshots.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "input_fingerprint", name="uq_recommendation_assessment_fingerprint"),
    )
    op.create_index(
        "ix_recommendation_assessment_context",
        "intelligence_recommendation_assessments",
        ["owner_id", "opportunity_id", "decision_target", "created_at"],
    )
    op.create_table(
        "intelligence_human_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_evidence_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("synthesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supersedes_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_target", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("provenance", sa.String(length=24), nullable=False, server_default="HUMAN"),
        sa.Column("context_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_writes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_cross_marketplace_suppliers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decision_evidence_snapshot_id"], ["intelligence_decision_evidence_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["synthesis_id"], ["intelligence_decision_synthesis_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["intelligence_recommendation_assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_decision_id"], ["intelligence_human_decisions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_human_decision_idempotency"),
    )
    op.create_index(
        "ix_human_decision_context",
        "intelligence_human_decisions",
        ["owner_id", "opportunity_id", "decision_target", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_human_decision_context", table_name="intelligence_human_decisions")
    op.drop_table("intelligence_human_decisions")
    op.drop_index(
        "ix_recommendation_assessment_context",
        table_name="intelligence_recommendation_assessments",
    )
    op.drop_table("intelligence_recommendation_assessments")
