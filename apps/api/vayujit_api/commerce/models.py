"""Normalized, owner-scoped commerce persistence models.

Marketplace records intentionally remain separate from generic publishing
executions.  A Product is the local source of truth; remote identifiers and
state are projections owned by this module.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
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


class Marketplace(StrEnum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    MEESHO = "meesho"
    SHOPIFY = "shopify"


class ListingStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SUBMITTING = "submitting"
    ACTIVE = "active"
    PAUSED = "paused"
    REJECTED = "rejected"
    ERROR = "error"
    ARCHIVED = "archived"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    REFUNDED = "refunded"
    FAILED = "failed"


class AttributeType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    MULTI_SELECT = "multi_select"
    DIMENSIONS = "dimensions"
    WEIGHT = "weight"
    MONEY = "money"
    DATE = "date"


class CommerceBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketplaceAccount(CommerceBase):
    __tablename__ = "marketplace_accounts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "marketplace", "seller_account_id", name="uq_marketplace_account"
        ),
        CheckConstraint(
            "marketplace IN ('amazon','flipkart','meesho','shopify')",
            name="ck_marketplace_account_marketplace",
        ),
        CheckConstraint(
            "environment IN ('sandbox','production')", name="ck_marketplace_account_environment"
        ),
        CheckConstraint(
            "validation_status IN ('unknown','valid','invalid','expired')",
            name="ck_marketplace_account_validation",
        ),
    )

    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    seller_account_id: Mapped[str] = mapped_column(String(160))
    environment: Mapped[str] = mapped_column(String(20), default="sandbox")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    credential_status: Mapped[str] = mapped_column(String(20), default="missing")
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capabilities_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    configuration_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class MarketplaceCategory(CommerceBase):
    __tablename__ = "marketplace_categories"
    __table_args__ = (
        UniqueConstraint("owner_id", "account_id", "remote_id", name="uq_marketplace_category"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    remote_id: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(240))
    parent_remote_id: Mapped[str | None] = mapped_column(String(160))
    attributes_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class MarketplaceListing(CommerceBase):
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "account_id", "local_listing_id", name="uq_marketplace_listing_local"
        ),
        UniqueConstraint(
            "owner_id", "account_id", "remote_listing_id", name="uq_marketplace_listing_remote"
        ),
        CheckConstraint(
            "status IN ("
            "'draft','ready','submitting','active','paused','rejected','error','archived')",
            name="ck_marketplace_listing_status",
        ),
        CheckConstraint(
            "drift_state IN ("
            "'none','detected','review_required','remote_kept','local_overwrite_pending')",
            name="ck_marketplace_listing_drift",
        ),
        Index("ix_marketplace_listing_filters", "owner_id", "marketplace", "status"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    local_listing_id: Mapped[str] = mapped_column(String(100))
    remote_listing_id: Mapped[str | None] = mapped_column(String(200), index=True)
    marketplace_sku: Mapped[str | None] = mapped_column(String(160), index=True)
    catalog_identifier: Mapped[str | None] = mapped_column(String(200))
    parent_identifier: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    description_source: Mapped[str] = mapped_column(String(30), default="product")
    category: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(30), default=ListingStatus.DRAFT.value, index=True)
    publication_state: Mapped[str] = mapped_column(String(30), default="not_submitted")
    external_url: Mapped[str | None] = mapped_column(String(500))
    raw_safe_status: Mapped[str | None] = mapped_column(String(120))
    remote_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remote_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synchronized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    drift_state: Mapped[str] = mapped_column(String(40), default="none", index=True)
    content_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL")
    )
    content_artifact_version: Mapped[int | None] = mapped_column(Integer)
    safe_metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class MarketplaceAttributeDefinition(CommerceBase):
    __tablename__ = "marketplace_attribute_definitions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "category_id",
            "key",
            name="uq_marketplace_attribute_definition",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_categories.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(240))
    attribute_type: Mapped[str] = mapped_column(String(30))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options_json: Mapped[list[object]] = mapped_column(JSONB, default=list)


class MarketplaceListingAttribute(CommerceBase):
    __tablename__ = "marketplace_listing_attributes"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "listing_id", "definition_id", name="uq_marketplace_listing_attribute"
        ),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_attribute_definitions.id", ondelete="RESTRICT")
    )
    value_json: Mapped[object] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(20), default="valid")


class MarketplaceIdentifierMapping(CommerceBase):
    __tablename__ = "marketplace_identifier_mappings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "identifier_type",
            "identifier_value",
            name="uq_marketplace_identifier",
        ),
        UniqueConstraint(
            "owner_id",
            "account_id",
            "product_id",
            "variant_key",
            name="uq_marketplace_product_identifier",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    variant_key: Mapped[str | None] = mapped_column(String(120))
    identifier_type: Mapped[str] = mapped_column(String(50))
    identifier_value: Mapped[str] = mapped_column(String(240))


class MarketplaceVariant(CommerceBase):
    __tablename__ = "marketplace_variants"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "listing_id", "stable_variant_key", name="uq_marketplace_variant"
        ),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    stable_variant_key: Mapped[str] = mapped_column(String(120))
    sku: Mapped[str | None] = mapped_column(String(100))
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    compare_at_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    barcode: Mapped[str | None] = mapped_column(String(100))
    options_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    remote_variant_id: Mapped[str | None] = mapped_column(String(200))
    remote_sku: Mapped[str | None] = mapped_column(String(100))
    listing_state: Mapped[str] = mapped_column(String(30), default="draft")


class MarketplacePrice(CommerceBase):
    __tablename__ = "marketplace_prices"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_marketplace_price_amount"),)

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_variants.id", ondelete="CASCADE")
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    mrp_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    sale_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    minimum_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    maximum_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceInventory(CommerceBase):
    __tablename__ = "marketplace_inventory"
    __table_args__ = (
        UniqueConstraint("owner_id", "listing_id", "variant_id", name="uq_marketplace_inventory"),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_variants.id", ondelete="CASCADE")
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    marketplace_reported_quantity: Mapped[int | None] = mapped_column(Integer)
    local_target_quantity: Mapped[int | None] = mapped_column(Integer)
    synchronization_status: Mapped[str] = mapped_column(String(30), default="not_synced")
    last_synchronized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceOrder(CommerceBase):
    __tablename__ = "marketplace_orders"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "account_id", "remote_order_id", name="uq_marketplace_order_remote"
        ),
        CheckConstraint(
            "status IN ("
            "'pending','confirmed','processing','shipped','delivered','cancelled','returned','refunded','failed')",
            name="ck_marketplace_order_status",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    remote_order_id: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    payment_status: Mapped[str] = mapped_column(String(30), default="unknown")
    fulfilment_status: Mapped[str] = mapped_column(String(30), default="unfulfilled")
    buyer_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    totals_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    shipping_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remote_raw_status: Mapped[str | None] = mapped_column(String(120))


class MarketplaceOrderItem(CommerceBase):
    __tablename__ = "marketplace_order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_variants.id", ondelete="SET NULL")
    )
    marketplace_sku: Mapped[str | None] = mapped_column(String(100))
    title_snapshot: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class MarketplaceAddressSnapshot(CommerceBase):
    __tablename__ = "marketplace_address_snapshots"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    address_type: Mapped[str] = mapped_column(String(20))
    recipient_name: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str | None] = mapped_column(String(3))
    postal_code: Mapped[str | None] = mapped_column(String(20))


class MarketplaceFulfilment(CommerceBase):
    __tablename__ = "marketplace_fulfilments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    remote_fulfilment_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="unfulfilled")
    carrier: Mapped[str | None] = mapped_column(String(120))
    tracking_reference: Mapped[str | None] = mapped_column(String(200))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceCancellation(CommerceBase):
    __tablename__ = "marketplace_cancellations"
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[int | None] = mapped_column(Integer)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="requested")
    marketplace_reference: Mapped[str | None] = mapped_column(String(200))
    safe_notes: Mapped[str | None] = mapped_column(String(500))


class MarketplaceReturn(CommerceBase):
    __tablename__ = "marketplace_returns"
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[int | None] = mapped_column(Integer)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="requested")
    marketplace_reference: Mapped[str | None] = mapped_column(String(200))
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    safe_notes: Mapped[str | None] = mapped_column(String(500))


class MarketplaceRefund(CommerceBase):
    __tablename__ = "marketplace_refunds"
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    reason: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    marketplace_reference: Mapped[str | None] = mapped_column(String(200))


class MarketplaceFee(CommerceBase):
    __tablename__ = "marketplace_fees"
    __table_args__ = (
        CheckConstraint(
            "fee_type IN ("
            "'commission','shipping','fulfilment','storage','advertising','payment',"
            "'tax','withholding','penalty','refund','other')",
            name="ck_marketplace_fee_type",
        ),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="SET NULL"), index=True
    )
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_settlements.id", ondelete="SET NULL"),
        index=True,
    )
    fee_type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    description: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketplaceSettlement(CommerceBase):
    __tablename__ = "marketplace_settlements"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "remote_settlement_id",
            name="uq_marketplace_settlement_remote",
        ),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="RESTRICT"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    remote_settlement_id: Mapped[str] = mapped_column(String(200))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_withholding_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(30), default="settled")
    other_adjustment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    remote_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceSettlementLine(CommerceBase):
    __tablename__ = "marketplace_settlement_lines"
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_settlements.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="SET NULL")
    )
    line_type: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    description: Mapped[str | None] = mapped_column(String(500))


class MarketplaceDriftRecord(CommerceBase):
    __tablename__ = "marketplace_drift_records"
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(40))
    local_value_json: Mapped[object | None] = mapped_column(JSONB)
    remote_value_json: Mapped[object | None] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(30), default="detected")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceIdempotencyKey(CommerceBase):
    __tablename__ = "marketplace_idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "operation",
            "idempotency_key",
            name="uq_marketplace_idempotency",
        ),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    operation: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class MarketplaceMediaMapping(CommerceBase):
    __tablename__ = "marketplace_media_mappings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "listing_id",
            "media_id",
            name="uq_marketplace_media_mapping",
        ),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    image_output_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    position: Mapped[int] = mapped_column(Integer, default=0)
    alt_text: Mapped[str | None] = mapped_column(String(500))
    remote_media_id: Mapped[str | None] = mapped_column(String(200))
    remote_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="pending")
