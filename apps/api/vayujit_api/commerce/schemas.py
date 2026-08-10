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


def capabilities_for(marketplace: str) -> list[str]:
    return list(CAPABILITIES.get(marketplace, []))
