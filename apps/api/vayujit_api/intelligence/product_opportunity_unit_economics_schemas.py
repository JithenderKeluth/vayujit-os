"""PR-5C explainable unit-economics request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vayujit_api.intelligence.product_opportunity_unit_economics_models import (
    CALCULATION_VERSION,
)

PROVENANCE = {
    "OBSERVED",
    "SOURCE_PROVIDED_CLAIM",
    "SELLER_SCENARIO",
    "DETERMINISTIC_TEST",
    "ASSUMED",
}
BASES = {"PER_UNIT", "PER_ORDER", "PER_SHIPMENT", "PERCENT_OF_SELLING_PRICE"}


class FXScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=0)
    provenance: Literal["OBSERVED", "SELLER_SCENARIO", "DETERMINISTIC_TEST"] = "DETERMINISTIC_TEST"
    reason: str | None = Field(default=None, max_length=4000)

    @field_validator("from_currency", "to_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("Currency must be an alphabetic three-letter code.")
        return normalized

    @field_validator("rate")
    @classmethod
    def finite_rate(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("FX rate must be finite.")
        return value


class SellingCostComponent(BaseModel):
    """One explicit cost-to-sell component.

    ``amount`` is per-unit for PER_UNIT, per order/shipment for the fixed
    bases, and ignored for percentage components. ``rate`` is a percentage,
    not a fraction (10 means 10%).
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    basis: str
    amount: Decimal | None = None
    rate: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    required: bool = True
    provenance: str = "ASSUMED"
    marker: str = "DETERMINISTIC_TEST"
    trust_state: str = "ASSUMED"
    source_reference: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=4000)

    @field_validator("basis")
    @classmethod
    def normalize_basis(cls, value: str) -> str:
        normalized = value.upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "PERCENT": "PERCENT_OF_SELLING_PRICE",
            "PERCENTAGE": "PERCENT_OF_SELLING_PRICE",
            "PER_ITEM": "PER_UNIT",
            "UNIT": "PER_UNIT",
            "ORDER": "PER_ORDER",
            "SHIPMENT": "PER_SHIPMENT",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in BASES:
            raise ValueError(f"Unsupported selling-cost basis: {value}")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("Currency must be an alphabetic three-letter code.")
        return normalized

    @field_validator("provenance")
    @classmethod
    def normalize_provenance(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in PROVENANCE:
            raise ValueError(f"Unsupported selling-cost provenance: {value}")
        return normalized

    @field_validator("amount", "rate")
    @classmethod
    def finite_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Selling-cost amounts must be finite.")
        return value


class UnitEconomicsCalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    landed_cost_calculation_id: uuid.UUID | None = None
    commercial_readiness_snapshot_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    scenario_key: str = Field(default="seller-scenario", min_length=1, max_length=120)
    selling_price: Decimal | None = None
    selling_price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    selling_price_provenance: str = "SELLER_SCENARIO"
    quantity: Decimal | None = Field(default=None)
    selling_cost_components: list[SellingCostComponent] = Field(default_factory=list, max_length=30)
    fx: list[FXScenario] = Field(default_factory=list, max_length=5)
    calculation_version: str = Field(default=CALCULATION_VERSION, min_length=1, max_length=120)

    @field_validator("selling_price_currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("selling_price_provenance")
    @classmethod
    def valid_price_provenance(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in PROVENANCE:
            raise ValueError(f"Unsupported selling-price provenance: {value}")
        return normalized

    @field_validator("selling_price", "quantity")
    @classmethod
    def finite_values(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("Unit-economics values must be finite.")
        return value


class UnitEconomicsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    landed_cost_calculation_id: uuid.UUID | None = None
    commercial_readiness_snapshot_id: uuid.UUID | None = None
    scenario_key: str
    calculation_version: str
    calculation_revision: int = 1
    status: str
    input_fingerprint: str | None = None
    idempotency_key: str | None = None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    readiness: dict[str, Any] = Field(default_factory=dict)
    selling_price: Decimal | None = None
    selling_price_currency: str | None = None
    selling_price_provenance: str
    base_currency: str | None = None
    quantity: Decimal | None = None
    selling_cost_components: list[Any] = Field(default_factory=list)
    per_unit_landed_cost: Decimal | None = None
    per_unit_selling_cost: Decimal | None = None
    per_unit_total_cost: Decimal | None = None
    per_unit_contribution: Decimal | None = None
    contribution_margin: Decimal | None = None
    order_economics: dict[str, Any] = Field(default_factory=dict)
    capital_available: Decimal | None = None
    capital_currency: str | None = None
    capital_required: Decimal | None = None
    capital_headroom: Decimal | None = None
    capital_shortfall: Decimal | None = None
    capital_fit_status: str
    unknown_excluded: list[Any] = Field(default_factory=list)
    contradictions: list[Any] = Field(default_factory=list)
    limitations: list[Any] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    notes: str = ""
