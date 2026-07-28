import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class MockConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    publication_prefix: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,20}$")
    ] = "PUB"
    simulate_failure: bool = False
    failure_type: Literal["retryable", "non_retryable"] = "non_retryable"


class DestinationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    brand_id: uuid.UUID | None = None
    connector_key: Literal["mock_publisher_v1"] = "mock_publisher_v1"
    configuration: MockConfiguration


class DestinationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    brand_id: uuid.UUID | None = None
    configuration: MockConfiguration | None = None


class DestinationResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    brand_name: str | None
    connector_key: str
    name: str
    status: Literal["active", "disabled"]
    configuration: MockConfiguration
    created_at: datetime
    updated_at: datetime
    disabled_at: datetime | None


class CreateExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: uuid.UUID
    destination_id: uuid.UUID
    idempotency_key: (
        Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{8,100}$")] | None
    ) = None


class AttemptResponse(BaseModel):
    attempt_number: int
    status: str
    result: dict[str, object] | None
    error_code: str | None
    safe_error_message: str | None
    retryable: bool
    started_at: datetime
    completed_at: datetime | None
    failed_at: datetime | None


class ExecutionResponse(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    destination_id: uuid.UUID
    brand_id: uuid.UUID
    product_id: uuid.UUID
    connector_key: str
    status: str
    idempotency_key: str
    attempt_count: int
    content_snapshot: dict[str, object]
    request_snapshot: dict[str, object]
    result: dict[str, object] | None
    external_reference: str | None
    external_url: str | None
    error_code: str | None
    safe_error_message: str | None
    retryable: bool
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    attempts: list[AttemptResponse] = Field(default_factory=list)


class Page(BaseModel):
    items: list[DestinationResponse] | list[ExecutionResponse]
    page: int
    page_size: int
    total: int
    pages: int
