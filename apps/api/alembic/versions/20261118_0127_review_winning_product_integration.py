"""Add the 11F immutable Review-to-Winning-Product projection."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261118_0127"
down_revision = "20261117_0126"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def j(name: str, default: str) -> sa.Column:
    return sa.Column(name, JSONB, nullable=False, server_default=sa.text(f"'{default}'::jsonb"))


def upgrade() -> None:
    op.create_table(
        "intelligence_review_winning_product_projections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            UUID,
            sa.ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_review_snapshots.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_analyses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "gap_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "change_comparison_id",
            UUID,
            sa.ForeignKey("intelligence_review_change_comparisons.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "contract_version",
            sa.String(120),
            nullable=False,
            server_default="review-winning-product-v1",
        ),
        sa.Column(
            "calculation_version",
            sa.String(120),
            nullable=False,
            server_default="review-winning-product-calculation-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "readiness", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column(
            "source_state", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        j("cohort", "{}"),
        j("rating_evidence", "{}"),
        j("feedback_evidence", "{}"),
        j("gap_evidence", "[]"),
        j("change_evidence", "{}"),
        j("research_gaps", "[]"),
        j("freshness", "{}"),
        j("contradictions", "[]"),
        j("evidence_lineage", "{}"),
        j("limitations", "[]"),
        j("projection", "{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "input_fingerprint",
            name="uq_review_winning_projection_fingerprint",
        ),
        sa.CheckConstraint(
            (
                "readiness IN ('AVAILABLE','PARTIAL','INSUFFICIENT_EVIDENCE','"
                "STALE','CONTRADICTORY','RESEARCH_REQUIRED')"
            ),
            name="ck_review_winning_projection_readiness",
        ),
    )
    op.create_index(
        "ix_review_winning_projection_owner",
        "intelligence_review_winning_product_projections",
        ["owner_id"],
    )
    op.create_index(
        "ix_review_winning_projection_opportunity",
        "intelligence_review_winning_product_projections",
        ["owner_id", "opportunity_id", "created_at"],
    )
    op.create_index(
        "ix_review_winning_projection_context",
        "intelligence_review_winning_product_projections",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_review_winning_projection_input",
        "intelligence_review_winning_product_projections",
        ["input_fingerprint"],
    )
    op.create_index(
        "ix_review_winning_projection_readiness",
        "intelligence_review_winning_product_projections",
        ["readiness"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_review_winning_product_projections")
