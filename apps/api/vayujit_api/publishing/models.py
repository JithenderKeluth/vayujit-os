import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class PublishingDestination(Base):
    __tablename__ = "publishing_destinations"
    __table_args__ = (
        UniqueConstraint("owner_id", "normalized_name", name="uq_destination_owner_name"),
        CheckConstraint("status IN ('active','disabled')", name="ck_destination_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), index=True
    )
    connector_key: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), index=True)
    configuration_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublishingExecution(Base):
    __tablename__ = "publishing_executions"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_execution_owner_idempotency"),
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_execution_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id"), index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id"), index=True
    )
    connector_key: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer)
    content_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    request_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    external_reference: Mapped[str | None] = mapped_column(String(200))
    external_url: Mapped[str | None] = mapped_column(String(500))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    retryable: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_action: Mapped[str] = mapped_column(String(30), default="publish")
    remote_entity_type: Mapped[str | None] = mapped_column(String(30))
    remote_entity_id: Mapped[str | None] = mapped_column(String(100))
    remote_edit_url: Mapped[str | None] = mapped_column(String(500))
    remote_status: Mapped[str | None] = mapped_column(String(30))
    remote_slug: Mapped[str | None] = mapped_column(String(200))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciliation_status: Mapped[str] = mapped_column(String(30), default="unknown")
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class PublishingExecutionAttempt(Base):
    __tablename__ = "publishing_execution_attempts"
    __table_args__ = (
        UniqueConstraint("execution_id", "attempt_number", name="uq_attempt_execution_number"),
        CheckConstraint("status IN ('running','succeeded','failed')", name="ck_attempt_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_executions.id"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    request_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    retryable: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    operation: Mapped[str] = mapped_column(String(40), default="publish")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_method: Mapped[str | None] = mapped_column(String(10))
    safe_endpoint_label: Mapped[str | None] = mapped_column(String(80))
    response_status: Mapped[int | None] = mapped_column(Integer)
    remote_request_id: Mapped[str | None] = mapped_column(String(160))
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    calculated_delay_ms: Mapped[int | None] = mapped_column(Integer)
    applied_delay_ms: Mapped[int | None] = mapped_column(Integer)
    ambiguous_result: Mapped[bool] = mapped_column(Boolean, default=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class WordPressConnectorConfiguration(Base):
    __tablename__ = "wordpress_connector_configurations"
    __table_args__ = (
        UniqueConstraint("owner_id", name="uq_wordpress_configuration_owner"),
        CheckConstraint("request_timeout_seconds BETWEEN 10 AND 120", name="ck_wordpress_timeout"),
        CheckConstraint("max_retry_attempts BETWEEN 1 AND 5", name="ck_wordpress_retries"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    site_url: Mapped[str] = mapped_column(String(500))
    username: Mapped[str] = mapped_column(String(160))
    encrypted_application_password: Mapped[str | None] = mapped_column(Text)
    credential_version: Mapped[int] = mapped_column(Integer, default=1)
    authentication_type: Mapped[str] = mapped_column(String(30), default="application_password")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    default_post_status: Mapped[str] = mapped_column(String(20), default="draft")
    request_timeout_seconds: Mapped[int] = mapped_column(Integer, default=45)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_status: Mapped[str] = mapped_column(String(20), default="unknown")
    safe_validation_message: Mapped[str | None] = mapped_column(String(500))
    last_validation_latency_ms: Mapped[int | None] = mapped_column(Integer)
    capabilities_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class ShopifyConnectorConfiguration(Base):
    __tablename__ = "shopify_connector_configurations"
    __table_args__ = (
        UniqueConstraint("owner_id", name="uq_shopify_configuration_owner"),
        CheckConstraint("request_timeout_seconds BETWEEN 10 AND 120", name="ck_shopify_timeout"),
        CheckConstraint("max_retry_attempts BETWEEN 1 AND 5", name="ck_shopify_retries"),
        CheckConstraint(
            "default_product_status IN ('draft','active')", name="ck_shopify_default_status"
        ),
        CheckConstraint(
            "inventory_policy IN ('no_inventory_write','track_without_quantity')",
            name="ck_shopify_inventory_policy",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    shop_domain: Mapped[str] = mapped_column(String(255))
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    credential_version: Mapped[int] = mapped_column(Integer, default=1)
    api_version: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    default_product_status: Mapped[str] = mapped_column(String(20), default="draft")
    default_publication_ids_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    inventory_policy: Mapped[str] = mapped_column(String(40), default="no_inventory_write")
    variant_policy: Mapped[str] = mapped_column(String(40), default="default_variant")
    media_policy: Mapped[str] = mapped_column(String(40), default="fail")
    request_timeout_seconds: Mapped[int] = mapped_column(Integer, default=45)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    validation_status: Mapped[str] = mapped_column(String(20), default="unknown")
    safe_validation_message: Mapped[str | None] = mapped_column(String(500))
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_validation_latency_ms: Mapped[int | None] = mapped_column(Integer)
    capabilities_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShopifyMediaMapping(Base):
    __tablename__ = "shopify_media_mappings"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "destination_id",
            "media_id",
            "shop_fingerprint",
            name="uq_shopify_media_mapping",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id", ondelete="CASCADE"), index=True
    )
    shop_fingerprint: Mapped[str] = mapped_column(String(64))
    remote_product_id: Mapped[str] = mapped_column(String(160))
    remote_media_id: Mapped[str] = mapped_column(String(160))
    remote_url: Mapped[str | None] = mapped_column(String(500))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    alt_text: Mapped[str] = mapped_column(String(512), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="mapped")
    reuse_state: Mapped[str] = mapped_column(String(30), default="unknown")
    polling_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShopifyVariantMapping(Base):
    __tablename__ = "shopify_variant_mappings"
    __table_args__ = (
        UniqueConstraint(
            "destination_id", "product_id", "local_variant_key", name="uq_shopify_variant_mapping"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    local_variant_key: Mapped[str] = mapped_column(String(100))
    remote_product_id: Mapped[str] = mapped_column(String(160))
    remote_variant_id: Mapped[str] = mapped_column(String(160))
    remote_inventory_item_id: Mapped[str | None] = mapped_column(String(160))
    sku: Mapped[str | None] = mapped_column(String(100))
    option_signature: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="mapped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShopifyProductAssignment(Base):
    __tablename__ = "shopify_product_assignments"
    __table_args__ = (
        UniqueConstraint(
            "destination_id",
            "remote_product_id",
            "assignment_type",
            "remote_target_id",
            name="uq_shopify_product_assignment",
        ),
        CheckConstraint(
            "assignment_type IN ('collection','publication')",
            name="ck_shopify_assignment_type",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    remote_product_id: Mapped[str] = mapped_column(String(160))
    assignment_type: Mapped[str] = mapped_column(String(20))
    remote_target_id: Mapped[str] = mapped_column(String(160))
    managed_by_vayujit: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="assigned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShopifyMediaPollAttempt(Base):
    __tablename__ = "shopify_media_poll_attempts"
    __table_args__ = (
        UniqueConstraint(
            "media_mapping_id", "attempt_number", name="uq_shopify_media_poll_attempt"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_executions.id", ondelete="CASCADE"), index=True
    )
    media_mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shopify_media_mappings.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    remote_status: Mapped[str] = mapped_column(String(30))
    delay_ms: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublishingSchedule(Base):
    __tablename__ = "publishing_schedules"
    __table_args__ = (
        CheckConstraint("schedule_type IN ('one_time','recurring')", name="ck_schedule_type"),
        CheckConstraint(
            "requested_action IN ('create_draft','publish','update','move_to_draft',"
            "'update_product','activate_product','archive_product','reconcile')",
            name="ck_schedule_action",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT"), index=True
    )
    artifact_version: Mapped[int] = mapped_column(Integer)
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishing_destinations.id", ondelete="RESTRICT"),
        index=True,
    )
    connector_key: Mapped[str] = mapped_column(String(80), index=True)
    requested_action: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(160))
    schedule_type: Mapped[str] = mapped_column(String(20))
    scheduled_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone_name: Mapped[str] = mapped_column(String(100))
    local_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    recurrence_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    recurrence_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    destination_snapshot_version: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_job_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str | None] = mapped_column(String(40))
    cancellation_reason: Mapped[str | None] = mapped_column(String(300))
    missed_occurrence_policy: Mapped[str] = mapped_column(String(30), default="next_occurrence")
    max_occurrences: Mapped[int] = mapped_column(Integer, default=100)
    materialized_occurrence_count: Mapped[int] = mapped_column(Integer, default=0)


class PublishingJob(Base):
    __tablename__ = "publishing_jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_job_owner_idempotency"),
        CheckConstraint(
            "state IN ('pending','scheduled','claimed','running','retry_wait','succeeded',"
            "'failed','cancel_requested','cancelled','paused','expired','dead_letter')",
            name="ck_publishing_job_state",
        ),
        CheckConstraint("max_execution_attempts BETWEEN 1 AND 10", name="ck_job_max_attempts"),
        CheckConstraint("priority BETWEEN -100 AND 100", name="ck_job_priority"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_schedules.id", ondelete="SET NULL"), index=True
    )
    workflow_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="SET NULL"), index=True
    )
    publishing_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_executions.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id")
    )
    artifact_version: Mapped[int] = mapped_column(Integer)
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id"), index=True
    )
    connector_key: Mapped[str] = mapped_column(String(80), index=True)
    requested_action: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(160), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_execution_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    recovery_state: Mapped[str | None] = mapped_column(String(40), index=True)
    recovery_reason: Mapped[str | None] = mapped_column(String(500))
    maintenance_blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublishingJobAttempt(Base):
    __tablename__ = "publishing_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
        CheckConstraint(
            "outcome IN ('running','succeeded','failed','cancelled','lease_lost')",
            name="ck_job_attempt_outcome",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_jobs.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(160), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(30))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    delay_seconds: Mapped[int | None] = mapped_column(Integer)
    connector_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_executions.id", ondelete="SET NULL")
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublishingWorkerHeartbeat(Base):
    __tablename__ = "publishing_worker_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    process_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    version: Mapped[str] = mapped_column(String(30))
    concurrency: Mapped[int] = mapped_column(Integer)
    active_jobs: Mapped[int] = mapped_column(Integer)
    draining: Mapped[bool] = mapped_column(Boolean, default=False)
    shutdown_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0)
    lease_renewal_failures: Mapped[int] = mapped_column(Integer, default=0)
    stale_recoveries: Mapped[int] = mapped_column(Integer, default=0)
    graceful_shutdowns: Mapped[int] = mapped_column(Integer, default=0)


class PublishingRecoveryRecord(Base):
    __tablename__ = "publishing_recovery_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_jobs.id", ondelete="CASCADE"), index=True
    )
    worker_id: Mapped[str | None] = mapped_column(String(160))
    publishing_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_executions.id", ondelete="SET NULL")
    )
    result: Mapped[str] = mapped_column(String(40), index=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    safe_message: Mapped[str] = mapped_column(String(500))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
