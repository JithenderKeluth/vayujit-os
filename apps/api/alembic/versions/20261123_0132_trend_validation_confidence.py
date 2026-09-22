# ruff: noqa: E501
"""Add Trend 12E validation and confidence intelligence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261123_0132"
down_revision = "20261122_0131"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def _json(default: str) -> object:
    return sa.text(f"'{default}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "intelligence_trend_validations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_trend_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "comparison_id",
            UUID,
            sa.ForeignKey("intelligence_trend_change_comparisons.id", ondelete="SET NULL"),
        ),
        sa.Column("validation_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "calculation_version",
            sa.String(80),
            nullable=False,
            server_default="trend-validation-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"),
        sa.Column("evidence_coverage", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("source_coverage", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("time_coverage", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("freshness_summary", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("agreement_summary", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("contradiction_summary", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "downstream_readiness",
            sa.String(32),
            nullable=False,
            server_default="INSUFFICIENT_EVIDENCE",
        ),
        sa.Column("materiality_summary", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("alert_summary", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("limitations", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("research_gaps", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_trend_validation_fingerprint"
        ),
        sa.UniqueConstraint(
            "owner_id", "context_id", "validation_version", name="uq_trend_validation_version"
        ),
        sa.CheckConstraint(
            "status IN ('VALIDATED','PARTIALLY_VALIDATED','INSUFFICIENT_EVIDENCE','CONTRADICTORY','STALE','NOT_COMPARABLE','RESEARCH_REQUIRED')",
            name="ck_trend_validation_status",
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH','MODERATE','LOW','UNKNOWN')",
            name="ck_trend_validation_confidence",
        ),
        sa.CheckConstraint(
            "downstream_readiness IN ('READY_FOR_DOWNSTREAM','PARTIALLY_READY','RESEARCH_REQUIRED','INSUFFICIENT_EVIDENCE','CONTRADICTORY','STALE','NOT_COMPARABLE')",
            name="ck_trend_validation_readiness",
        ),
        sa.CheckConstraint(
            "freshness_state IN ('CURRENT','MIXED','STALE','UNKNOWN')",
            name="ck_trend_validation_freshness",
        ),
    )
    op.create_table(
        "intelligence_trend_validation_hypotheses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "validation_id",
            UUID,
            sa.ForeignKey("intelligence_trend_validations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "signal_definition_id",
            UUID,
            sa.ForeignKey("intelligence_trend_signal_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("hypothesis_type", sa.String(40), nullable=False),
        sa.Column("signal_semantics", sa.String(200), nullable=False, server_default=""),
        sa.Column("source_scope", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("time_window", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("geography", sa.String(80), nullable=False, server_default="UNKNOWN"),
        sa.Column("granularity", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("supporting_source_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("opposing_source_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("supporting_signal_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("supporting_analysis_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("supporting_series_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("supporting_change_event_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("supporting_observation_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("supporting_evidence_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("support_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("opposition_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unknown_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("agreement", sa.String(24), nullable=False, server_default="UNKNOWN"),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "readiness", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column("materiality", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("momentum", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("limitations", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("hypothesis_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "validation_id",
            "hypothesis_fingerprint",
            name="uq_trend_validation_hypothesis_fingerprint",
        ),
        sa.CheckConstraint(
            "hypothesis_type IN ('OBSERVED_SIGNAL_INCREASING','OBSERVED_SIGNAL_DECREASING','OBSERVED_SIGNAL_STABLE','SUSTAINED_INCREASE','SUSTAINED_DECREASE','REVERSING','HIGH_VARIABILITY','EVIDENCE_STRENGTHENING','EVIDENCE_WEAKENING')",
            name="ck_trend_validation_hypothesis_type",
        ),
        sa.CheckConstraint(
            "agreement IN ('AGREE','MOSTLY_AGREE','MIXED','DISAGREE','UNKNOWN','NOT_COMPARABLE','INSUFFICIENT_EVIDENCE')",
            name="ck_trend_validation_hypothesis_agreement",
        ),
        sa.CheckConstraint(
            "confidence IN ('HIGH','MODERATE','LOW','UNKNOWN')",
            name="ck_trend_validation_hypothesis_confidence",
        ),
        sa.CheckConstraint(
            "readiness IN ('READY_FOR_DOWNSTREAM','PARTIALLY_READY','RESEARCH_REQUIRED','INSUFFICIENT_EVIDENCE','CONTRADICTORY','STALE','NOT_COMPARABLE')",
            name="ck_trend_validation_hypothesis_readiness",
        ),
    )
    op.create_table(
        "intelligence_trend_validation_contradictions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "validation_id",
            UUID,
            sa.ForeignKey("intelligence_trend_validations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("contradiction_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="MODERATE"),
        sa.Column("supporting_source_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("opposing_source_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("series_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("time_windows", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("limitations", JSONB, nullable=False, server_default=_json("[]")),
        sa.Column("contradiction_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "validation_id",
            "contradiction_fingerprint",
            name="uq_trend_validation_contradiction_fingerprint",
        ),
        sa.CheckConstraint(
            "contradiction_type IN ('DIRECTION_CONTRADICTION','PERSISTENCE_CONTRADICTION','VALUE_CONTRADICTION','FRESHNESS_CONTRADICTION','COVERAGE_CONTRADICTION','SOURCE_CONTRADICTION','UNKNOWN')",
            name="ck_trend_validation_contradiction_type",
        ),
    )
    op.create_table(
        "intelligence_trend_validation_gaps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "validation_id",
            UUID,
            sa.ForeignKey("intelligence_trend_validations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gap_type", sa.String(48), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("detail", JSONB, nullable=False, server_default=_json("{}")),
        sa.Column("recommendation", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "validation_id", "gap_type", name="uq_trend_validation_gap_type"
        ),
    )
    indexes = (
        (
            "ix_trend_validation_context_created",
            "intelligence_trend_validations",
            ["owner_id", "context_id", "created_at"],
        ),
        (
            "ix_trend_validation_analysis_snapshot",
            "intelligence_trend_validations",
            ["owner_id", "analysis_id", "snapshot_id"],
        ),
        (
            "ix_trend_validation_status_confidence",
            "intelligence_trend_validations",
            ["owner_id", "status", "confidence"],
        ),
        (
            "ix_trend_validation_hypothesis_validation",
            "intelligence_trend_validation_hypotheses",
            ["owner_id", "validation_id"],
        ),
        (
            "ix_trend_validation_hypothesis_signal",
            "intelligence_trend_validation_hypotheses",
            ["owner_id", "signal_definition_id"],
        ),
        (
            "ix_trend_validation_hypothesis_confidence",
            "intelligence_trend_validation_hypotheses",
            ["owner_id", "confidence"],
        ),
        (
            "ix_trend_validation_hypothesis_readiness",
            "intelligence_trend_validation_hypotheses",
            ["owner_id", "readiness"],
        ),
        (
            "ix_trend_validation_contradiction_validation",
            "intelligence_trend_validation_contradictions",
            ["owner_id", "validation_id"],
        ),
        (
            "ix_trend_validation_contradiction_type",
            "intelligence_trend_validation_contradictions",
            ["owner_id", "contradiction_type"],
        ),
        (
            "ix_trend_validation_gap_validation_type",
            "intelligence_trend_validation_gaps",
            ["owner_id", "validation_id", "gap_type"],
        ),
    )
    for name, table, columns in indexes:
        op.create_index(name, table, columns)


def downgrade() -> None:
    op.drop_table("intelligence_trend_validation_gaps")
    op.drop_table("intelligence_trend_validation_contradictions")
    op.drop_table("intelligence_trend_validation_hypotheses")
    op.drop_table("intelligence_trend_validations")
