"""Immutable, descriptive Trend Intelligence 12C analysis models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

ANALYSIS_STATUSES = ("COMPLETED", "FAILED")
READINESS_STATES = (
    "AVAILABLE",
    "PARTIAL",
    "INSUFFICIENT_EVIDENCE",
    "NOT_COMPARABLE",
    "UNSUPPORTED",
)
DIRECTION_STATES = (
    "INCREASING",
    "DECREASING",
    "STABLE",
    "MIXED",
    "UNKNOWN",
    "INSUFFICIENT_EVIDENCE",
)
PERSISTENCE_STATES = (
    "PERSISTENT_INCREASE",
    "PERSISTENT_DECREASE",
    "INTERMITTENT",
    "REVERSING",
    "FLAT",
    "UNKNOWN",
    "INSUFFICIENT_EVIDENCE",
)
VARIABILITY_STATES = (
    "STABLE",
    "LOW_VARIABILITY",
    "MODERATE_VARIABILITY",
    "HIGH_VARIABILITY",
    "UNKNOWN",
)
FRESHNESS_STATES = ("CURRENT", "STALE", "MIXED", "UNKNOWN")
GAP_TYPES = (
    "NO_OBSERVATIONS",
    "SINGLE_OBSERVATION",
    "INSUFFICIENT_HISTORY",
    "MISSING_PERIODS",
    "STALE_EVIDENCE",
    "UNKNOWN_FRESHNESS",
    "INCOMPATIBLE_UNITS",
    "INCOMPATIBLE_SCALES",
    "INCOMPATIBLE_GEOGRAPHY",
    "INCOMPATIBLE_GRANULARITY",
    "SINGLE_SOURCE_ONLY",
    "CONTRADICTORY_SOURCES",
)


def _check(name: str, field: str, values: tuple[str, ...]) -> CheckConstraint:
    return CheckConstraint(
        f"{field} IN (" + ",".join(f"'{value}'" for value in values) + ")", name=name
    )


class TrendAnalysis(Base):
    """A reproducible analysis bound to one immutable TrendSnapshot."""

    __tablename__ = "intelligence_trend_analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_trend_analysis_fingerprint"
        ),
        UniqueConstraint(
            "owner_id", "context_id", "analysis_version", name="uq_trend_analysis_version"
        ),
        _check("ck_trend_analysis_status", "status", ANALYSIS_STATUSES),
        _check("ck_trend_analysis_readiness", "readiness", READINESS_STATES),
        _check("ck_trend_analysis_freshness", "freshness_state", FRESHNESS_STATES),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_snapshots.id", ondelete="CASCADE"),
        index=True,
    )
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default="trend-analysis-v1"
    )
    input_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="COMPLETED", index=True)
    readiness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSUFFICIENT_EVIDENCE"
    )
    included_observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    included_reasons: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    excluded_reasons: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    time_coverage: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    source_coverage: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    signal_coverage: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    freshness_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class TrendAnalysisSeries(Base):
    """One source/signal/comparability cohort within an analysis."""

    __tablename__ = "intelligence_trend_analysis_series"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "cohort_fingerprint", name="uq_trend_analysis_series_cohort"
        ),
        _check("ck_trend_analysis_series_readiness", "readiness", READINESS_STATES),
        _check("ck_trend_analysis_series_direction", "direction", DIRECTION_STATES),
        _check("ck_trend_analysis_series_persistence", "persistence", PERSISTENCE_STATES),
        _check("ck_trend_analysis_series_variability", "variability_state", VARIABILITY_STATES),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    signal_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_signal_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="RESTRICT"), index=True
    )
    cohort_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    measurement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    scale: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    geography_scope: Mapped[str] = mapped_column(String(24), nullable=False)
    country: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    marketplace: Mapped[str | None] = mapped_column(String(120))
    granularity: Mapped[str] = mapped_column(String(24), nullable=False)
    readiness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSUFFICIENT_EVIDENCE"
    )
    direction: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSUFFICIENT_EVIDENCE"
    )
    persistence: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSUFFICIENT_EVIDENCE"
    )
    variability_state: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    freshness_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    included_observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_period_count: Mapped[int | None] = mapped_column(Integer)
    observed_period_count: Mapped[int | None] = mapped_column(Integer)
    missing_period_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_ratio: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    statistics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    change: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    movement: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    missing_periods: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    observation_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class TrendAnalysisGap(Base):
    """Bounded evidence gaps explaining why a series is limited."""

    __tablename__ = "intelligence_trend_analysis_gaps"
    __table_args__ = (
        Index("ix_trend_analysis_gap_analysis_type", "owner_id", "analysis_id", "gap_type"),
        _check("ck_trend_analysis_gap_type", "gap_type", GAP_TYPES),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_analysis_series.id", ondelete="CASCADE"),
        index=True,
    )
    gap_type: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


Index(
    "ix_trend_analysis_owner_context_created",
    TrendAnalysis.owner_id,
    TrendAnalysis.context_id,
    TrendAnalysis.created_at,
)
Index(
    "ix_trend_analysis_context_snapshot",
    TrendAnalysis.owner_id,
    TrendAnalysis.context_id,
    TrendAnalysis.snapshot_id,
)
Index(
    "ix_trend_analysis_fingerprint_version",
    TrendAnalysis.owner_id,
    TrendAnalysis.input_fingerprint,
    TrendAnalysis.analysis_version,
)
Index(
    "ix_trend_analysis_series_signal_source",
    TrendAnalysisSeries.owner_id,
    TrendAnalysisSeries.signal_definition_id,
    TrendAnalysisSeries.source_id,
)
Index(
    "ix_trend_analysis_series_direction_readiness",
    TrendAnalysisSeries.owner_id,
    TrendAnalysisSeries.direction,
    TrendAnalysisSeries.readiness,
)
Index(
    "ix_trend_analysis_series_time_range",
    TrendAnalysisSeries.owner_id,
    TrendAnalysisSeries.time_start,
    TrendAnalysisSeries.time_end,
)
