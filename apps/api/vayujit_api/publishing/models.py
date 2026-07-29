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
