"""Add Review Intelligence 11E change comparisons and events."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261117_0126"
down_revision = "20261116_0125"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def j(name: str, default: str) -> sa.Column:
    return sa.Column(name, JSONB, nullable=False, server_default=sa.text(f"'{default}'::jsonb"))


def upgrade() -> None:
    op.create_table(
        "intelligence_review_change_comparisons",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "baseline_snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_review_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "baseline_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "baseline_gap_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "current_gap_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="SET NULL"),
        ),
        sa.Column("comparison_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "calculation_version",
            sa.String(80),
            nullable=False,
            server_default="review-change-calculation-v1",
        ),
        sa.Column(
            "materiality_version",
            sa.String(80),
            nullable=False,
            server_default="review-change-materiality-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        j("summary", "{}"),
        j("limitations", "[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_review_change_comparison_input"
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED','PARTIALLY_COMPLETED','FAILED')",
            name="ck_review_change_comparison_status",
        ),
    )
    op.create_index(
        "ix_review_change_comparison_owner", "intelligence_review_change_comparisons", ["owner_id"]
    )
    op.create_index(
        "ix_review_change_comparison_context",
        "intelligence_review_change_comparisons",
        ["owner_id", "context_id", "created_at"],
    )

    op.create_table(
        "intelligence_review_change_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_review_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "comparison_id",
            UUID,
            sa.ForeignKey("intelligence_review_change_comparisons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(48), nullable=False, server_default="REVIEW_ANALYSIS"),
        sa.Column("subject_key", sa.String(180), nullable=False),
        sa.Column(
            "observed_or_derived",
            sa.String(40),
            nullable=False,
            server_default="DERIVED_SEMANTIC_CHANGE",
        ),
        j("baseline_value", "null"),
        j("current_value", "null"),
        sa.Column("absolute_delta", sa.Numeric(18, 8)),
        sa.Column("relative_delta", sa.Numeric(18, 8)),
        sa.Column("baseline_support", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_support", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("baseline_cohort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_cohort", sa.Integer(), nullable=False, server_default="0"),
        j("baseline_evidence", "{}"),
        j("current_evidence", "{}"),
        j("source_distribution", "{}"),
        j("freshness", "{}"),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("materiality", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "materiality_version",
            sa.String(80),
            nullable=False,
            server_default="review-change-materiality-v1",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("alert_eligibility", sa.String(16), nullable=False, server_default="NO_ALERT"),
        sa.Column("alert_reason", sa.String(300), nullable=False, server_default=""),
        j("research_gaps", "[]"),
        j("limitations", "[]"),
        sa.Column("explanation", sa.String(1200), nullable=False, server_default=""),
        j("supporting_review_ids", "[]"),
        j("supporting_evidence_ids", "[]"),
        sa.Column("event_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "rule_version",
            sa.String(80),
            nullable=False,
            server_default="review-change-calculation-v1",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "event_fingerprint", name="uq_review_change_event_fingerprint"
        ),
        sa.CheckConstraint(
            "change_type IN ('REVIEW_COUNT_CHANGE','SOURCE_COVERAGE_CHANGE','EVIDENCE_COVERAGE_CHANGE','FRESHNESS_CHANGE','RATING_DISTRIBUTION_CHANGE','SENTIMENT_DISTRIBUTION_CHANGE','THEME_APPEARED','THEME_DISAPPEARED','THEME_SUPPORT_CHANGED','PAIN_POINT_APPEARED','PAIN_POINT_DISAPPEARED','PAIN_POINT_SUPPORT_CHANGED','PAIN_POINT_SEVERITY_CHANGED','PRAISE_APPEARED','PRAISE_DISAPPEARED','PRAISE_SUPPORT_CHANGED','FEATURE_REQUEST_APPEARED','FEATURE_REQUEST_DISAPPEARED','FEATURE_REQUEST_SUPPORT_CHANGED','QUALITY_SIGNAL_APPEARED','QUALITY_SIGNAL_DISAPPEARED','QUALITY_SIGNAL_CHANGED','QUALITY_SIGNAL_SEVERITY_CHANGED','PRODUCT_GAP_APPEARED','PRODUCT_GAP_DISAPPEARED','PRODUCT_GAP_SUPPORT_CHANGED','OPPORTUNITY_SIGNAL_APPEARED','OPPORTUNITY_SIGNAL_DISAPPEARED','OPPORTUNITY_SIGNAL_STATUS_CHANGED','OPPORTUNITY_SIGNAL_STRENGTH_CHANGED','CONTRADICTION_CHANGED','RESEARCH_GAP_CHANGED','REVIEW_OBSERVATION_CHANGED')",  # noqa: E501
            name="ck_review_change_event_type",  # noqa: E501
        ),
        sa.CheckConstraint(
            "observed_or_derived IN ('OBSERVED_CHANGE','DERIVED_DETERMINISTIC_CHANGE','DERIVED_SEMANTIC_CHANGE')",  # noqa: E501
            name="ck_review_change_event_semantics",
        ),
        sa.CheckConstraint(
            "status IN ('NEW','ONGOING','RESOLVED','REVERTED','SUPERSEDED','UNRESOLVED','POSSIBLY_DISAPPEARED')",  # noqa: E501
            name="ck_review_change_event_status",
        ),
        sa.CheckConstraint(
            "materiality IN ('IMMATERIAL','LOW','MODERATE','HIGH','UNKNOWN')",
            name="ck_review_change_event_materiality",
        ),
        sa.CheckConstraint(
            "alert_eligibility IN ('NO_ALERT','REVIEW','ALERT')",
            name="ck_review_change_event_alert",
        ),
    )
    op.create_index(
        "ix_review_change_event_owner", "intelligence_review_change_events", ["owner_id"]
    )
    op.create_index(
        "ix_review_change_event_context",
        "intelligence_review_change_events",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_review_change_event_type", "intelligence_review_change_events", ["change_type"]
    )
    op.create_index(
        "ix_review_change_event_materiality", "intelligence_review_change_events", ["materiality"]
    )
    op.create_index(
        "ix_review_change_event_alert", "intelligence_review_change_events", ["alert_eligibility"]
    )


def downgrade() -> None:
    op.drop_table("intelligence_review_change_events")
    op.drop_table("intelligence_review_change_comparisons")
