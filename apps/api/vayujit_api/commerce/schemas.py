"""Public commerce API contracts with safe, bounded responses."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vayujit_api.commerce.models import Marketplace

CAPABILITIES: dict[str, list[str]] = {
    "amazon": [
        "listing_create",
        "listing_update",
        "inventory",
        "pricing",
        "orders",
        "returns",
        "settlements",
        "media",
        "analytics",
    ],
    "flipkart": [
        "listing_create",
        "listing_update",
        "inventory",
        "pricing",
        "orders",
        "returns",
        "settlements",
        "media",
        "analytics",
    ],
    "meesho": [
        "listing_create",
        "listing_update",
        "inventory",
        "pricing",
        "orders",
        "returns",
        "settlements",
        "media",
        "analytics",
    ],
    "shopify": [
        "listing_create",
        "listing_update",
        "inventory",
        "pricing",
        "orders",
        "fulfilment",
        "returns",
        "settlements",
        "media",
        "analytics",
    ],
}


class AccountCreate(BaseModel):
    marketplace: Marketplace
    display_name: str = Field(min_length=1, max_length=160)
    seller_account_id: str = Field(min_length=1, max_length=160)
    environment: str = Field(default="sandbox", pattern="^(sandbox|production)$")
    credentials: dict[str, str] = Field(default_factory=dict, max_length=12)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    marketplace: str
    display_name: str
    seller_account_id: str
    environment: str
    enabled: bool
    credential_status: str
    validation_status: str
    last_validated_at: datetime | None
    capabilities: list[str]
    # Connectivity is intentionally explicit.  A locally validated fake
    # connector never becomes a real marketplace connection.
    connection_state: str = "AUTHORIZATION_REQUIRED"
    permission_state: str = "UNVERIFIED"
    transport_mode: str = "SYNTHETIC"
    created_at: datetime
    updated_at: datetime


class ListingCreate(BaseModel):
    product_id: uuid.UUID
    brand_id: uuid.UUID
    account_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=240)
    marketplace_sku: str | None = Field(default=None, max_length=160)
    artifact_id: uuid.UUID | None = None
    idempotency_key: str = Field(default="", max_length=200)


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=240)
    marketplace_sku: str | None = Field(default=None, max_length=160)
    status: str | None = Field(
        default=None, pattern="^(draft|ready|active|paused|rejected|error|archived)$"
    )
    idempotency_key: str = Field(default="", max_length=200)


class ListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    product_id: uuid.UUID
    account_id: uuid.UUID
    marketplace: str
    local_listing_id: str
    remote_listing_id: str | None
    marketplace_sku: str | None
    catalog_identifier: str | None
    title: str
    description_source: str
    category: str | None
    status: str
    publication_state: str
    external_url: str | None
    last_synchronized_at: datetime | None
    drift_state: str
    content_artifact_id: uuid.UUID | None
    content_artifact_version: int | None
    created_at: datetime
    updated_at: datetime


class InventoryUpdate(BaseModel):
    listing_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    available_quantity: int = Field(ge=0, le=10_000_000)
    reserved_quantity: int = Field(default=0, ge=0, le=10_000_000)
    idempotency_key: str = Field(default="", max_length=200)


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    variant_id: uuid.UUID | None
    product_id: uuid.UUID
    available_quantity: int
    reserved_quantity: int
    marketplace_reported_quantity: int | None
    local_target_quantity: int | None
    synchronization_status: str
    last_synchronized_at: datetime | None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    marketplace: str
    remote_order_id: str
    status: str
    payment_status: str
    fulfilment_status: str
    totals: dict[str, Any]
    ordered_at: datetime
    buyer_summary: dict[str, str]


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    marketplace: str
    remote_settlement_id: str
    period_start: datetime
    period_end: datetime
    gross_amount: Decimal
    fee_amount: Decimal
    refund_amount: Decimal
    tax_withholding_amount: Decimal
    net_amount: Decimal
    currency: str


class CategoryResponse(BaseModel):
    id: uuid.UUID
    remote_id: str
    name: str
    parent_remote_id: str | None
    attributes: list[dict[str, Any]]


class AnalyticsResponse(BaseModel):
    gross_sales: Decimal
    fees: Decimal
    refunds: Decimal
    net_contribution: Decimal
    estimated_profit: Decimal | None
    profit_status: str
    order_count: int
    active_listing_count: int
    low_stock_count: int
    sales_by_marketplace: dict[str, Decimal]


class ConnectorResult(BaseModel):
    status: str
    idempotent_reuse: bool = False
    message: str
    resource_id: uuid.UUID | None = None


class DriftResponse(BaseModel):
    listing_id: uuid.UUID
    drift_state: str
    fields: list[dict[str, Any]]


class InventoryItemCreate(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None
    internal_sku: str = Field(min_length=1, max_length=100)
    location_code: str = Field(default="default", min_length=1, max_length=80)
    unit: str = Field(default="each", min_length=1, max_length=24)
    opening_quantity: int = Field(default=0, ge=0, le=2_000_000_000)
    low_stock_threshold: int = Field(default=0, ge=0, le=2_000_000_000)
    idempotency_key: str = Field(min_length=1, max_length=220)


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    internal_sku: str
    location_code: str
    unit: str
    on_hand_quantity: int
    reserved_quantity: int
    damaged_quantity: int
    available_to_promise: int
    low_stock_threshold: int
    version: int
    last_reconciled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InventoryAdjustmentRequest(BaseModel):
    delta: int = Field(ne=0, ge=-2_000_000_000, le=2_000_000_000)
    reason: str = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=220)


class InventoryReserveRequest(BaseModel):
    order_line_key: str = Field(min_length=1, max_length=240)
    quantity: int = Field(gt=0, le=2_000_000_000)
    idempotency_key: str = Field(min_length=1, max_length=220)
    order_id: uuid.UUID | None = None
    source_event_id: str | None = Field(default=None, max_length=240)


class InventoryReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    order_id: uuid.UUID | None
    order_line_key: str
    quantity: int
    state: str
    created_at: datetime
    updated_at: datetime


class InventoryMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity: int
    movement_type: str
    source_reference: str | None
    actor_type: str
    reason: str
    before_on_hand: int
    after_on_hand: int
    before_reserved: int
    after_reserved: int
    created_at: datetime


class ChannelSkuMappingCreate(BaseModel):
    account_id: uuid.UUID
    inventory_item_id: uuid.UUID
    external_sku: str = Field(min_length=1, max_length=160)
    listing_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=220)


class ChannelSkuMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    inventory_item_id: uuid.UUID
    marketplace: str
    external_sku: str
    listing_id: uuid.UUID | None
    status: str
    effective_version: int
    provenance_json: dict[str, object]


class FakeOrderLine(BaseModel):
    external_sku: str = Field(min_length=1, max_length=160)
    quantity: int = Field(gt=0, le=2_000_000_000)
    unit_price: Decimal = Field(ge=0)


class FakeOrderEventRequest(BaseModel):
    account_id: uuid.UUID
    external_order_id: str = Field(min_length=1, max_length=200)
    event_id: str = Field(min_length=1, max_length=240)
    event_type: str = Field(pattern="^(new_order|cancel|ship|return)$")
    event_version: int = Field(default=1, ge=1)
    lines: list[FakeOrderLine] = Field(default_factory=list, max_length=50)
    reason: str | None = Field(default=None, max_length=240)


class UnifiedOrderResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    marketplace: str
    remote_order_id: str
    status: str
    fulfilment_status: str
    reservation_state: str
    line_count: int
    fake_provider: bool
    ordered_at: datetime


class ReconciliationResponse(BaseModel):
    inventory_items: int
    low_stock_items: int
    out_of_stock_items: int
    active_reservations: int
    reservation_failures: int
    unmapped_order_lines: int
    stale_provider_events: int
    next_actions: list[str]


def capabilities_for(marketplace: str) -> list[str]:
    return list(CAPABILITIES.get(marketplace, []))
