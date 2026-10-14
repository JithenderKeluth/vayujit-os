"""PR-8A reassessment API contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vayujit_api.intelligence.commercial_readiness_schemas import CommercialReadinessAssumption
from vayujit_api.intelligence.landed_cost_schemas import LandedCostCalculateRequest
from vayujit_api.intelligence.product_opportunity_unit_economics_schemas import (
    UnitEconomicsCalculateRequest,
)


class CommercialReassessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    promotion_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    scenario_key: str = Field(default="reviewed-quote-reassessment", min_length=1, max_length=120)
    assumptions: list[CommercialReadinessAssumption] = Field(default_factory=list, max_length=30)
    landed_cost: LandedCostCalculateRequest | None = None
    unit_economics: UnitEconomicsCalculateRequest | None = None
    baseline_landed_cost_id: uuid.UUID | None = None
    baseline_unit_economics_id: uuid.UUID | None = None


class CommercialReassessmentReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=3, max_length=220)
    decision: Literal["ACKNOWLEDGE", "KEEP_UNDER_REVIEW"]
    provenance: Literal["HUMAN"] = "HUMAN"
    reason: str = Field(default="", max_length=4000)


class CommercialReassessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    goal_id: uuid.UUID | None
    opportunity_id: uuid.UUID
    assessment_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_product_id: uuid.UUID
    promotion_id: uuid.UUID
    commercial_term_id: uuid.UUID
    baseline_landed_cost_id: uuid.UUID | None
    baseline_unit_economics_id: uuid.UUID | None
    current_readiness_id: uuid.UUID | None
    current_landed_cost_id: uuid.UUID | None
    current_unit_economics_id: uuid.UUID | None
    scenario_key: str
    status: str
    review_status: str
    input_fingerprint: str
    idempotency_key: str
    quote_version: int
    quote_evidence: dict[str, object]
    assumptions: list[object]
    baseline: dict[str, object]
    current: dict[str, object]
    comparison: dict[str, object]
    blockers: list[object]
    provenance: dict[str, object]
    lineage: dict[str, object]
    created_at: object
    notes: str
    idempotent_reuse: bool = False
    review: dict[str, object] | None = None


class ComparisonMetric(BaseModel):
    metric: str
    baseline: Decimal | str | None = None
    reassessment: Decimal | str | None = None
    delta: Decimal | str | None = None
    state: str = "AVAILABLE"
