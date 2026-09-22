"""Immutable Trend 12E validation and cross-source confidence models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

VALIDATION_STATUSES = (
    "VALIDATED",
    "PARTIALLY_VALIDATED",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTORY",
    "STALE",
    "NOT_COMPARABLE",
    "RESEARCH_REQUIRED",
)
HYPOTHESIS_TYPES = (
    "OBSERVED_SIGNAL_INCREASING",
    "OBSERVED_SIGNAL_DECREASING",
    "OBSERVED_SIGNAL_STABLE",
    "SUSTAINED_INCREASE",
    "SUSTAINED_DECREASE",
    "REVERSING",
    "HIGH_VARIABILITY",
    "EVIDENCE_STRENGTHENING",
    "EVIDENCE_WEAKENING",
)
AGREEMENT_STATES = (
    "AGREE",
    "MOSTLY_AGREE",
    "MIXED",
    "DISAGREE",
    "UNKNOWN",
    "NOT_COMPARABLE",
    "INSUFFICIENT_EVIDENCE",
)
CONFIDENCE_STATES = ("HIGH", "MODERATE", "LOW", "UNKNOWN")
READINESS_STATES = (
    "READY_FOR_DOWNSTREAM",
    "PARTIALLY_READY",
    "RESEARCH_REQUIRED",
    "INSUFFICIENT_EVIDENCE",
    "CONTRADICTORY",
    "STALE",
    "NOT_COMPARABLE",
)
FRESHNESS_STATES = ("CURRENT", "MIXED", "STALE", "UNKNOWN")
CONTRADICTION_TYPES = (
    "DIRECTION_CONTRADICTION",
    "PERSISTENCE_CONTRADICTION",
    "VALUE_CONTRADICTION",
    "FRESHNESS_CONTRADICTION",
    "COVERAGE_CONTRADICTION",
    "SOURCE_CONTRADICTION",
    "UNKNOWN",
)
GAP_TYPES = (
    "NO_OBSERVATIONS",
    "INSUFFICIENT_HISTORY",
    "SINGLE_SOURCE_ONLY",
    "INSUFFICIENT_INDEPENDENT_SOURCES",
    "MISSING_PERIODS",
    "STALE_EVIDENCE",
    "UNKNOWN_FRESHNESS",
    "CONTRADICTORY_SOURCES",
    "INCOMPATIBLE_SOURCES",
    "INSUFFICIENT_QUALITY",
    "BROKEN_LINEAGE",
    "NO_CURRENT_COMPARISON",
)


def _check(name: str, field: str, values: tuple[str, ...]) -> CheckConstraint:
    return CheckConstraint(
        f"{field} IN (" + ",".join(f"'{value}'" for value in values) + ")", name=name
    )


class TrendValidation(Base):
    __tablename__ = "intelligence_trend_validations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "context_id", "input_fingerprint", name="uq_trend_validation_fingerprint"
        ),
        UniqueConstraint(
            "owner_id", "context_id", "validation_version", name="uq_trend_validation_version"
        ),
        _check("ck_trend_validation_status", "status", VALIDATION_STATUSES),
        _check("ck_trend_validation_confidence", "confidence", CONFIDENCE_STATES),
        _check("ck_trend_validation_readiness", "downstream_readiness", READINESS_STATES),
        _check("ck_trend_validation_freshness", "freshness_state", FRESHNESS_STATES),
        Index("ix_trend_validation_context_created", "owner_id", "context_id", "created_at"),
        Index("ix_trend_validation_analysis_snapshot", "owner_id", "analysis_id", "snapshot_id"),
        Index("ix_trend_validation_status_confidence", "owner_id", "status", "confidence"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE")
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_analyses.id", ondelete="RESTRICT")
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_snapshots.id", ondelete="RESTRICT")
    )
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_change_comparisons.id", ondelete="SET NULL"),
    )
    validation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    calculation_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default="trend-validation-v1"
    )
    input_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INSUFFICIENT_EVIDENCE")
    evidence_coverage: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    source_coverage: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    time_coverage: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    freshness_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    freshness_state: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    agreement_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    contradiction_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    downstream_readiness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSUFFICIENT_EVIDENCE"
    )
    materiality_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    alert_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    research_gaps: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrendValidationHypothesis(Base):
    __tablename__ = "intelligence_trend_validation_hypotheses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "validation_id",
            "hypothesis_fingerprint",
            name="uq_trend_validation_hypothesis_fingerprint",
        ),
        _check("ck_trend_validation_hypothesis_type", "hypothesis_type", HYPOTHESIS_TYPES),
        _check("ck_trend_validation_hypothesis_agreement", "agreement", AGREEMENT_STATES),
        _check("ck_trend_validation_hypothesis_confidence", "confidence", CONFIDENCE_STATES),
        _check("ck_trend_validation_hypothesis_readiness", "readiness", READINESS_STATES),
        Index("ix_trend_validation_hypothesis_validation", "owner_id", "validation_id"),
        Index("ix_trend_validation_hypothesis_signal", "owner_id", "signal_definition_id"),
        Index("ix_trend_validation_hypothesis_confidence", "owner_id", "confidence"),
        Index("ix_trend_validation_hypothesis_readiness", "owner_id", "readiness"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_validations.id", ondelete="CASCADE")
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE")
    )
    signal_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_signal_definitions.id", ondelete="SET NULL"),
    )
    hypothesis_type: Mapped[str] = mapped_column(String(40), nullable=False)
    signal_semantics: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    source_scope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    time_window: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    geography: Mapped[str] = mapped_column(String(80), nullable=False, default="UNKNOWN")
    granularity: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    supporting_source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    opposing_source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    supporting_signal_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    supporting_analysis_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    supporting_series_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    supporting_change_event_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    supporting_observation_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opposition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agreement: Mapped[str] = mapped_column(String(24), nullable=False, default="UNKNOWN")
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    readiness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSUFFICIENT_EVIDENCE"
    )
    materiality: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    momentum: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    hypothesis_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrendValidationContradiction(Base):
    __tablename__ = "intelligence_trend_validation_contradictions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "validation_id",
            "contradiction_fingerprint",
            name="uq_trend_validation_contradiction_fingerprint",
        ),
        _check("ck_trend_validation_contradiction_type", "contradiction_type", CONTRADICTION_TYPES),
        Index("ix_trend_validation_contradiction_validation", "owner_id", "validation_id"),
        Index("ix_trend_validation_contradiction_type", "owner_id", "contradiction_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_validations.id", ondelete="CASCADE")
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE")
    )
    contradiction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="MODERATE")
    supporting_source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    opposing_source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    series_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    time_windows: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    contradiction_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrendValidationGap(Base):
    __tablename__ = "intelligence_trend_validation_gaps"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "validation_id", "gap_type", name="uq_trend_validation_gap_type"
        ),
        Index("ix_trend_validation_gap_validation_type", "owner_id", "validation_id", "gap_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_validations.id", ondelete="CASCADE")
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_trend_contexts.id", ondelete="CASCADE")
    )
    gap_type: Mapped[str] = mapped_column(String(48), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    detail: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    recommendation: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
