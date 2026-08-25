from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourcingModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RequirementCreate(SourcingModel):

    opportunity_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=3, max_length=180)
    payload: dict[str, object] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def bounded_payload(cls, value: dict[str, object]) -> dict[str, object]:
        if len(value) > 40:
            raise ValueError("Sourcing requirement payload is too large.")
        return value


class RequirementVersionCreate(SourcingModel):
    payload: dict[str, object] = Field(default_factory=dict)


class RequirementResponse(SourcingModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    opportunity_id: uuid.UUID | None
    product_id: uuid.UUID | None
    current_version: int
    status: str
    idempotency_key: str
    payload: dict[str, object]
    created_at: datetime
    updated_at: datetime


class RFQCreate(SourcingModel):
    requirement_id: uuid.UUID
    requirement_version: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=200)
    supplier_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=3, max_length=180)
    payload: dict[str, object] = Field(default_factory=dict)


class RFQResponse(SourcingModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    requirement_id: uuid.UUID
    requirement_version: int
    version: int
    status: str
    dispatch_status: str
    title: str
    payload: dict[str, object]
    idempotency_key: str
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DispatchRequest(SourcingModel):
    status: str


class QuoteLine(SourcingModel):
    kind: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=2000)
    amount: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)


class QuoteCreate(SourcingModel):
    rfq_id: uuid.UUID
    supplier_id: uuid.UUID
    quote_reference: str = Field(min_length=1, max_length=180)
    quote_date: datetime | None = None
    valid_until: datetime | None = None
    currency: str = Field(min_length=3, max_length=3)
    unit_price: float = Field(ge=0)
    moq: int = Field(gt=0)
    payload: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[object] = Field(default_factory=list)
    lines: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=3, max_length=180)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, v):
        return (
            v.upper()
            if v.isalpha()
            else (_ for _ in ()).throw(ValueError("Currency must be alphabetic."))
        )


class QuoteResponse(SourcingModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    rfq_id: uuid.UUID
    supplier_id: uuid.UUID
    version: int
    quote_reference: str
    quote_date: datetime
    valid_until: datetime | None
    currency: str
    unit_price: float
    moq: int
    status: str
    payload: dict[str, object]
    evidence_refs: list[object]
    created_at: datetime
    idempotency_key: str | None


class SampleRequestCreate(SourcingModel):
    rfq_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    quantity: int = Field(gt=0, le=100000)
    notes: str = Field(default="", max_length=5000)


class SampleStatusUpdate(SourcingModel):
    status: str


class SampleEvaluate(SourcingModel):
    decision: str
    dimensions: dict[str, object] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=5000)


class SampleResponse(SourcingModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    request_id: uuid.UUID
    status: str
    evidence: list[object]
    notes: str
    created_at: datetime


class InspectionCreate(SourcingModel):
    sample_id: uuid.UUID | None = None
    inspection_type: str = Field(min_length=3, max_length=32)
    notes: str = Field(default="", max_length=5000)


class FindingCreate(SourcingModel):
    severity: str
    category: str
    finding: str = Field(max_length=5000)
    evidence: list[object] = Field(default_factory=list)
    quantity_checked: int | None = Field(default=None, ge=0)
    quantity_defective: int | None = Field(default=None, ge=0)


class NegotiationCreate(SourcingModel):
    quote_id: uuid.UUID
    requested_change: str = Field(max_length=5000)
    supplier_response: str = Field(default="", max_length=5000)
    delta: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[object] = Field(default_factory=list)


class ScenarioCreate(SourcingModel):
    requirement_id: uuid.UUID | None = None
    quote_id: uuid.UUID | None = None
    name: str = Field(default="BASE", pattern="^(BASE|BEST_CASE|WORST_CASE|CUSTOM)$")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    inputs: dict[str, object] = Field(default_factory=dict)


class DecisionCreate(SourcingModel):
    requirement_id: uuid.UUID
    quote_id: uuid.UUID
    classification: str = "review_required"
    decision: str = "hold"
    critic: list[object] = Field(default_factory=list)
    confirmed: bool = False


class ApprovalCreate(SourcingModel):
    note: str = Field(default="", max_length=2000)


class WorkerCreate(SourcingModel):
    task: str = Field(min_length=2, max_length=64)
    idempotency_key: str = Field(min_length=3, max_length=180)
    payload: dict[str, object] = Field(default_factory=dict)


class RecoveryCreate(SourcingModel):
    entity_type: str
    entity_id: uuid.UUID
    action: str
    failure_code: str = "checkpoint_invalid"
    idempotency_key: str | None = None
    reason: str = Field(default="", max_length=2000)


class RFQRevisionCreate(SourcingModel):
    payload: dict[str, object] = Field(default_factory=dict)
    requirement_version: int | None = Field(default=None, ge=1)
    supplier_ids: list[uuid.UUID] | None = None
    quantity: int | None = Field(default=None, gt=0)
    packaging: str | None = Field(default=None, max_length=500)
    private_label: bool | None = None
    customization: str | None = Field(default=None, max_length=2000)
    sample_requirements: str | None = Field(default=None, max_length=2000)
    certifications: list[str] | None = None
    destination: str | None = Field(default=None, max_length=240)
    incoterm: str | None = Field(default=None, max_length=8)
    lead_time: str | None = Field(default=None, max_length=120)
    payment_terms: str | None = Field(default=None, max_length=240)


class AssumptionCreate(SourcingModel):
    scenario_id: uuid.UUID
    payload: dict[str, object] = Field(default_factory=dict)


class ScoreEvaluate(SourcingModel):
    requirement_id: uuid.UUID
    quote_id: uuid.UUID
    model_version: str = Field(default="v1", min_length=2, max_length=32)
    weights: dict[str, float] | None = None
    inputs: dict[str, object] = Field(default_factory=dict)


class RuleEvaluate(SourcingModel):
    requirement_id: uuid.UUID
    inputs: dict[str, object] = Field(default_factory=dict)
    rules: dict[str, object] = Field(default_factory=dict)


class CalendarCreate(SourcingModel):
    kind: str = Field(min_length=2, max_length=48)
    title: str = Field(min_length=2, max_length=240)
    due_at: datetime | None = None
    entity_type: str = Field(min_length=2, max_length=64)
    entity_id: uuid.UUID
    idempotency_key: str = Field(min_length=3, max_length=180)
    payload: dict[str, object] = Field(default_factory=dict)
