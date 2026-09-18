from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vayujit_api.intelligence.product_opportunity_scoring_models import SCORING_DIMENSIONS

DECISION_ACTIONS = ("watch", "research_more", "shortlist", "reject", "archive")


class ScoreCalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str | None = Field(default=None, max_length=220)
    weights: dict[str, Decimal] | None = None
    profile_version: str = Field(default="canonical-v1", max_length=80)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, value: dict[str, Decimal] | None) -> dict[str, Decimal] | None:
        if value is None:
            return None
        if set(value) != set(SCORING_DIMENSIONS):
            raise ValueError(
                "A scoring profile must define every canonical dimension exactly once."
            )
        if any(not value[key].is_finite() or value[key] < 0 or value[key] > 60 for key in value):
            raise ValueError("Scoring weights must be finite values between 0 and 60.")
        if sum(value.values(), Decimal("0")) != Decimal("100"):
            raise ValueError("Scoring weights must sum exactly to 100.")
        return value


class ScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    opportunity_id: UUID
    assessment_id: UUID
    scoring_model_version: str
    calculation_version: str
    profile_version: str
    input_fingerprint: str
    upstream_lineage: dict[str, Any]
    eligibility: str
    overall_score: Decimal | None
    classification: str
    decision_label: str
    confidence: str
    risk_level: str
    assessment_readiness: str
    evidence_state: str
    dimensions: list[Any]
    unavailable_dimensions: list[Any]
    risk_adjustments: list[Any]
    positive_drivers: list[Any]
    negative_drivers: list[Any]
    improvement_areas: list[Any]
    sensitivity: dict[str, Any]
    comparability: dict[str, Any]
    weights: dict[str, Any]
    idempotency_key: str
    created_at: datetime
    notes: str


class ScoreHistoryItem(BaseModel):
    id: UUID
    assessment_id: UUID
    scoring_model_version: str
    profile_version: str
    eligibility: str
    overall_score: Decimal | None
    classification: str
    created_at: datetime


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_ids: list[UUID] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def unique_assessments(self) -> ComparisonRequest:
        if len(set(self.assessment_ids)) != len(self.assessment_ids):
            raise ValueError("Comparison assessment IDs must be unique.")
        return self


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["watch", "research_more", "shortlist", "reject", "archive"]
    rationale: str = Field(min_length=1, max_length=4000)
    idempotency_key: str | None = Field(default=None, max_length=220)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    opportunity_id: UUID
    assessment_id: UUID
    score_id: UUID
    action: str
    rationale: str
    idempotency_key: str
    created_at: datetime
