from __future__ import annotations

import math
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingJob,
    PublishingSchedule,
)
from vayujit_api.publishing.scheduler_schemas import ScheduleCreate, ScheduleUpdate
from vayujit_api.publishing.scheduler_time import (
    local_to_utc,
    next_utc_occurrence,
    occurrence_key,
    utcnow,
)


def create_schedule(db: Session, owner: User, data: ScheduleCreate) -> PublishingSchedule:
    count = db.scalar(
        select(func.count())
        .select_from(PublishingSchedule)
        .where(
            PublishingSchedule.owner_id == owner.id,
            PublishingSchedule.archived.is_(False),
        )
    )
    if (count or 0) >= get_settings().publishing_schedule_max_per_owner:
        raise ValueError("The publishing schedule quota has been reached.")
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == data.artifact_id,
            GeneratedArtifact.owner_id == owner.id,
        )
    )
    destination = db.scalar(
        select(PublishingDestination).where(
            PublishingDestination.id == data.destination_id,
            PublishingDestination.owner_id == owner.id,
        )
    )
    if not artifact or artifact.status != "approved":
        raise ValueError("Scheduling requires an approved artifact.")
    if not destination or destination.status != "active":
        raise ValueError("Scheduling requires an active destination.")
    if data.schedule_type == "recurring" and not data.recurrence:
        raise ValueError("A recurring schedule requires a recurrence rule.")
    if data.schedule_type == "one_time" and data.recurrence:
        raise ValueError("A one-time schedule cannot have a recurrence rule.")
    fold = data.recurrence.fold if data.recurrence else 0
    scheduled_utc = local_to_utc(data.local_scheduled_at, data.timezone_name, fold)
    timestamp = utcnow()
    value = PublishingSchedule(
        owner_id=owner.id,
        brand_id=artifact.brand_id,
        product_id=artifact.product_id,
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        destination_id=destination.id,
        connector_key=destination.connector_key,
        requested_action=data.requested_action,
        name=data.name.strip(),
        schedule_type=data.schedule_type,
        scheduled_at_utc=scheduled_utc,
        timezone_name=data.timezone_name,
        local_scheduled_at=data.local_scheduled_at,
        recurrence_json=data.recurrence.model_dump() if data.recurrence else None,
        recurrence_end_at=data.recurrence_end_at,
        enabled=True,
        paused=False,
        archived=False,
        approval_snapshot_json={
            "artifact_status": artifact.status,
            "approved_at": artifact.approved_at.isoformat() if artifact.approved_at else None,
            "approved_by": str(artifact.approved_by) if artifact.approved_by else None,
        },
        destination_snapshot_version=destination.updated_at.isoformat(),
        created_by=owner.id,
        created_at=timestamp,
        updated_at=timestamp,
        next_run_at_utc=scheduled_utc,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.schedule_created",
        entity_type="publishing_schedule",
        entity_id=value.id,
        metadata={"connector": value.connector_key, "schedule_type": value.schedule_type},
    )
    db.commit()
    db.refresh(value)
    return value


def update_schedule(
    db: Session, owner: User, value: PublishingSchedule, data: ScheduleUpdate
) -> PublishingSchedule:
    if value.owner_id != owner.id or value.archived:
        raise LookupError("Schedule not found.")
    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        value.name = str(values["name"]).strip()
    if "timezone_name" in values:
        value.timezone_name = str(values["timezone_name"])
    if "local_scheduled_at" in values:
        value.local_scheduled_at = values["local_scheduled_at"]  # type: ignore[assignment]
    if "recurrence" in values:
        recurrence = data.recurrence
        value.recurrence_json = recurrence.model_dump() if recurrence else None
    if "recurrence_end_at" in values:
        value.recurrence_end_at = data.recurrence_end_at
    fold = int(cast(Any, (value.recurrence_json or {}).get("fold", 0)))
    value.scheduled_at_utc = local_to_utc(value.local_scheduled_at, value.timezone_name, fold)
    value.next_run_at_utc = value.scheduled_at_utc
    value.updated_at = utcnow()
    record_event(
        db,
        actor_id=owner.id,
        action="publishing.schedule_updated",
        entity_type="publishing_schedule",
        entity_id=value.id,
    )
    db.commit()
    db.refresh(value)
    return value


def materialize_due_schedules(db: Session) -> int:
    timestamp = utcnow()
    horizon = timestamp + timedelta(days=get_settings().publishing_schedule_horizon_days)
    schedules = list(
        db.scalars(
            select(PublishingSchedule)
            .where(
                PublishingSchedule.enabled.is_(True),
                PublishingSchedule.paused.is_(False),
                PublishingSchedule.archived.is_(False),
                PublishingSchedule.next_run_at_utc.is_not(None),
                PublishingSchedule.next_run_at_utc <= horizon,
            )
            .with_for_update(skip_locked=True)
        )
    )
    created = 0
    for schedule in schedules:
        while schedule.next_run_at_utc and schedule.next_run_at_utc <= horizon:
            due = schedule.next_run_at_utc
            key = occurrence_key(schedule.id, due)
            exists = db.scalar(
                select(PublishingJob.id).where(
                    PublishingJob.owner_id == schedule.owner_id,
                    PublishingJob.idempotency_key == key,
                )
            )
            if not exists:
                db.add(
                    PublishingJob(
                        owner_id=schedule.owner_id,
                        schedule_id=schedule.id,
                        product_id=schedule.product_id,
                        artifact_id=schedule.artifact_id,
                        artifact_version=schedule.artifact_version,
                        destination_id=schedule.destination_id,
                        connector_key=schedule.connector_key,
                        requested_action=schedule.requested_action,
                        idempotency_key=key,
                        state="scheduled" if due > timestamp else "pending",
                        priority=0,
                        scheduled_at_utc=due,
                        available_at_utc=due,
                        claim_count=0,
                        execution_attempt_count=0,
                        max_execution_attempts=get_settings().publishing_job_max_attempts,
                        retryable=False,
                        created_at=timestamp,
                        updated_at=timestamp,
                        row_version=1,
                    )
                )
                created += 1
            schedule.last_job_created_at = timestamp
            if schedule.schedule_type == "one_time":
                schedule.next_run_at_utc = None
                break
            recurrence = schedule.recurrence_json or {}
            local_value, next_value = next_utc_occurrence(
                schedule.local_scheduled_at,
                schedule.timezone_name,
                recurrence,
                fold=int(cast(Any, recurrence.get("fold", 0))),
            )
            schedule.local_scheduled_at = local_value
            if schedule.recurrence_end_at and next_value > schedule.recurrence_end_at:
                schedule.next_run_at_utc = None
                break
            schedule.next_run_at_utc = next_value
    db.commit()
    return created


def paginate(total: int, page: int, page_size: int, items: list[object]) -> dict[str, object]:
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": math.ceil(total / page_size) if total else 0,
    }
