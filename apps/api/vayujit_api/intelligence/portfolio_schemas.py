"""Strict HTTP contracts for the supplier portfolio foundation."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PortfolioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


ScopeType = Literal[
    "whole_business",
    "product",
    "product_family",
    "category",
    "brand",
    "marketplace",
    "sourcing_program",
    "manual",
]


class PortfolioCreate(PortfolioInput):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    scope_type: ScopeType = "manual"
    scope_reference: str | None = Field(default=None, max_length=240)
    idempotency_key: str = Field(min_length=3, max_length=180)


class PortfolioPatch(PortfolioInput):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    scope_type: ScopeType | None = None
    scope_reference: str | None = Field(default=None, max_length=240)
    status: Literal["active", "review_required", "stale", "archived"] | None = None


class PortfolioMemberCreate(PortfolioInput):
    supplier_id: uuid.UUID
    version: int = Field(default=1, ge=1)
    associated_products: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    associated_opportunities: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    shortlist_lineage_id: uuid.UUID | None = None
    due_diligence_lineage_id: uuid.UUID | None = None
    sourcing_scenario_lineage_id: uuid.UUID | None = None
    allocation_percent: float | None = Field(default=None, ge=0, le=100)
    evidence_freshness: str = Field(default="unknown", max_length=24)
    confidence: float | None = Field(default=None, ge=0, le=100)
    risk: str | None = Field(default=None, max_length=32)
    country_region: str | None = Field(default=None, max_length=120)
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    alternate_source_status: str = Field(default="unknown", max_length=32)


class AssessmentCreate(PortfolioInput):
    idempotency_key: str = Field(min_length=3, max_length=180)
    input_snapshot: dict[str, object] = Field(default_factory=dict)
