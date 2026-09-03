from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class CrossMarketplaceReconcileRequest(BaseModel):
    supplier_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)


class CrossMarketplaceCompareRequest(BaseModel):
    supplier_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)


class CrossMarketplaceRankingRequest(BaseModel):
    model_version: str = Field(default="v1", min_length=1, max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=180)
    weights: dict[str, float] | None = None


class CrossMarketplaceHandoffRequest(BaseModel):
    product_id: uuid.UUID | None = None
    confirmed: bool = False


class CrossMarketplaceReportQuery(BaseModel):
    format: Literal["json", "markdown", "html"] = "json"
