import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    ),
]
HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


class BrandCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    slug: Slug | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None
    ) = None
    tagline: Annotated[str, StringConstraints(strip_whitespace=True, max_length=240)] | None = None
    website_url: AnyHttpUrl | None = None
    primary_color: HexColor | None = None
    secondary_color: HexColor | None = None

    @field_validator("website_url")
    @classmethod
    def require_http(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and value.scheme not in {"http", "https"}:
            raise ValueError("Website URL must use HTTP or HTTPS.")
        return value


class BrandUpdate(BaseModel):
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
        | None
    ) = None
    slug: Slug | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None
    ) = None
    tagline: Annotated[str, StringConstraints(strip_whitespace=True, max_length=240)] | None = None
    website_url: AnyHttpUrl | None = None
    primary_color: HexColor | None = None
    secondary_color: HexColor | None = None

    @field_validator("website_url")
    @classmethod
    def require_http(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        return BrandCreate.require_http(value)


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    tagline: str | None
    status: Literal["active", "archived"]
    website_url: str | None
    primary_color: str | None
    secondary_color: str | None
    is_active_context: bool
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class BrandListResponse(BaseModel):
    items: list[BrandResponse]
    page: int
    page_size: int
    total: int
    pages: int


class AuditSummary(BaseModel):
    action: str
    occurred_at: datetime


class BrandDetailsResponse(BrandResponse):
    recent_audit_events: list[AuditSummary] = Field(default_factory=list)
