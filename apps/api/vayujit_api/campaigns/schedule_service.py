import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityDependency,
    CampaignScheduleLink,
)
from vayujit_api.campaigns.readiness_service import activity_readiness
from vayujit_api.campaigns.schemas import ScheduleRequest
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.publishing.models import PublishingJob
from vayujit_api.publishing.scheduler_schemas import ScheduleCreate
from vayujit_api.publishing.scheduler_service import create_schedule


def schedule_activities(
    db: Session,
    owner: User,
    campaign: Campaign,
    activities: list[CampaignActivity],
    request: ScheduleRequest,
) -> dict[str, object]:
    selected = (
        [activity for activity in activities if activity.id in set(request.activity_ids)]
        if request.activity_ids
        else [activity for activity in activities if activity.enabled]
    )
    if not selected:
        raise HTTPException(422, "Select at least one activity.")
    if not request.confirm:
        raise HTTPException(409, "Campaign scheduling requires explicit confirmation.")
    results: list[dict[str, object]] = []
    blocked: list[CampaignActivity] = []
    for activity in selected:
        readiness = activity_readiness(db, campaign, activity)
        if readiness.state not in {"ready", "warning"}:
            blocked.append(activity)
    if blocked and request.behavior == "require_all_ready":
        raise HTTPException(409, "One or more selected activities are not ready.")
    for activity in selected:
        if activity in blocked:
            results.append({"activity_id": activity.id, "status": "blocked"})
            continue
        if activity.activity_type == "video_campaign":
            from vayujit_api.campaigns.campaign_video_runtime import materialize_campaign_video

            result = materialize_campaign_video(
                db,
                owner,
                campaign.id,
                activity.id,
                expected_fingerprint=activity.video_preview_fingerprint or "",
                expected_row_version=activity.row_version,
            )
            results.append(result)
            continue
        if activity.connector_key is None:
            activity.status = "succeeded"
            activity.completed_at = now()
            results.append({"activity_id": activity.id, "status": "checkpoint_completed"})
            continue
        existing = db.scalar(
            select(CampaignScheduleLink).where(CampaignScheduleLink.activity_id == activity.id)
        )
        if existing:
            results.append(
                {
                    "activity_id": activity.id,
                    "status": "already_scheduled",
                    "schedule_id": existing.schedule_id,
                }
            )
            continue
        if not activity.artifact_id or not activity.destination_id or not activity.requested_action:
            results.append({"activity_id": activity.id, "status": "blocked"})
            continue
        schedule = create_schedule(
            db,
            owner,
            ScheduleCreate(
                name=f"{campaign.name}: {activity.name}",
                artifact_id=activity.artifact_id,
                destination_id=activity.destination_id,
                requested_action=cast(Any, activity.requested_action),
                local_scheduled_at=activity.scheduled_at_utc.replace(tzinfo=None),
                timezone_name="UTC",
                schedule_type="one_time",
                max_occurrences=1,
            ),
        )
        link = CampaignScheduleLink(
            owner_id=owner.id,
            campaign_id=campaign.id,
            activity_id=activity.id,
            schedule_id=schedule.id,
            occurrence_key=f"campaign:{campaign.id}:activity:{activity.id}:v1",
            created_at=now(),
        )
        db.add(link)
        activity.schedule_id = schedule.id
        activity.status = "scheduled"
        activity.updated_at = now()
        results.append(
            {"activity_id": activity.id, "status": "scheduled", "schedule_id": schedule.id}
        )
    campaign.status = "scheduled"
    campaign.updated_at = now()
    campaign.row_version += 1
    record_event(
        db,
        actor_id=owner.id,
        action="campaign.scheduled",
        entity_type="campaign",
        entity_id=campaign.id,
        metadata={"selected": len(selected), "blocked": len(blocked), "behavior": request.behavior},
    )
    db.commit()
    return {"campaign_id": campaign.id, "results": results}


def project_activity_states(db: Session, campaign_id: uuid.UUID) -> int:
    activities = list(
        db.scalars(select(CampaignActivity).where(CampaignActivity.campaign_id == campaign_id))
    )
    changed = 0
    mapping = {
        "pending": "queued",
        "scheduled": "scheduled",
        "claimed": "queued",
        "running": "running",
        "retry_wait": "retrying",
        "succeeded": "succeeded",
        "failed": "failed",
        "dead_letter": "dead_letter",
        "cancel_requested": "cancel_requested",
        "cancelled": "cancelled",
        "paused": "paused",
        "expired": "reconciliation_required",
    }
    for activity in activities:
        if activity.status == "missed":
            # A missed Activity is an explicit operator state. Its historical job may
            # still exist for audit/recovery, but must not project back to queued.
            continue
        if not activity.schedule_id:
            continue
        job = db.scalar(
            select(PublishingJob)
            .where(PublishingJob.schedule_id == activity.schedule_id)
            .order_by(PublishingJob.created_at.desc())
            .limit(1)
        )
        if job:
            projected = (
                "maintenance_blocked"
                if job.maintenance_blocked_at and job.state in {"pending", "scheduled"}
                else mapping.get(job.state, activity.status)
            )
            if projected != activity.status:
                activity.status = projected
                activity.job_id = job.id
                activity.publishing_execution_id = job.publishing_execution_id
                activity.updated_at = now()
                if projected in {"succeeded", "completed_with_warning"}:
                    activity.completed_at = now()
                changed += 1
    if changed:
        db.commit()
    return changed


def dependencies(db: Session, campaign_id: uuid.UUID) -> list[CampaignActivityDependency]:
    return list(
        db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.campaign_id == campaign_id
            )
        )
    )
