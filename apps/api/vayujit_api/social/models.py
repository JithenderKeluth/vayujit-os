from __future__ import annotations

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

SOCIAL_PLATFORMS = ("instagram", "facebook", "youtube")
SOCIAL_STATUSES = (
    "draft",
    "pending_review",
    "approved",
    "scheduled",
    "publishing",
    "published",
    "failed",
    "cancelled",
)
CONTENT_TYPES = (
    "instagram_post",
    "instagram_story",
    "instagram_reel",
    "facebook_post",
    "facebook_story",
    "facebook_reel",
    "youtube_video",
    "youtube_short",
    "youtube_community_post",
    "youtube_thumbnail",
    "generic_social_post",
)


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "platform", "remote_account_id", name="uq_social_account_remote"
        ),
        CheckConstraint(
            "platform IN ('instagram','facebook','youtube')", name="ck_social_platform"
        ),
        CheckConstraint(
            "validation_status IN ('unknown','valid','invalid')", name="ck_social_validation"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(24), index=True)
    identity_type: Mapped[str] = mapped_column(String(32), default="account")
    display_name: Mapped[str] = mapped_column(String(160))
    remote_account_id: Mapped[str] = mapped_column(String(200))
    environment: Mapped[str] = mapped_column(String(24), default="local")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    validation_status: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    capabilities_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    credential_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SocialPost(Base):
    __tablename__ = "social_posts"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_social_post_idempotency"),
        CheckConstraint(
            "platform IN ('instagram','facebook','youtube')", name="ck_social_post_platform"
        ),
        CheckConstraint(
            "lifecycle_status IN ("
            "'draft','pending_review','approved','scheduled','publishing','published','failed','cancelled')",
            name="ck_social_post_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="RESTRICT"), index=True
    )
    platform: Mapped[str] = mapped_column(String(24), index=True)
    content_type: Mapped[str] = mapped_column(String(48), index=True)
    content_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT"), index=True
    )
    content_artifact_version: Mapped[int] = mapped_column(Integer)
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="SET NULL")
    )
    source_artifact_version: Mapped[int | None] = mapped_column(Integer)
    generation_reason: Mapped[str | None] = mapped_column(String(40))
    media_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    caption: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    cta_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    destination_url: Mapped[str | None] = mapped_column(String(2048))
    scheduled_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    timezone_name: Mapped[str | None] = mapped_column(String(100))
    lifecycle_status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    remote_publication_id: Mapped[str | None] = mapped_column(String(200), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    preview_fingerprint: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_failure_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SocialMetric(Base):
    __tablename__ = "social_metrics"
    __table_args__ = (UniqueConstraint("post_id", "metric_key", name="uq_social_metric_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="CASCADE"), index=True
    )
    metric_key: Mapped[str] = mapped_column(String(40))
    value: Mapped[float | None] = mapped_column()
    availability: Mapped[str] = mapped_column(String(20), default="not_synced")
    source: Mapped[str] = mapped_column(String(30), default="synthetic_test_data")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
