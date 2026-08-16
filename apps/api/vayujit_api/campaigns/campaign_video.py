"""Campaign Video orchestration over the existing Campaign domain.

The module stores exact immutable Video identities on CampaignActivity and keeps
preview/confirmation server-authoritative. It deliberately delegates downstream
execution to the existing Social and Marketplace Video workers.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.campaigns.campaign_service import owned_campaign
from vayujit_api.campaigns.campaign_video_runtime import (
    campaign_video_summary,
    materialize_campaign_video,
    resume_waiting_campaign_videos,
)
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityDependency,
)
from vayujit_api.campaigns.recovery_service import recovery_eligibility
from vayujit_api.commerce.marketplace_video import MarketplaceVideoJob
from vayujit_api.commerce.models import MarketplaceAccount, MarketplaceListing
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product
from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.publishing.scheduler_time import local_to_utc, utcnow
from vayujit_api.social.models import SocialAccount, SocialPost
from vayujit_api.video.models import VideoCaptionTrack, VideoGeneration, VideoOutput

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaign-video"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]

SOCIAL_CHANNELS = {
    "youtube_video": "youtube",
    "youtube_short": "youtube",
    "instagram_reel": "instagram",
    "instagram_story": "instagram",
    "facebook_reel": "facebook",
    "facebook_story": "facebook",
}
MARKETPLACE_CHANNELS = {"amazon", "flipkart", "meesho"}


class VideoActivityRequest(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: uuid.UUID
    video_generation_id: uuid.UUID
    video_output_id: uuid.UUID
    video_media_id: uuid.UUID
    video_version: int = Field(ge=1)
    video_channel: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    scheduled_local_at: datetime
    timezone_name: str = Field(min_length=1, max_length=100)
    target_account_id: uuid.UUID
    target_listing_id: uuid.UUID | None = None
    thumbnail_output_id: uuid.UUID | None = None
    thumbnail_media_id: uuid.UUID | None = None
    thumbnail_version: int | None = Field(default=None, ge=1)
    caption_track_id: uuid.UUID | None = None
    caption_version: int | None = Field(default=None, ge=1)
    metadata: dict[str, object] = Field(default_factory=dict)
    metadata_artifact_id: uuid.UUID | None = None
    metadata_artifact_version: int | None = Field(default=None, ge=1)
    preview_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    confirm: bool = False
    idempotency_key: str = Field(min_length=1, max_length=160)
    expected_activity_row_version: int | None = Field(default=None, ge=1)
    activity_id: uuid.UUID | None = None


class VideoReplacementRequest(VideoActivityRequest):
    activity_id: uuid.UUID
    reason: str = Field(default="Approved Video replacement.", max_length=500)
    preview_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)


class VideoMaterializeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    preview_fingerprint: str = Field(min_length=64, max_length=64)
    expected_activity_row_version: int = Field(ge=1)
    confirm: Literal[True]


def _version(db: Session, generation: VideoGeneration) -> int:
    value = 1
    parent = generation.parent_generation_id
    seen: set[uuid.UUID] = set()
    while parent and parent not in seen:
        seen.add(parent)
        value += 1
        row = db.get(VideoGeneration, parent)
        parent = row.parent_generation_id if row else None
    return value


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _target(
    db: Session, owner: User, request: VideoActivityRequest
) -> tuple[str, object, object | None, list[str]]:
    blockers: list[str] = []
    if request.video_channel in SOCIAL_CHANNELS:
        account = db.scalar(
            select(SocialAccount).where(
                SocialAccount.id == request.target_account_id,
                SocialAccount.owner_id == owner.id,
            )
        )
        if account is None:
            blockers.append("social_account_missing")
            return SOCIAL_CHANNELS[request.video_channel], None, None, blockers
        if account.platform != SOCIAL_CHANNELS[request.video_channel]:
            blockers.append("social_channel_mismatch")
        if not account.enabled:
            blockers.append("social_account_disabled")
        if account.validation_status != "valid":
            blockers.append("social_account_not_validated")
        return SOCIAL_CHANNELS[request.video_channel], account, None, blockers
    if request.video_channel in MARKETPLACE_CHANNELS:
        marketplace_account = db.scalar(
            select(MarketplaceAccount).where(
                MarketplaceAccount.id == request.target_account_id,
                MarketplaceAccount.owner_id == owner.id,
            )
        )
        listing = (
            db.scalar(
                select(MarketplaceListing).where(
                    MarketplaceListing.id == request.target_listing_id,
                    MarketplaceListing.owner_id == owner.id,
                )
            )
            if request.target_listing_id
            else None
        )
        if marketplace_account is None:
            blockers.append("marketplace_account_missing")
        elif marketplace_account.marketplace != request.video_channel:
            blockers.append("marketplace_channel_mismatch")
        elif not marketplace_account.enabled or marketplace_account.validation_status != "valid":
            blockers.append("marketplace_account_not_ready")
        if listing is None:
            blockers.append("marketplace_listing_missing")
        elif listing.product_id != request.product_id:
            blockers.append("marketplace_listing_product_mismatch")
        elif listing.status not in {"active", "ready"}:
            blockers.append("marketplace_listing_not_ready")
        return request.video_channel, marketplace_account, listing, blockers
    blockers.append("unsupported_video_channel")
    return request.video_channel, None, None, blockers


def _validate(
    db: Session, owner: User, campaign: Campaign, request: VideoActivityRequest
) -> dict[str, object]:
    blockers: list[str] = []
    warnings: list[str] = []
    product = db.scalar(
        select(Product).where(Product.id == request.product_id, Product.owner_id == owner.id)
    )
    generation = db.scalar(
        select(VideoGeneration).where(
            VideoGeneration.id == request.video_generation_id,
            VideoGeneration.owner_id == owner.id,
        )
    )
    output = db.scalar(
        select(VideoOutput).where(
            VideoOutput.id == request.video_output_id,
            VideoOutput.generation_id == request.video_generation_id,
            VideoOutput.owner_id == owner.id,
        )
    )
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == request.video_media_id,
            MediaAsset.owner_id == owner.id,
        )
    )
    metadata_artifact = (
        db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == request.metadata_artifact_id,
                GeneratedArtifact.owner_id == owner.id,
            )
        )
        if request.metadata_artifact_id
        else None
    )
    thumbnail_output = (
        db.scalar(
            select(AIImageOutput).where(
                AIImageOutput.id == request.thumbnail_output_id,
                AIImageOutput.owner_id == owner.id,
            )
        )
        if request.thumbnail_output_id
        else None
    )
    thumbnail_media = (
        db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == request.thumbnail_media_id,
                MediaAsset.owner_id == owner.id,
            )
        )
        if request.thumbnail_media_id
        else None
    )
    caption_track = (
        db.get(VideoCaptionTrack, request.caption_track_id) if request.caption_track_id else None
    )
    if metadata_artifact is None:
        blockers.append("approved_metadata_missing")
    elif (
        metadata_artifact.product_id != request.product_id
        or metadata_artifact.status != "approved"
        or metadata_artifact.version_number != request.metadata_artifact_version
    ):
        blockers.append("approved_metadata_invalid")
    if any((request.thumbnail_output_id, request.thumbnail_media_id, request.thumbnail_version)):
        if not all(
            (request.thumbnail_output_id, request.thumbnail_media_id, request.thumbnail_version)
        ):
            blockers.append("thumbnail_lineage_incomplete")
        elif (
            thumbnail_output is None
            or thumbnail_media is None
            or thumbnail_output.product_id != request.product_id
            or thumbnail_output.status != "approved"
            or thumbnail_output.media_id != thumbnail_media.id
            or thumbnail_media.status != "ready"
        ):
            blockers.append("thumbnail_not_approved")
    if any((request.caption_track_id, request.caption_version)):
        if not all((request.caption_track_id, request.caption_version)):
            blockers.append("caption_lineage_incomplete")
        elif (
            caption_track is None
            or caption_track.generation_id != request.video_generation_id
            or caption_track.version != request.caption_version
            or caption_track.approval_state != "approved"
        ):
            blockers.append("caption_not_approved")
    allowed_metadata = {"title", "caption", "description", "hashtags", "locale"}
    if set(request.metadata) - allowed_metadata:
        blockers.append("unsafe_metadata")
    serialized_metadata = json.dumps(request.metadata, default=str).lower()
    if any(
        value in serialized_metadata
        for value in (
            "http://",
            "https://",
            "file://",
            "database_url",
            "token",
            "cookie",
            "password",
        )
    ):
        blockers.append("unsafe_metadata")
    if product is None:
        blockers.append("product_missing")
    elif product.brand_id != campaign.brand_id:
        blockers.append("product_brand_mismatch")
    if generation is None or output is None or media is None:
        blockers.append("exact_video_reference_missing")
    else:
        if generation.product_id != request.product_id:
            blockers.append("video_product_mismatch")
        if generation.status != "succeeded" or output.status != "approved":
            blockers.append("video_not_approved")
        if media.status != "ready":
            blockers.append("video_media_not_ready")
        if request.video_version != _version(db, generation):
            blockers.append("video_version_mismatch")
    channel, account, listing, target_blockers = _target(db, owner, request)
    blockers.extend(target_blockers)
    try:
        scheduled_utc = local_to_utc(
            request.scheduled_local_at.replace(tzinfo=None), request.timezone_name, 0
        )
    except ValueError:
        blockers.append("invalid_schedule_timezone")
        scheduled_utc = request.scheduled_local_at
    if campaign.status in {"cancelled", "archived", "completed"}:
        blockers.append("campaign_not_mutable")
    if request.activity_id:
        activity = db.get(CampaignActivity, request.activity_id)
        if activity is None or activity.owner_id != owner.id or activity.campaign_id != campaign.id:
            blockers.append("activity_missing")
        elif (
            request.expected_activity_row_version is not None
            and activity.row_version != request.expected_activity_row_version
        ):
            blockers.append("activity_version_stale")
        if activity and activity.video_version and activity.video_version != request.video_version:
            warnings.append("replacement_changes_video_version")
    state = {
        "campaign_id": str(campaign.id),
        "campaign_status": campaign.status,
        "campaign_row_version": campaign.row_version,
        "activity_id": str(request.activity_id) if request.activity_id else None,
        "activity_row_version": request.expected_activity_row_version,
        "product_id": str(request.product_id),
        "video_generation_id": str(request.video_generation_id),
        "video_output_id": str(request.video_output_id),
        "video_media_id": str(request.video_media_id),
        "video_version": request.video_version,
        "video_channel": channel,
        "metadata_artifact_id": (
            str(request.metadata_artifact_id) if request.metadata_artifact_id else None
        ),
        "metadata_artifact_version": request.metadata_artifact_version,
        "thumbnail_output_id": (
            str(request.thumbnail_output_id) if request.thumbnail_output_id else None
        ),
        "thumbnail_media_id": (
            str(request.thumbnail_media_id) if request.thumbnail_media_id else None
        ),
        "thumbnail_version": request.thumbnail_version,
        "caption_track_id": str(request.caption_track_id) if request.caption_track_id else None,
        "caption_version": request.caption_version,
        "metadata": request.metadata,
        "target_account_id": str(request.target_account_id),
        "target_listing_id": str(request.target_listing_id) if request.target_listing_id else None,
        "scheduled_local_at": request.scheduled_local_at.isoformat(),
        "timezone_name": request.timezone_name,
        "target_updated_at": getattr(account, "updated_at", None),
        "listing_updated_at": getattr(listing, "updated_at", None),
    }
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status},
        "product": {"id": request.product_id, "name": getattr(product, "name", None)},
        "video": {
            "generation_id": request.video_generation_id,
            "output_id": request.video_output_id,
            "media_id": request.video_media_id,
            "version": request.video_version,
            "status": getattr(generation, "status", None),
            "output_status": getattr(output, "status", None),
        },
        "channel": channel,
        "target": {
            "account_id": request.target_account_id,
            "listing_id": request.target_listing_id,
            "display_name": getattr(account, "display_name", None),
        },
        "schedule": {
            "local": request.scheduled_local_at,
            "timezone": request.timezone_name,
            "utc": scheduled_utc,
        },
        "dependencies": {"state": "ready", "count": 0},
        "fingerprint": _fingerprint(state),
        "correlation_id": uuid.uuid4().hex[:32],
    }


def _activity_response(value: CampaignActivity) -> dict[str, object]:
    return {
        "id": value.id,
        "campaign_id": value.campaign_id,
        "product_id": value.product_id,
        "activity_type": value.activity_type,
        "name": value.name,
        "status": value.status,
        "readiness_status": value.readiness_status,
        "video_generation_id": value.video_generation_id,
        "video_output_id": value.video_output_id,
        "video_media_id": value.video_media_id,
        "video_version": value.video_version,
        "video_channel": value.video_channel,
        "video_target_account_id": value.video_target_account_id,
        "video_target_listing_id": value.video_target_listing_id,
        "video_mapping_id": value.video_mapping_id,
        "video_marketplace_job_id": value.video_marketplace_job_id,
        "video_remote_id": value.video_remote_id,
        "video_downstream_state": value.video_downstream_state,
        "video_job_payload_version": value.video_job_payload_version,
        "scheduled_at_utc": value.scheduled_at_utc,
        "timezone_name": value.timezone_name,
        "schedule_id": value.schedule_id,
        "job_id": value.job_id,
        "social_post_id": value.social_post_id,
        "replaces_activity_id": value.replaces_activity_id,
        "replaced_by_activity_id": value.replaced_by_activity_id,
        "dependency_state": value.dependency_state,
        "row_version": value.row_version,
    }


@router.post("/{campaign_id}/video/activities/preview")
def preview_activity(
    campaign_id: uuid.UUID, request: VideoActivityRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    value = _validate(db, owner, campaign, request)
    value["intended_mutation"] = (
        "replace_video_activity" if request.activity_id else "create_video_activity"
    )
    value["safe_message"] = (
        "Review the exact Video, target, dependencies, and schedule before confirming."
    )
    record_event(
        db,
        actor_id=owner.id,
        action="campaign_video_previewed",
        entity_type="campaign",
        entity_id=campaign.id,
        metadata={"video_version": request.video_version, "channel": request.video_channel},
    )
    db.commit()
    return value


@router.post("/{campaign_id}/video/activities")
def confirm_activity(
    campaign_id: uuid.UUID, request: VideoActivityRequest, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id, lock=True)
    value = _validate(db, owner, campaign, request)
    fingerprint = str(value["fingerprint"])
    if not request.confirm:
        raise HTTPException(422, "Explicit Campaign Video confirmation is required.")
    if request.preview_fingerprint != fingerprint:
        raise HTTPException(409, "The Campaign Video preview is stale; create a fresh preview.")
    if request.activity_id:
        existing_activity = db.get(CampaignActivity, request.activity_id)
        if (
            existing_activity
            and request.expected_activity_row_version
            and existing_activity.row_version != request.expected_activity_row_version
        ):
            raise HTTPException(409, "The Campaign Activity changed; create a fresh Video preview.")
    existing = db.scalar(
        select(CampaignActivity).where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.idempotency_key == request.idempotency_key,
        )
    )
    if existing:
        return {
            "activity": _activity_response(existing),
            "idempotent_reuse": True,
            "fingerprint": fingerprint,
        }
    if value["blockers"]:
        raise HTTPException(
            409,
            {
                "code": "campaign_video_not_ready",
                "blockers": value["blockers"],
                "safe_message": "Campaign Video is not ready for confirmation.",
            },
        )
    schedule = cast(dict[str, Any], value["schedule"])
    timestamp = utcnow()
    sequence = (
        db.scalar(
            select(func.max(CampaignActivity.sequence)).where(
                CampaignActivity.campaign_id == campaign.id
            )
        )
        or 0
    )
    activity = CampaignActivity(
        owner_id=owner.id,
        campaign_id=campaign.id,
        product_id=request.product_id,
        artifact_id=request.metadata_artifact_id,
        artifact_version=request.metadata_artifact_version,
        video_generation_id=request.video_generation_id,
        video_output_id=request.video_output_id,
        video_media_id=request.video_media_id,
        video_version=request.video_version,
        video_channel=request.video_channel,
        video_thumbnail_output_id=request.thumbnail_output_id,
        video_thumbnail_media_id=request.thumbnail_media_id,
        video_thumbnail_version=request.thumbnail_version,
        video_caption_track_id=request.caption_track_id,
        video_caption_version=request.caption_version,
        video_metadata_json=request.metadata,
        video_preview_fingerprint=fingerprint,
        video_target_account_id=request.target_account_id,
        video_target_listing_id=request.target_listing_id,
        dependency_state="ready",
        video_replacement_state="current",
        connector_key=f"campaign_video:{request.video_channel}",
        requested_action="publish",
        activity_type="video_campaign",
        name=request.name.strip(),
        description=request.description.strip(),
        sequence=int(sequence) + 1,
        dependency_policy="success_required",
        scheduled_local_date=schedule["local"].date(),
        scheduled_local_time=schedule["local"].time(),
        timezone_name=request.timezone_name,
        scheduled_at_utc=schedule["utc"],
        duration_minutes=None,
        status="ready",
        readiness_status="ready",
        required=True,
        enabled=True,
        created_by=owner.id,
        created_at=timestamp,
        updated_at=timestamp,
        correlation_id=str(value["correlation_id"]),
        idempotency_key=request.idempotency_key,
        row_version=1,
    )
    db.add(activity)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="campaign_video_created",
        entity_type="campaign_activity",
        entity_id=activity.id,
        metadata={
            "campaign_id": str(campaign.id),
            "video_version": request.video_version,
            "channel": request.video_channel,
        },
    )
    db.commit()
    db.refresh(activity)
    return {
        "activity": _activity_response(activity),
        "idempotent_reuse": False,
        "fingerprint": fingerprint,
    }


@router.post("/{campaign_id}/video/activities/{activity_id}/replacement/preview")
def preview_replacement(
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    request: VideoActivityRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    request.activity_id = activity_id
    campaign = owned_campaign(db, owner.id, campaign_id)
    current = db.get(CampaignActivity, activity_id)
    if request.activity_id != activity_id:
        raise HTTPException(422, "Replacement Activity identity must match the route.")
    if current is None or current.owner_id != owner.id or current.campaign_id != campaign.id:
        raise HTTPException(404, "Campaign Video Activity not found.")
    value = _validate(db, owner, campaign, request)
    value["current_video"] = {
        "generation_id": current.video_generation_id,
        "output_id": current.video_output_id,
        "version": current.video_version,
    }
    value["intended_mutation"] = "replace_video_activity"
    value["safe_message"] = (
        "Review the current and proposed exact Video versions before confirming replacement."
    )
    record_event(
        db,
        actor_id=owner.id,
        action="campaign_video_replacement_previewed",
        entity_type="campaign_activity",
        entity_id=current.id,
        metadata={
            "old_video_version": current.video_version,
            "new_video_version": request.video_version,
        },
    )
    db.commit()
    return value


@router.post("/{campaign_id}/video/activities/{activity_id}/replacement")
def confirm_replacement(
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    request: VideoReplacementRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id, lock=True)
    current = db.get(CampaignActivity, activity_id)
    if request.activity_id != activity_id:
        raise HTTPException(422, "Replacement Activity identity must match the route.")
    if current is None or current.owner_id != owner.id or current.campaign_id != campaign.id:
        raise HTTPException(404, "Campaign Video Activity not found.")
    key = request.idempotency_key
    existing = db.scalar(
        select(CampaignActivity).where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.campaign_id == campaign.id,
            CampaignActivity.idempotency_key == key,
            CampaignActivity.replaces_activity_id == current.id,
        )
    )
    if existing:
        return {"activity": _activity_response(existing), "idempotent_reuse": True}
    value = _validate(db, owner, campaign, request)
    if not request.confirm:
        raise HTTPException(422, "Explicit Campaign Video replacement confirmation is required.")
    if request.preview_fingerprint != value["fingerprint"]:
        raise HTTPException(
            409, "The Campaign Video replacement preview is stale; create a fresh preview."
        )
    if value["blockers"]:
        raise HTTPException(
            409,
            {
                "code": "campaign_video_replacement_not_ready",
                "blockers": value["blockers"],
                "safe_message": "Campaign Video replacement is not ready.",
            },
        )
    timestamp = utcnow()
    sequence = (
        db.scalar(
            select(func.max(CampaignActivity.sequence)).where(
                CampaignActivity.campaign_id == campaign.id
            )
        )
        or 0
    )
    schedule = cast(dict[str, Any], value["schedule"])
    replacement = CampaignActivity(
        id=uuid.uuid4(),
        owner_id=owner.id,
        campaign_id=campaign.id,
        product_id=request.product_id,
        artifact_id=request.metadata_artifact_id,
        artifact_version=request.metadata_artifact_version,
        video_generation_id=request.video_generation_id,
        video_output_id=request.video_output_id,
        video_media_id=request.video_media_id,
        video_version=request.video_version,
        video_channel=request.video_channel,
        video_thumbnail_output_id=request.thumbnail_output_id,
        video_thumbnail_media_id=request.thumbnail_media_id,
        video_thumbnail_version=request.thumbnail_version,
        video_caption_track_id=request.caption_track_id,
        video_caption_version=request.caption_version,
        video_metadata_json=request.metadata,
        video_preview_fingerprint=str(value["fingerprint"]),
        video_target_account_id=request.target_account_id,
        video_target_listing_id=request.target_listing_id,
        dependency_state="ready",
        video_replacement_state="current",
        connector_key=f"campaign_video:{request.video_channel}",
        requested_action="publish",
        activity_type="video_campaign",
        name=request.name.strip(),
        description=request.description.strip(),
        sequence=int(sequence) + 1,
        dependency_policy="success_required",
        scheduled_local_date=schedule["local"].date(),
        scheduled_local_time=schedule["local"].time(),
        timezone_name=request.timezone_name,
        scheduled_at_utc=schedule["utc"],
        status="ready",
        readiness_status="ready",
        required=current.required,
        enabled=True,
        created_by=owner.id,
        created_at=timestamp,
        updated_at=timestamp,
        correlation_id=str(value["correlation_id"]),
        idempotency_key=key,
        row_version=1,
        replaces_activity_id=current.id,
        replacement_reason=request.reason,
    )
    if current.schedule_id:
        old_schedule = db.get(PublishingSchedule, current.schedule_id)
        if old_schedule:
            old_schedule.enabled = False
            old_schedule.archived = True
            old_schedule.cancellation_reason = "Superseded by Campaign Video replacement."
    if current.job_id:
        old_job = db.get(PublishingJob, current.job_id)
        if old_job and old_job.state not in {"succeeded", "failed", "cancelled", "dead_letter"}:
            old_job.state = "cancelled"
            old_job.recovery_state = "superseded"
            old_job.recovery_reason = "Superseded by Campaign Video replacement."
            old_job.completed_at = timestamp
            old_job.updated_at = timestamp
            old_job.row_version += 1
    db.add(replacement)
    db.flush()
    current.video_replacement_state = "replaced"
    current.replaced_by_activity_id = replacement.id
    current.status = "completed_with_warning" if current.status == "succeeded" else current.status
    current.updated_at = timestamp
    current.row_version += 1
    record_event(
        db,
        actor_id=owner.id,
        action="campaign_video_replaced",
        entity_type="campaign_activity",
        entity_id=replacement.id,
        metadata={
            "replaces_activity_id": str(current.id),
            "old_video_version": current.video_version,
            "new_video_version": request.video_version,
        },
    )
    db.commit()
    db.refresh(replacement)
    return {"activity": _activity_response(replacement), "idempotent_reuse": False}


@router.post("/{campaign_id}/video/activities/{activity_id}/materialize")
def materialize_activity(
    campaign_id: uuid.UUID,
    activity_id: uuid.UUID,
    request: VideoMaterializeRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return materialize_campaign_video(
        db,
        owner,
        campaign_id,
        activity_id,
        expected_fingerprint=request.preview_fingerprint,
        expected_row_version=request.expected_activity_row_version,
    )


@router.post("/{campaign_id}/video/dependencies/resume")
def resume_dependencies(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    owned_campaign(db, owner.id, campaign_id)
    return {
        "campaign_id": campaign_id,
        "resumed": resume_waiting_campaign_videos(db, owner, campaign_id),
    }


@router.get("/{campaign_id}/video/analytics")
def video_analytics(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    owned_campaign(db, owner.id, campaign_id)
    return campaign_video_summary(db, owner.id, campaign_id)


@router.get("/{campaign_id}/video/overview")
def campaign_video_overview(campaign_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    rows = list(
        db.scalars(
            select(CampaignActivity)
            .where(
                CampaignActivity.owner_id == owner.id,
                CampaignActivity.campaign_id == campaign.id,
                CampaignActivity.activity_type == "video_campaign",
            )
            .order_by(CampaignActivity.scheduled_at_utc)
        )
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return {
        "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status},
        "video_activity_count": len(rows),
        "counts": counts,
        "update_available": False,
        "upcoming": [
            _activity_response(row) for row in rows if row.status not in {"succeeded", "cancelled"}
        ][:10],
        "recent": [_activity_response(row) for row in rows[-10:]],
    }


@router.get("/{campaign_id}/video/activities/{activity_id}/detail")
def campaign_video_detail(
    campaign_id: uuid.UUID, activity_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    value = db.get(CampaignActivity, activity_id)
    if value is None or value.owner_id != owner.id or value.campaign_id != campaign.id:
        raise HTTPException(404, "Campaign Video Activity not found.")
    dependencies = list(
        db.scalars(
            select(CampaignActivityDependency).where(
                CampaignActivityDependency.owner_id == owner.id,
                (
                    (CampaignActivityDependency.predecessor_activity_id == value.id)
                    | (CampaignActivityDependency.successor_activity_id == value.id)
                ),
            )
        )
    )
    decisions = recovery_eligibility(campaign, value, db=db)
    linked_actions: list[str] = []
    if value.social_post_id:
        post = db.get(SocialPost, value.social_post_id)
        if post and post.lifecycle_status in {"failed", "reconciliation_required"}:
            linked_actions = ["retry", "reconcile", "review_failure", "cancel"]
    elif value.video_marketplace_job_id:
        marketplace_job = db.get(MarketplaceVideoJob, value.video_marketplace_job_id)
        if marketplace_job and marketplace_job.state == "failed":
            linked_actions = ["retry", "reconcile", "open_listing", "cancel"]
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.entity_type == "campaign_activity",
                AuditEvent.entity_id == value.id,
            )
            .order_by(AuditEvent.occurred_at)
        )
    )
    return {
        "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status},
        "activity": _activity_response(value),
        "history": [
            {
                "action": event.action,
                "occurred_at": event.occurred_at,
                "metadata": event.metadata_json,
            }
            for event in events
        ],
        "recovery": {
            "failure_code": value.failure_code,
            "safe_message": value.safe_failure_message,
            "retryable": value.status == "retrying",
            "correlation_id": value.correlation_id,
            "campaign_actions": [
                {
                    "action": item.action,
                    "eligible": item.eligible,
                    "reason_code": item.reason_code,
                    "explanation": item.explanation,
                    "confirmation_required": item.confirmation_required,
                    "navigation_target": item.navigation_target,
                }
                for item in decisions
            ],
            "linked_downstream_actions": linked_actions,
        },
        "dependencies": [
            {
                "id": edge.id,
                "predecessor_activity_id": edge.predecessor_activity_id,
                "successor_activity_id": edge.successor_activity_id,
                "dependency_type": edge.dependency_type,
                "released_at": edge.released_at,
            }
            for edge in dependencies
        ],
    }


@router.get("/{campaign_id}/video/history")
def campaign_video_history(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    campaign = owned_campaign(db, owner.id, campaign_id)
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.metadata_json["campaign_id"].as_string() == str(campaign.id),
            )
            .order_by(AuditEvent.occurred_at)
        )
    )
    return [
        {
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "occurred_at": event.occurred_at,
            "metadata": event.metadata_json,
        }
        for event in events
    ]


@router.get("/video/products/{product_id}/channel")
def campaign_video_product_channel(
    product_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner.id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    rows = list(
        db.scalars(
            select(CampaignActivity)
            .where(
                CampaignActivity.owner_id == owner.id,
                CampaignActivity.product_id == product_id,
                CampaignActivity.activity_type == "video_campaign",
            )
            .order_by(CampaignActivity.updated_at.desc())
        )
    )
    latest_generations = list(
        db.scalars(
            select(VideoGeneration).where(
                VideoGeneration.owner_id == owner.id,
                VideoGeneration.product_id == product_id,
                VideoGeneration.status == "succeeded",
            )
        )
    )
    channels: list[dict[str, object]] = []
    for row in rows:
        campaign = db.get(Campaign, row.campaign_id)
        job = db.get(PublishingJob, row.job_id) if row.job_id else None
        latest_version = max((_version(db, item) for item in latest_generations), default=0)
        actions = ["open_campaign", "open_activity"]
        if row.schedule_id:
            actions.append("view_schedule")
        if latest_version > (row.video_version or 0):
            actions.extend(["preview_campaign_video_update", "preview_campaign_replacement"])
        if row.status in {"failed", "retrying", "reconciliation_required"}:
            actions.append("open_recovery")
        channels.append(
            {
                "channel": row.video_channel,
                "current_video_output_id": row.video_output_id,
                "current_video_version": row.video_version,
                "campaign": {"id": campaign.id, "name": campaign.name} if campaign else None,
                "campaign_activity_id": row.id,
                "activity_state": row.status,
                "next_scheduled_execution": row.scheduled_at_utc,
                "latest_execution": (
                    {
                        "job_id": job.id,
                        "state": job.state,
                        "attempt_count": job.execution_attempt_count,
                    }
                    if job
                    else None
                ),
                "update_available": latest_version > (row.video_version or 0),
                "downstream_state": row.video_downstream_state,
                "downstream_id": row.social_post_id or row.video_marketplace_job_id,
                "failure_code": row.failure_code,
                "safe_failure_message": row.safe_failure_message,
                "replacement_available": row.video_replacement_state == "current",
                "actions": actions,
            }
        )
    return {"product_id": product.id, "channels": channels}


@router.get("/video/products/{product_id}/media-usage")
def campaign_video_product_media_usage(
    product_id: uuid.UUID, db: DB, owner: Owner
) -> list[dict[str, object]]:
    if (
        db.scalar(select(Product.id).where(Product.id == product_id, Product.owner_id == owner.id))
        is None
    ):
        raise HTTPException(404, "Product not found.")
    rows = list(
        db.scalars(
            select(CampaignActivity).where(
                CampaignActivity.owner_id == owner.id,
                CampaignActivity.product_id == product_id,
                CampaignActivity.activity_type == "video_campaign",
            )
        )
    )
    return [
        {
            "campaign_id": row.campaign_id,
            "campaign_activity_id": row.id,
            "channel": row.video_channel,
            "video_output_id": row.video_output_id,
            "video_media_id": row.video_media_id,
            "video_version": row.video_version,
            "schedule_id": row.schedule_id,
            "state": row.status,
            "downstream_id": row.social_post_id or row.video_marketplace_job_id,
            "remote_id": row.video_remote_id,
        }
        for row in rows
    ]
