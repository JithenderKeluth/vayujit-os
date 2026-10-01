"""Schemas for the PR-5A evidence/readiness boundary."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommercialReadinessAssumption(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: Decimal | str | None = None
    unit: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=4000)
    provenance: Literal["ASSUMED"] = "ASSUMED"
    marker: Literal["DETERMINISTIC_TEST", "SELLER_SCENARIO"] = "DETERMINISTIC_TEST"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("Currency must be an alphabetic three-letter code.")
        return normalized


class CommercialReadinessCreate(BaseModel):
    idempotency_key: str = Field(min_length=3, max_length=220)
    supplier_id: uuid.UUID | None = None
    scenario_key: str = Field(default="source-evidence", min_length=1, max_length=120)
    assumptions: list[CommercialReadinessAssumption] = Field(default_factory=list, max_length=30)


class CommercialReadinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    supplier_id: uuid.UUID | None
    scenario_key: str
    readiness: dict[str, object]
    known_inputs: list[object]
    claims: list[object]
    assumptions: list[object]
    unknown_inputs: list[object]
    missing_inputs: list[object]
    optional_gaps: list[object]
    contradictions: list[object]
    lineage: dict[str, object]
    idempotency_key: str
    notes: str
    created_at: datetime
