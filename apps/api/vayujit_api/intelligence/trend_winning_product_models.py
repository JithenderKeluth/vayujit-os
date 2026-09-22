"""Immutable 12F Trend evidence projection into Winning Product detail."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base
from vayujit_api.identity.service import now

INTEGRATION_CONTRACT_VERSION = "trend-winning-product-v1"
CALCULATION_VERSION = "trend-winning-product-calculation-v1"
READINESS_STATES = (
    "AVAILABLE",
    "PARTIAL",
    "INSUFFICIENT_EVIDENCE",
    "STALE",
    "CONTRADICTORY",
    "RESEARCH_REQUIRED",
    "NOT_COMPARABLE",
)
SOURCE_STATES = READINESS_STATES


class TrendWinningProductProjection(Base):
    """Append-only adapter; it contains Trend evidence, never a winner score."""

    __tablename__ = "intelligence_trend_winning_product_projections"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "input_fingerprint",
            name="uq_trend_winning_projection_fingerprint",
        ),
        UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "projection_version",
            name="uq_trend_winning_projection_version",
        ),
        Index(
            "ix_trend_winning_projection_opportunity",
            "owner_id",
            "opportunity_id",
            "created_at",
        ),
        Index("ix_trend_winning_projection_assessment", "owner_id", "assessment_id", "created_at"),
        Index("ix_trend_winning_projection_context", "owner_id", "context_id", "created_at"),
        Index("ix_trend_winning_projection_validation", "owner_id", "validation_id", "created_at"),
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
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_contexts.id", ondelete="SET NULL"),
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_snapshots.id", ondelete="SET NULL"),
        index=True,
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_analyses.id", ondelete="SET NULL"),
        index=True,
    )
    comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_change_comparisons.id", ondelete="SET NULL"),
        index=True,
    )
    validation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_trend_validations.id", ondelete="SET NULL"),
        index=True,
    )
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contract_version: Mapped[str] = mapped_column(String(120), default=INTEGRATION_CONTRACT_VERSION)
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    readiness: Mapped[str] = mapped_column(String(32), default="INSUFFICIENT_EVIDENCE", index=True)
    source_state: Mapped[str] = mapped_column(
        String(32), default="INSUFFICIENT_EVIDENCE", index=True
    )
    validated_hypotheses: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    signal_summaries: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    momentum_summaries: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    evidence_confidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    freshness: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    contradictions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    research_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    evidence_lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    projection: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
