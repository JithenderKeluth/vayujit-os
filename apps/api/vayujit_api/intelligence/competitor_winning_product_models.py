"""Persisted 10E projection from dedicated competitor intelligence into 9B."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base
from vayujit_api.intelligence.competitor_models import competitor_now

INTEGRATION_CONTRACT_VERSION = "competitor-winning-product-v1"
SOURCE_DEDICATED = "DEDICATED_COMPETITOR_INTELLIGENCE"
SOURCE_LEGACY = "LEGACY_9B_EVIDENCE"
SOURCE_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


class CompetitorWinningProductProjection(Base):
    """Immutable, owner-scoped authoritative 10C/10D -> 9B projection."""

    __tablename__ = "intelligence_competitor_winning_product_projections"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "opportunity_id",
            "assessment_id",
            "input_fingerprint",
            name="uq_comp_winning_projection_fingerprint",
        ),
        Index(
            "ix_comp_winning_projection_opportunity",
            "owner_id",
            "opportunity_id",
            "created_at",
        ),
        Index("ix_comp_winning_projection_context", "owner_id", "context_id", "created_at"),
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
        ForeignKey("intelligence_competitor_contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    competitor_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_commercial_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    change_comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_competitor_change_comparisons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_state: Mapped[str] = mapped_column(String(48), index=True)
    contract_version: Mapped[str] = mapped_column(String(120))
    nine_b_calculation_version: Mapped[str] = mapped_column(String(120))
    ten_c_calculation_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ten_d_calculation_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    projection: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    research_gaps: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    freshness_state: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    contradiction_state: Mapped[str] = mapped_column(String(32), default="NONE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=competitor_now, index=True
    )
