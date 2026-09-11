from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class DueDiligenceContextCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    shortlist_context_id: uuid.UUID | None = None
    shortlist_version_id: uuid.UUID | None = None
    recommendation_id: uuid.UUID | None = None
    requirement_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=3, max_length=180)


class ResearchPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=3, max_length=180)
    max_tasks: int = Field(default=10, ge=1, le=50)
    max_sources: int = Field(default=10, ge=1, le=100)
    max_provider_calls: int = Field(default=10, ge=1, le=100)


class HumanGapAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="", max_length=2000)

    selected_gap_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
