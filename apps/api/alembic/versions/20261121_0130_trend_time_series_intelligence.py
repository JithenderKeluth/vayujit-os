"""Add Trend 12C descriptive time-series analyses."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261121_0130"
down_revision = "20261120_0129"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "intelligence_trend_analyses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "owner_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            UUID,
            sa.ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            UUID,
            sa.ForeignKey("intelligence_trend_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_version", sa.Integer, nullable=False),
        sa.Column(
            "calculation_version",
            sa.String(80),
            nullable=False,
            server_default="trend-analysis-v1",
        ),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="COMPLETED"),
        sa.Column(
            "readiness",
            sa.String(32),
            nullable=False,
            server_default="INSUFFICIENT_EVIDENCE",
        ),
        sa.Column("included_observation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("excluded_observation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("included_reasons", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("excluded_reasons", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("time_coverage", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_coverage", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("signal_coverage", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_trend_analysis_fingerprint"
        ),
        sa.UniqueConstraint(
            "owner_id", "context_id", "analysis_version", name="uq_trend_analysis_version"
        ),
        sa.CheckConstraint("status IN ('COMPLETED','FAILED')", name="ck_trend_analysis_status"),
        sa.CheckConstraint(
            "readiness IN ("
            "'AVAILABLE','PARTIAL','INSUFFICIENT_EVIDENCE',"
            "'NOT_COMPARABLE','UNSUPPORTED')",
            name="ck_trend_analysis_readiness",
        ),
        sa.CheckConstraint(
            "freshness_state IN ('CURRENT','STALE','MIXED','UNKNOWN')",
            name="ck_trend_analysis_freshness",
        ),
    )
    op.create_table(
        "intelligence_trend_analysis_series",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "owner_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analyses.id", ondelete="CASCADE"),
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
            sa.ForeignKey("intelligence_trend_signal_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            UUID,
            sa.ForeignKey("intelligence_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("cohort_fingerprint", sa.String(128), nullable=False),
        sa.Column("measurement_type", sa.String(24), nullable=False),
        sa.Column("unit", sa.String(40)),
        sa.Column("scale", sa.Numeric(30, 10)),
        sa.Column("geography_scope", sa.String(24), nullable=False),
        sa.Column("country", sa.String(80)),
        sa.Column("region", sa.String(120)),
        sa.Column("city", sa.String(120)),
        sa.Column("marketplace", sa.String(120)),
        sa.Column("granularity", sa.String(24), nullable=False),
        sa.Column(
            "readiness", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column(
            "direction", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column(
            "persistence", sa.String(32), nullable=False, server_default="INSUFFICIENT_EVIDENCE"
        ),
        sa.Column("variability_state", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("freshness_state", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("included_observation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("excluded_observation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("time_start", sa.DateTime(timezone=True)),
        sa.Column("time_end", sa.DateTime(timezone=True)),
        sa.Column("expected_period_count", sa.Integer),
        sa.Column("observed_period_count", sa.Integer),
        sa.Column("missing_period_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("coverage_ratio", sa.Numeric(30, 10)),
        sa.Column("statistics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("change", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("movement", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("missing_periods", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("observation_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "analysis_id", "cohort_fingerprint", name="uq_trend_analysis_series_cohort"
        ),
        sa.CheckConstraint(
            "readiness IN ("
            "'AVAILABLE','PARTIAL','INSUFFICIENT_EVIDENCE',"
            "'NOT_COMPARABLE','UNSUPPORTED')",
            name="ck_trend_analysis_series_readiness",
        ),
        sa.CheckConstraint(
            "direction IN ("
            "'INCREASING','DECREASING','STABLE','MIXED','UNKNOWN',"
            "'INSUFFICIENT_EVIDENCE')",
            name="ck_trend_analysis_series_direction",
        ),
        sa.CheckConstraint(
            "persistence IN ("
            "'PERSISTENT_INCREASE','PERSISTENT_DECREASE','INTERMITTENT',"
            "'REVERSING','FLAT','UNKNOWN','INSUFFICIENT_EVIDENCE')",
            name="ck_trend_analysis_series_persistence",
        ),
        sa.CheckConstraint(
            "variability_state IN ("
            "'STABLE','LOW_VARIABILITY','MODERATE_VARIABILITY',"
            "'HIGH_VARIABILITY','UNKNOWN')",
            name="ck_trend_analysis_series_variability",
        ),
    )
    op.create_table(
        "intelligence_trend_analysis_gaps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "owner_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "series_id",
            UUID,
            sa.ForeignKey("intelligence_trend_analysis_series.id", ondelete="CASCADE"),
        ),
        sa.Column("gap_type", sa.String(40), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "gap_type IN ("
            "'NO_OBSERVATIONS','SINGLE_OBSERVATION','INSUFFICIENT_HISTORY',"
            "'MISSING_PERIODS','STALE_EVIDENCE','UNKNOWN_FRESHNESS',"
            "'INCOMPATIBLE_UNITS','INCOMPATIBLE_SCALES','INCOMPATIBLE_GEOGRAPHY',"
            "'INCOMPATIBLE_GRANULARITY','SINGLE_SOURCE_ONLY','CONTRADICTORY_SOURCES')",
            name="ck_trend_analysis_gap_type",
        ),
    )
    op.create_index(
        "ix_trend_analysis_owner_context_created",
        "intelligence_trend_analyses",
        ["owner_id", "context_id", "created_at"],
    )
    op.create_index(
        "ix_trend_analysis_context_snapshot",
        "intelligence_trend_analyses",
        ["owner_id", "context_id", "snapshot_id"],
    )
    op.create_index(
        "ix_trend_analysis_fingerprint_version",
        "intelligence_trend_analyses",
        ["owner_id", "input_fingerprint", "analysis_version"],
    )
    op.create_index(
        "ix_trend_analysis_series_signal_source",
        "intelligence_trend_analysis_series",
        ["owner_id", "signal_definition_id", "source_id"],
    )
    op.create_index(
        "ix_trend_analysis_series_direction_readiness",
        "intelligence_trend_analysis_series",
        ["owner_id", "direction", "readiness"],
    )
    op.create_index(
        "ix_trend_analysis_series_time_range",
        "intelligence_trend_analysis_series",
        ["owner_id", "time_start", "time_end"],
    )
    op.create_index(
        "ix_trend_analysis_gap_analysis_type",
        "intelligence_trend_analysis_gaps",
        ["owner_id", "analysis_id", "gap_type"],
    )


def downgrade() -> None:
    op.drop_table("intelligence_trend_analysis_gaps")
    op.drop_table("intelligence_trend_analysis_series")
    op.drop_table("intelligence_trend_analyses")
