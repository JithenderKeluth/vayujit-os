"""Immutable competitor commercial analysis persistence (Slice 10C)."""

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
from vayujit_api.intelligence.competitor_models import competitor_now

ANALYSIS_STATUSES = ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED")
CALCULATION_VERSION = "competitor-commercial-v1"
COHORT_IDENTITY_STATES = (
    "CONFIRMED",
    "PROBABLE",
    "AMBIGUOUS",
    "REJECTED",
    "UNRESOLVED",
    "CANDIDATE",
)


class CompetitorCommercialAnalysis(Base):
    """Immutable, owner-scoped pricing/positioning/assortment analysis."""

    __tablename__ = "intelligence_competitor_commercial_analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "context_id",
            "input_fingerprint",
            name="uq_comp_commercial_analysis_fingerprint",
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_comp_commercial_analysis_idempotency"
        ),
        CheckConstraint(
            "status IN ('COMPLETED','PARTIALLY_COMPLETED','FAILED')",
            name="ck_comp_commercial_analysis_status",
        ),
        CheckConstraint("analysis_version >= 1", name="ck_comp_commercial_analysis_version"),
        Index("ix_comp_commercial_analysis_context", "owner_id", "context_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    discovery_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_discovery_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_version: Mapped[int] = mapped_column(Integer, default=1)
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    cohort_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    pricing_analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    concentration_analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    rating_analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    review_analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    assortment_analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    positioning_analysis: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    differentiation_analysis: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    competitive_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    evidence_coverage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    freshness_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    contradictions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    research_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    explanation: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )


class CompetitorComparableCohortEntry(Base):
    """Explainable inclusion/exclusion decision for one competitor product."""

    __tablename__ = "intelligence_competitor_comparable_cohort_entries"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "analysis_id",
            "product_id",
            name="uq_comp_comparable_cohort_product",
        ),
        CheckConstraint(
            (
                "identity_state IN ('CONFIRMED','PROBABLE','AMBIGUOUS',"
                "'REJECTED','UNRESOLVED','CANDIDATE')"
            ),
            name="ck_comp_cohort_identity_state",
        ),
        Index("ix_comp_cohort_analysis_included", "owner_id", "analysis_id", "included"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="CASCADE"),
        index=True,
    )
    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_contexts.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_foundation_products.id", ondelete="CASCADE"),
        index=True,
    )
    identity_state: Mapped[str] = mapped_column(String(24))
    included: Mapped[bool] = mapped_column(default=False, index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    evidence_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    freshness_state: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    observation_ids: Mapped[list[object]] = mapped_column(JSONB, default=list)
    explanation: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
