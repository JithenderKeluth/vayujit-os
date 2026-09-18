"""Create immutable 9F Winning Product scores and human decisions."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261105_0114"
down_revision = "20261104_0113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intelligence_product_opportunity_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scoring_model_version", sa.String(80), nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("profile_version", sa.String(80), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("upstream_lineage", postgresql.JSONB, nullable=False),
        sa.Column("eligibility", sa.String(32), nullable=False),
        sa.Column("overall_score", sa.Numeric(8, 3), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("decision_label", sa.String(48), nullable=False),
        sa.Column("confidence", sa.String(24), nullable=False),
        sa.Column("risk_level", sa.String(24), nullable=False),
        sa.Column("assessment_readiness", sa.String(32), nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False),
        sa.Column("dimensions", postgresql.JSONB, nullable=False),
        sa.Column("unavailable_dimensions", postgresql.JSONB, nullable=False),
        sa.Column("risk_adjustments", postgresql.JSONB, nullable=False),
        sa.Column("positive_drivers", postgresql.JSONB, nullable=False),
        sa.Column("negative_drivers", postgresql.JSONB, nullable=False),
        sa.Column("improvement_areas", postgresql.JSONB, nullable=False),
        sa.Column("sensitivity", postgresql.JSONB, nullable=False),
        sa.Column("comparability", postgresql.JSONB, nullable=False),
        sa.Column("weights", postgresql.JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "assessment_id",
            "scoring_model_version",
            "profile_version",
            name="uq_product_opportunity_score_logical",
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_score_idempotency"
        ),
    )
    op.create_index(
        "ix_intelligence_product_opportunity_scores_owner_id",
        "intelligence_product_opportunity_scores",
        ["owner_id"],
    )
    op.create_index(
        "ix_intelligence_product_opportunity_scores_assessment_id",
        "intelligence_product_opportunity_scores",
        ["assessment_id"],
    )
    op.create_table(
        "intelligence_product_opportunity_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "score_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_product_opportunity_scores.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.String(220), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_decision_idempotency"
        ),
    )
    op.create_index(
        "ix_intelligence_product_opportunity_decisions_owner_id",
        "intelligence_product_opportunity_decisions",
        ["owner_id"],
    )
    op.create_index(
        "ix_intelligence_product_opportunity_decisions_assessment_id",
        "intelligence_product_opportunity_decisions",
        ["assessment_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_product_opportunity_decisions")
    op.drop_table("intelligence_product_opportunity_scores")
