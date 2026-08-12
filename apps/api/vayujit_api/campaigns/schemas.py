import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

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
    "mock_publish",
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
    campaign_manager_user_id: uuid.UUID | None = None
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
    replaces_activity_id: uuid.UUID | None = None
    social_post_id: uuid.UUID | None = None
    social_platform: str | None = None
    social_account_id: uuid.UUID | None = None
    social_content_type: str | None = None
    social_media_ids: list[str] = []
    social_timezone_name: str | None = None
    replaced_by_activity_id: uuid.UUID | None = None
    replacement_reason: str | None = None
    replacement_created_at: datetime | None = None
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
    catch_up_replacement: uuid.UUID | None = None
    next_future: uuid.UUID | None
    blocked_successors: list[uuid.UUID]
    confirmation_required: bool


class WorkflowActionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correlation_id: str = Field(min_length=8, max_length=64)


class CreateCampaignAction(WorkflowActionBase):
    action: Literal["create_campaign"]
    campaign: CampaignCreate


class UpdateCampaignAction(WorkflowActionBase):
    action: Literal["update_campaign"]
    campaign_id: uuid.UUID
    changes: CampaignUpdate


class AddCampaignActivityAction(WorkflowActionBase):
    action: Literal["add_campaign_activity"]
    campaign_id: uuid.UUID
    activity: ActivityCreate


class AddCampaignDependencyAction(WorkflowActionBase):
    action: Literal["add_campaign_dependency"]
    campaign_id: uuid.UUID
    dependency: DependencyCreate


class CampaignIdAction(WorkflowActionBase):
    campaign_id: uuid.UUID


class ValidateCampaignAction(CampaignIdAction):
    action: Literal["validate_campaign"]


class ReleaseCampaignAction(CampaignIdAction):
    action: Literal["release_campaign"]
    confirm: Literal[True]


class ScheduleCampaignAction(CampaignIdAction):
    action: Literal["schedule_campaign"]
    request: ScheduleRequest


class PauseCampaignAction(CampaignIdAction):
    action: Literal["pause_campaign"]


class ResumeCampaignAction(CampaignIdAction):
    action: Literal["resume_campaign"]
    missed_activity_policy: Literal[
        "skip_missed", "run_next", "one_catch_up", "reschedule_manually"
    ]


class CancelCampaignAction(CampaignIdAction):
    action: Literal["cancel_campaign"]
    reason: str = Field(min_length=1, max_length=500)


class WaitForCampaignAction(CampaignIdAction):
    action: Literal["wait_for_campaign"]
    workflow_instance_id: uuid.UUID
    workflow_step_id: uuid.UUID
    expected_state: Literal[
        "scheduled",
        "running",
        "partially_completed",
        "completed",
        "failed",
        "cancelled",
        "blocked",
    ] = "completed"


CampaignWorkflowAction = Annotated[
    CreateCampaignAction
    | UpdateCampaignAction
    | AddCampaignActivityAction
    | AddCampaignDependencyAction
    | ValidateCampaignAction
    | ReleaseCampaignAction
    | ScheduleCampaignAction
    | PauseCampaignAction
    | ResumeCampaignAction
    | CancelCampaignAction
    | WaitForCampaignAction,
    Field(discriminator="action"),
]


class CampaignWorkflowResult(BaseModel):
    result: Literal[
        "campaign_created",
        "campaign_updated",
        "activity_created",
        "dependency_created",
        "campaign_validated",
        "campaign_released",
        "campaign_scheduled",
        "campaign_paused",
        "campaign_resumed",
        "campaign_cancelled",
        "campaign_wait_created",
        "campaign_wait_completed",
        "campaign_wait_failed",
    ]
    campaign_id: uuid.UUID
    correlation_id: str
    status: str
    activity_id: uuid.UUID | None = None
    dependency_id: uuid.UUID | None = None
    schedule_ids: list[uuid.UUID] = Field(default_factory=list)
    job_ids: list[uuid.UUID] = Field(default_factory=list)
    scheduled_activity_ids: list[uuid.UUID] = Field(default_factory=list)
    blocked_activity_ids: list[uuid.UUID] = Field(default_factory=list)
    readiness_state: str | None = None
    blocking_issue_count: int = 0
    warning_count: int = 0
    conflict_count: int = 0
    workflow_wait_id: uuid.UUID | None = None


class SelectorItem(BaseModel):
    id: uuid.UUID
    label: str
    kind: Literal["brand", "product", "artifact", "destination", "manager", "activity"]
    disabled: bool = False
    disabled_reason: str | None = None
    version: int | None = None
    status: str
    connector_key: str | None = None
    product_id: uuid.UUID | None = None


class SelectorPage(BaseModel):
    items: list[SelectorItem]
    page: int
    page_size: int
    total: int


