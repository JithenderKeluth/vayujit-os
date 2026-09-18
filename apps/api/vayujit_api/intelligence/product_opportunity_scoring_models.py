"""Immutable deterministic Winning Product scoring projections (Slice 9F)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

SCORING_MODEL_VERSION = "winning-product-score-v1"
CALCULATION_VERSION = "winning-product-scoring-v1"
PROFILE_VERSION = "canonical-v1"
SCORING_DIMENSIONS = (
    "DEMAND_ATTRACTIVENESS",
    "COMPETITIVE_OPPORTUNITY",
    "COMMERCIAL_VIABILITY",
    "CAPITAL_EFFICIENCY",
    "SUPPLIER_FEASIBILITY",
    "SOURCING_RESILIENCE",
    "DIFFERENTIATION_POTENTIAL",
)


class ProductOpportunityScore(Base):
    __tablename__ = "intelligence_product_opportunity_scores"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "assessment_id",
            "scoring_model_version",
            "profile_version",
            name="uq_product_opportunity_score_logical",
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_score_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
        index=True,
    )
    scoring_model_version: Mapped[str] = mapped_column(String(80), default=SCORING_MODEL_VERSION)
    calculation_version: Mapped[str] = mapped_column(String(80), default=CALCULATION_VERSION)
    profile_version: Mapped[str] = mapped_column(String(80), default=PROFILE_VERSION)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    upstream_lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    eligibility: Mapped[str] = mapped_column(String(32))
    overall_score: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    classification: Mapped[str] = mapped_column(String(32))
    decision_label: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[str] = mapped_column(String(24))
    risk_level: Mapped[str] = mapped_column(String(24))
    assessment_readiness: Mapped[str] = mapped_column(String(32))
    evidence_state: Mapped[str] = mapped_column(String(32))
    dimensions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    unavailable_dimensions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    risk_adjustments: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    positive_drivers: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    negative_drivers: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    improvement_areas: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    sensitivity: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    comparability: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")


class ProductOpportunityDecision(Base):
    __tablename__ = "intelligence_product_opportunity_decisions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_decision_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="CASCADE"),
        index=True,
    )
    score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_scores.id", ondelete="RESTRICT"),
        index=True,
    )
    action: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
