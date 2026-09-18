from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vayujit_api.intelligence.product_opportunity_commercial_models import CALCULATION_VERSION


class FXContext(BaseModel):
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=0)
    source: str = Field(min_length=1, max_length=500)
    observed_at: datetime | None = None
    valid_until: datetime | None = None

    @field_validator("from_currency", "to_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("rate")
    @classmethod
    def finite_rate(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("FX rate must be finite.")
        return value


class CommercialCalculateRequest(BaseModel):
    selling_price: Decimal | None = Field(default=None, ge=0)
    selling_price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    fee_per_unit: Decimal | None = Field(default=None, ge=0)
    fixed_costs: Decimal | None = Field(default=None, ge=0)
    moq: Decimal | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    landed_cost_estimate_id: uuid.UUID | None = None
    scenario_version_id: uuid.UUID | None = None
    supplier_product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    supplier_quote_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    fx: list[FXContext] = Field(default_factory=list, max_length=3)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=220)

    @field_validator("selling_price_currency")
    @classmethod
    def uppercase_selling_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("selling_price", "fee_per_unit", "fixed_costs", "moq")
    @classmethod
    def finite_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Commercial amounts must be finite.")
        return value

    @model_validator(mode="after")
    def require_selling_currency(self) -> CommercialCalculateRequest:
        if self.selling_price is not None and self.selling_price_currency is None:
            raise ValueError("Selling-price currency is required for a modeled selling price.")
        if self.landed_cost_estimate_id and self.scenario_version_id:
            raise ValueError("Choose one landed-cost reference.")
        return self


class CommercialDimension(BaseModel):
    dimension: str
    value: Any = None
    classification: str
    evidence_state: str
    explanation: str
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    calculation_version: str = CALCULATION_VERSION


class CommercialOutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    calculation_version: str
    constraint_snapshot: dict[str, object]
    input_snapshot: dict[str, object]
    dimensions: list[CommercialDimension]
    economics: dict[str, object]
    sensitivity: dict[str, object]
    evidence_summary: dict[str, object]
    research_gaps: list[dict[str, object]]
    idempotency_key: str
    created_at: datetime
    notes: str


class CommercialHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    calculation_version: str
    created_at: datetime
    economics: dict[str, object]
