from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShortlistingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShortlistContextCreate(ShortlistingModel):
    product_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    requirement_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=120)
    target_market: str | None = Field(default=None, max_length=120)
    budget: float | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, min_length=3, max_length=3)
    moq_preference: float | None = Field(default=None, ge=0)
    lead_time_preference_days: int | None = Field(default=None, ge=0)
    required_capabilities: list[str] = Field(default_factory=list, max_length=30)
    required_certifications: list[str] = Field(default_factory=list, max_length=30)
    required_facilities: list[str] = Field(default_factory=list, max_length=30)
    risk_tolerance: str = Field(default="medium", max_length=32)
    minimum_verification: float = Field(default=0, ge=0, le=100)
    minimum_confidence: float = Field(default=0, ge=0, le=100)
    freshness_requirement: str = Field(default="unknown", max_length=24)
    idempotency_key: str = Field(min_length=3, max_length=180)


class ShortlistRequest(ShortlistingModel):
    context_version: int = Field(default=1, ge=1)
    top_n: int = Field(default=5, ge=1, le=10)
    model_version: str = Field(default="shortlisting-v1", min_length=1, max_length=80)
    weights: dict[str, float] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=3, max_length=180)


Decision = Literal[
    "APPROVE_FOR_SOURCING",
    "REJECT",
    "REQUEST_MORE_RESEARCH",
    "KEEP_UNDER_REVIEW",
]


class ShortlistDecisionRequest(ShortlistingModel):
    shortlist_version_id: uuid.UUID
    supplier_id: uuid.UUID
    decision: Decision
    reason: str = Field(default="", max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    decision_key: str = Field(min_length=3, max_length=180)


class SourcingHandoffRequest(ShortlistingModel):
    decision_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    confirmed: bool = False
