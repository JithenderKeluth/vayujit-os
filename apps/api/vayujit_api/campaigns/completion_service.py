import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityDependency,
    CampaignMissedActivityResolution,
)
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User

SUCCESS = {"succeeded", "completed_with_warning"}
ACTIVE = {"scheduled", "queued", "running", "retrying", "cancel_requested"}
BLOCKING = {"blocked", "waiting_dependency", "maintenance_blocked", "reconciliation_required"}
FAILED = {"failed", "dead_letter", "cancelled"}


class ActivityState(Protocol):
    status: str
    required: bool
    enabled: bool


def utcnow() -> datetime:
    return datetime.now(UTC)


def terminal_state(activities: Sequence[ActivityState]) -> str:
    required = [value for value in activities if value.required and value.enabled]
    optional = [value for value in activities if not value.required and value.enabled]
    if any(value.status in FAILED for value in required):
        return "failed"
    if any(value.status in BLOCKING for value in required):
        return "blocked"
    if any(
        value.status in ACTIVE or value.status in {"draft", "ready", "missed"} for value in required
    ):
        return "running" if any(value.status in ACTIVE for value in required) else "planning"
    if required and all(value.status in SUCCESS for value in required):
        if any(value.status in FAILED | {"skipped"} for value in optional):
            return "partially_completed"
        return "completed"
    return "planning"


@dataclass(frozen=True)
class ResumePreview:
    missed: list[uuid.UUID]
    required_missed: list[uuid.UUID]
    optional_missed: list[uuid.UUID]
    to_skip: list[uuid.UUID]
    catch_up: uuid.UUID | None
    catch_up_replacement: uuid.UUID | None
    next_future: uuid.UUID | None
    blocked_successors: list[uuid.UUID]
    confirmation_required: bool = True


def resume_preview(
    db: Session, campaign: Campaign, policy: str, *, at: datetime | None = None
) -> ResumePreview:
    stamp = at or utcnow()
    activities = list(
        db.scalars(
            select(CampaignActivity)
            .where(
                CampaignActivity.campaign_id == campaign.id,
                CampaignActivity.enabled.is_(True),
                CampaignActivity.scheduled_at_utc < stamp,
                CampaignActivity.status.in_(["draft", "ready", "scheduled", "paused", "missed"]),
            )
            .order_by(CampaignActivity.scheduled_at_utc, CampaignActivity.sequence)
        )
    )
    missed_ids = [value.id for value in activities]
    required = [value.id for value in activities if value.required]
    optional = [value.id for value in activities if not value.required]
    skipped = optional if policy == "skip_missed" else []
    catch_up = activities[0].id if policy == "one_catch_up" and activities else None
    edges = (
        list(
            db.scalars(
                select(CampaignActivityDependency).where(
                    CampaignActivityDependency.campaign_id == campaign.id,
                    CampaignActivityDependency.predecessor_activity_id.in_(skipped),
                )
            )
        )
        if skipped
        else []
    )
    future = db.scalar(
        select(CampaignActivity)
        .where(
            CampaignActivity.campaign_id == campaign.id,
            CampaignActivity.enabled.is_(True),
            CampaignActivity.scheduled_at_utc >= stamp,
        )
        .order_by(CampaignActivity.scheduled_at_utc, CampaignActivity.sequence)
        .limit(1)
    )
    return ResumePreview(
        missed=missed_ids,
        required_missed=required,
        optional_missed=optional,
        to_skip=skipped,
        catch_up=catch_up,
        catch_up_replacement=None,
        next_future=future.id if future else None,
        blocked_successors=sorted({edge.successor_activity_id for edge in edges}, key=str),
    )


