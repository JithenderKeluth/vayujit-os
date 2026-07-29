import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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


class WordPressDestinationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    post_status: Literal["draft", "publish"] = "draft"
    category_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list, max_length=100)
    tag_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list, max_length=100)
    author_id: Annotated[int, Field(ge=1)] | None = None
    media_policy: Literal["fail", "publish_without", "draft_degraded"] = "fail"
    update_existing_remote_post: bool = True
    content_mapping_version: Literal[1] = 1


class DestinationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    brand_id: uuid.UUID | None = None
    connector_key: Literal["mock_publisher_v1", "wordpress"] = "mock_publisher_v1"
    configuration: MockConfiguration | WordPressDestinationConfiguration

    @model_validator(mode="after")
    def connector_configuration_matches(self) -> "DestinationWrite":
        expected = (
            WordPressDestinationConfiguration
            if self.connector_key == "wordpress"
            else MockConfiguration
        )
        if not isinstance(self.configuration, expected):
            raise ValueError("Destination configuration does not match its connector.")
        return self


class DestinationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    brand_id: uuid.UUID | None = None
    configuration: MockConfiguration | WordPressDestinationConfiguration | None = None


class DestinationResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    brand_name: str | None
    connector_key: str
    name: str
    status: Literal["active", "disabled"]
    configuration: MockConfiguration | WordPressDestinationConfiguration
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
    action: Literal["create_draft", "publish", "update"] = "publish"


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
    operation: str = "publish"
    latency_ms: int | None = None
    response_status: int | None = None
    retry_after_seconds: int | None = None
    ambiguous_result: bool = False
    correlation_id: str | None = None


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
    requested_action: str = "publish"
    remote_entity_id: str | None = None
    remote_status: str | None = None
    remote_slug: str | None = None
    remote_edit_url: str | None = None
    reconciliation_status: str = "unknown"
    last_reconciled_at: datetime | None = None
    correlation_id: str | None = None
    cancellation_requested_at: datetime | None = None
    cancelled_at: datetime | None = None


class WordPressConnectorUpdate(BaseModel):
    site_url: Annotated[str, StringConstraints(min_length=8, max_length=500)]
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    application_password: (
        Annotated[str, StringConstraints(min_length=1, max_length=4096)] | None
    ) = None
    enabled: bool = False
    default_post_status: Literal["draft", "publish"] = "draft"
    request_timeout_seconds: int = Field(default=45, ge=10, le=120)
    max_retry_attempts: int = Field(default=3, ge=1, le=5)


class WordPressConnectorResponse(BaseModel):
    connector_key: Literal["wordpress"] = "wordpress"
    display_name: str = "WordPress"
    configured: bool
    credential_source: Literal["application", "deployment", "not_configured"]
    masked_username: str | None
    site_url: str
    enabled: bool
    default_post_status: str
    request_timeout_seconds: int
    max_retry_attempts: int
    validation_status: str
    safe_validation_message: str | None
    last_validated_at: datetime | None
    last_validation_latency_ms: int | None
    capabilities: dict[str, bool]


class WordPressValidationResult(BaseModel):
    valid: bool
    safe_message: str
    site_url: str
    user_id: int | None
    display_name: str | None
    capabilities: dict[str, bool]
    latency_ms: int
    correlation_id: str | None


class WordPressTerm(BaseModel):
    id: int
    name: str
    slug: str


class WordPressAuthor(BaseModel):
    id: int
    name: str


class CancellationResponse(BaseModel):
    id: uuid.UUID
    status: str
    remote_cancellation: bool = False


class ReconciliationResponse(BaseModel):
    id: uuid.UUID
    reconciliation_status: str
    remote_status: str | None
    remote_slug: str | None
    remote_url: str | None
    drift_fields: list[str]
    correlation_id: str | None


class Page(BaseModel):
    items: list[DestinationResponse] | list[ExecutionResponse]
    page: int
    page_size: int
    total: int
    pages: int
