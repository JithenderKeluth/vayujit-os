import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from vayujit_api.core.database import Base

CAMPAIGN_STATUSES = (
    "draft",
    "planning",
    "ready",
    "scheduled",
    "running",
    "paused",
    "partially_completed",
    "completed",
    "failed",
    "cancelled",
    "archived",
)
ACTIVITY_STATUSES = (
    "draft",
    "blocked",
    "ready",
    "scheduled",
    "waiting_dependency",
    "queued",
    "running",
    "retrying",
    "succeeded",
    "failed",
    "dead_letter",
    "cancel_requested",
    "cancelled",
    "paused",
    "maintenance_blocked",
    "reconciliation_required",
    "completed_with_warning",
    "archived",
)


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_campaign_owner_slug"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{value}'" for value in CAMPAIGN_STATUSES) + ")",
            name="ck_campaign_status",
        ),
        CheckConstraint("priority BETWEEN -100 AND 100", name="ck_campaign_priority"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    timezone_name: Mapped[str] = mapped_column(String(100))
    start_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    local_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    local_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    campaign_manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    approval_policy: Mapped[str] = mapped_column(String(40))
    scheduling_policy: Mapped[str] = mapped_column(String(40))
    conflict_policy: Mapped[str] = mapped_column(String(40))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class CampaignDefaultDestination(Base):
    __tablename__ = "campaign_default_destinations"
    __table_args__ = (
        UniqueConstraint("campaign_id", "destination_id", name="uq_campaign_default_destination"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_destinations.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CampaignActivity(Base):
    __tablename__ = "campaign_activities"
    __table_args__ = (
        UniqueConstraint("campaign_id", "sequence", name="uq_campaign_activity_sequence"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_campaign_activity_identity"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{value}'" for value in ACTIVITY_STATUSES) + ")",
            name="ck_campaign_activity_status",
        ),
        CheckConstraint(
            "readiness_status IN ('ready','incomplete','blocked','warning','invalid')",
            name="ck_campaign_activity_readiness",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_artifacts.id", ondelete="RESTRICT")
    )
    artifact_version: Mapped[int | None] = mapped_column(Integer)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishing_destinations.id", ondelete="RESTRICT"),
        index=True,
    )
    connector_key: Mapped[str | None] = mapped_column(String(80))
    requested_action: Mapped[str | None] = mapped_column(String(30))
    activity_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    sequence: Mapped[int] = mapped_column(Integer)
    dependency_policy: Mapped[str] = mapped_column(String(30), default="success_required")
    scheduled_local_date: Mapped[date] = mapped_column(Date)
    scheduled_local_time: Mapped[time] = mapped_column(Time)
    timezone_name: Mapped[str] = mapped_column(String(100))
    scheduled_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), index=True)
    readiness_status: Mapped[str] = mapped_column(String(20), index=True)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_schedules.id", ondelete="SET NULL")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_jobs.id", ondelete="SET NULL")
    )
    publishing_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_executions.id", ondelete="SET NULL")
    )
    workflow_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="SET NULL")
    )
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    safe_failure_message: Mapped[str | None] = mapped_column(String(500))
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    row_version: Mapped[int] = mapped_column(Integer, default=1)


class CampaignActivityDependency(Base):
    __tablename__ = "campaign_activity_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "predecessor_activity_id",
            "successor_activity_id",
            name="uq_campaign_activity_dependency_edge",
        ),
        CheckConstraint(
            "dependency_type IN "
            "('finish_to_start','success_required','completion_required','manual_release')",
            name="ck_campaign_dependency_type",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    predecessor_activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_activities.id", ondelete="CASCADE")
    )
    successor_activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_activities.id", ondelete="CASCADE")
    )
    dependency_type: Mapped[str] = mapped_column(String(30))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CampaignScheduleLink(Base):
    __tablename__ = "campaign_schedule_links"
    __table_args__ = (
        UniqueConstraint("activity_id", "schedule_id", name="uq_campaign_activity_schedule"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_activities.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_schedules.id", ondelete="RESTRICT"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishing_jobs.id", ondelete="SET NULL")
    )
    occurrence_key: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
