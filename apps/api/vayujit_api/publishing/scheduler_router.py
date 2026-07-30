import math
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    WorkerResponse,
)
from vayujit_api.publishing.scheduler_service import create_schedule, update_schedule
from vayujit_api.publishing.scheduler_time import utcnow

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing-scheduler"])
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
def schedule_resume(schedule_id: uuid.UUID, db: DB, owner: Owner) -> PublishingSchedule:
    return set_schedule_state(schedule_id, db, owner, "resume")


@router.delete("/schedules/{schedule_id}", response_model=ScheduleResponse)
def schedule_archive(schedule_id: uuid.UUID, db: DB, owner: Owner) -> PublishingSchedule:
    return set_schedule_state(schedule_id, db, owner, "archive")


@router.get("/jobs")
def job_list(
    db: DB,
    owner: Owner,
    state: str | None = None,
    schedule_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    filters = [PublishingJob.owner_id == owner.id]
    if state:
        filters.append(PublishingJob.state == state)
    if schedule_id:
        filters.append(PublishingJob.schedule_id == schedule_id)
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
