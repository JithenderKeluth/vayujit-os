"""Add immutable PR-8A commercial reassessment and HUMAN review records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261010_0151"
down_revision = "20261009_0150"
branch_labels = None
depends_on = None


def _json(default: str = "{}") -> sa.TextClause:
    return sa.text(f"'{default}'::jsonb")


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    js = postgresql.JSONB()
    op.create_table(
        "intelligence_commercial_reassessments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("goal_id", uuid, nullable=True),
        sa.Column("opportunity_id", uuid, nullable=False),
        sa.Column("assessment_id", uuid, nullable=False),
        sa.Column("supplier_id", uuid, nullable=False),
        sa.Column("supplier_product_id", uuid, nullable=False),
        sa.Column("promotion_id", uuid, nullable=False),
        sa.Column("commercial_term_id", uuid, nullable=False),
        sa.Column("baseline_landed_cost_id", uuid, nullable=True),
        sa.Column("baseline_unit_economics_id", uuid, nullable=True),
        sa.Column("current_readiness_id", uuid, nullable=True),
        sa.Column("current_landed_cost_id", uuid, nullable=True),
        sa.Column("current_unit_economics_id", uuid, nullable=True),
        sa.Column("scenario_key", sa.String(120), nullable=False, server_default="reviewed-quote-reassessment"),
        sa.Column("status", sa.String(32), nullable=False, server_default="BLOCKED"),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="NEEDS_HUMAN_REVIEW"),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("quote_version", sa.Integer(), nullable=False),
        sa.Column("quote_evidence", js, nullable=False, server_default=_json()),
        sa.Column("assumptions", js, nullable=False, server_default=_json("[]")),
        sa.Column("baseline", js, nullable=False, server_default=_json()),
        sa.Column("current", js, nullable=False, server_default=_json()),
        sa.Column("comparison", js, nullable=False, server_default=_json()),
        sa.Column("blockers", js, nullable=False, server_default=_json("[]")),
        sa.Column("provenance", js, nullable=False, server_default=_json()),
        sa.Column("lineage", js, nullable=False, server_default=_json()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["intelligence_business_agent_goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["intelligence_product_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["intelligence_product_opportunity_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["intelligence_suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_product_id"], ["intelligence_supplier_products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["promotion_id"], ["intelligence_supplier_response_promotions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commercial_term_id"], ["intelligence_supplier_commercial_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["baseline_landed_cost_id"], ["intelligence_economic_calculations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["baseline_unit_economics_id"], ["intelligence_product_opportunity_unit_economics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_readiness_id"], ["intelligence_commercial_readiness_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_landed_cost_id"], ["intelligence_economic_calculations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_unit_economics_id"], ["intelligence_product_opportunity_unit_economics.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8a_reassessment_idempotency"),
        sa.UniqueConstraint("owner_id", "input_fingerprint", name="uq_pr8a_reassessment_fingerprint"),
    )
    for name, cols in {
        "owner": ["owner_id"], "goal": ["goal_id"], "opportunity": ["opportunity_id"],
        "assessment": ["assessment_id"], "supplier": ["supplier_id"], "product": ["supplier_product_id"],
        "promotion": ["promotion_id"], "term": ["commercial_term_id"], "status": ["status"],
        "fingerprint": ["input_fingerprint"],
    }.items():
        op.create_index(f"ix_pr8a_reassessment_{name}", "intelligence_commercial_reassessments", cols)

    op.create_table(
        "intelligence_commercial_reassessment_reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("owner_id", uuid, nullable=False),
        sa.Column("reassessment_id", uuid, nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False, server_default="HUMAN"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reassessment_id"], ["intelligence_commercial_reassessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_pr8a_review_idempotency"),
        sa.CheckConstraint("decision IN ('ACKNOWLEDGE','KEEP_UNDER_REVIEW')", name="ck_pr8a_review_decision"),
        sa.CheckConstraint("provenance = 'HUMAN'", name="ck_pr8a_review_provenance"),
    )
    op.create_index("ix_pr8a_review_owner", "intelligence_commercial_reassessment_reviews", ["owner_id"])
    op.create_index("ix_pr8a_review_reassessment", "intelligence_commercial_reassessment_reviews", ["reassessment_id"])


def downgrade() -> None:
    op.drop_table("intelligence_commercial_reassessment_reviews")
    op.drop_table("intelligence_commercial_reassessments")
