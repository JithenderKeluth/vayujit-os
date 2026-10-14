"""PR-5B readiness-gated landed-cost request contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LandedCostCalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    base_currency: str = Field(min_length=3, max_length=3)
    target_quantity: Decimal = Field(gt=0)
    quantity_unit: str = Field(min_length=1, max_length=40)
    fx_snapshot_id: uuid.UUID | None = None
    calculation_version: str = Field(default="landed-cost-v5", min_length=1, max_length=64)
    policy_version: str = Field(
        default="readiness-gated-landed-cost-v1", min_length=1, max_length=64
    )
    options: dict[str, object] = Field(default_factory=dict)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Base currency must be a three-letter alphabetic code.")
        return normalized

    @field_validator("options")
    @classmethod
    def bounded_options(cls, value: dict[str, object]) -> dict[str, object]:
        if len(value) > 40:
            raise ValueError("Too many calculation options.")
        blocked = {"token", "secret", "password", "cookie", "authorization", "api_key"}
        if any(str(key).lower() in blocked for key in value):
            raise ValueError("Sensitive calculation metadata is not allowed.")
        return value