def resolve_missed(db: Session, owner: User, campaign: Campaign, policy: str) -> ResumePreview:
    preview = resume_preview(db, campaign, policy)
    existing = db.scalar(
        select(CampaignMissedActivityResolution)
        .where(
            CampaignMissedActivityResolution.owner_id == owner.id,
            CampaignMissedActivityResolution.campaign_id == campaign.id,
            CampaignMissedActivityResolution.policy == policy,
        )
        .order_by(CampaignMissedActivityResolution.resolved_at.desc())
        .limit(1)
    )
    if existing:
        return ResumePreview(
            **{
                **preview.__dict__,
                "catch_up_replacement": existing.replacement_activity_id,
            }
        )
    if policy == "skip_missed" and preview.required_missed:
        raise ValueError("Required missed activities cannot be skipped.")
    stamp = utcnow()
    catch_up_replacement: CampaignActivity | None = None
    if preview.catch_up:
        original = db.get(CampaignActivity, preview.catch_up)
        if original:
            sequence = (
                db.scalar(
                    select(func.max(CampaignActivity.sequence)).where(
                        CampaignActivity.campaign_id == campaign.id
                    )
                )
                or 0
            ) + 1
            catch_up_replacement = CampaignActivity(
                owner_id=original.owner_id,
                campaign_id=original.campaign_id,
                product_id=original.product_id,
                artifact_id=original.artifact_id,
                artifact_version=original.artifact_version,
                destination_id=original.destination_id,
                connector_key=original.connector_key,
                requested_action=original.requested_action,
                activity_type=original.activity_type,
                name=f"{original.name} (catch-up)",
                description=original.description,
                sequence=sequence,
                dependency_policy=original.dependency_policy,
                scheduled_local_date=stamp.date(),
                scheduled_local_time=stamp.time().replace(microsecond=0),
                timezone_name=original.timezone_name,
                scheduled_at_utc=stamp,
                duration_minutes=original.duration_minutes,
                status="ready",
                readiness_status="ready",
                required=original.required,
                enabled=True,
                created_by=owner.id,
                created_at=stamp,
                updated_at=stamp,
                correlation_id=correlation_id(),
                idempotency_key=f"catch-up:{original.id}:{stamp.isoformat()}",
            )
            db.add(catch_up_replacement)
            db.flush()
    for activity_id in preview.missed:
        activity = db.get(CampaignActivity, activity_id)
        if not activity:
            continue
        status = "skipped" if activity_id in preview.to_skip else "unresolved"
        activity.status = "skipped" if status == "skipped" else "missed"
        is_catch_up = activity_id == preview.catch_up and catch_up_replacement is not None
        replacement_id = catch_up_replacement.id if catch_up_replacement is not None else None
        resolution = CampaignMissedActivityResolution(
            owner_id=owner.id,
            campaign_id=campaign.id,
            activity_id=activity.id,
            policy=policy,
            original_scheduled_at_utc=activity.scheduled_at_utc,
            resolution_status="catch_up_created" if is_catch_up else status,
            replacement_activity_id=replacement_id if is_catch_up else None,
            reason="Campaign resumed using an explicit missed-activity policy.",
            correlation_id=correlation_id(),
            resolved_by=owner.id,
            resolved_at=stamp,
        )
        db.add(resolution)
    if catch_up_replacement is not None:
        from vayujit_api.campaigns.schedule_service import schedule_activities
        from vayujit_api.campaigns.schemas import ScheduleRequest
        from vayujit_api.publishing.models import PublishingJob
        from vayujit_api.publishing.scheduler_service import materialize_due_schedules

        schedule_activities(
            db,
            owner,
            campaign,
            [catch_up_replacement],
            ScheduleRequest(
                activity_ids=[catch_up_replacement.id],
                behavior="require_all_ready",
                confirm=True,
            ),
        )
        materialize_due_schedules(db)
        job = db.scalar(
            select(PublishingJob)
            .where(PublishingJob.schedule_id == catch_up_replacement.schedule_id)
            .order_by(PublishingJob.created_at.desc())
            .limit(1)
        )
        linked_resolution = db.scalar(
            select(CampaignMissedActivityResolution).where(
                CampaignMissedActivityResolution.replacement_activity_id == catch_up_replacement.id
            )
        )
        if linked_resolution:
            linked_resolution.replacement_schedule_id = catch_up_replacement.schedule_id
            linked_resolution.replacement_job_id = job.id if job else None
        record_event(
            db,
            actor_id=owner.id,
            action="campaign.catch_up_scheduled",
            entity_type="campaign",
            entity_id=campaign.id,
            metadata={"replacement_activity_id": str(catch_up_replacement.id)},
        )
        preview = ResumePreview(
            **{
                **preview.__dict__,
                "catch_up_replacement": catch_up_replacement.id,
            }
        )
    record_event(
        db,
        actor_id=owner.id,
        action=f"campaign.{policy}",
        entity_type="campaign",
        entity_id=campaign.id,
        metadata={"missed_count": len(preview.missed), "skipped_count": len(preview.to_skip)},
    )
    return preview
