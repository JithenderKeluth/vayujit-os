"""supplier due diligence contexts, evidence gaps, plans and tasks"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261022_0101"
down_revision = "20261021_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    dt = sa.DateTime(timezone=True)

    def owner() -> sa.Column:
        return sa.Column(
            "owner_id", uid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )

    op.create_table(
        "intelligence_supplier_due_diligence_contexts",
        sa.Column("id", uid, primary_key=True),
        owner(),
        sa.Column(
            "supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", uid),
        sa.Column("opportunity_id", uid),
        sa.Column("shortlist_context_id", uid),
        sa.Column("shortlist_version_id", uid),
        sa.Column("recommendation_id", uid),
        sa.Column("requirement_id", uid),
        sa.Column("current_assessment_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_due_diligence_context_idempotency"
        ),
    )
    op.create_table(
        "intelligence_supplier_due_diligence_assessments",
        sa.Column("id", uid, primary_key=True),
        owner(),
        sa.Column(
            "context_id",
            uid,
            sa.ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("readiness", sa.String(32), nullable=False),
        sa.Column("summary", js, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.UniqueConstraint("context_id", "version", name="uq_due_diligence_assessment_version"),
    )
    op.create_table(
        "intelligence_supplier_evidence_gaps",
        sa.Column("id", uid, primary_key=True),
        owner(),
        sa.Column(
            "context_id",
            uid,
            sa.ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", uid),
        sa.Column("assessment_version", sa.Integer, nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("classification", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("required_evidence", js, nullable=False),
        sa.Column("evidence_refs", js, nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("freshness_state", sa.String(24), nullable=False),
        sa.Column("contradiction_state", sa.String(24), nullable=False),
        sa.Column("priority_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("priority_level", sa.String(16), nullable=False),
        sa.Column("resolution_evidence_refs", js, nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.Column("updated_at", dt, nullable=False),
        sa.Column("resolved_at", dt),
        sa.UniqueConstraint(
            "context_id",
            "assessment_version",
            "dimension",
            name="uq_due_diligence_gap_dimension_version",
        ),
    )
    op.create_table(
        "intelligence_supplier_due_diligence_plans",
        sa.Column("id", uid, primary_key=True),
        owner(),
        sa.Column(
            "context_id",
            uid,
            sa.ForeignKey("intelligence_supplier_due_diligence_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            uid,
            sa.ForeignKey("intelligence_cross_marketplace_suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assessment_version", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("priority", sa.Numeric(8, 4), nullable=False),
        sa.Column("budget", js, nullable=False),
        sa.Column("allowed_methods", js, nullable=False),
        sa.Column("prohibited_methods", js, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "assessment_version",
            "idempotency_key",
            name="uq_due_diligence_plan_identity",
        ),
    )
    op.create_table(
        "intelligence_supplier_due_diligence_tasks",
        sa.Column("id", uid, primary_key=True),
        owner(),
        sa.Column(
            "plan_id",
            uid,
            sa.ForeignKey("intelligence_supplier_due_diligence_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "gap_id",
            uid,
            sa.ForeignKey("intelligence_supplier_evidence_gaps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shared_execution_id", uid),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.Numeric(8, 4), nullable=False),
        sa.Column("result", js, nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("created_at", dt, nullable=False),
        sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "plan_id",
            "gap_id",
            "idempotency_key",
            name="uq_due_diligence_task_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("intelligence_supplier_due_diligence_tasks")
    op.drop_table("intelligence_supplier_due_diligence_plans")
    op.drop_table("intelligence_supplier_evidence_gaps")
    op.drop_table("intelligence_supplier_due_diligence_assessments")
    op.drop_table("intelligence_supplier_due_diligence_contexts")