CampaignRecoveryActionKey = Literal[
    "retry_activity",
    "reconcile_activity",
    "open_campaign",
    "open_activity",
    "open_product",
    "open_artifact",
    "open_destination",
    "open_job",
    "open_publishing_execution",
    "review_dependency",
    "release_checkpoint",
    "replace_with_new_approved_activity",
    "skip_optional_activity",
    "reschedule_activity",
    "create_one_catch_up",
    "skip_missed_activity",
    "resume_campaign",
    "pause_campaign",
    "cancel_activity",
    "cancel_campaign",
    "retry_campaign_workflow_wait",
]


class CampaignRecoveryProjection(BaseModel):
    recovery_type: str
    campaign_id: uuid.UUID
    campaign_name: str
    campaign_status: str
    activity_id: uuid.UUID | None
    activity_name: str | None
    required: bool | None
    product_id: uuid.UUID | None
    artifact_id: uuid.UUID | None
    artifact_version: int | None
    destination_id: uuid.UUID | None
    connector_key: str | None
    schedule_id: uuid.UUID | None
    job_id: uuid.UUID | None
    publishing_execution_id: uuid.UUID | None
    workflow_wait_id: uuid.UUID | None
    safe_failure_message: str
    correlation_id: str | None
    eligible_actions: list[CampaignRecoveryActionKey]
    catch_up_activity_id: uuid.UUID | None = None
    catch_up_schedule_id: uuid.UUID | None = None
    catch_up_job_id: uuid.UUID | None = None
    catch_up_status: str | None = None


class CampaignRecoveryActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: CampaignRecoveryActionKey
    campaign_id: uuid.UUID
    activity_id: uuid.UUID | None = None
    workflow_wait_id: uuid.UUID | None = None
    replacement_artifact_id: uuid.UUID | None = None
    replacement_artifact_version: int | None = Field(default=None, ge=1, le=2_147_483_647)
    expected_activity_row_version: int | None = Field(default=None, ge=1)
    reason: str = Field(default="Operator recovery action.", max_length=500)
    confirm: Literal[True]
    proposed_local_datetime: datetime | None = None
    proposed_timezone: str | None = Field(default=None, max_length=100)
    fold: Literal[0, 1] | None = None
    preview_fingerprint: str | None = Field(default=None, max_length=128)


CampaignRecoveryRequest = CampaignRecoveryActionRequest


class ReschedulePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: uuid.UUID
    proposed_local_datetime: datetime
    proposed_timezone: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=500)
    expected_activity_row_version: int = Field(ge=1)
    fold: Literal[0, 1] | None = None


class ReschedulePreviewResponse(BaseModel):
    campaign_id: uuid.UUID
    activity_id: uuid.UUID
    original_scheduled_at_utc: datetime
    proposed_local_datetime: datetime
    proposed_scheduled_at_utc: datetime
    timezone: str
    confirmation_required: bool
    preview_fingerprint: str
    safe_message: str
    correlation_id: str
    dst_classification: str = "normal"
    utc_offset: str | None = None
    fold: int | None = None
    issue_code: str | None = None
    warnings: list[str] = Field(default_factory=list)
    readiness_issues: list[ReadinessIssue] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    current_schedule_status: str | None = None
    current_job_status: str | None = None


class CatchUpPreviewRequest(ReschedulePreviewRequest):
    """Preview input for creating one durable catch-up occurrence."""


class CatchUpPreviewResponse(ReschedulePreviewResponse):
    original_activity_name: str
    original_activity_status: str
    artifact_id: uuid.UUID | None = None
    artifact_version: int | None = None
    artifact_status: str | None = None
    destination_id: uuid.UUID | None = None
    destination_status: str | None = None
    dependency_warnings: list[str] = Field(default_factory=list)


class RescheduleHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campaign_id: uuid.UUID
    activity_id: uuid.UUID
    original_schedule_id: uuid.UUID | None
    replacement_schedule_id: uuid.UUID | None
    original_job_id: uuid.UUID | None
    replacement_job_id: uuid.UUID | None
    original_scheduled_for_utc: datetime | None
    requested_local_datetime: datetime
    requested_timezone: str
    resolved_scheduled_for_utc: datetime
    reason: str
    status: str
    requested_at: datetime
    confirmed_at: datetime | None
    confirmed_by: uuid.UUID | None


class CampaignRecoveryActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: CampaignRecoveryActionKey
    outcome: str
    resource_ids: dict[str, str] = Field(default_factory=dict)
    safe_message: str
    navigation_targets: dict[str, str] = Field(default_factory=dict)
    confirmation_required: bool
    correlation_id: str
    idempotency_result: str
    scheduled: bool = False
    status: str | None = None
    idempotent_reuse: bool = False
    publishing_execution_id: uuid.UUID | None = None
    reconciliation_status: str | None = None


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
