import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class ShopifyOptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ShopifyVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_key: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9._:-]{1,100}$")
    ]
    options: list[ShopifyOptionInput] = Field(default_factory=list, max_length=3)
    sku: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    price: Annotated[str, StringConstraints(pattern=r"^\d{1,10}(?:\.\d{1,2})?$")] | None = None
    compare_at_price: (
        Annotated[str, StringConstraints(pattern=r"^\d{1,10}(?:\.\d{1,2})?$")] | None
    ) = None
    barcode: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    weight: Annotated[str, StringConstraints(pattern=r"^\d{1,9}(?:\.\d{1,3})?$")] | None = None
    weight_unit: Literal["g", "kg", "oz", "lb"] | None = None
    taxable: bool = True
    track_inventory: bool = False

    @model_validator(mode="after")
    def commerce_values_are_consistent(self) -> "ShopifyVariantInput":
        from decimal import Decimal

        if self.compare_at_price is not None and self.price is None:
            raise ValueError("Variant price is required with compare-at price.")
        if (
            self.compare_at_price is not None
            and self.price is not None
            and Decimal(self.compare_at_price) < Decimal(self.price)
        ):
            raise ValueError("Compare-at price cannot be lower than variant price.")
        if self.weight is not None and self.weight_unit is None:
            raise ValueError("Weight unit is required with variant weight.")
        return self


class ShopifyMediaSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: uuid.UUID
    position: Annotated[int, Field(ge=0, le=99)]
    alt_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=512)] = ""


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
    featured_image_policy: Literal["none", "optional", "required"] = "none"
    default_media_id: uuid.UUID | None = None
    update_existing_remote_post: bool = True
    content_mapping_version: Literal[1] = 1


class ShopifyDestinationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_product_status: Literal["draft", "active"] = "draft"
    default_collection_ids: list[Annotated[str, StringConstraints(max_length=160)]] = Field(
        default_factory=list, max_length=100
    )
    default_publication_ids: list[Annotated[str, StringConstraints(max_length=160)]] = Field(
        default_factory=list, max_length=100
    )
    default_vendor: Annotated[str, StringConstraints(max_length=255)] = ""
    default_product_type: Annotated[str, StringConstraints(max_length=255)] = ""
    default_tags: list[Annotated[str, StringConstraints(max_length=255)]] = Field(
        default_factory=list, max_length=100
    )
    variant_policy: Literal["default_variant", "structured_variants"] = "default_variant"
    require_variant_price: bool = False
    require_variant_sku: bool = False
    inventory_policy: Literal["no_inventory_write", "track_without_quantity"] = "no_inventory_write"
    media_policy: Literal["fail", "draft_without_media", "degraded"] = "fail"
    update_existing_remote_product: bool = True
    content_mapping_version: Literal[1] = 1


class DestinationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    brand_id: uuid.UUID | None = None
    connector_key: Literal["mock_publisher_v1", "wordpress", "shopify"] = "mock_publisher_v1"
    configuration: (
        MockConfiguration | WordPressDestinationConfiguration | ShopifyDestinationConfiguration
    )

    @model_validator(mode="after")
    def connector_configuration_matches(self) -> "DestinationWrite":
        expected = {
            "wordpress": WordPressDestinationConfiguration,
            "shopify": ShopifyDestinationConfiguration,
        }.get(self.connector_key, MockConfiguration)
        if not isinstance(self.configuration, expected):
            raise ValueError("Destination configuration does not match its connector.")
        return self


class DestinationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    brand_id: uuid.UUID | None = None
    configuration: (
        MockConfiguration
        | WordPressDestinationConfiguration
        | ShopifyDestinationConfiguration
        | None
    ) = None


class DestinationResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID | None
    brand_name: str | None
    connector_key: str
    name: str
    status: Literal["active", "disabled"]
    configuration: (
        MockConfiguration | WordPressDestinationConfiguration | ShopifyDestinationConfiguration
    )
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
    action: Literal["create_draft", "publish", "activate", "update", "archive"] = "publish"
    featured_media_id: uuid.UUID | None = None
    shopify_variants: list[ShopifyVariantInput] = Field(default_factory=list, max_length=100)
    shopify_media: list[ShopifyMediaSelection] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def structured_shopify_values_are_unique(self) -> "CreateExecution":
        keys = [item.local_key.casefold() for item in self.shopify_variants]
        if len(keys) != len(set(keys)):
            raise ValueError("Shopify variant local keys must be unique.")
        signatures = [
            tuple((option.name.casefold(), option.value.casefold()) for option in item.options)
            for item in self.shopify_variants
        ]
        if len(signatures) != len(set(signatures)):
            raise ValueError("Shopify variant option combinations must be unique.")
        skus = [item.sku.casefold() for item in self.shopify_variants if item.sku]
        if len(skus) != len(set(skus)):
            raise ValueError("Shopify variant SKUs must be unique.")
        positions = [item.position for item in self.shopify_media]
        if len(positions) != len(set(positions)):
            raise ValueError("Shopify media positions must be unique.")
        return self


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
    calculated_delay_ms: int | None = None
    applied_delay_ms: int | None = None
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


