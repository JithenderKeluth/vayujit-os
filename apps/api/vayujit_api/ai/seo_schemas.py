import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

SEOChannel = Literal["canonical", "wordpress", "shopify", "amazon", "flipkart", "meesho"]
SEOIntent = Literal[
    "informational", "commercial", "transactional", "navigational", "mixed", "unknown"
]
TagScope = Literal["product", "marketplace", "website", "campaign", "social"]


class SEORequest(BaseModel):
    product_id: uuid.UUID
    artifact_id: uuid.UUID | None = None
    keyword_set_id: uuid.UUID | None = None
    channel: SEOChannel = "canonical"
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    primary_keyword: Annotated[str | None, StringConstraints(max_length=160)] = None
    secondary_keywords: list[str] = Field(default_factory=list, max_length=100)
    intent: SEOIntent = "unknown"
    force: bool = False


class SEOFinding(BaseModel):
    actions: list[Literal["edit", "regenerate", "reanalyze", "open_keywords", "review_product"]] = (
        Field(default_factory=list)
    )
    severity: Literal["blocker", "warning", "recommendation", "information"]
    field: str
    code: str
    explanation: str
    suggested_action: str | None = None


class SEOAnalysisResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    artifact_id: uuid.UUID | None
    artifact_version: int | None
    keyword_set_id: uuid.UUID | None
    keyword_set_version: int | None
    channel: str
    seo_type: str
    locale: str
    intent: str
    overall_score: int
    dimensions: dict[str, dict[str, object]]
    findings: list[SEOFinding]
    recommendations: list[SEOFinding]
    keyword_coverage: dict[str, object]
    metrics: dict[str, object]
    fingerprint: str
    rule_version: str
    status: str
    analyzed_at: datetime


class KeywordSetUpsert(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    description: Annotated[str | None, StringConstraints(max_length=500)] = None
    brand_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    primary: list[str] = Field(default_factory=list, max_length=100)
    secondary: list[str] = Field(default_factory=list, max_length=100)
    marketplace: list[str] = Field(default_factory=list, max_length=100)
    website: list[str] = Field(default_factory=list, max_length=100)
    campaign: list[str] = Field(default_factory=list, max_length=100)
    excluded: list[str] = Field(default_factory=list, max_length=100)
    negative: list[str] = Field(default_factory=list, max_length=100)
    competitor_reference: list[str] = Field(default_factory=list, max_length=100)
    source: Annotated[str, StringConstraints(max_length=80)] = "manual"
    notes: Annotated[str | None, StringConstraints(max_length=1000)] = None
    is_default: bool = False


class KeywordSetDetail(KeywordSetUpsert):
    id: uuid.UUID
    version: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class KeywordSuggestionRequest(BaseModel):
    product_id: uuid.UUID
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    channel: SEOChannel = "canonical"


class TagSuggestion(BaseModel):
    tag: str
    source: Literal["ai_suggested"] = "ai_suggested"


class KeywordSuggestion(BaseModel):
    keyword: str
    category: str
    source: Literal["ai_suggested"] = "ai_suggested"
    accepted: bool = False


class TagSetUpsert(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    product_id: uuid.UUID | None = None
    scope: TagScope = "product"
    locale: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "en-IN"
    tags: list[Annotated[str, StringConstraints(max_length=80)]] = Field(
        default_factory=list, max_length=100
    )

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            tag = " ".join(item.strip().lstrip("#").split())
            if tag and tag.casefold() not in seen:
                seen.add(tag.casefold())
                result.append(tag)
        return result[:50]


class TagSetResponse(TagSetUpsert):
    id: uuid.UUID
    archived: bool
    created_at: datetime
    updated_at: datetime
    tag_details: list[dict[str, object]] = Field(default_factory=list)


class SEOAnalysisComparison(BaseModel):
    current: SEOAnalysisResponse
    previous: SEOAnalysisResponse
    score_delta: int
    dimension_deltas: dict[str, int]
    changes: list[str]


class ProductChannelIntelligence(BaseModel):
    channel: str
    approved_artifact_id: uuid.UUID | None
    approved_version: int | None
    locale: str | None
    content_quality_score: int | None
    search_score: int | None
    listing_used_version: int | None
    last_generated: datetime | None
    last_approved: datetime | None
    blockers: list[str]
    warnings: list[str]
    analysis_stale: bool
    update_available: bool
    readiness: Literal[
        "not_generated", "draft", "needs_review", "approved", "update_available", "blocked", "ready"
    ]
