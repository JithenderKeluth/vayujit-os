"""Persistent AI Content + SEO Studio records layered on GeneratedArtifact."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base


class BrandVoice(Base):
    __tablename__ = "ai_brand_voices"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", "version", name="uq_ai_brand_voice_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    tone: Mapped[str] = mapped_column(String(80), default="professional")
    personality: Mapped[str | None] = mapped_column(String(500))
    terminology_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    target_audience: Mapped[str | None] = mapped_column(String(500))
    preferred_phrases_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    prohibited_phrases_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    spelling_conventions: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(16), default="en")
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    formatting_preferences_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    compliance_notes: Mapped[str | None] = mapped_column(String(1000))
    custom_instructions: Mapped[str | None] = mapped_column(String(2000))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GenerationPreset(Base):
    __tablename__ = "ai_generation_presets"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", "version", name="uq_ai_generation_preset_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    brand_voice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_brand_voices.id", ondelete="SET NULL")
    )
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    guidance: Mapped[str | None] = mapped_column(String(2000))
    preferred_provider: Mapped[str | None] = mapped_column(String(100))
    preferred_model: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    output_types_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    channels_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    tone: Mapped[str | None] = mapped_column(String(80))
    length: Mapped[str | None] = mapped_column(String(40))
    required_context_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    validation_rules_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KeywordSet(Base):
    __tablename__ = "ai_keyword_sets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    primary_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    secondary_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    marketplace_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    website_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    campaign_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    negative_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded_keywords_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    competitor_references_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(String(80), default="manual")
    notes: Mapped[str | None] = mapped_column(String(1000))
    locale: Mapped[str] = mapped_column(String(16), default="en-IN", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIStudioGeneration(Base):
    __tablename__ = "ai_studio_generations"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_studio_generation_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_ids_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    channels_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    content_types_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    brand_voice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_brand_voices.id", ondelete="SET NULL")
    )
    preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_generation_presets.id", ondelete="SET NULL")
    )
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    user_instructions: Mapped[str | None] = mapped_column(String(2000))
    provider_key: Mapped[str] = mapped_column(String(100), default="deterministic_mock_v1")
    model: Mapped[str] = mapped_column(String(120), default="studio-deterministic-v1")
    context_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="completed", index=True)
    total_outputs: Mapped[int] = mapped_column(Integer, default=0)
    completed_outputs: Mapped[int] = mapped_column(Integer, default=0)
    failed_outputs: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    failure_category: Mapped[str | None] = mapped_column(String(80), index=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_actions_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    context_refresh_required: Mapped[bool] = mapped_column(Boolean, default=False)


class AIStudioOutput(Base):
    __tablename__ = "ai_studio_outputs"
    __table_args__ = (
        UniqueConstraint(
            "generation_id",
            "product_id",
            "channel",
            "content_type",
            name="uq_ai_studio_output_target",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_generations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(40))
    content_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIStudioJob(Base):
    """Durable AI work item represented in the shared worker runtime."""

    __tablename__ = "ai_studio_jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_ai_studio_job_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_generations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(40), index=True)
    channel: Mapped[str] = mapped_column(String(40))
    content_type: Mapped[str] = mapped_column(String(60))
    locale: Mapped[str] = mapped_column(String(16))
    context_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    brand_voice_version: Mapped[int | None] = mapped_column(Integer)
    preset_version: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(120))
    user_instruction_fingerprint: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    provider_result_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    provider_result_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL"), index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(160), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    failure_category: Mapped[str | None] = mapped_column(String(80), index=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_actions_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    context_refresh_required: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    calculated_delay_seconds: Mapped[int | None] = mapped_column(Integer)
    applied_delay_seconds: Mapped[int | None] = mapped_column(Integer)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIStudioJobAttempt(Base):
    __tablename__ = "ai_studio_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_ai_studio_job_attempt_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_studio_jobs.id", ondelete="CASCADE"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(24))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    failure_category: Mapped[str | None] = mapped_column(String(80))
    calculated_delay_seconds: Mapped[int | None] = mapped_column(Integer)
    applied_delay_seconds: Mapped[int | None] = mapped_column(Integer)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer)
    checkpoint_fingerprint: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
