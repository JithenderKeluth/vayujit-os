"""Typed 13F economic scenario and sensitivity contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
BoundedMoney = Annotated[Decimal, Field(ge=0, le=Decimal("1e12"), max_digits=24, decimal_places=8)]
BoundedRate = Annotated[Decimal, Field(gt=0, le=Decimal("1e6"), max_digits=24, decimal_places=12)]


class ScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, hide_input_in_errors=True)


class ScenarioOverrides(ScenarioInput):
    target_quantity: int | None = Field(default=None, gt=0, le=100_000_000, strict=True)
    product_unit_cost: BoundedMoney | None = None
    component_category: (
        Literal[
            "PRODUCT_COST",
            "FREIGHT",
            "BROKERAGE",
            "INSPECTION",
            "OTHER",
            "IMPORT_DUTY",
            "IMPORT_TAX",
            "SURCHARGE",
        ]
        | None
    ) = None
    component_amount: BoundedMoney | None = None
    fx_snapshot_id: uuid.UUID | None = None
    fx_rate: BoundedRate | None = None
    freight_snapshot_id: uuid.UUID | None = None
    freight_amount: BoundedMoney | None = None
    customs_tax_snapshot_id: uuid.UUID | None = None
    duty_rate: Annotated[Decimal, Field(ge=0, le=1, max_digits=12, decimal_places=8)] | None = None
    tax_rate: Annotated[Decimal, Field(ge=0, le=1, max_digits=12, decimal_places=8)] | None = None
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_component_pair(self) -> ScenarioOverrides:
        if (self.component_category is None) != (self.component_amount is None):
            raise ValueError("component_category and component_amount must be supplied together.")
        if self.fx_rate is not None and self.fx_snapshot_id is None:
            raise ValueError("fx_rate requires an explicit FX snapshot reference.")
        if self.freight_amount is not None and self.freight_snapshot_id is None:
            raise ValueError("freight_amount requires an explicit freight snapshot reference.")
        if (
            self.duty_rate is not None or self.tax_rate is not None
        ) and self.customs_tax_snapshot_id is None:
            raise ValueError(
                "Duty/tax rate overrides require an explicit customs/tax snapshot reference."
            )
        return self


class EconomicScenarioCreate(ScenarioInput):
    idempotency_key: str = Field(min_length=3, max_length=180, pattern=r"^[a-zA-Z0-9:_-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    baseline_calculation_id: uuid.UUID
    sourcing_scenario_id: uuid.UUID | None = None
    overrides: ScenarioOverrides


class EconomicScenarioRun(ScenarioInput):
    idempotency_key: str = Field(min_length=3, max_length=180, pattern=r"^[a-zA-Z0-9:_-]+$")


SensitivityDimension = Literal[
    "product_unit_cost", "target_quantity", "fx_rate", "freight_amount", "duty_rate", "tax_rate"
]


class SensitivityPoint(ScenarioInput):
    dimension: SensitivityDimension
    value: Decimal = Field(ge=0, le=Decimal("1e12"), max_digits=24, decimal_places=8)

    @model_validator(mode="after")
    def validate_value(self) -> SensitivityPoint:
        if self.dimension in {"fx_rate"} and self.value <= 0:
            raise ValueError("FX sensitivity values must be greater than zero.")
        if self.dimension == "target_quantity" and (
            self.value <= 0 or self.value != self.value.to_integral_value()
        ):
            raise ValueError("Quantity sensitivity values must be positive whole numbers.")
        if self.dimension in {"duty_rate", "tax_rate"} and self.value > 1:
            raise ValueError("Duty and tax sensitivity values must be fractions from zero to one.")
        return self


class EconomicSensitivityCreate(ScenarioInput):
    idempotency_key: str = Field(min_length=3, max_length=180, pattern=r"^[a-zA-Z0-9:_-]+$")
    points: list[SensitivityPoint] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def one_variable_at_a_time(self) -> EconomicSensitivityCreate:
        dimensions = [point.dimension for point in self.points]
        if len(set(dimensions)) != 1:
            raise ValueError("A sensitivity run must vary one dimension at a time.")
        if len({str(point.value) for point in self.points}) != len(self.points):
            raise ValueError("Sensitivity values must be unique.")
        return self
