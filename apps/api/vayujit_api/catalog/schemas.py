from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vayujit_api.products.schemas import ProductResponse

Channel = Literal["amazon_in", "flipkart"]
CatalogStatus = Literal[
    "draft", "incomplete", "needs_review", "approved_for_future_submission", "blocked", "archived"
]


class LineageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_kind: str
    opportunity_id: uuid.UUID | None
    goal_id: uuid.UUID | None
    assessment_id: uuid.UUID | None
    provenance_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class VariantCreate(BaseModel):
    variant_key: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=160)
    sku: str | None = Field(default=None, max_length=100)
    option_values: dict[str, object] = Field(default_factory=dict)
    attributes: dict[str, object] = Field(default_factory=dict)
    image_refs: list[object] = Field(default_factory=list, max_length=20)
    price_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("sku", "currency")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class VariantUpdate(VariantCreate):
    version: int = Field(ge=1)
    status: Literal["draft", "active", "archived"] | None = None


class VariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    variant_key: str
    title: str
    sku: str | None
    option_values: dict[str, object]
    attributes: dict[str, object]
    image_refs: list[object]
    price_amount: Decimal | None
    currency: str | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class ProductImageCreate(BaseModel):
    media_id: uuid.UUID
    alt_text: str | None = Field(default=None, max_length=500)
    position: int = Field(default=0, ge=0, le=99)
    is_primary: bool = False


class ProductImageUpdate(BaseModel):
    version: int = Field(ge=1)
    alt_text: str | None = Field(default=None, max_length=500)
    position: int | None = Field(default=None, ge=0, le=99)
    is_primary: bool | None = None


class ProductImageResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    media_id: uuid.UUID
    alt_text: str | None
    position: int
    is_primary: bool
    version: int
    preview_url: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    status: str
    created_at: datetime
    updated_at: datetime


class SupplierAssociationCreate(BaseModel):
    supplier_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    status: Literal["candidate", "review_required", "accepted", "archived"] = "review_required"
    provenance_json: dict[str, object] = Field(default_factory=dict)


class SupplierAssociationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: uuid.UUID
    opportunity_id: uuid.UUID | None
    status: str
    provenance_json: dict[str, object]
    created_at: datetime
    updated_at: datetime


class ListingDraftCreate(BaseModel):
    channel: Channel
    title: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=20_000)
    bullets: list[str] = Field(default_factory=list, max_length=10)
    category: str | None = Field(default=None, max_length=240)
    attributes: dict[str, object] = Field(default_factory=dict)
    image_refs: list[object] = Field(default_factory=list, max_length=20)
    intended_price_amount: Decimal | None = Field(default=None, ge=0)
    intended_currency: str | None = Field(default=None, min_length=3, max_length=3)
    compliance: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=220)

    @field_validator("intended_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ListingDraftUpdate(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    bullets: list[str] | None = Field(default=None, max_length=10)
    category: str | None = Field(default=None, max_length=240)
    attributes: dict[str, object] | None = None
    image_refs: list[object] | None = Field(default=None, max_length=20)
    intended_price_amount: Decimal | None = Field(default=None, ge=0)
    intended_currency: str | None = Field(default=None, min_length=3, max_length=3)
    compliance: dict[str, object] | None = None

    @field_validator("intended_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class ListingReviewRequest(BaseModel):
    version: int = Field(ge=1)
    decision: Literal["approve", "return_for_changes"]


class ListingDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    channel: str
    title: str
    description: str
    bullets: list[object]
    category: str | None
    attributes: dict[str, object]
    image_refs: list[object]
    intended_price_amount: Decimal | None
    intended_currency: str | None
    compliance: dict[str, object]
    missing_fields: list[object]
    validation_state: str
    readiness_state: str
    human_review_state: str
    status: CatalogStatus
    provenance_json: dict[str, object]
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class CatalogProductResponse(BaseModel):
    product: ProductResponse
    lineage: LineageResponse | None
    variants: list[VariantResponse]
    images: list[ProductImageResponse]
    supplier_associations: list[SupplierAssociationResponse]
    listing_drafts: list[ListingDraftResponse]


class OpportunityConversionRequest(BaseModel):
    brand_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    product_type: Literal["physical", "digital", "service", "affiliate"] = "physical"
    sku: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=220)


class CatalogReadinessResponse(BaseModel):
    product_id: uuid.UUID
    readiness: str
    blockers: list[str]
    next_actions: list[str]
    external_publication: str = "DISABLED_IN_PR_SOS_01"


class CatalogEconomicsResponse(BaseModel):
    product_id: uuid.UUID
    available: bool
    opportunity_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    projection: dict[str, object] | None = None
    reason: str | None = None
