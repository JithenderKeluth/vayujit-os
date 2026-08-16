"""Durable Campaign Video scheduling and downstream execution delegation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityDependency,
    CampaignScheduleLink,
)
from vayujit_api.campaigns.readiness_service import activity_readiness
from vayujit_api.campaigns.workflow_service import project_campaign_state
from vayujit_api.commerce.marketplace_video import (
    MarketplaceVideoJob,
    MarketplaceVideoRequest,
)
from vayujit_api.commerce.marketplace_video import (
    preview as marketplace_video_preview,
)
from vayujit_api.commerce.marketplace_video import (
    run_job as run_marketplace_video_job,
)
from vayujit_api.identity.models import User
from vayujit_api.publishing.models import PublishingDestination, PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.social.models import SocialPost
from vayujit_api.social.worker import execute_social_job

SOCIAL_CHANNELS = {
    "youtube_video": "youtube",
    "youtube_short": "youtube",
    "instagram_reel": "instagram",
    "instagram_story": "instagram",
    "facebook_reel": "facebook",
    "facebook_story": "facebook",
}
MARKETPLACE_CHANNELS = {"amazon", "flipkart", "meesho"}
TERMINAL_FAILURES = {"failed", "dead_letter", "cancelled", "archived", "skipped"}
SUCCESS_STATES = {"succeeded", "completed_with_warning"}


@dataclass(frozen=True)
class CampaignVideoJobResult:
    status: str
    retryable: bool = False
    error_code: str | None = None
    safe_message: str | None = None


def dependency_state(db: Session, activity: CampaignActivity) -> tuple[str, list[str]]:
    waiting: list[str] = []
    failed: list[str] = []
    edges = list(
        db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.successor_activity_id == activity.id
            )
        )
    )
    for edge in edges:
        predecessor = db.get(CampaignActivity, edge.predecessor_activity_id)
        if predecessor is None or predecessor.owner_id != activity.owner_id:
            failed.append("dependency_missing")
        elif edge.dependency_type == "manual_release":
            if edge.released_at is None:
                waiting.append("dependency_manual_release_required")
        elif predecessor.status in SUCCESS_STATES or (
            edge.dependency_type == "completion_required"
            and predecessor.status in TERMINAL_FAILURES
        ):
            continue
        elif predecessor.status in TERMINAL_FAILURES:
            failed.append("dependency_permanently_invalid")
        else:
            waiting.append("dependency_waiting")
    return (
        ("failed", sorted(set(failed)))
        if failed
        else (("waiting", sorted(set(waiting))) if waiting else ("ready", []))
    )


def _destination(
    db: Session, owner: User, campaign: Campaign, activity: CampaignActivity
) -> PublishingDestination:
    if activity.video_channel in SOCIAL_CHANNELS:
        platform = SOCIAL_CHANNELS[activity.video_channel]
        connector_key = f"social_fake:{platform}:{activity.video_target_account_id}"
    else:
        connector_key = (
            f"campaign_video_marketplace:{activity.video_channel}:"
            f"{activity.video_target_account_id}"
        )
    normalized_name = f"campaign-video-{activity.video_target_account_id}"
    value = db.scalar(
        select(PublishingDestination).where(
            PublishingDestination.owner_id == owner.id,
            PublishingDestination.normalized_name == normalized_name,
        )
    )
    if value:
        if value.status != "active":
            raise HTTPException(409, "The Campaign Video destination is disabled.")
        return value
    stamp = utcnow()
    value = PublishingDestination(
        owner_id=owner.id,
        brand_id=campaign.brand_id,
        connector_key=connector_key,
        name=f"Campaign Video {activity.video_channel}",
        normalized_name=normalized_name,
        status="active",
        configuration_json={
            "campaign_video": True,
            "channel": activity.video_channel,
            "account_id": str(activity.video_target_account_id),
        },
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(value)
    db.flush()
    return value


def _social_post(
    db: Session,
    owner: User,
    campaign: Campaign,
    activity: CampaignActivity,
    artifact: GeneratedArtifact,
) -> SocialPost:
    existing = db.get(SocialPost, activity.social_post_id) if activity.social_post_id else None
    if existing:
        return existing
    supplied = dict(activity.video_metadata_json or {})
    content = dict(artifact.content_json or {})
    title = supplied.get("title", content.get("product_title"))
    caption = supplied.get("caption", content.get("social_caption"))
    description = supplied.get("description", content.get("long_description"))
    hashtags = supplied.get("hashtags", [])
    platform = SOCIAL_CHANNELS[cast(str, activity.video_channel)]
    post = SocialPost(
        owner_id=owner.id,
        brand_id=campaign.brand_id,
        product_id=activity.product_id,
        account_id=cast(uuid.UUID, activity.video_target_account_id),
        platform=platform,
        content_type=cast(str, activity.video_channel),
        content_artifact_id=artifact.id,
        content_artifact_version=artifact.version_number,
        media_ids=[
            str(v) for v in (activity.video_media_id, activity.video_thumbnail_media_id) if v
        ],
        video_generation_id=activity.video_generation_id,
        video_output_id=activity.video_output_id,
        video_media_id=activity.video_media_id,
        video_version=activity.video_version,
        metadata_artifact_id=artifact.id,
        metadata_artifact_version=artifact.version_number,
        thumbnail_output_id=activity.video_thumbnail_output_id,
        thumbnail_media_id=activity.video_thumbnail_media_id,
        thumbnail_version=activity.video_thumbnail_version,
        caption_track_id=activity.video_caption_track_id,
        caption_version=activity.video_caption_version,
        locale=str(supplied.get("locale") or "en-IN")[:16],
        caption=str(caption)[:5000] if caption else None,
        title=str(title)[:500] if title else None,
        description=str(description)[:5000] if description else None,
        hashtags=(
            [str(v)[:100] for v in cast(list[object], hashtags)[:30]]
            if isinstance(hashtags, list)
            else []
        ),
        cta_json=None,
        destination_url=None,
        scheduled_at_utc=activity.scheduled_at_utc,
        timezone_name=activity.timezone_name,
        lifecycle_status="scheduled",
        correlation_id=activity.correlation_id or uuid.uuid4().hex[:32],
        campaign_id=campaign.id,
        idempotency_key=f"campaign-video-social:{activity.id}",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(post)
    db.flush()
    activity.social_post_id = post.id
    activity.social_platform = platform
    activity.social_account_id = post.account_id
    activity.social_content_type = post.content_type
    activity.social_media_ids = list(post.media_ids)
    activity.social_timezone_name = activity.timezone_name
    return post


def _marketplace_job(db: Session, owner: User, activity: CampaignActivity) -> MarketplaceVideoJob:
    existing = (
        db.get(MarketplaceVideoJob, activity.video_marketplace_job_id)
        if activity.video_marketplace_job_id
        else None
    )
    if existing:
        return existing
    if activity.video_target_listing_id is None:
        raise HTTPException(409, "Campaign Video requires an exact marketplace listing.")
    request = MarketplaceVideoRequest(
        listing_id=activity.video_target_listing_id,
        video_generation_id=cast(uuid.UUID, activity.video_generation_id),
        video_output_id=cast(uuid.UUID, activity.video_output_id),
        video_media_id=cast(uuid.UUID, activity.video_media_id),
        video_version=cast(int, activity.video_version),
        account_id=activity.video_target_account_id,
        idempotency_key=f"campaign-video-marketplace:{activity.id}",
        correlation_id=activity.correlation_id,
    )
    readiness = marketplace_video_preview(db, owner, request)
    if not readiness["ready"]:
        raise HTTPException(409, "Marketplace Video is not ready for Campaign execution.")
    job = MarketplaceVideoJob(
        owner_id=owner.id,
        product_id=cast(uuid.UUID, activity.product_id),
        account_id=cast(uuid.UUID, activity.video_target_account_id),
        listing_id=activity.video_target_listing_id,
        marketplace=cast(str, activity.video_channel),
        operation="attach",
        idempotency_key=f"campaign-video-marketplace:{activity.id}",
        state="pending",
        attempt_count=0,
        payload_json={
            "video_generation_id": str(activity.video_generation_id),
            "video_output_id": str(activity.video_output_id),
            "video_media_id": str(activity.video_media_id),
            "video_version": activity.video_version,
            "fingerprint": readiness["fingerprint"],
            "campaign_id": str(activity.campaign_id),
            "campaign_activity_id": str(activity.id),
        },
        correlation_id=activity.correlation_id or uuid.uuid4().hex[:32],
        created_at=utcnow(),
    )
    db.add(job)
    db.flush()
    activity.video_marketplace_job_id = job.id
    return job


def _schedule(
    db: Session,
    owner: User,
    campaign: Campaign,
    activity: CampaignActivity,
    artifact: GeneratedArtifact,
    destination: PublishingDestination,
    downstream_kind: str,
    downstream_id: uuid.UUID,
) -> PublishingSchedule:
    stamp = utcnow()
    context = {
        "payload_version": 1,
        "campaign_id": str(campaign.id),
        "campaign_video_activity_id": str(activity.id),
        "video_generation_id": str(activity.video_generation_id),
        "video_output_id": str(activity.video_output_id),
        "video_media_id": str(activity.video_media_id),
        "video_version": activity.video_version,
        "video_channel": activity.video_channel,
        "video_target_account_id": str(activity.video_target_account_id),
        "video_target_listing_id": (
            str(activity.video_target_listing_id) if activity.video_target_listing_id else None
        ),
        "thumbnail_output_id": (
            str(activity.video_thumbnail_output_id) if activity.video_thumbnail_output_id else None
        ),
        "thumbnail_media_id": (
            str(activity.video_thumbnail_media_id) if activity.video_thumbnail_media_id else None
        ),
        "thumbnail_version": activity.video_thumbnail_version,
        "caption_track_id": (
            str(activity.video_caption_track_id) if activity.video_caption_track_id else None
        ),
        "caption_version": activity.video_caption_version,
        "downstream_kind": downstream_kind,
        "downstream_id": str(downstream_id),
        "correlation_id": activity.correlation_id,
    }
    value = PublishingSchedule(
        owner_id=owner.id,
        brand_id=campaign.brand_id,
        product_id=artifact.product_id,
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        destination_id=destination.id,
        connector_key=destination.connector_key,
        requested_action="publish",
        name=f"{campaign.name}: {activity.name}",
        schedule_type="one_time",
        scheduled_at_utc=activity.scheduled_at_utc,
        timezone_name=activity.timezone_name,
        local_scheduled_at=datetime.combine(
            activity.scheduled_local_date, activity.scheduled_local_time
        ),
        recurrence_json=None,
        recurrence_end_at=None,
        enabled=True,
        paused=False,
        archived=False,
        approval_snapshot_json={
            "artifact_status": artifact.status,
            "approved_at": artifact.approved_at.isoformat() if artifact.approved_at else None,
            "approved_by": str(artifact.approved_by) if artifact.approved_by else None,
        },
        context_json=context,
        destination_snapshot_version=destination.updated_at.isoformat(),
        created_by=owner.id,
        created_at=stamp,
        updated_at=stamp,
        next_run_at_utc=activity.scheduled_at_utc,
        missed_occurrence_policy="next_occurrence",
        max_occurrences=1,
        materialized_occurrence_count=0,
    )
    db.add(value)
    db.flush()
    return value


def materialize_campaign_video(
    db: Session,
    owner: User,
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    *,
    expected_fingerprint: str,
    expected_row_version: int,
) -> dict[str, object]:
    activity = db.scalar(
        select(CampaignActivity)
        .where(
            CampaignActivity.id == activity_id,
            CampaignActivity.campaign_id == campaign_id,
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.activity_type == "video_campaign",
        )
        .with_for_update()
    )
    campaign = db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.owner_id == owner.id)
    )
    if activity is None or campaign is None:
        raise HTTPException(404, "Campaign Video Activity was not found.")
    if activity.schedule_id:
        job = db.scalar(
            select(PublishingJob).where(PublishingJob.schedule_id == activity.schedule_id)
        )
        return {
            "activity_id": activity.id,
            "schedule_id": activity.schedule_id,
            "job_id": job.id if job else activity.job_id,
            "downstream_id": activity.social_post_id or activity.video_marketplace_job_id,
            "status": activity.status,
            "idempotent_reuse": True,
        }
    if activity.video_preview_fingerprint != expected_fingerprint:
        raise HTTPException(409, "The Campaign Video preview is stale; create a fresh preview.")
    if activity.row_version != expected_row_version:
        raise HTTPException(409, "The Campaign Video Activity changed; refresh before scheduling.")
    if activity.video_replacement_state == "replaced" or activity.status in {
        "cancelled",
        "archived",
    }:
        raise HTTPException(409, "This historical Campaign Video Activity cannot be scheduled.")
    state, dependency_blockers = dependency_state(db, activity)
    activity.dependency_state = state
    if state != "ready":
        activity.status = "waiting_dependency" if state == "waiting" else "failed"
        activity.readiness_status = "blocked"
        activity.failure_code = None if state == "waiting" else "campaign_video_dependency_invalid"
        activity.safe_failure_message = (
            None if state == "waiting" else "A Campaign Video dependency is permanently invalid."
        )
        activity.updated_at = utcnow()
        record_event(
            db,
            actor_id=owner.id,
            action=(
                "campaign_video_dependency_waiting"
                if state == "waiting"
                else "campaign_video_failed"
            ),
            entity_type="campaign_activity",
            entity_id=activity.id,
            metadata={
                "campaign_id": str(campaign.id),
                "blockers": dependency_blockers,
                "failure_code": activity.failure_code,
            },
        )
        db.commit()
        return {
            "activity_id": activity.id,
            "schedule_id": None,
            "job_id": None,
            "status": activity.status,
            "failure_code": activity.failure_code,
            "idempotent_reuse": False,
        }
    readiness = activity_readiness(db, campaign, activity)
    if readiness.state not in {"ready", "warning"}:
        raise HTTPException(
            409,
            {
                "code": "campaign_video_not_ready",
                "issues": [issue.model_dump(mode="json") for issue in readiness.issues],
                "safe_message": "Campaign Video is not ready for durable scheduling.",
            },
        )
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == activity.artifact_id,
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.product_id == activity.product_id,
        )
    )
    if (
        artifact is None
        or artifact.status != "approved"
        or artifact.version_number != activity.artifact_version
    ):
        raise HTTPException(409, "The exact approved Video metadata Artifact is unavailable.")
    destination = _destination(db, owner, campaign, activity)
    downstream: SocialPost | MarketplaceVideoJob
    if activity.video_channel in SOCIAL_CHANNELS:
        downstream = _social_post(db, owner, campaign, activity, artifact)
        downstream_kind = "social_post"
    elif activity.video_channel in MARKETPLACE_CHANNELS:
        downstream = _marketplace_job(db, owner, activity)
        downstream_kind = "marketplace_video_job"
    else:
        raise HTTPException(409, "The Campaign Video channel is unsupported.")
    schedule = _schedule(
        db, owner, campaign, activity, artifact, destination, downstream_kind, downstream.id
    )
    if isinstance(downstream, SocialPost):
        downstream.schedule_id = schedule.id
    link = CampaignScheduleLink(
        owner_id=owner.id,
        campaign_id=campaign.id,
        activity_id=activity.id,
        schedule_id=schedule.id,
        occurrence_key=f"campaign-video:{activity.id}:v{activity.video_version}",
        created_at=utcnow(),
    )
    db.add(link)
    activity.destination_id = destination.id
    activity.connector_key = destination.connector_key
    activity.schedule_id = schedule.id
    activity.status = "scheduled"
    activity.readiness_status = "ready"
    activity.dependency_state = "ready"
    activity.video_downstream_state = "scheduled"
    activity.video_job_payload_version = 1
    activity.updated_at = utcnow()
    activity.row_version += 1
    record_event(
        db,
        actor_id=owner.id,
        action="campaign_video_dependency_ready",
        entity_type="campaign_activity",
        entity_id=activity.id,
        metadata={"campaign_id": str(campaign.id), "video_version": activity.video_version},
    )
    record_event(
        db,
        actor_id=owner.id,
        action="campaign_video_scheduled",
        entity_type="campaign_activity",
        entity_id=activity.id,
        metadata={
            "campaign_id": str(campaign.id),
            "schedule_id": str(schedule.id),
            "video_version": activity.video_version,
            "channel": activity.video_channel,
        },
    )
    materialize_due_schedules(db, commit=False)
    job = db.scalar(select(PublishingJob).where(PublishingJob.schedule_id == schedule.id))
    if job:
        link.job_id = job.id
        activity.job_id = job.id
        activity.status = "queued" if job.state == "pending" else "scheduled"
        record_event(
            db,
            actor_id=owner.id,
            action="campaign_video_materialized",
            entity_type="campaign_activity",
            entity_id=activity.id,
            metadata={
                "campaign_id": str(campaign.id),
                "schedule_id": str(schedule.id),
                "job_id": str(job.id),
                "payload_version": 1,
                "video_version": activity.video_version,
            },
        )
    if campaign.status in {"draft", "planning", "ready", "paused"}:
        campaign.status = "scheduled"
        campaign.updated_at = utcnow()
        campaign.row_version += 1
    db.commit()
    return {
        "activity_id": activity.id,
        "schedule_id": schedule.id,
        "job_id": job.id if job else None,
        "downstream_kind": downstream_kind,
        "downstream_id": downstream.id,
        "status": activity.status,
        "idempotent_reuse": False,
    }


def _audit_once(
    db: Session, activity: CampaignActivity, action: str, metadata: dict[str, object]
) -> None:
    from vayujit_api.audit.models import AuditEvent

    exists = db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.actor_id == activity.owner_id,
            AuditEvent.action == action,
            AuditEvent.entity_type == "campaign_activity",
            AuditEvent.entity_id == activity.id,
        )
    )
    if not exists:
        record_event(
            db,
            actor_id=activity.owner_id,
            action=action,
            entity_type="campaign_activity",
            entity_id=activity.id,
            metadata=metadata,
        )


def execute_campaign_video_job(db: Session, job: PublishingJob) -> CampaignVideoJobResult:
    raw_activity_id = job.context_json.get("campaign_video_activity_id")
    try:
        activity_id = uuid.UUID(str(raw_activity_id))
    except (TypeError, ValueError):
        return CampaignVideoJobResult(
            "failed",
            error_code="campaign_video_activity_invalid",
            safe_message="The Campaign Video Activity identity is invalid.",
        )
    activity = db.scalar(
        select(CampaignActivity)
        .where(CampaignActivity.id == activity_id, CampaignActivity.owner_id == job.owner_id)
        .with_for_update()
    )
    if activity is None:
        return CampaignVideoJobResult(
            "failed",
            error_code="campaign_video_activity_missing",
            safe_message="The Campaign Video Activity no longer exists.",
        )
    if (
        activity.schedule_id != job.schedule_id
        or activity.status in {"cancelled", "cancel_requested", "archived"}
        or activity.video_replacement_state == "replaced"
    ):
        return CampaignVideoJobResult(
            "cancelled",
            error_code="campaign_video_stale_job",
            safe_message="The stale Campaign Video Job was safely refused.",
        )
    state, _ = dependency_state(db, activity)
    if state != "ready":
        activity.status = "waiting_dependency" if state == "waiting" else "failed"
        activity.dependency_state = state
        activity.failure_code = None if state == "waiting" else "campaign_video_dependency_invalid"
        activity.safe_failure_message = (
            None if state == "waiting" else "A Campaign Video dependency is invalid."
        )
        db.commit()
        return CampaignVideoJobResult(
            "failed",
            retryable=state == "waiting",
            error_code=activity.failure_code or "campaign_video_dependency_waiting",
            safe_message=activity.safe_failure_message
            or "Campaign Video is waiting for a dependency.",
        )
    activity.status = "running"
    activity.video_downstream_state = "running"
    activity.updated_at = utcnow()
    _audit_once(
        db,
        activity,
        "campaign_video_started",
        {
            "campaign_id": str(activity.campaign_id),
            "job_id": str(job.id),
            "video_version": activity.video_version,
            "channel": activity.video_channel,
        },
    )
    db.commit()
    owner = db.get(User, activity.owner_id)
    if owner is None:
        return CampaignVideoJobResult(
            "failed",
            error_code="campaign_video_owner_missing",
            safe_message="The Campaign Video owner is unavailable.",
        )
    if activity.social_post_id:
        result = execute_social_job(db, job)
        post = db.get(SocialPost, activity.social_post_id)
        if post:
            activity.video_remote_id = post.remote_publication_id
            activity.video_downstream_state = post.lifecycle_status
            activity.failure_code = post.failure_code
            activity.safe_failure_message = post.safe_failure_message
            if post.lifecycle_status == "published":
                activity.status = "succeeded"
                activity.completed_at = utcnow()
            elif post.failure_code == "social.video.ambiguous_publication":
                activity.status = "reconciliation_required"
            elif post.lifecycle_status == "failed":
                activity.status = "retrying" if result.retryable else "failed"
        final = CampaignVideoJobResult(
            "succeeded" if activity.status == "succeeded" else "failed",
            result.retryable,
            result.error_code,
            result.safe_message,
        )
    elif activity.video_marketplace_job_id:
        downstream = db.get(MarketplaceVideoJob, activity.video_marketplace_job_id)
        if downstream is None:
            final = CampaignVideoJobResult(
                "failed",
                error_code="campaign_video_downstream_missing",
                safe_message="The Marketplace Video operation is unavailable.",
            )
        else:
            response = run_marketplace_video_job(db, owner, downstream)
            db.refresh(activity)
            db.refresh(downstream)
            activity.video_mapping_id = downstream.mapping_id
            activity.video_downstream_state = downstream.state
            activity.failure_code = downstream.last_error_code
            activity.safe_failure_message = downstream.safe_error_message
            remote_id = response.get("remote_video_id")
            activity.video_remote_id = str(remote_id) if remote_id else activity.video_remote_id
            if downstream.state == "succeeded":
                activity.status = "succeeded"
                activity.completed_at = utcnow()
            elif downstream.last_error_code == "commerce.video.ambiguous_result":
                activity.status = "reconciliation_required"
            else:
                activity.status = "failed"
            retryable = downstream.last_error_code in {
                "commerce.video.throttled",
                "commerce.video.timeout",
                "commerce.video.connector_unavailable",
            }
            final = CampaignVideoJobResult(
                "succeeded" if downstream.state == "succeeded" else "failed",
                retryable,
                downstream.last_error_code,
                downstream.safe_error_message,
            )
    else:
        activity.status = "failed"
        final = CampaignVideoJobResult(
            "failed",
            error_code="campaign_video_downstream_missing",
            safe_message="The Campaign Video downstream identity is unavailable.",
        )
    activity.updated_at = utcnow()
    activity.row_version += 1
    action = (
        "campaign_video_completed"
        if activity.status == "succeeded"
        else (
            "campaign_video_ambiguous"
            if activity.status == "reconciliation_required"
            else "campaign_video_failed"
        )
    )
    _audit_once(
        db,
        activity,
        action,
        {
            "campaign_id": str(activity.campaign_id),
            "job_id": str(job.id),
            "video_version": activity.video_version,
            "channel": activity.video_channel,
            "downstream_id": str(
                activity.social_post_id or activity.video_marketplace_job_id or ""
            ),
            "remote_id": activity.video_remote_id,
            "failure_code": activity.failure_code,
        },
    )
    campaign = db.get(Campaign, activity.campaign_id)
    if campaign:
        activity_states = set(
            db.scalars(
                select(CampaignActivity.status).where(
                    CampaignActivity.campaign_id == campaign.id,
                    CampaignActivity.enabled.is_(True),
                )
            )
        )
        mixed_outcome = bool(activity_states & {"succeeded", "completed_with_warning"}) and bool(
            activity_states
            & {
                "failed",
                "dead_letter",
                "retrying",
                "reconciliation_required",
                "cancelled",
                "skipped",
            }
        )
        projected = "partially_completed" if mixed_outcome else project_campaign_state(db, campaign)
        if projected == "blocked":
            projected = "running"
        if projected in {
            "planning",
            "scheduled",
            "running",
            "partially_completed",
            "completed",
            "failed",
            "cancelled",
        }:
            campaign.status = projected
            campaign.updated_at = utcnow()
            if projected == "completed":
                campaign.completed_at = utcnow()
    db.commit()
    return final


def resume_waiting_campaign_videos(db: Session, owner: User, campaign_id: uuid.UUID) -> int:
    rows = list(
        db.scalars(
            select(CampaignActivity).where(
                CampaignActivity.owner_id == owner.id,
                CampaignActivity.campaign_id == campaign_id,
                CampaignActivity.activity_type == "video_campaign",
                CampaignActivity.status == "waiting_dependency",
            )
        )
    )
    resumed = 0
    for activity in rows:
        state, _ = dependency_state(db, activity)
        if state == "ready":
            activity.status = "ready"
            activity.readiness_status = "ready"
            activity.dependency_state = "ready"
            activity.updated_at = utcnow()
            record_event(
                db,
                actor_id=owner.id,
                action="campaign_video_dependency_ready",
                entity_type="campaign_activity",
                entity_id=activity.id,
                metadata={"campaign_id": str(campaign_id)},
            )
            resumed += 1
        elif state == "failed":
            activity.status = "failed"
            activity.dependency_state = "failed"
            activity.failure_code = "campaign_video_dependency_invalid"
            activity.safe_failure_message = "A Campaign Video dependency is permanently invalid."
    db.commit()
    return resumed


def campaign_video_summary(
    db: Session, owner_id: uuid.UUID, campaign_id: uuid.UUID
) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(CampaignActivity).where(
                CampaignActivity.owner_id == owner_id,
                CampaignActivity.campaign_id == campaign_id,
                CampaignActivity.activity_type == "video_campaign",
            )
        )
    )
    statuses = (
        "waiting_dependency",
        "scheduled",
        "queued",
        "running",
        "succeeded",
        "retrying",
        "failed",
        "cancelled",
        "reconciliation_required",
    )
    counts = {status: sum(row.status == status for row in rows) for status in statuses}
    channels: dict[str, int] = {}
    versions: dict[str, int] = {}
    for row in rows:
        channel = row.video_channel or "unknown"
        version = str(row.video_version or "unknown")
        channels[channel] = channels.get(channel, 0) + 1
        versions[version] = versions.get(version, 0) + 1
    return {
        "total": len(rows),
        **counts,
        "retry_wait": counts["retrying"],
        "by_channel": channels,
        "by_video_version": versions,
        "mixed_state": len({row.status for row in rows}) > 1,
    }
