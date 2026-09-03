from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator


class AlibabaDiscoveryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=240)
    product_id: uuid.UUID | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=120)
    result_limit: int = Field(default=10, ge=1, le=20)
    correlation_id: str | None = Field(default=None, max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=180)
    mission_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class AlibabaEvidenceHandoffRequest(BaseModel):
    mission_id: uuid.UUID
    task_id: uuid.UUID
