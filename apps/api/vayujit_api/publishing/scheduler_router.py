import hashlib
import math
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.publishing.job_queue import TERMINAL_STATES
from vayujit_api.publishing.models import (
    PublishingJob,
    PublishingJobAttempt,
    PublishingSchedule,
    PublishingWorkerHeartbeat,
)
from vayujit_api.publishing.scheduler_schemas import (
    JobResponse,
    OccurrencePreview,
    ResumeScheduleRequest,
    ScheduleCreate,
    SchedulePreviewRequest,
    SchedulePreviewResponse,
    ScheduleResponse,
    ScheduleUpdate,
    WorkerResponse,
)
from vayujit_api.publishing.scheduler_service import create_schedule, update_schedule
from vayujit_api.publishing.scheduler_time import local_to_utc, next_utc_occurrence, utcnow

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing-scheduler"])
operations_router = APIRouter(prefix="/api/v1/operations", tags=["scheduler-operations"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def owned_schedule(db: DB, owner: Owner, schedule_id: uuid.UUID) -> PublishingSchedule:
    value = db.scalar(
        select(PublishingSchedule).where(
            PublishingSchedule.id == schedule_id,
            PublishingSchedule.owner_id == owner.id,
        )
    )
    if not value:
        raise HTTPException(404, "Schedule not found.")
    return value


def owned_job(db: DB, owner: Owner, job_id: uuid.UUID) -> PublishingJob:
    value = db.scalar(
        select(PublishingJob).where(PublishingJob.id == job_id, PublishingJob.owner_id == owner.id)
    )
    if not value:
        raise HTTPException(404, "Publishing job not found.")
    return value


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
def schedule_create(data: ScheduleCreate, db: DB, owner: Owner) -> PublishingSchedule:
    try:
        return create_schedule(db, owner, data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/schedules")
def schedule_list(
    db: DB,
    owner: Owner,
    status: str | None = None,
    connector_key: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    filters = [PublishingSchedule.owner_id == owner.id]
    if status == "paused":
        filters.append(PublishingSchedule.paused.is_(True))
    elif status == "archived":
        filters.append(PublishingSchedule.archived.is_(True))
    elif status == "active":
        filters.extend(
            [
                PublishingSchedule.enabled.is_(True),
                PublishingSchedule.paused.is_(False),
                PublishingSchedule.archived.is_(False),
            ]
        )
    if connector_key:
        filters.append(PublishingSchedule.connector_key == connector_key)
    total = db.scalar(select(func.count()).select_from(PublishingSchedule).where(*filters)) or 0
    values = list(
        db.scalars(
            select(PublishingSchedule)
            .where(*filters)
            .order_by(
                PublishingSchedule.next_run_at_utc.asc().nullslast(),
                PublishingSchedule.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [ScheduleResponse.model_validate(value) for value in values],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
def schedule_get(schedule_id: uuid.UUID, db: DB, owner: Owner) -> PublishingSchedule:
    return owned_schedule(db, owner, schedule_id)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def schedule_patch(
    schedule_id: uuid.UUID, data: ScheduleUpdate, db: DB, owner: Owner
) -> PublishingSchedule:
    try:
        return update_schedule(db, owner, owned_schedule(db, owner, schedule_id), data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def set_schedule_state(
    schedule_id: uuid.UUID, db: DB, owner: Owner, action: str
) -> PublishingSchedule:
    value = owned_schedule(db, owner, schedule_id)
    timestamp = utcnow()
    if action == "pause":
        value.paused = True
    elif action == "resume":
        value.paused = False
    elif action == "archive":
        value.archived = True
        value.enabled = False
        value.next_run_at_utc = None
    value.updated_at = timestamp
    db.commit()
    db.refresh(value)
    return value


@router.post("/schedules/{schedule_id}/pause", response_model=ScheduleResponse)
def schedule_pause(schedule_id: uuid.UUID, db: DB, owner: Owner) -> PublishingSchedule:
    return set_schedule_state(schedule_id, db, owner, "pause")


@router.post("/schedules/{schedule_id}/resume", response_model=ScheduleResponse)
def schedule_resume(
    schedule_id: uuid.UUID,
    data: ResumeScheduleRequest,
    db: DB,
    owner: Owner,
) -> PublishingSchedule:
    value = owned_schedule(db, owner, schedule_id)
    if not value.paused:
        raise HTTPException(409, "Only a paused schedule can be resumed.")
    timestamp = utcnow()
    recurrence = value.recurrence_json or {}
    missed = 0
    catch_up_due = value.next_run_at_utc
    while (
        value.schedule_type == "recurring"
        and value.next_run_at_utc
        and value.next_run_at_utc <= timestamp
    ):
        missed += 1
        local_value, next_value = next_utc_occurrence(
            value.local_scheduled_at,
            value.timezone_name,
            recurrence,
            fold=int(cast(Any, recurrence.get("fold", 0))),
        )
        value.local_scheduled_at = local_value
        value.next_run_at_utc = next_value
    value.missed_occurrence_policy = data.policy
    value.paused = False
    value.updated_at = timestamp
    if data.policy == "one_catch_up" and missed and catch_up_due:
        key = f"schedule:{value.id}:catch-up:{timestamp.replace(microsecond=0).isoformat()}"
        job = PublishingJob(
            owner_id=owner.id,
            schedule_id=value.id,
            product_id=value.product_id,
            artifact_id=value.artifact_id,
            artifact_version=value.artifact_version,
            destination_id=value.destination_id,
            connector_key=value.connector_key,
            requested_action=value.requested_action,
            idempotency_key=key,
            state="pending",
            priority=1,
            scheduled_at_utc=catch_up_due,
            available_at_utc=timestamp,
            claim_count=0,
            execution_attempt_count=0,
            max_execution_attempts=get_settings().publishing_job_max_attempts,
            retryable=False,
            created_at=timestamp,
            updated_at=timestamp,
            row_version=1,
        )
        db.add(job)
        db.flush()
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.schedule_catch_up_created",
            entity_type="publishing_job",
            entity_id=job.id,
            metadata={"schedule_id": str(value.id), "missed_count": missed},
        )
    elif missed:
        record_event(
            db,
            actor_id=owner.id,
            action="publishing.schedule_occurrence_skipped",
            entity_type="publishing_schedule",
            entity_id=value.id,
            metadata={"missed_count": missed, "policy": data.policy},
        )
    db.commit()
    db.refresh(value)
    return value


@router.post("/schedules/preview", response_model=SchedulePreviewResponse)
def schedule_preview(data: SchedulePreviewRequest, owner: Owner) -> SchedulePreviewResponse:
    del owner
    recurrence = data.recurrence.model_dump() if data.recurrence else None
    if data.schedule_type == "recurring" and not recurrence:
        raise HTTPException(422, "Recurring preview requires a recurrence rule.")
    try:
        local = data.local_scheduled_at
        utc = local_to_utc(
            local,
            data.timezone_name,
            int(cast(Any, (recurrence or {}).get("fold", 0))),
        )
        values = [OccurrencePreview(local=local, utc=utc)]
        while recurrence and len(values) < data.count:
            local, utc = next_utc_occurrence(
                local,
                data.timezone_name,
                recurrence,
                fold=int(cast(Any, recurrence.get("fold", 0))),
            )
            values.append(OccurrencePreview(local=local, utc=utc))
        return SchedulePreviewResponse(occurrences=values, dst_warning=None)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.delete("/schedules/{schedule_id}", response_model=ScheduleResponse)
def schedule_archive(schedule_id: uuid.UUID, db: DB, owner: Owner) -> PublishingSchedule:
    return set_schedule_state(schedule_id, db, owner, "archive")


@router.get("/jobs")
def job_list(
    db: DB,
    owner: Owner,
    state: str | None = None,
    schedule_id: uuid.UUID | None = None,
    connector_key: str | None = None,
    destination_id: uuid.UUID | None = None,
    retryable: bool | None = None,
    overdue: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    filters = [PublishingJob.owner_id == owner.id]
    if state:
        filters.append(PublishingJob.state == state)
    if schedule_id:
        filters.append(PublishingJob.schedule_id == schedule_id)
    if connector_key:
        filters.append(PublishingJob.connector_key == connector_key)
    if destination_id:
        filters.append(PublishingJob.destination_id == destination_id)
    if retryable is not None:
        filters.append(PublishingJob.retryable.is_(retryable))
    if overdue:
        filters.extend(
            [
                PublishingJob.available_at_utc < utcnow(),
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
            ]
        )
    total = db.scalar(select(func.count()).select_from(PublishingJob).where(*filters)) or 0
    values = list(
        db.scalars(
            select(PublishingJob)
            .where(*filters)
            .order_by(PublishingJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [JobResponse.model_validate(value) for value in values],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/jobs/{job_id}", response_model=JobResponse)
def job_get(job_id: uuid.UUID, db: DB, owner: Owner) -> PublishingJob:
    return owned_job(db, owner, job_id)


@router.get("/jobs/{job_id}/attempts")
def job_attempts(job_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    owned_job(db, owner, job_id)
    values = db.scalars(
        select(PublishingJobAttempt)
        .where(PublishingJobAttempt.job_id == job_id)
        .order_by(PublishingJobAttempt.attempt_number)
    )
    return [
        {
            column.name: getattr(value, column.name)
            for column in PublishingJobAttempt.__table__.columns
        }
        for value in values
    ]


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def job_cancel(job_id: uuid.UUID, db: DB, owner: Owner) -> PublishingJob:
    value = owned_job(db, owner, job_id)
    if value.state not in TERMINAL_STATES:
        if value.state in {"claimed", "running"}:
            value.state = "cancel_requested"
        else:
            value.state = "cancelled"
            value.completed_at = utcnow()
        value.updated_at = utcnow()
        db.commit()
        db.refresh(value)
    return value


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
def job_retry(job_id: uuid.UUID, db: DB, owner: Owner) -> PublishingJob:
    value = owned_job(db, owner, job_id)
    if value.state not in {"failed", "dead_letter", "cancelled", "expired"}:
        raise HTTPException(409, "Only terminal unsuccessful jobs can be retried.")
    value.state = "pending"
    value.available_at_utc = utcnow()
    value.completed_at = None
    value.lease_owner = None
    value.lease_expires_at = None
    value.next_retry_at = None
    value.updated_at = utcnow()
    value.row_version += 1
    db.commit()
    db.refresh(value)
    return value


@router.get("/workers", response_model=list[WorkerResponse])
def worker_list(db: DB, owner: Owner) -> list[PublishingWorkerHeartbeat]:
    del owner
    return list(
        db.scalars(
            select(PublishingWorkerHeartbeat).order_by(
                PublishingWorkerHeartbeat.last_heartbeat_at.desc()
            )
        )
    )


@router.get("/scheduler/summary")
def scheduler_summary(db: DB, owner: Owner) -> dict[str, object]:
    now = utcnow()
    state_counts: dict[str, int] = {
        state: count
        for state, count in db.execute(
            select(PublishingJob.state, func.count())
            .where(PublishingJob.owner_id == owner.id)
            .group_by(PublishingJob.state)
        ).all()
    }
    active_schedules = db.scalar(
        select(func.count())
        .select_from(PublishingSchedule)
        .where(
            PublishingSchedule.owner_id == owner.id,
            PublishingSchedule.enabled.is_(True),
            PublishingSchedule.paused.is_(False),
            PublishingSchedule.archived.is_(False),
        )
    )
    live_workers = db.scalar(
        select(func.count())
        .select_from(PublishingWorkerHeartbeat)
        .where(PublishingWorkerHeartbeat.last_heartbeat_at >= now - timedelta(minutes=2))
    )
    return {
        "active_schedules": active_schedules or 0,
        "jobs": state_counts,
        "live_workers": live_workers or 0,
        "generated_at": now,
    }


def safe_worker_id(worker_id: str) -> str:
    return f"worker-{hashlib.sha256(worker_id.encode()).hexdigest()[:12]}"


@operations_router.get("/workers")
def operations_workers(db: DB, owner: Owner) -> list[dict[str, object]]:
    del owner
    timestamp = utcnow()
    values = db.scalars(
        select(PublishingWorkerHeartbeat).order_by(
            PublishingWorkerHeartbeat.last_heartbeat_at.desc()
        )
    )
    return [
        {
            "worker_id": safe_worker_id(value.worker_id),
            "status": (
                "draining"
                if value.draining
                else (
                    "online"
                    if value.last_heartbeat_at >= timestamp - timedelta(minutes=2)
                    else (
                        "stale"
                        if value.last_heartbeat_at >= timestamp - timedelta(minutes=10)
                        else "offline"
                    )
                )
            ),
            "version": value.version,
            "process_started_at": value.process_started_at,
            "last_heartbeat_at": value.last_heartbeat_at,
            "concurrency": value.concurrency,
            "active_jobs": value.active_jobs,
            "draining": value.draining,
            "shutdown_requested": value.shutdown_requested,
            "completed_jobs": value.completed_jobs,
            "failed_jobs": value.failed_jobs,
            "lease_renewal_failures": value.lease_renewal_failures,
            "stale_recoveries": value.stale_recoveries,
            "graceful_shutdowns": value.graceful_shutdowns,
        }
        for value in values
    ]


@operations_router.get("/workers/{worker_id}")
def operations_worker(worker_id: str, db: DB, owner: Owner) -> dict[str, object]:
    values = list(db.scalars(select(PublishingWorkerHeartbeat)))
    worker = next((item for item in values if safe_worker_id(item.worker_id) == worker_id), None)
    if not worker:
        raise HTTPException(404, "Worker not found.")
    jobs = list(
        db.scalars(
            select(PublishingJob)
            .where(
                PublishingJob.owner_id == owner.id,
                PublishingJob.lease_owner == worker.worker_id,
            )
            .order_by(PublishingJob.updated_at.desc())
            .limit(20)
        )
    )
    return {
        **next(item for item in operations_workers(db, owner) if item["worker_id"] == worker_id),
        "recent_jobs": [JobResponse.model_validate(job) for job in jobs],
    }


@operations_router.get("/scheduler-health")
def scheduler_health(db: DB, owner: Owner) -> dict[str, object]:
    timestamp = utcnow()
    settings = get_settings()
    maintenance = Path(settings.maintenance_marker).resolve().exists()
    state_counts = {
        state: count
        for state, count in db.execute(
            select(PublishingJob.state, func.count())
            .where(PublishingJob.owner_id == owner.id)
            .group_by(PublishingJob.state)
        )
    }
    due = (
        db.scalar(
            select(func.count())
            .select_from(PublishingJob)
            .where(
                PublishingJob.owner_id == owner.id,
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
                PublishingJob.available_at_utc <= timestamp,
            )
        )
        or 0
    )
    oldest = db.scalar(
        select(func.min(PublishingJob.available_at_utc)).where(
            PublishingJob.owner_id == owner.id,
            PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
            PublishingJob.available_at_utc < timestamp,
        )
    )
    workers = operations_workers(db, owner)
    connector_counts = {
        f"{connector}:{state}": count
        for connector, state, count in db.execute(
            select(PublishingJob.connector_key, PublishingJob.state, func.count())
            .where(PublishingJob.owner_id == owner.id)
            .group_by(PublishingJob.connector_key, PublishingJob.state)
        )
    }
    return {
        "scheduler_enabled": settings.publishing_worker_enabled,
        "globally_paused": False,
        "maintenance_blocked": maintenance,
        "active_schedule_count": db.scalar(
            select(func.count())
            .select_from(PublishingSchedule)
            .where(
                PublishingSchedule.owner_id == owner.id,
                PublishingSchedule.enabled.is_(True),
                PublishingSchedule.paused.is_(False),
                PublishingSchedule.archived.is_(False),
            )
        )
        or 0,
        "paused_schedule_count": sum(
            1
            for item in db.scalars(
                select(PublishingSchedule).where(
                    PublishingSchedule.owner_id == owner.id,
                    PublishingSchedule.paused.is_(True),
                )
            )
        ),
        "recurring_schedule_count": db.scalar(
            select(func.count())
            .select_from(PublishingSchedule)
            .where(
                PublishingSchedule.owner_id == owner.id,
                PublishingSchedule.schedule_type == "recurring",
            )
        )
        or 0,
        "due_job_count": due,
        "overdue_job_count": due,
        "retry_wait_count": state_counts.get("retry_wait", 0),
        "failed_count": state_counts.get("failed", 0),
        "dead_letter_count": state_counts.get("dead_letter", 0),
        "cancelled_count": state_counts.get("cancelled", 0),
        "oldest_overdue_age_seconds": (
            int((timestamp - oldest).total_seconds()) if oldest else None
        ),
        "workers": workers,
        "connector_backlog": connector_counts,
        "generated_at": timestamp,
    }
