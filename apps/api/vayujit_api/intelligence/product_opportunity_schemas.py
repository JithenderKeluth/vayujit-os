from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vayujit_api.intelligence.product_opportunity_models import (
    EVIDENCE_STATES,
    OPPORTUNITY_LIFECYCLES,
    RESEARCH_ORIGINS,
)


class OpportunityBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10_000)
    product_concept: str = Field(default="", max_length=10_000)
    category: str = Field(default="", max_length=120)
    subcategory: str = Field(default="", max_length=120)
    brand_strategy: str = Field(default="", max_length=120)
    target_marketplace: str = Field(default="", max_length=120)
    target_region: str = Field(default="", max_length=120)
    customer_segment: str = Field(default="", max_length=160)
    business_model: str = Field(default="", max_length=120)
    research_objective: str = Field(default="", max_length=10_000)
    origin: str = "manual"
    tags: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=10_000)
    product_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    research_run_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=180)

    @field_validator("origin")
    @classmethod
    def valid_origin(cls, value: str) -> str:
        value = value.casefold()
        if value not in RESEARCH_ORIGINS:
            raise ValueError("Unsupported research origin.")
        return value


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    product_concept: str | None = Field(default=None, max_length=10_000)
    category: str | None = Field(default=None, max_length=120)
    subcategory: str | None = Field(default=None, max_length=120)
    brand_strategy: str | None = Field(default=None, max_length=120)
    target_marketplace: str | None = Field(default=None, max_length=120)
    target_region: str | None = Field(default=None, max_length=120)
    customer_segment: str | None = Field(default=None, max_length=160)
    business_model: str | None = Field(default=None, max_length=120)
    research_objective: str | None = Field(default=None, max_length=10_000)
    tags: list[str] | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=10_000)
    lifecycle_status: str | None = None
    research_state: str | None = Field(default=None, max_length=32)
    evidence_state: str | None = Field(default=None, max_length=32)

    @field_validator("lifecycle_status")
    @classmethod
    def valid_lifecycle(cls, value: str | None) -> str | None:
        if value is not None and value.casefold() not in OPPORTUNITY_LIFECYCLES:
            raise ValueError("Unsupported opportunity lifecycle.")
        return value.casefold() if value else value

    @field_validator("evidence_state")
    @classmethod
    def valid_evidence_state(cls, value: str | None) -> str | None:
        value = value.casefold() if value else value
        if value is not None and value not in EVIDENCE_STATES:
            raise ValueError("Unsupported evidence state.")
        return value


class ConstraintCreate(BaseModel):
    available_capital: Decimal | None = Field(default=None, ge=0)
    target_selling_price_min: Decimal | None = Field(default=None, ge=0)
    target_selling_price_max: Decimal | None = Field(default=None, ge=0)
    target_margin: Decimal | None = Field(default=None, ge=0, le=1)
    maximum_landed_cost: Decimal | None = Field(default=None, ge=0)
    maximum_moq: Decimal | None = Field(default=None, ge=0)
    maximum_lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    target_launch_window: str | None = Field(default=None, max_length=120)
    acceptable_risk_level: str | None = Field(default=None, max_length=40)
    marketplace: str | None = Field(default=None, max_length=120)
    country_region: str | None = Field(default=None, max_length=120)
    category_restrictions: list[str] = Field(default_factory=list, max_length=100)
    supplier_geography_preferences: list[str] = Field(default_factory=list, max_length=100)
    minimum_evidence_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    idempotency_key: str | None = Field(default=None, max_length=180)


class ConstraintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    opportunity_id: uuid.UUID
    version: int
    available_capital: Decimal | None
    target_selling_price_min: Decimal | None
    target_selling_price_max: Decimal | None
    target_margin: Decimal | None
    maximum_landed_cost: Decimal | None
    maximum_moq: Decimal | None
    maximum_lead_time_days: int | None
    target_launch_window: str | None
    acceptable_risk_level: str | None
    marketplace: str | None
    country_region: str | None
    category_restrictions: list[str]
    supplier_geography_preferences: list[str]
    minimum_evidence_confidence: Decimal | None
    currency: str | None
    idempotency_key: str
    created_at: datetime


class AssessmentCreate(BaseModel):
    @field_validator("evidence_state")
    @classmethod
    def valid_evidence_state(cls, value: str) -> str:
        value = value.casefold()
        if value not in ("unknown", "partial", "insufficient_evidence", "available"):
            raise ValueError("Unsupported evidence state.")
        return value

    constraint_version_id: uuid.UUID | None = None
    evidence_state: str = "unknown"
    status: str = Field(default="created", max_length=32)
    calculation_version: str = Field(default="product-opportunity-foundation-v1", max_length=120)
    input_snapshot: dict[str, Any] = Field(default_factory=dict)


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    opportunity_id: uuid.UUID
    version: int
    constraint_version_id: uuid.UUID
    input_snapshot_id: uuid.UUID
    calculation_version: str
    evidence_state: str
    status: str
    created_at: datetime


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    product_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    research_run_id: uuid.UUID | None
    name: str
    description: str
    product_concept: str
    category: str
    subcategory: str
    brand_strategy: str
    target_marketplace: str
    target_region: str
    customer_segment: str
    business_model: str
    research_objective: str
    origin: str
    tags: list[str]
    notes: str
    lifecycle_status: str
    research_state: str
    evidence_state: str
    current_constraint_version_id: uuid.UUID | None
    current_assessment_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class OpportunityDetail(OpportunityResponse):
    constraints: list[ConstraintResponse]
    assessments: list[AssessmentResponse]
