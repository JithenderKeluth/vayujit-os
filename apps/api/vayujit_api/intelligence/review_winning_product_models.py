"""Immutable 11F Review Intelligence projection into Winning Product detail."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base
from vayujit_api.identity.service import now

INTEGRATION_CONTRACT_VERSION = "review-winning-product-v1"
CALCULATION_VERSION = "review-winning-product-calculation-v1"
READINESS_STATES = (
    "AVAILABLE",
    "PARTIAL",
    "INSUFFICIENT_EVIDENCE",
    "STALE",
    "CONTRADICTORY",
    "RESEARCH_REQUIRED",
)
SOURCE_STATES = ("AVAILABLE", "PARTIAL", "INSUFFICIENT_EVIDENCE", "STALE", "CONTRADICTORY")


class ReviewWinningProductProjection(Base):
    """Owner-scoped, append-only evidence adapter; it never stores a winner score."""

    __tablename__ = "intelligence_review_winning_product_projections"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "input_fingerprint",
            name="uq_review_winning_projection_fingerprint",
        ),
        Index(
            "ix_review_winning_projection_opportunity",
            "owner_id",
            "opportunity_id",
            "created_at",
        ),
        Index("ix_review_winning_projection_context", "owner_id", "context_id", "created_at"),
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
        ForeignKey("intelligence_review_contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gap_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_product_gap_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    change_comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_review_change_comparisons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contract_version: Mapped[str] = mapped_column(String(120), default=INTEGRATION_CONTRACT_VERSION)
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    readiness: Mapped[str] = mapped_column(String(32), default="INSUFFICIENT_EVIDENCE", index=True)
    source_state: Mapped[str] = mapped_column(
        String(32), default="INSUFFICIENT_EVIDENCE", index=True
    )
    cohort: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    rating_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    feedback_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    gap_evidence: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    change_evidence: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    research_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    freshness: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    contradictions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    evidence_lineage: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    projection: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
