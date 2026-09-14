"""Bounded sourcing scenario contracts; amounts serialize as decimal strings."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, le=Decimal("1e12"), max_digits=19, decimal_places=6)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=9, decimal_places=6)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
ScenarioType = Literal[
    "SINGLE_SUPPLIER",
    "MULTI_SUPPLIER",
    "LOWEST_COST",
    "LOWEST_CAPITAL",
    "FASTEST_SUPPLY",
    "HIGHEST_MARGIN",
    "LOWEST_RISK",
    "MAXIMUM_RESILIENCE",
    "BALANCED",
    "CUSTOM",
]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Command(StrictInput):
    idempotency_key: str = Field(min_length=8, max_length=160, pattern=r"^[a-zA-Z0-9:_-]+$")


class ContextCreate(Command):
    shortlist_version_id: uuid.UUID
    base_currency: Currency
    target_market: str = Field(min_length=1, max_length=80)
    target_channel: str = Field(min_length=1, max_length=80)
    target_quantity: int = Field(gt=0, le=100000000, strict=True)
    target_sale_price: Money | None = None
    margin_target: Percent | None = None
    capital_limit: Money | None = None
    risk_tolerance: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"


class Allocation(StrictInput):
    supplier_id: uuid.UUID
    due_diligence_id: uuid.UUID
    quantity: int = Field(gt=0, le=100000000, strict=True)
    unit_price: Money | None = None
    currency: Currency
    moq: int | None = Field(default=None, gt=0, le=100000000, strict=True)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650, strict=True)
    availability: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"] = "UNKNOWN"
    incoterm: Literal["EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP"] | None = None
    assumption_reason: str = Field(min_length=3, max_length=500)


class FxAssumption(StrictInput):
    from_currency: Currency
    rate: Annotated[Decimal, Field(gt=0, le=1000000, max_digits=19, decimal_places=10)]
    reference: str = Field(min_length=3, max_length=160)
    observed_at: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def aware_interval(self) -> FxAssumption:
        if self.observed_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("FX timestamps require timezone offsets.")
        if self.observed_at >= self.valid_until:
            raise ValueError("FX validity interval is invalid.")
        return self


class ScenarioCreate(Command):
    name: str = Field(min_length=1, max_length=120)
    scenario_type: ScenarioType = "CUSTOM"
    allocations: list[Allocation] = Field(min_length=1, max_length=20)
    logistics_mode: Literal["AIR", "SEA", "EXPRESS", "LOCAL", "CUSTOM"]
    # Explicit total base-currency charges, not per-unit charges.
    costs: dict[str, Money] = Field(default_factory=dict, max_length=13)
    fx: list[FxAssumption] = Field(default_factory=list, max_length=20)
    channel_fee_per_unit: Money | None = None
    payment_fee_per_unit: Money | None = None
    returns_per_unit: Money | None = None
    advertising_per_unit: Money | None = None
    working_capital_buffer: Money | None = None
    logistics_days: int | None = Field(default=None, ge=0, le=3650, strict=True)
    customs_days: int | None = Field(default=None, ge=0, le=3650, strict=True)
    domestic_days: int | None = Field(default=None, ge=0, le=3650, strict=True)

    @model_validator(mode="after")
    def unique_allocations(self) -> ScenarioCreate:
        if len({a.supplier_id for a in self.allocations}) != len(self.allocations):
            raise ValueError("Duplicate supplier allocation.")
        if len({f.from_currency for f in self.fx}) != len(self.fx):
            raise ValueError("Duplicate FX currency.")
        return self


class GenerateRequest(Command):
    """Explicit commercial assumptions for deterministic baseline candidates."""

    basis: ScenarioCreate


class VersionCommand(Command):
    expected_version: int = Field(gt=0, strict=True)
    reason: str = Field(min_length=3, max_length=500)


class DecisionRequest(VersionCommand):
    action: Literal["approve", "reject", "review", "archive"]
    confirm: Literal[True]


class SensitivityRequest(VersionCommand):
    dimension: Literal[
        "purchase", "freight", "fx", "sale_price", "returns", "advertising", "lead_time"
    ]
    change_percent: Annotated[Decimal, Field(ge=-20, le=20, decimal_places=2)]
