"""Durable, normalized IndiaMART read-only discovery records."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class IndiaMartDiscoveryRequest(Base):
    __tablename__ = "intelligence_indiamart_discovery_requests"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_indiamart_discovery_request_idempotency"
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
    query: Mapped[str] = mapped_column(String(240))
    country_code: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(120))
    result_limit: Mapped[int] = mapped_column(default=10)
    provider: Mapped[str] = mapped_column(String(32), default="INDIAMART")
    mode: Mapped[str] = mapped_column(String(32), default="LOCAL_FIXTURE")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    result_count: Mapped[int] = mapped_column(default=0)
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IndiaMartDiscoveryResult(Base):
    __tablename__ = "intelligence_indiamart_discovery_results"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "provider_result_id",
            name="uq_indiamart_discovery_result_identity",
        ),
        UniqueConstraint(
            "owner_id",
            "request_id",
            "idempotency_key",
            name="uq_indiamart_result_request_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_indiamart_discovery_requests.id", ondelete="CASCADE"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    offering_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_supplier_products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), default="INDIAMART")
    provider_result_id: Mapped[str] = mapped_column(String(180))
    supplier_name: Mapped[str] = mapped_column(String(240))
    listing_name: Mapped[str] = mapped_column(String(240))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(240))
    category: Mapped[str | None] = mapped_column(String(160))
    price_claim: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    moq_claim: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    moq_unit: Mapped[str | None] = mapped_column(String(40))
    lead_time_claim: Mapped[str | None] = mapped_column(String(120))
    availability_claim: Mapped[str | None] = mapped_column(String(120))
    verification_claim: Mapped[str | None] = mapped_column(String(160))
    identity_match: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    product_match: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    freshness_status: Mapped[str] = mapped_column(String(24), default="fresh")
    classification: Mapped[str] = mapped_column(String(80), default="DISCOVERY_ONLY")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    observation_key: Mapped[str] = mapped_column(String(240))
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
