import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.campaigns.activity_service import (
    add_dependency,
    create_activity,
    owned_activity,
    update_activity,
)
from vayujit_api.campaigns.calendar_service import calendar_events, progress
from vayujit_api.campaigns.campaign_service import (
    create_campaign,
    owned_campaign,
    transition,
    update_campaign,
)
from vayujit_api.campaigns.conflict_service import detect_conflicts
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityDependency,
)
from vayujit_api.campaigns.readiness_service import activity_readiness, campaign_readiness
from vayujit_api.campaigns.schedule_service import (
    dependencies,
    project_activity_states,
    schedule_activities,
)
from vayujit_api.campaigns.schemas import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    CalendarEvent,
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    Conflict,
    DependencyCreate,
    DependencyResponse,
    LifecycleRequest,
    ProgressResponse,
    ReadinessResponse,
    RescheduleRequest,
    ScheduleRequest,
)
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_time import local_to_utc, utcnow

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def campaign_activities(db: Session, campaign_id: uuid.UUID) -> list[CampaignActivity]:
    return list(
        db.scalars(
            select(CampaignActivity)
            .where(CampaignActivity.campaign_id == campaign_id)
            .order_by(CampaignActivity.sequence)
        )
    )


@router.get("/calendar", response_model=list[CalendarEvent])
def global_calendar(
    db: DB,
    owner: Owner,
    start: datetime,
    end: datetime,
    campaign_id: uuid.UUID | None = None,
) -> list[CalendarEvent]:
    if end <= start or end - start > timedelta(days=get_settings().campaign_calendar_max_days):
        raise HTTPException(422, "Calendar range must be positive and within the configured limit.")
    return calendar_events(db, owner.id, start, end, campaign_id=campaign_id)


