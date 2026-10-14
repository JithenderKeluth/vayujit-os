"""API contracts for the non-sending PR-7A engagement foundation."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EngagementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: uuid.UUID
    supplier_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    human_decision_id: uuid.UUID | None = None
    engagement_type: Literal["REQUEST_INFORMATION", "REQUEST_QUOTE"] = "REQUEST_QUOTE"
    decision_target: Literal[
        "PRODUCT_SELECTION", "SUPPLIER_SELECTION", "COMMERCIAL_ASSESSMENT", "LAUNCH_DECISION"
    ] = "SUPPLIER_SELECTION"
    requested_quantity: int = Field(gt=0, le=10_000_000)
    destination_region: str = Field(default="", max_length=160)
    requested_fields: list[str] = Field(default_factory=list, max_length=30)
    idempotency_key: str = Field(min_length=8, max_length=220)


class DraftRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: uuid.UUID | None = None
    requested_quantity: int = Field(gt=0, le=10_000_000)
    destination_region: str = Field(default="", max_length=160)
    requested_fields: list[str] = Field(default_factory=list, max_length=30)
    subject: str | None = Field(default=None, max_length=240)
    message_body: str | None = Field(default=None, max_length=20_000)
    idempotency_key: str = Field(min_length=8, max_length=220)
    provenance: Literal["HUMAN"] = "HUMAN"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=220)
    reason: str = Field(default="", max_length=4000)
    provenance: Literal["HUMAN"] = "HUMAN"


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=220)
    provenance: Literal["HUMAN"] = "HUMAN"


class EngagementResponse(BaseModel):
    model_config = ConfigDict(extra="allow", from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID
    supplier_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    human_decision_id: uuid.UUID | None = None
    recommendation_id: uuid.UUID | None = None
    synthesis_id: uuid.UUID | None = None
    decision_target: str | None = None
    engagement_type: str
    engagement_version: int
    current_draft_version: int
    status: str
    blocking_reasons: list[Any] = Field(default_factory=list)
    idempotency_key: str
    input_fingerprint: str
    external_writes: list[Any] = Field(default_factory=list)
    can_send: bool = False
    send_status: str = "NOT_EXECUTED"
    current_draft: dict[str, Any] | None = None
    latest_approval: dict[str, Any] | None = None
    created_at: Any
    updated_at: Any
