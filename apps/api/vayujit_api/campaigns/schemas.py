import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CampaignStatus = Literal[
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
]
ActivityType = Literal[
    "wordpress_create_draft",
    "wordpress_publish",
    "wordpress_update",
    "wordpress_move_to_draft",
    "shopify_create_draft",
    "shopify_update_product",
    "shopify_activate_product",
    "shopify_archive_product",
    "shopify_reconcile",
    "review_checkpoint",
    "approval_checkpoint",
]


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    objective: str = Field(default="", max_length=500)
    priority: int = Field(default=0, ge=-100, le=100)
    timezone_name: str = Field(min_length=1, max_length=100)
    local_start_at: datetime
    local_end_at: datetime
    default_destination_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    approval_policy: Literal[
        "all_artifacts_preapproved",
        "approve_before_scheduling",
        "approve_before_execution",
        "manual_campaign_release",
    ] = "approve_before_scheduling"
    scheduling_policy: Literal[
        "strict_window", "warn_outside_window", "allow_with_confirmation"
    ] = "strict_window"
    conflict_policy: Literal["block", "allow_warnings"] = "block"

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "CampaignCreate":
        if self.local_end_at <= self.local_start_at:
            raise ValueError("Campaign end must be after its start.")
        return self


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    objective: str | None = Field(default=None, max_length=500)
    priority: int | None = Field(default=None, ge=-100, le=100)
    timezone_name: str | None = Field(default=None, min_length=1, max_length=100)
    local_start_at: datetime | None = None
    local_end_at: datetime | None = None
    row_version: int = Field(ge=1)


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    slug: str
    description: str
    objective: str
    status: CampaignStatus
    priority: int
    timezone_name: str
    start_at_utc: datetime
    end_at_utc: datetime
    local_start_at: datetime
    local_end_at: datetime
    approval_policy: str
    scheduling_policy: str
    conflict_policy: str
    created_at: datetime
    updated_at: datetime
    launched_at: datetime | None
    paused_at: datetime | None
    completed_at: datetime | None
    archived_at: datetime | None
    cancellation_reason: str | None
    row_version: int


class ActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: uuid.UUID | None = None
    artifact_id: uuid.UUID | None = None
    destination_id: uuid.UUID | None = None
    activity_type: ActivityType
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    sequence: int = Field(ge=1, le=500)
    scheduled_local_date: date
    scheduled_local_time: time
    timezone_name: str | None = Field(default=None, max_length=100)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    required: bool = True
    enabled: bool = True


class ActivityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    scheduled_local_date: date | None = None
    scheduled_local_time: time | None = None
    timezone_name: str | None = Field(default=None, max_length=100)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    required: bool | None = None
    enabled: bool | None = None
    row_version: int = Field(ge=1)


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campaign_id: uuid.UUID
    product_id: uuid.UUID | None
    artifact_id: uuid.UUID | None
    artifact_version: int | None
    destination_id: uuid.UUID | None
    connector_key: str | None
    requested_action: str | None
    activity_type: str
    name: str
    description: str
    sequence: int
    scheduled_local_date: date
    scheduled_local_time: time
    timezone_name: str
    scheduled_at_utc: datetime
    duration_minutes: int | None
    status: str
    readiness_status: str
    schedule_id: uuid.UUID | None
    job_id: uuid.UUID | None
    publishing_execution_id: uuid.UUID | None
    required: bool
    enabled: bool
    failure_code: str | None
    safe_failure_message: str | None
    correlation_id: str | None
    row_version: int


class DependencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predecessor_activity_id: uuid.UUID
    successor_activity_id: uuid.UUID
    dependency_type: Literal[
        "finish_to_start", "success_required", "completion_required", "manual_release"
    ] = "success_required"


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    predecessor_activity_id: uuid.UUID
    successor_activity_id: uuid.UUID
    dependency_type: str
    released_at: datetime | None


class ReadinessIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    safe_message: str
    activity_id: uuid.UUID | None = None
    suggested_resolution: str
    navigation_target: str | None = None


class ReadinessResponse(BaseModel):
    state: Literal["ready", "incomplete", "blocked", "warning", "invalid"]
    issues: list[ReadinessIssue]


class Conflict(BaseModel):
    conflict_type: str
    severity: Literal["warning", "error"]
    activity_ids: list[uuid.UUID]
    safe_explanation: str
    suggested_correction: str
    override_allowed: bool


class ScheduleRequest(BaseModel):
    activity_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    behavior: Literal["schedule_ready_only", "require_all_ready"] = "require_all_ready"
    confirm: bool = False


class LifecycleRequest(BaseModel):
    confirm: bool = False
    reason: str | None = Field(default=None, max_length=500)
    missed_activity_policy: (
        Literal["skip_missed", "run_next", "one_catch_up", "reschedule_manually"] | None
    ) = None


class ActivityTimeChange(BaseModel):
    activity_id: uuid.UUID
    scheduled_local_date: date
    scheduled_local_time: time
    timezone_name: str
    row_version: int = Field(ge=1)


class RescheduleRequest(BaseModel):
    changes: list[ActivityTimeChange] = Field(min_length=1, max_length=100)
    confirm: bool = False


class CalendarEvent(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    activity_id: uuid.UUID
    activity_name: str
    brand_id: uuid.UUID
    product_id: uuid.UUID | None
    destination_id: uuid.UUID | None
    connector_key: str | None
    requested_action: str | None
    status: str
    readiness_status: str
    scheduled_at_utc: datetime
    timezone_name: str
    has_conflict: bool


class MonthDay(BaseModel):
    date: date
    activity_count: int
    campaign_count: int
    status_summary: dict[str, int]
    conflict_count: int
    previews: list[CalendarEvent]
    overflow_count: int


class MonthCalendar(BaseModel):
    view: Literal["month"] = "month"
    start: datetime
    end: datetime
    days: list[MonthDay]


class WeekSlot(BaseModel):
    date: date
    events: list[CalendarEvent]
    destination_workload: dict[str, int]
    overlap_count: int


class WeekCalendar(BaseModel):
    view: Literal["week"] = "week"
    start: datetime
    end: datetime
    timezone_name: str
    slots: list[WeekSlot]


class AgendaDay(BaseModel):
    date: date
    events: list[CalendarEvent]


class AgendaCalendar(BaseModel):
    view: Literal["agenda"] = "agenda"
    start: datetime
    end: datetime
    days: list[AgendaDay]
    next_offset: int | None


class ResumePreviewResponse(BaseModel):
    missed: list[uuid.UUID]
    required_missed: list[uuid.UUID]
    optional_missed: list[uuid.UUID]
    to_skip: list[uuid.UUID]
    catch_up: uuid.UUID | None
    next_future: uuid.UUID | None
    blocked_successors: list[uuid.UUID]
    confirmation_required: bool


class ProgressResponse(BaseModel):
    total: int
    required: int
    optional: int
    ready: int
    scheduled: int
    running: int
    succeeded: int
    failed: int
    blocked: int
    cancelled: int
    completion_percentage: int
