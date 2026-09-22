"""Immutable Trend 12D change and momentum intelligence models."""

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

COMPARISON_STATUSES = ("COMPLETED", "FAILED")
EVENT_TYPES = (
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
EVENT_STATUSES = (
    "NEW",
    "ONGOING",
    "RESOLVED",
    "REVERTED",
    "SUPERSEDED",
    "UNRESOLVED",
    "POSSIBLY_DISAPPEARED",
)
MOMENTUM_STATES = (
    "EMERGING_INCREASE",
    "SUSTAINED_INCREASE",
    "WEAKENING_INCREASE",
    "EMERGING_DECREASE",
    "SUSTAINED_DECREASE",
    "WEAKENING_DECREASE",
    "STABLE",
    "MIXED",
    "REVERSING",
    "INSUFFICIENT_EVIDENCE",
    "NOT_COMPARABLE",
    "UNKNOWN",
)
MATERIALITY_LEVELS = ("IMMATERIAL", "LOW", "MODERATE", "HIGH", "UNKNOWN")
ALERT_ELIGIBILITY = ("NO_ALERT", "REVIEW", "ALERT")
CHANGE_SEMANTICS = ("OBSERVED_CHANGE", "DERIVED_DETERMINISTIC_CHANGE")
CALCULATION_VERSION = "trend-change-v1"
MATERIALITY_POLICY_VERSION = "trend-change-materiality-v1"


def _check(name: str, field: str, values: tuple[str, ...]) -> CheckConstraint:
    return CheckConstraint(
        f"{field} IN (" + ",".join(f"'{value}'" for value in values) + ")", name=name
    )


class TrendChangeComparison(Base):
    """An immutable comparison between two ordered authoritative analyses."""

    __tablename__ = "intelligence_trend_change_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "input_fingerprint",
            name="uq_trend_change_comparison_fingerprint",
        ),
        UniqueConstraint(
            "owner_id",
            "context_id",
            "comparison_version",
            name="uq_trend_change_comparison_version",
        ),
        _check("ck_trend_change_comparison_status", "status", COMPARISON_STATUSES),
        Index("ix_trend_change_comparison_context_created", "owner_id", "context_id", "created_at"),
        Index(
            "ix_trend_change_comparison_baseline_current",
            "owner_id",
            "baseline_analysis_id",
            "current_analysis_id",
        ),
        Index("ix_trend_change_comparison_fingerprint", "owner_id", "input_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
    )
    baseline_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_analyses.id", ondelete="RESTRICT"),
    )
    current_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_analyses.id", ondelete="RESTRICT"),
    )
    baseline_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_snapshots.id", ondelete="RESTRICT"),
    )
    current_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_snapshots.id", ondelete="RESTRICT"),
    )
    comparison_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    calculation_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default=CALCULATION_VERSION
    )
    materiality_policy_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default=MATERIALITY_POLICY_VERSION
    )
    input_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="COMPLETED")
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrendChangeEvent(Base):
    """Append-only deterministic observed/derived change event."""

    __tablename__ = "intelligence_trend_change_events"
    __table_args__ = (
        UniqueConstraint("owner_id", "event_fingerprint", name="uq_trend_change_event_fingerprint"),
        _check("ck_trend_change_event_type", "event_type", EVENT_TYPES),
        _check("ck_trend_change_event_semantics", "change_semantics", CHANGE_SEMANTICS),
        _check("ck_trend_change_event_status", "status", EVENT_STATUSES),
        _check("ck_trend_change_event_momentum", "momentum", MOMENTUM_STATES),
        _check("ck_trend_change_event_materiality", "materiality", MATERIALITY_LEVELS),
        _check("ck_trend_change_event_alert", "alert_eligibility", ALERT_ELIGIBILITY),
        Index(
            "ix_trend_change_event_comparison_created", "owner_id", "comparison_id", "created_at"
        ),
        Index("ix_trend_change_event_type", "owner_id", "event_type"),
        Index(
            "ix_trend_change_event_signal_source", "owner_id", "signal_definition_id", "source_id"
        ),
        Index("ix_trend_change_event_materiality", "owner_id", "materiality"),
        Index("ix_trend_change_event_status", "owner_id", "status"),
        Index("ix_trend_change_event_alert", "owner_id", "alert_eligibility"),
        Index("ix_trend_change_event_created", "owner_id", "context_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE"),
    )
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_change_comparisons.id", ondelete="CASCADE"),
    )
    signal_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_signal_definitions.id", ondelete="SET NULL"),
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_sources.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    change_semantics: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DERIVED_DETERMINISTIC_CHANGE"
    )
    old_value: Mapped[object] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[object] = mapped_column(JSONB, nullable=True)
    absolute_delta: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    relative_delta: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    relative_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    momentum: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    materiality: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    materiality_policy_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default=MATERIALITY_POLICY_VERSION
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="NEW")
    alert_eligibility: Mapped[str] = mapped_column(String(16), nullable=False, default="NO_ALERT")
    alert_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    baseline_reference: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    current_reference: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    evidence_references: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    freshness_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    event_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    previous_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_change_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