class ShopifyConnectorUpdate(BaseModel):
    shop_domain: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=4, max_length=253)
    ]
    access_token: Annotated[str, StringConstraints(min_length=8, max_length=4096)] | None = None
    api_version: Annotated[str, StringConstraints(pattern=r"^20\d{2}-(01|04|07|10)$")] = "2026-07"
    default_product_status: Literal["draft", "active"] = "draft"
    default_publication_ids: list[Annotated[str, StringConstraints(max_length=160)]] = Field(
        default_factory=list, max_length=100
    )
    inventory_policy: Literal["no_inventory_write", "track_without_quantity"] = "no_inventory_write"
    variant_policy: Literal["default_variant", "structured_variants"] = "default_variant"
    media_policy: Literal["fail", "draft_without_media", "degraded"] = "fail"
    request_timeout_seconds: int = Field(default=45, ge=10, le=120)
    max_retry_attempts: int = Field(default=3, ge=1, le=5)


class ShopifyConnectorResponse(BaseModel):
    connector_key: Literal["shopify"] = "shopify"
    display_name: str = "Shopify"
    configured: bool
    credential_source: Literal["application", "deployment", "not_configured"]
    shop_domain: str
    api_version: str
    enabled: bool
    default_product_status: str
    default_publication_ids: list[str]
    inventory_policy: str
    variant_policy: str
    media_policy: str
    request_timeout_seconds: int
    max_retry_attempts: int
    validation_status: str
    safe_validation_message: str | None
    last_validated_at: datetime | None
    last_validation_latency_ms: int | None
    capabilities: dict[str, bool]


class ShopifyValidationResult(BaseModel):
    valid: bool
    safe_message: str
    shop_domain: str
    api_version: str
    shop_id: str | None
    shop_name: str | None
    primary_domain: str | None
    capabilities: dict[str, bool]
    latency_ms: int
    correlation_id: str | None


class ShopifyRemoteItem(BaseModel):
    id: str
    name: str
    handle: str | None = None


class ShopifyDiscoveryPage(BaseModel):
    items: list[ShopifyRemoteItem]
    has_more: bool
    end_cursor: str | None
    cached: bool
    stale: bool = False


class WordPressTerm(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None = None


class WordPressAuthor(BaseModel):
    id: int
    name: str
    username: str | None = None


class WordPressTaxonomyPage(BaseModel):
    items: list[WordPressTerm] | list[WordPressAuthor]
    page: int
    page_size: int
    has_more: bool
    cached: bool
    stale: bool = False


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
    differences: list["RemoteDriftField"] = Field(default_factory=list)
    correlation_id: str | None


class ShopifyOverwritePreview(BaseModel):
    execution_id: uuid.UUID
    reconciliation_status: str
    fields_available: list[str]
    remote_only_fields_preserved: list[str]
    differences: list["RemoteDriftField"]
    correlation_id: str | None


class ShopifyOverwriteConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Field(
        min_length=1, max_length=100
    )
    confirmed: Literal[True]


class ShopifyAssignmentRemovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignment_type: Literal["collection", "publication"]
    remote_target_ids: list[Annotated[str, StringConstraints(min_length=1, max_length=160)]] = (
        Field(min_length=1, max_length=100)
    )
    confirmed: Literal[True]


class ShopifyAssignmentRemovalPreview(BaseModel):
    execution_id: uuid.UUID
    assignment_type: Literal["collection", "publication"]
    removable_target_ids: list[str]
    preserved_target_ids: list[str]
    required_target_ids: list[str]
    activation_impact: str
    correlation_id: str | None


class RemoteDriftField(BaseModel):
    field: str
    display_label: str = ""
    expected: object | None
    remote: object | None
    normalized_expected: object | None = None
    normalized_remote: object | None = None
    status: Literal["in_sync", "changed_remotely", "unknown"]
    drift_type: Literal[
        "value_changed", "missing_remote", "extra_remote", "inaccessible", "unknown", "conflict"
    ] = "value_changed"
    severity: Literal["info", "warning", "blocking"] = "warning"
    resolution: Literal["overwrite", "keep_remote", "manual", "none"] = "keep_remote"
    safe_explanation: str = ""


class SanitizationChange(BaseModel):
    kind: Literal["escaped_html", "converted_paragraphs", "normalized_slug"]
    message: str


class PublishingPreviewRequest(BaseModel):
    artifact_id: uuid.UUID
    destination_id: uuid.UUID
    action: Literal["create_draft", "publish", "activate", "update", "archive"] = "publish"
    featured_media_id: uuid.UUID | None = None


class PublishingPreviewResponse(BaseModel):
    title: str
    slug: str
    excerpt: str
    sanitized_body: str
    post_status: str
    author_id: int | None
    category_ids: list[int]
    tag_ids: list[int]
    featured_media_id: uuid.UUID | None
    destination_id: uuid.UUID
    destination_name: str
    remote_update_target: str | None
    artifact_id: uuid.UUID
    artifact_version: int
    product_id: uuid.UUID
    product_name: str
    brand_id: uuid.UUID
    brand_name: str
    original_text: str
    sanitization_changes: list[SanitizationChange]


class ShopifyPreviewResponse(BaseModel):
    title: str
    sanitized_description_html: str
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"]
    vendor: str
    product_type: str
    tags: list[str]
    seo_title: str
    seo_description: str
    collection_ids: list[str]
    publication_ids: list[str]
    inventory_policy: str
    destination_id: uuid.UUID
    destination_name: str
    artifact_id: uuid.UUID
    artifact_version: int
    product_id: uuid.UUID
    product_name: str
    brand_id: uuid.UUID
    brand_name: str
    original_text: str


class Page(BaseModel):
    items: list[DestinationResponse] | list[ExecutionResponse]
    page: int
    page_size: int
    total: int
    pages: int