@router.get("/health")
def health(db: DB, owner: Owner) -> dict[str, object]:
    timestamp = utcnow()
    active = db.scalar(
        select(func.count())
        .select_from(Campaign)
        .where(
            Campaign.owner_id == owner.id,
            Campaign.status.notin_(["completed", "cancelled", "archived"]),
        )
    )
    upcoming = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.scheduled_at_utc >= timestamp,
            CampaignActivity.status.notin_(["cancelled", "archived"]),
        )
    )
    blocked = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.status.in_(["blocked", "dead_letter", "maintenance_blocked"]),
        )
    )
    overdue = db.scalar(
        select(func.count())
        .select_from(CampaignActivity)
        .where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.scheduled_at_utc < timestamp,
            CampaignActivity.status.in_(["draft", "ready", "scheduled", "queued"]),
        )
    )
    return {
        "active_campaigns": active or 0,
        "upcoming_activities": upcoming or 0,
        "blocked_activities": blocked or 0,
        "overdue_activities": overdue or 0,
        "generated_at": timestamp,
    }


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    db: DB,
    owner: Owner,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Campaign]:
    query = select(Campaign).where(Campaign.owner_id == owner.id)
    if status:
        query = query.where(Campaign.status == status)
    return list(
        db.scalars(
            query.order_by(Campaign.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )


@router.post("", response_model=CampaignResponse, status_code=201)
def create(data: CampaignCreate, db: DB, owner: Owner) -> Campaign:
    return create_campaign(db, owner, data)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    project_activity_states(db, campaign_id)
    return owned_campaign(db, owner.id, campaign_id)


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update(campaign_id: uuid.UUID, data: CampaignUpdate, db: DB, owner: Owner) -> Campaign:
    return update_campaign(db, owner, campaign_id, data)


@router.get("/{campaign_id}/activities", response_model=list[ActivityResponse])
def activities(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[CampaignActivity]:
    owned_campaign(db, owner.id, campaign_id)
    project_activity_states(db, campaign_id)
    return campaign_activities(db, campaign_id)


@router.post("/{campaign_id}/activities", response_model=ActivityResponse, status_code=201)
def activity_create(
    campaign_id: uuid.UUID, data: ActivityCreate, db: DB, owner: Owner
) -> CampaignActivity:
    return create_activity(db, owner, campaign_id, data)


@router.get("/{campaign_id}/activities/{activity_id}", response_model=ActivityResponse)
def activity_get(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    return owned_activity(db, owner.id, campaign_id, activity_id)


@router.put("/{campaign_id}/activities/{activity_id}", response_model=ActivityResponse)
def activity_update(
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    data: ActivityUpdate,
    db: DB,
    owner: Owner,
) -> CampaignActivity:
    return update_activity(db, owner, campaign_id, activity_id, data)


@router.post("/{campaign_id}/dependencies", response_model=DependencyResponse, status_code=201)
def dependency_create(
    campaign_id: uuid.UUID, data: DependencyCreate, db: DB, owner: Owner
) -> CampaignActivityDependency:
    return add_dependency(db, owner, campaign_id, data)


@router.get("/{campaign_id}/dependencies", response_model=list[DependencyResponse])
def dependency_list(
    campaign_id: uuid.UUID, db: DB, owner: Owner
) -> list[CampaignActivityDependency]:
    owned_campaign(db, owner.id, campaign_id)
    return dependencies(db, campaign_id)


@router.post("/{campaign_id}/activities/{activity_id}/validate", response_model=ReadinessResponse)
def activity_validate(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> ReadinessResponse:
    campaign = owned_campaign(db, owner.id, campaign_id)
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    result = activity_readiness(db, campaign, activity)
    db.commit()
    return result


@router.post("/{campaign_id}/validate", response_model=ReadinessResponse)
def validate(campaign_id: uuid.UUID, db: DB, owner: Owner) -> ReadinessResponse:
    campaign = owned_campaign(db, owner.id, campaign_id)
    result = campaign_readiness(db, campaign, campaign_activities(db, campaign_id))
    if result.state in {"ready", "warning"} and campaign.status in {"draft", "planning"}:
        campaign.status = "ready"
        campaign.updated_at = now()
        campaign.row_version += 1
    db.commit()
    return result


@router.get("/{campaign_id}/conflicts", response_model=list[Conflict])
def conflicts(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[Conflict]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    return detect_conflicts(
        campaign, campaign_activities(db, campaign_id), dependencies(db, campaign_id)
    )


@router.post("/{campaign_id}/schedule-preview")
def schedule_preview(
    campaign_id: uuid.UUID, request: ScheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    values = campaign_activities(db, campaign_id)
    selected = [
        value for value in values if not request.activity_ids or value.id in request.activity_ids
    ]
    readiness = [
        {"activity_id": value.id, **activity_readiness(db, campaign, value).model_dump()}
        for value in selected
    ]
    return {
        "campaign_id": campaign.id,
        "selected_count": len(selected),
        "readiness": readiness,
        "conflicts": detect_conflicts(campaign, selected, dependencies(db, campaign_id)),
        "requires_confirmation": True,
    }


@router.post("/{campaign_id}/schedule")
def schedule(
    campaign_id: uuid.UUID, request: ScheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id, lock=True)
    if campaign.status not in {"ready", "scheduled", "paused"}:
        raise HTTPException(409, "Campaign is not eligible for scheduling.")
    return schedule_activities(db, owner, campaign, campaign_activities(db, campaign_id), request)


@router.post("/{campaign_id}/activities/{activity_id}/schedule")
def schedule_one(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id, lock=True)
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    return schedule_activities(
        db,
        owner,
        campaign,
        [activity],
        ScheduleRequest(activity_ids=[activity.id], confirm=True),
    )


@router.post("/{campaign_id}/activities/{activity_id}/cancel", response_model=ActivityResponse)
def activity_cancel(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    if activity.status in {"succeeded", "completed_with_warning", "archived"}:
        raise HTTPException(409, "Completed activity history cannot be cancelled.")
    job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    if job and job.state in {"claimed", "running"}:
        job.state = "cancel_requested"
        activity.status = "cancel_requested"
    else:
        if job and job.state not in {"succeeded", "cancelled"}:
            job.state = "cancelled"
            job.completed_at = now()
        activity.status = "cancelled"
        activity.completed_at = now()
    activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


@router.post("/{campaign_id}/activities/{activity_id}/retry", response_model=ActivityResponse)
def activity_retry(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
    if not job or job.state not in {"failed", "dead_letter", "expired", "cancelled"}:
        raise HTTPException(409, "Activity has no retryable terminal job.")
    job.state = "pending"
    job.available_at_utc = utcnow()
    job.completed_at = None
    job.lease_owner = None
    job.lease_expires_at = None
    job.next_retry_at = None
    job.updated_at = utcnow()
    activity.status = "queued"
    activity.failure_code = activity.safe_failure_message = None
    activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


@router.post("/{campaign_id}/activities/{activity_id}/release", response_model=ActivityResponse)
def activity_release(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    edges = list(
        db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.predecessor_activity_id == activity.id,
                CampaignActivityDependency.dependency_type == "manual_release",
                CampaignActivityDependency.released_at.is_(None),
            )
        )
    )
    if not edges:
        raise HTTPException(409, "Activity has no manual checkpoint to release.")
    for edge in edges:
        edge.released_at = now()
    activity.status = "succeeded"
    activity.completed_at = activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


@router.post("/{campaign_id}/activities/{activity_id}/archive", response_model=ActivityResponse)
def activity_archive(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> CampaignActivity:
    activity = owned_activity(db, owner.id, campaign_id, activity_id)
    if activity.status not in {"succeeded", "failed", "cancelled", "dead_letter"}:
        raise HTTPException(409, "Only terminal activities can be archived.")
    activity.status = "archived"
    activity.updated_at = now()
    db.commit()
    db.refresh(activity)
    return activity


def reschedule_projection(
    db: Session, campaign: Campaign, request: RescheduleRequest
) -> list[dict[str, object]]:
    projection: list[dict[str, object]] = []
    for change in request.changes:
        activity = owned_activity(db, campaign.owner_id, campaign.id, change.activity_id)
        new_utc = local_to_utc(
            datetime.combine(change.scheduled_local_date, change.scheduled_local_time),
            change.timezone_name,
            0,
        )
        projection.append(
            {
                "activity_id": activity.id,
                "old_scheduled_at_utc": activity.scheduled_at_utc,
                "new_scheduled_at_utc": new_utc,
                "requires_recreation": activity.status in {"scheduled", "queued"},
                "blocked": activity.status in {"running", "succeeded"},
            }
        )
    return projection


@router.post("/{campaign_id}/reschedule-preview")
def reschedule_preview(
    campaign_id: uuid.UUID, request: RescheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    return {"campaign_id": campaign.id, "changes": reschedule_projection(db, campaign, request)}


@router.post("/{campaign_id}/reschedule")
def reschedule(
    campaign_id: uuid.UUID, request: RescheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    if not request.confirm:
        raise HTTPException(409, "Rescheduling requires explicit confirmation.")
    projection = reschedule_projection(db, campaign, request)
    if any(bool(value["blocked"]) for value in projection):
        raise HTTPException(409, "Running or completed activities cannot be rescheduled.")
    for change in request.changes:
        activity = owned_activity(db, owner.id, campaign.id, change.activity_id)
        if activity.row_version != change.row_version:
            raise HTTPException(409, "Activity changed; reload the rescheduling preview.")
        activity.scheduled_local_date = change.scheduled_local_date
        activity.scheduled_local_time = change.scheduled_local_time
        activity.timezone_name = change.timezone_name
        activity.scheduled_at_utc = local_to_utc(
            datetime.combine(change.scheduled_local_date, change.scheduled_local_time),
            change.timezone_name,
            0,
        )
        activity.row_version += 1
        activity.updated_at = now()
        if activity.schedule_id:
            schedule_value = db.get(PublishingSchedule, activity.schedule_id)
            if schedule_value:
                schedule_value.archived = True
                schedule_value.enabled = False
            activity.schedule_id = None
            activity.job_id = None
            activity.status = "ready"
    db.commit()
    return {"campaign_id": campaign.id, "changes": projection}


@router.get("/{campaign_id}/calendar", response_model=list[CalendarEvent])
def campaign_calendar(
    campaign_id: uuid.UUID, db: DB, owner: Owner, start: datetime, end: datetime
) -> list[CalendarEvent]:
    owned_campaign(db, owner.id, campaign_id)
    if end <= start or end - start > timedelta(days=get_settings().campaign_calendar_max_days):
        raise HTTPException(422, "Calendar range must be positive and within the configured limit.")
    return calendar_events(db, owner.id, start, end, campaign_id=campaign_id)


@router.get("/{campaign_id}/progress", response_model=ProgressResponse)
def campaign_progress(campaign_id: uuid.UUID, db: DB, owner: Owner) -> ProgressResponse:
    owned_campaign(db, owner.id, campaign_id)
    project_activity_states(db, campaign_id)
    return progress(campaign_activities(db, campaign_id))


def pause_campaign_resources(db: Session, campaign_id: uuid.UUID) -> None:
    activity_values = campaign_activities(db, campaign_id)
    schedule_ids = [value.schedule_id for value in activity_values if value.schedule_id]
    if schedule_ids:
        for schedule_value in db.scalars(
            select(PublishingSchedule).where(PublishingSchedule.id.in_(schedule_ids))
        ):
            schedule_value.paused = True
            schedule_value.updated_at = now()
        for job in db.scalars(
            select(PublishingJob).where(
                PublishingJob.schedule_id.in_(schedule_ids),
                PublishingJob.state.in_(["pending", "scheduled", "retry_wait"]),
            )
        ):
            job.state = "paused"
            job.updated_at = now()


@router.post("/{campaign_id}/release", response_model=CampaignResponse)
def release(campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner) -> Campaign:
    if not request.confirm:
        raise HTTPException(409, "Campaign release requires explicit confirmation.")
    campaign = owned_campaign(db, owner.id, campaign_id)
    readiness = campaign_readiness(db, campaign, campaign_activities(db, campaign_id))
    if readiness.state not in {"ready", "warning"}:
        raise HTTPException(409, "Campaign is not ready for release.")
    if campaign.status == "draft":
        transition(db, owner, campaign_id, "planning")
    return transition(db, owner, campaign_id, "ready")


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
def pause(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    value = transition(db, owner, campaign_id, "paused")
    pause_campaign_resources(db, campaign_id)
    db.commit()
    return value


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
def resume(campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner) -> Campaign:
    if not request.missed_activity_policy:
        raise HTTPException(422, "A missed-activity policy is required.")
    campaign = owned_campaign(db, owner.id, campaign_id)
    if campaign.status != "paused":
        raise HTTPException(409, "Only paused Campaigns can resume.")
    future = [
        value
        for value in campaign_activities(db, campaign_id)
        if value.schedule_id and value.scheduled_at_utc >= utcnow()
    ]
    for activity in future:
        schedule_value = db.get(PublishingSchedule, activity.schedule_id)
        if schedule_value:
            schedule_value.paused = False
        job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state == "paused":
            job.state = "pending"
            job.available_at_utc = max(job.available_at_utc, utcnow())
    target = "scheduled" if any(value.schedule_id for value in future) else "ready"
    value = transition(db, owner, campaign_id, target)
    db.commit()
    return value


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
def cancel(campaign_id: uuid.UUID, request: LifecycleRequest, db: DB, owner: Owner) -> Campaign:
    value = transition(db, owner, campaign_id, "cancelled", reason=request.reason)
    for activity in campaign_activities(db, campaign_id):
        job = db.get(PublishingJob, activity.job_id) if activity.job_id else None
        if job and job.state in {"claimed", "running"}:
            job.state = "cancel_requested"
            activity.status = "cancel_requested"
        elif activity.status not in {"succeeded", "completed_with_warning"}:
            if job and job.state not in {"cancelled", "succeeded"}:
                job.state = "cancelled"
                job.completed_at = now()
            schedule_value = (
                db.get(PublishingSchedule, activity.schedule_id) if activity.schedule_id else None
            )
            if schedule_value:
                schedule_value.enabled = False
                schedule_value.paused = True
                schedule_value.cancellation_reason = request.reason
            activity.status = "cancelled"
    db.commit()
    return value


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
def complete(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    values = campaign_activities(db, campaign_id)
    required = [value for value in values if value.required and value.enabled]
    if any(value.status not in {"succeeded", "completed_with_warning"} for value in required):
        raise HTTPException(409, "All required activities must complete successfully.")
    return transition(db, owner, campaign_id, "completed")


@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
def archive(campaign_id: uuid.UUID, db: DB, owner: Owner) -> Campaign:
    return transition(db, owner, campaign_id, "archived")
