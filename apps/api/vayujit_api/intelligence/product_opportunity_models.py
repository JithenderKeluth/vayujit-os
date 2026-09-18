"""Canonical owner-scoped Product Opportunity foundation (Slice 9A)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

OPPORTUNITY_LIFECYCLES = (
    "draft",
    "researching",
    "ready_for_assessment",
    "assessed",
    "watching",
    "archived",
)
RESEARCH_ORIGINS = (
    "manual",
    "marketplace_discovery",
    "trend_research",
    "competitor_research",
    "review_research",
    "external_research",
    "ai_research",
    "supplier_discovery",
    "import",
)
EVIDENCE_STATES = ("unknown", "partial", "insufficient_evidence", "available")


def opportunity_now() -> datetime:
    return datetime.now(UTC)


class ProductOpportunity(Base):
    __tablename__ = "intelligence_product_opportunities"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_product_opportunity_owner_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_research_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    product_concept: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(120), default="", index=True)
    subcategory: Mapped[str] = mapped_column(String(120), default="")
    brand_strategy: Mapped[str] = mapped_column(String(120), default="")
    target_marketplace: Mapped[str] = mapped_column(String(120), default="", index=True)
    target_region: Mapped[str] = mapped_column(String(120), default="")
    customer_segment: Mapped[str] = mapped_column(String(160), default="")
    business_model: Mapped[str] = mapped_column(String(120), default="")
    research_objective: Mapped[str] = mapped_column(Text, default="")
    origin: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    research_state: Mapped[str] = mapped_column(String(32), default="not_started")
    evidence_state: Mapped[str] = mapped_column(String(32), default="unknown")
    current_constraint_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    current_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=opportunity_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=opportunity_now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductOpportunityConstraintVersion(Base):
    __tablename__ = "intelligence_product_opportunity_constraint_versions"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id", "version", name="uq_product_opportunity_constraint_version"
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
    version: Mapped[int] = mapped_column(Integer)
    available_capital: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_selling_price_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_selling_price_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    target_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    maximum_landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    maximum_moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    maximum_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_launch_window: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acceptable_risk_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    marketplace: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category_restrictions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    supplier_geography_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list)
    minimum_evidence_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=opportunity_now, index=True
    )


class ProductOpportunityInputSnapshot(Base):
    __tablename__ = "intelligence_product_opportunity_input_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_state: Mapped[str] = mapped_column(String(32), default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=opportunity_now, index=True
    )


class ProductOpportunityAssessment(Base):
    __tablename__ = "intelligence_product_opportunity_assessments"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id", "version", name="uq_product_opportunity_assessment_version"
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
    version: Mapped[int] = mapped_column(Integer)
    constraint_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_constraint_versions.id", ondelete="RESTRICT"),
        index=True,
    )
    input_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_input_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    calculation_version: Mapped[str] = mapped_column(
        String(120), default="product-opportunity-foundation-v1"
    )
    evidence_state: Mapped[str] = mapped_column(String(32), default="unknown")
    status: Mapped[str] = mapped_column(String(32), default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=opportunity_now, index=True
    )
