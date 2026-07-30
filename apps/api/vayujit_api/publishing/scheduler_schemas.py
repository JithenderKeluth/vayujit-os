import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecurrenceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: Literal["daily", "weekly", "monthly"]
    interval: int = Field(default=1, ge=1, le=366)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    fold: Literal[0, 1] = 0


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    artifact_id: uuid.UUID
    destination_id: uuid.UUID
    requested_action: Literal[
        "create_draft",
        "publish",
        "update",
        "move_to_draft",
        "update_product",
        "activate_product",
        "archive_product",
        "reconcile",
    ] = "publish"
    local_scheduled_at: datetime
    timezone_name: str = Field(min_length=1, max_length=100)
    schedule_type: Literal["one_time", "recurring"] = "one_time"
    recurrence: RecurrenceRule | None = None
    recurrence_end_at: datetime | None = None
    max_occurrences: int = Field(default=100, ge=1, le=1000)
    missed_occurrence_policy: Literal["skip_missed", "next_occurrence", "one_catch_up"] = (
        "next_occurrence"
    )


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    local_scheduled_at: datetime | None = None
    timezone_name: str | None = Field(default=None, min_length=1, max_length=100)
    recurrence: RecurrenceRule | None = None
    recurrence_end_at: datetime | None = None
    max_occurrences: int | None = Field(default=None, ge=1, le=1000)


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    connector_key: str
    requested_action: str
    schedule_type: str
    scheduled_at_utc: datetime
    timezone_name: str
    local_scheduled_at: datetime
    recurrence_json: dict[str, object] | None
    recurrence_end_at: datetime | None
    enabled: bool
    paused: bool
    archived: bool
    next_run_at_utc: datetime | None
    last_run_at_utc: datetime | None
    last_result: str | None
    created_at: datetime
    updated_at: datetime
    missed_occurrence_policy: str
    max_occurrences: int
    materialized_occurrence_count: int


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    schedule_id: uuid.UUID | None
    publishing_execution_id: uuid.UUID | None
    connector_key: str
    requested_action: str
    state: str
    priority: int
    scheduled_at_utc: datetime
    available_at_utc: datetime
    claim_count: int
    execution_attempt_count: int
    max_execution_attempts: int
    last_error_code: str | None
    last_error_message: str | None
    retryable: bool
    created_at: datetime
    updated_at: datetime
    product_id: uuid.UUID
    artifact_id: uuid.UUID
    artifact_version: int
    destination_id: uuid.UUID
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    next_retry_at: datetime | None
    correlation_id: str | None
    recovery_state: str | None
    recovery_reason: str | None
    maintenance_blocked_at: datetime | None


class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    worker_id: str
    process_started_at: datetime
    last_heartbeat_at: datetime
    version: str
    concurrency: int
    active_jobs: int
    draining: bool
    shutdown_requested: bool
    safe_status: str
    completed_jobs: int
    failed_jobs: int
    lease_renewal_failures: int
    stale_recoveries: int
    graceful_shutdowns: int


class ResumeScheduleRequest(BaseModel):
    policy: Literal["skip_missed", "next_occurrence", "one_catch_up"]


class OccurrencePreview(BaseModel):
    local: datetime
    utc: datetime


class SchedulePreviewRequest(BaseModel):
    local_scheduled_at: datetime
    timezone_name: str
    schedule_type: Literal["one_time", "recurring"]
    recurrence: RecurrenceRule | None = None
    count: int = Field(default=5, ge=1, le=10)


class SchedulePreviewResponse(BaseModel):
    occurrences: list[OccurrencePreview]
    dst_warning: str | None


class Page(BaseModel):
    items: list[object]
    page: int
    page_size: int
    total: int
    pages: int
