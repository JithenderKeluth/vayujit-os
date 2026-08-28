from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ExternalSearchRequestBody(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    market: str = Field(default="", max_length=120)
    language: str = Field(default="en", max_length=32)
    max_results: int = Field(default=10, ge=1, le=50)
    safe_search: bool = True
    source_categories: list[str] = Field(default_factory=list, max_length=10)
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)
    excluded_domains: list[str] = Field(default_factory=list, max_length=20)
    correlation_id: str = Field(default="", max_length=80)
    refresh: bool = False
    mission_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None

    @field_validator("query", "market", "language")
    @classmethod
    def no_control_chars(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError("control characters are not allowed")
        return value.strip()


class ExternalFetchRequestBody(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)
    blocked_domains: list[str] = Field(default_factory=list, max_length=20)
    source_profile: str = Field(default="default", max_length=120)
    mission_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    search_result_id: uuid.UUID | None = None
    correlation_id: str = Field(default="", max_length=80)
    refresh: bool = False


class ExternalSearchResultResponse(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    canonical_url: str
    domain: str
    snippet: str
    published_at: datetime | None
    retrieved_at: datetime
    provider: str
    provider_result_id: str
    rank: int
    source_classification: str
    fetch_eligible: bool = True


class ExternalSearchResponse(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    mode: str
    result_count: int
    failure_code: str | None
    results: list[ExternalSearchResultResponse]
