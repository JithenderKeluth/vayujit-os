"""Add Trend 12D change and momentum intelligence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261122_0131"
down_revision = "20261121_0130"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_trend_change_comparisons",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "baseline_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_analysis_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analyses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "baseline_snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_trend_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_trend_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("comparison_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "calculation_version", sa.String(80), nullable=False, server_default="trend-change-v1"
        ),
        sa.Column(
            "materiality_policy_version",
            sa.String(80),
            nullable=False,
            server_default="trend-change-materiality-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="COMPLETED"),
        sa.Column("summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "input_fingerprint",
            name="uq_trend_change_comparison_fingerprint",
        ),
        sa.UniqueConstraint(
            "owner_id",
            "context_id",
            "comparison_version",
            name="uq_trend_change_comparison_version",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED','FAILED')", name="ck_trend_change_comparison_status"
        ),
    )
    op.create_table(
        "intelligence_trend_change_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "comparison_id",
            UUID,
            sa.ForeignKey("intelligence_trend_change_comparisons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "signal_definition_id",
            UUID,
            sa.ForeignKey("intelligence_trend_signal_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("source_id", UUID, sa.ForeignKey("intelligence_sources.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "change_semantics",
            sa.String(32),
            nullable=False,
            server_default="DERIVED_DETERMINISTIC_CHANGE",
        ),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB),
        sa.Column("absolute_delta", sa.Numeric(30, 10)),
        sa.Column("relative_delta", sa.Numeric(30, 10)),
        sa.Column("relative_reason", sa.String(40)),
        sa.Column("momentum", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("materiality", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column(
            "materiality_policy_version",
            sa.String(80),
            nullable=False,
            server_default="trend-change-materiality-v1",
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column("alert_eligibility", sa.String(16), nullable=False, server_default="NO_ALERT"),
        sa.Column("alert_reason", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "baseline_reference", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "current_reference", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "evidence_references", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("event_fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "previous_event_id",
            UUID,
            sa.ForeignKey("intelligence_trend_change_events.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "event_fingerprint", name="uq_trend_change_event_fingerprint"
        ),
        sa.CheckConstraint(
            "event_type IN ("
            + ",".join(
                "'" + value + "'"
                for value in (
                    "SIGNAL_VALUE_INCREASED",
                    "SIGNAL_VALUE_DECREASED",
                    "SIGNAL_VALUE_UNCHANGED",
                    "DIRECTION_CHANGED",
                    "DIRECTION_STRENGTHENED",
                    "DIRECTION_WEAKENED",
                    "DIRECTION_REVERSED",
                    "PERSISTENCE_STARTED",
                    "PERSISTENCE_CONTINUED",
                    "PERSISTENCE_WEAKENED",
                    "PERSISTENCE_ENDED",
                    "VARIABILITY_INCREASED",
                    "VARIABILITY_DECREASED",
                    "VARIABILITY_CHANGED",
                    "EVIDENCE_APPEARED",
                    "EVIDENCE_POSSIBLY_DISAPPEARED",
                    "SOURCE_ADDED",
                    "SOURCE_POSSIBLY_REMOVED",
                    "COVERAGE_INCREASED",
                    "COVERAGE_DECREASED",
                    "FRESHNESS_IMPROVED",
                    "FRESHNESS_DEGRADED",
                    "MISSING_PERIODS_INCREASED",
                    "MISSING_PERIODS_DECREASED",
                    "COMPARABILITY_CHANGED",
                    "CONTRADICTION_APPEARED",
                    "CONTRADICTION_RESOLVED",
                    "RESEARCH_GAP_APPEARED",
                    "RESEARCH_GAP_RESOLVED",
                )
            )
            + ")",
            name="ck_trend_change_event_type",
        ),
        sa.CheckConstraint(
            "change_semantics IN ('OBSERVED_CHANGE','DERIVED_DETERMINISTIC_CHANGE')",
            name="ck_trend_change_event_semantics",
        ),
        sa.CheckConstraint(
            "status IN ('NEW','ONGOING','RESOLVED','REVERTED','SUPERSEDED','UNRESOLVED','POSSIBLY_DISAPPEARED')",  # noqa: E501
            name="ck_trend_change_event_status",
        ),
        sa.CheckConstraint(
            "momentum IN ('EMERGING_INCREASE','SUSTAINED_INCREASE','WEAKENING_INCREASE','EMERGING_DECREASE','SUSTAINED_DECREASE','WEAKENING_DECREASE','STABLE','MIXED','REVERSING','INSUFFICIENT_EVIDENCE','NOT_COMPARABLE','UNKNOWN')",  # noqa: E501
            name="ck_trend_change_event_momentum",
        ),
        sa.CheckConstraint(
            "materiality IN ('IMMATERIAL','LOW','MODERATE','HIGH','UNKNOWN')",
            name="ck_trend_change_event_materiality",
        ),
        sa.CheckConstraint(
            "alert_eligibility IN ('NO_ALERT','REVIEW','ALERT')", name="ck_trend_change_event_alert"
        ),
    )
    indexes = (
        (
            "ix_trend_change_comparison_context_created",
            "intelligence_trend_change_comparisons",
            ["owner_id", "context_id", "created_at"],
        ),
        (
            "ix_trend_change_comparison_baseline_current",
            "intelligence_trend_change_comparisons",
            ["owner_id", "baseline_analysis_id", "current_analysis_id"],
        ),
        (
            "ix_trend_change_comparison_fingerprint",
            "intelligence_trend_change_comparisons",
            ["owner_id", "input_fingerprint"],
        ),
        (
            "ix_trend_change_event_comparison_created",
            "intelligence_trend_change_events",
            ["owner_id", "comparison_id", "created_at"],
        ),
        (
            "ix_trend_change_event_type",
            "intelligence_trend_change_events",
            ["owner_id", "event_type"],
        ),
        (
            "ix_trend_change_event_signal_source",
            "intelligence_trend_change_events",
            ["owner_id", "signal_definition_id", "source_id"],
        ),
        (
            "ix_trend_change_event_materiality",
            "intelligence_trend_change_events",
            ["owner_id", "materiality"],
        ),
        (
            "ix_trend_change_event_status",
            "intelligence_trend_change_events",
            ["owner_id", "status"],
        ),
        (
            "ix_trend_change_event_alert",
            "intelligence_trend_change_events",
            ["owner_id", "alert_eligibility"],
        ),
        (
            "ix_trend_change_event_created",
            "intelligence_trend_change_events",
            ["owner_id", "context_id", "created_at"],
        ),
    )
    for name, table, columns in indexes:
        op.create_index(name, table, columns)


def downgrade() -> None:
    op.drop_table("intelligence_trend_change_events")
    op.drop_table("intelligence_trend_change_comparisons")
