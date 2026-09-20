"""Add Review Intelligence 11D product gaps and opportunity signals."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261116_0125"
down_revision = "20261115_0124"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def j(name: str, default: str) -> sa.Column:
    return sa.Column(name, JSONB, nullable=False, server_default=sa.text(f"'{default}'::jsonb"))


def upgrade() -> None:
    op.create_table(
        "intelligence_review_product_gap_analyses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "review_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column(
            "product_opportunity_id",
            UUID,
            sa.ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "analysis_version",
            sa.String(40),
            nullable=False,
            server_default="review-gap-analysis-v1",
        ),
        sa.Column(
            "calculation_version",
            sa.String(40),
            nullable=False,
            server_default="review-gap-calculation-v1",
        ),
        sa.Column(
            "rule_version", sa.String(40), nullable=False, server_default="review-gap-rules-v1"
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="COMPLETED"),
        sa.Column("gap_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("signal_count", sa.Integer, nullable=False, server_default="0"),
        j("limitations", "[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_gap_analysis_input"
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED','FAILED')", name="ck_review_gap_analysis_status"
        ),
    )
    op.create_index(
        "ix_review_gap_analysis_context_created",
        "intelligence_review_product_gap_analyses",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_review_gap_analysis_owner",
        "intelligence_review_product_gap_analyses",
        ["owner_id"],
    )
    op.create_index(
        "ix_review_gap_analysis_context",
        "intelligence_review_product_gap_analyses",
        ["context_id"],
    )
    op.create_index(
        "ix_review_gap_analysis_input_fingerprint",
        "intelligence_review_product_gap_analyses",
        ["input_fingerprint"],
    )

    op.create_table(
        "intelligence_review_product_gaps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gap_type", sa.String(40), nullable=False),
        sa.Column("canonical_label", sa.String(120), nullable=False),
        sa.Column("hypothesis", sa.String(500), nullable=False),
        j("source_item_types", "[]"),
        sa.Column(
            "support_classification", sa.String(32), nullable=False, server_default="UNKNOWN"
        ),
        sa.Column("support_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cohort_count", sa.Integer, nullable=False, server_default="0"),
        j("coverage", "{}"),
        j("source_distribution", "{}"),
        j("supporting_review_ids", "[]"),
        j("supporting_evidence_ids", "[]"),
        j("opposing_review_ids", "[]"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("evidence_strength", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="UNKNOWN"),
        j("freshness", "{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="RESEARCH_REQUIRED"),
        j("required_validations", "[]"),
        j("limitations", "[]"),
        sa.Column(
            "rule_version", sa.String(40), nullable=False, server_default="review-gap-rules-v1"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "analysis_id", "gap_type", "canonical_label", name="uq_review_product_gap"
        ),
    )
    op.create_index(
        "ix_review_product_gap_analysis",
        "intelligence_review_product_gaps",
        ["owner_id", "analysis_id"],
    )
    op.create_index(
        "ix_review_product_gap_owner",
        "intelligence_review_product_gaps",
        ["owner_id"],
    )
    op.create_index(
        "ix_review_product_gap_context",
        "intelligence_review_product_gaps",
        ["context_id"],
    )

    op.create_table(
        "intelligence_review_opportunity_signals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "gap_id",
            UUID,
            sa.ForeignKey("intelligence_review_product_gaps.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_type", sa.String(40), nullable=False),
        sa.Column("canonical_label", sa.String(120), nullable=False),
        sa.Column("hypothesis", sa.String(500), nullable=False),
        sa.Column("explanation", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RESEARCH_REQUIRED"),
        sa.Column("evidence_strength", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("support_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cohort_count", sa.Integer, nullable=False, server_default="0"),
        j("coverage", "{}"),
        j("source_distribution", "{}"),
        j("supporting_review_ids", "[]"),
        j("supporting_evidence_ids", "[]"),
        j("opposing_review_ids", "[]"),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="UNKNOWN"),
        j("freshness", "{}"),
        j("required_validations", "[]"),
        j("limitations", "[]"),
        sa.Column(
            "rule_version", sa.String(40), nullable=False, server_default="review-gap-rules-v1"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "analysis_id", "signal_type", "canonical_label", name="uq_review_opportunity_signal"
        ),
    )
    op.create_index(
        "ix_review_opportunity_signal_analysis",
        "intelligence_review_opportunity_signals",
        ["owner_id", "analysis_id"],
    )
    op.create_index(
        "ix_review_opportunity_signal_owner",
        "intelligence_review_opportunity_signals",
        ["owner_id"],
    )
    op.create_index(
        "ix_review_opportunity_signal_context",
        "intelligence_review_opportunity_signals",
        ["context_id"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_review_opportunity_signals")
    op.drop_table("intelligence_review_product_gaps")
    op.drop_table("intelligence_review_product_gap_analyses")
