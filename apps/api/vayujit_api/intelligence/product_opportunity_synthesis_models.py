"""Immutable Product Opportunity risk and evidence synthesis (Slice 9E)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CALCULATION_VERSION = "product-opportunity-risk-evidence-synthesis-v1"


class ProductOpportunityRiskEvidenceSynthesis(Base):
    __tablename__ = "intelligence_product_opportunity_risk_evidence_syntheses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "assessment_id", name="uq_product_opportunity_synthesis_assessment"
        ),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_synthesis_idempotency"
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
    calculation_version: Mapped[str] = mapped_column(String(120), default=CALCULATION_VERSION)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    upstream_lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    risks: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    domain_readiness: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    evidence_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    research_gaps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dimensions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
