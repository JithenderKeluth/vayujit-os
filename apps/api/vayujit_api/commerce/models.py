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


class InventoryItem(CommerceBase):
    """Canonical local stock balance for one sellable catalog SKU/location."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "internal_sku", "location_code", name="uq_inventory_item_sku_location"
        ),
        CheckConstraint("on_hand_quantity >= 0", name="ck_inventory_on_hand_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
        CheckConstraint("damaged_quantity >= 0", name="ck_inventory_damaged_nonnegative"),
        CheckConstraint(
            "reserved_quantity + damaged_quantity <= on_hand_quantity",
            name="ck_inventory_reserved_within_on_hand",
        ),
        CheckConstraint("low_stock_threshold >= 0", name="ck_inventory_low_stock_threshold"),
        Index("ix_inventory_item_owner_product", "owner_id", "product_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_product_variants.id", ondelete="SET NULL"),
        index=True,
    )
    internal_sku: Mapped[str] = mapped_column(String(100))
    location_code: Mapped[str] = mapped_column(String(80), default="default")
    unit: Mapped[str] = mapped_column(String(24), default="each")
    on_hand_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    damaged_quantity: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryMovement(CommerceBase):
    """Append-only stock movement; balances are reconstructed from its lineage."""

    __tablename__ = "inventory_movements"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "inventory_item_id", "idempotency_key", name="uq_inventory_movement_key"
        ),
        CheckConstraint(
            "movement_type IN ("
            "'opening_balance','receipt','adjustment','reservation','reservation_release',"
            "'shipment','return_receipt','damage','reconciliation')",
            name="ck_inventory_movement_type",
        ),
        CheckConstraint(
            "actor_type IN ('HUMAN','SYSTEM')", name="ck_inventory_movement_actor_type"
        ),
        Index("ix_inventory_movement_item_time", "inventory_item_id", "created_at"),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    location_code: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[str] = mapped_column(String(32))
    source_reference: Mapped[str | None] = mapped_column(String(240))
    actor_type: Mapped[str] = mapped_column(String(12), default="HUMAN")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(220))
    reason: Mapped[str] = mapped_column(String(500), default="")
    before_on_hand: Mapped[int] = mapped_column(Integer)
    after_on_hand: Mapped[int] = mapped_column(Integer)
    before_reserved: Mapped[int] = mapped_column(Integer)
    after_reserved: Mapped[int] = mapped_column(Integer)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class InventoryReservation(CommerceBase):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "inventory_item_id", "order_line_key", name="uq_inventory_reservation_line"
        ),
        UniqueConstraint(
            "owner_id", "inventory_item_id", "idempotency_key", name="uq_inventory_reservation_key"
        ),
        CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity"),
        CheckConstraint(
            "state IN ('active','released','consumed','failed')",
            name="ck_inventory_reservation_state",
        ),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="SET NULL"), index=True
    )
    order_line_key: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="active", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220))
    source_event_id: Mapped[str | None] = mapped_column(String(240))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class ChannelSkuMapping(CommerceBase):
    __tablename__ = "channel_sku_mappings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "account_id", "external_sku", name="uq_channel_sku_account_external"
        ),
        UniqueConstraint(
            "owner_id", "account_id", "inventory_item_id", name="uq_channel_sku_account_item"
        ),
        CheckConstraint(
            "status IN ('active','archived','conflict')", name="ck_channel_sku_mapping_status"
        ),
    )

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    external_sku: Mapped[str] = mapped_column(String(160))
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    effective_version: Mapped[int] = mapped_column(Integer, default=1)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class MarketplaceOrderEvent(CommerceBase):
    __tablename__ = "marketplace_order_events"
    __table_args__ = (
        UniqueConstraint("owner_id", "account_id", "event_id", name="uq_marketplace_order_event"),
        CheckConstraint(
            "status IN ('received','applied','duplicate','rejected','reconciliation_required')",
            name="ck_marketplace_order_event_status",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    event_id: Mapped[str] = mapped_column(String(240))
    remote_order_id: Mapped[str] = mapped_column(String(200), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="received", index=True)
    error_message: Mapped[str | None] = mapped_column(String(500))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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


class MarketplaceImportJob(CommerceBase):
    """Durable, owner-scoped read-only marketplace import execution.

    This is deliberately an execution ledger, not a second catalog/order or
    financial authority.  ``summary_json`` carries safe provider evidence and
    checkpoints while canonical records continue to be owned by the existing
    commerce projections.  Production providers are never contacted by this
    local certification path: only ``SYNTHETIC`` jobs may complete here.
    """

    __tablename__ = "marketplace_import_jobs"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "account_id",
            "operation",
            "idempotency_key",
            name="uq_marketplace_import_job_idempotency",
        ),
        CheckConstraint(
            "operation IN ('catalog','orders','inventory','financial')",
            name="ck_marketplace_import_job_operation",
        ),
        CheckConstraint(
            "mode IN ('SYNTHETIC','SANDBOX','LIVE_READ_ONLY')",
            name="ck_marketplace_import_job_mode",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','PARTIAL','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_marketplace_import_job_status",
        ),
        Index(
            "ix_marketplace_import_job_owner_account_time",
            "owner_id",
            "account_id",
            "created_at",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    operation: Mapped[str] = mapped_column(String(30), index=True)
    mode: Mapped[str] = mapped_column(String(30), default="SYNTHETIC")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(240))
    correlation_id: Mapped[str] = mapped_column(String(120), index=True)
    checkpoint_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, default=0)
    records_reused: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AmazonListingReview(CommerceBase):
    """Immutable HUMAN review of the exact Amazon listing payload.

    This is deliberately separate from content-artifact approval: an approved
    artifact proves content review, while this row records the seller's
    explicit decision to prepare this listing for controlled execution.
    """

    __tablename__ = "amazon_listing_reviews"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "listing_id", "payload_fingerprint", name="uq_amazon_listing_review_payload"
        ),
        CheckConstraint("status IN ('approved','revoked')", name="ck_amazon_listing_review_status"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT"), index=True
    )
    artifact_version: Mapped[int] = mapped_column(Integer)
    product_type: Mapped[str] = mapped_column(String(100))
    attributes_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", index=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AmazonListingExecutionAuthorization(CommerceBase):
    """Single-use HUMAN authorization for a specific reviewed payload."""

    __tablename__ = "amazon_listing_execution_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "listing_id",
            "operation",
            "idempotency_key",
            name="uq_amazon_listing_execution_auth_idempotency",
        ),
        CheckConstraint(
            "status IN ('issued','consumed','revoked','expired')",
            name="ck_amazon_listing_execution_auth_status",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("amazon_listing_reviews.id", ondelete="RESTRICT"), index=True
    )
    operation: Mapped[str] = mapped_column(String(40), default="listing_submit")
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="issued", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    issued_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )


class MarketplaceListingReview(CommerceBase):
    """HUMAN review of an exact listing payload for any supported marketplace.

    Amazon's original controls remain backwards-compatible, while new
    marketplaces use this shared authority instead of creating weaker,
    marketplace-specific approval tables.
    """

    __tablename__ = "marketplace_listing_reviews"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "listing_id",
            "payload_fingerprint",
            name="uq_marketplace_listing_review_payload",
        ),
        CheckConstraint(
            "status IN ('approved','revoked')",
            name="ck_marketplace_listing_review_status",
        ),
    )

    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT"), index=True
    )
    artifact_version: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", index=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceListingExecutionAuthorization(CommerceBase):
    """Durable, single-use HUMAN authorization for a reviewed payload."""

    __tablename__ = "marketplace_listing_execution_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "listing_id",
            "operation",
            "idempotency_key",
            name="uq_marketplace_listing_execution_auth_idempotency",
        ),
        CheckConstraint(
            "status IN ('issued','consumed','revoked','expired')",
            name="ck_marketplace_listing_execution_auth_status",
        ),
    )

    marketplace: Mapped[str] = mapped_column(String(30), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listing_reviews.id", ondelete="RESTRICT"),
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(40), default="listing_submit")
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="issued", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    issued_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )


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
