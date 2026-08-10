import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_prompt_template_key_version"),
        CheckConstraint("status IN ('enabled', 'disabled')", name="ck_prompt_templates_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer)
    template_type: Mapped[str] = mapped_column(String(50), index=True)
    system_instructions: Mapped[str] = mapped_column(Text)
    user_template: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), index=True)
    is_default: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIGenerationRequest(Base):
    __tablename__ = "ai_generation_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_generation_requests_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="RESTRICT")
    )
    provider_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), index=True)
    additional_instructions: Mapped[str | None] = mapped_column(String(2000))
    normalized_input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    selected_model: Mapped[str | None] = mapped_column(String(120))
    final_provider_key: Mapped[str | None] = mapped_column(String(100))
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    cost_currency: Mapped[str | None] = mapped_column(String(3))
    channel: Mapped[str] = mapped_column(String(40), default="canonical")
    content_type: Mapped[str] = mapped_column(String(60), default="product_content")
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    context_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    brand_voice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    generation_reason: Mapped[str] = mapped_column(String(80), default="initial")
    user_instruction_fingerprint: Mapped[str | None] = mapped_column(String(64))


class AIProviderConfiguration(Base):
    __tablename__ = "ai_provider_configurations"
    __table_args__ = (
        UniqueConstraint("owner_id", "provider_key", name="uq_ai_provider_owner_key"),
        CheckConstraint(
            "request_timeout_seconds BETWEEN 10 AND 120", name="ck_ai_provider_timeout"
        ),
        CheckConstraint("max_retry_attempts BETWEEN 1 AND 5", name="ck_ai_provider_retries"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider_key: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(160))
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    credential_version: Mapped[int] = mapped_column(Integer, default=1)
    base_url: Mapped[str] = mapped_column(String(500))
    default_model: Mapped[str] = mapped_column(String(120))
    manual_model_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_provider_key: Mapped[str | None] = mapped_column(String(100))
    request_timeout_seconds: Mapped[int] = mapped_column(Integer, default=45)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_status: Mapped[str] = mapped_column(String(20), default="unknown")
    safe_validation_message: Mapped[str | None] = mapped_column(String(500))
    last_validation_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_successful_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIGenerationAttempt(Base):
    __tablename__ = "ai_generation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "generation_request_id", "attempt_number", name="uq_ai_generation_attempt_number"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_generation_requests.id", ondelete="CASCADE"),
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider_key: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    usage_source: Mapped[str] = mapped_column(String(20), default="unavailable")
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    cost_currency: Mapped[str | None] = mapped_column(String(3))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class AIModelPricing(Base):
    __tablename__ = "ai_model_pricing"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "provider_key",
            "model_pattern",
            "effective_from",
            name="uq_ai_model_pricing_effective",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider_key: Mapped[str] = mapped_column(String(100))
    model_pattern: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    input_cost_per_million_tokens: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    output_cost_per_million_tokens: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_note: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"
    __table_args__ = (
        UniqueConstraint("product_id", "version_number", name="uq_artifact_product_version"),
        UniqueConstraint("generation_request_id", name="uq_artifact_generation_request"),
        CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected', 'superseded')",
            name="ck_generated_artifacts_status",
        ),
        CheckConstraint("version_number > 0", name="ck_generated_artifacts_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    generation_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_generation_requests.id", ondelete="RESTRICT")
    )
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="RESTRICT")
    )
    artifact_type: Mapped[str] = mapped_column(String(50))
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), index=True)
    content_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    validation_result: Mapped[dict[str, object]] = mapped_column(JSONB)
    provider_metadata: Mapped[dict[str, object]] = mapped_column(JSONB)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    rejection_category: Mapped[str | None] = mapped_column(String(80))
    rejection_feedback: Mapped[str | None] = mapped_column(Text)
    rejection_field_notes: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    rejection_regeneration_guidance: Mapped[str | None] = mapped_column(String(1000))
    channel: Mapped[str] = mapped_column(String(40), default="canonical", index=True)
    content_type: Mapped[str] = mapped_column(String(60), default="product_content", index=True)
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    context_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    brand_voice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    parent_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    source_artifact_version: Mapped[int | None] = mapped_column(Integer)
    source_locale: Mapped[str | None] = mapped_column(String(16))
    source_product_context: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    generation_reason: Mapped[str] = mapped_column(String(80), default="initial")
    source: Mapped[str] = mapped_column(String(30), default="ai_generated")
    user_instructions: Mapped[str | None] = mapped_column(Text)
    input_context_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
