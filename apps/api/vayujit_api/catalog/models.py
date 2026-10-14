"""Durable, owner-scoped Seller Catalog and listing-preparation records.

These records are intentionally separate from remote marketplace listings.  A
catalog product and listing draft never imply publication or supplier
verification; remote marketplace IDs are not stored here.
"""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class CatalogProductLineage(Base):
    __tablename__ = "catalog_product_lineages"
    __table_args__ = (
        UniqueConstraint("owner_id", "product_id", name="uq_catalog_lineage_product"),
        CheckConstraint(
            "source_kind IN ('manual','opportunity')", name="ck_catalog_lineage_source_kind"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_business_agent_goals.id", ondelete="SET NULL"),
        index=True,
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunity_assessments.id", ondelete="SET NULL"),
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(String(24), default="manual")
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogProductVariant(Base):
    __tablename__ = "catalog_product_variants"
    __table_args__ = (
        UniqueConstraint("owner_id", "product_id", "variant_key", name="uq_catalog_variant_key"),
        UniqueConstraint("owner_id", "sku", name="uq_catalog_variant_sku"),
        CheckConstraint(
            "status IN ('draft','active','archived')", name="ck_catalog_variant_status"
        ),
        CheckConstraint(
            "price_amount IS NULL OR price_amount >= 0", name="ck_catalog_variant_price"
        ),
        Index("ix_catalog_variant_product", "owner_id", "product_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    variant_key: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160), default="")
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option_values: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    image_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogProductImage(Base):
    """Owner-scoped product image selection backed by the secure MediaAsset.

    The association stores presentation metadata only.  The bytes, MIME and
    private preview remain owned by ``MediaAsset``/``/media`` so catalog code
    never creates a second asset or storage authority.
    """

    __tablename__ = "catalog_product_images"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "product_id", "media_id", name="uq_catalog_product_image_media"
        ),
        CheckConstraint("position >= 0", name="ck_catalog_product_image_position"),
        CheckConstraint("version >= 1", name="ck_catalog_product_image_version"),
        Index("ix_catalog_product_image_order", "owner_id", "product_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(default=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogSupplierAssociation(Base):
    __tablename__ = "catalog_supplier_associations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "product_id", "supplier_id", name="uq_catalog_supplier_product"
        ),
        CheckConstraint(
            "status IN ('candidate','review_required','accepted','archived')",
            name="ck_catalog_supplier_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intelligence_suppliers.id", ondelete="RESTRICT"), index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_product_opportunities.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), default="review_required")
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogListingDraft(Base):
    __tablename__ = "catalog_listing_drafts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "product_id", "channel", name="uq_catalog_listing_product_channel"
        ),
        CheckConstraint("channel IN ('amazon_in','flipkart')", name="ck_catalog_listing_channel"),
        CheckConstraint(
            "status IN ('draft','incomplete','needs_review',"
            "'approved_for_future_submission','blocked','archived')",
            name="ck_catalog_listing_status",
        ),
        CheckConstraint(
            "human_review_state IN ('not_reviewed','needs_review','approved')",
            name="ck_catalog_listing_human_review",
        ),
        Index("ix_catalog_listing_owner_status", "owner_id", "channel", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(24), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    bullets: Mapped[list[object]] = mapped_column(JSONB, default=list)
    category: Mapped[str | None] = mapped_column(String(240), nullable=True)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    image_refs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    intended_price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    intended_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    compliance: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)
    validation_state: Mapped[str] = mapped_column(String(24), default="incomplete")
    readiness_state: Mapped[str] = mapped_column(String(40), default="BLOCKED")
    human_review_state: Mapped[str] = mapped_column(String(24), default="not_reviewed")
    status: Mapped[str] = mapped_column(String(32), default="incomplete", index=True)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(220), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
