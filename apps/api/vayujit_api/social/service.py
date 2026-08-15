from __future__ import annotations

import hashlib
import ipaddress
import json
import uuid
from typing import cast
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.credentials import encrypt_credential
from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.campaigns.models import Campaign, CampaignActivity
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.models import PublishingDestination
from vayujit_api.publishing.scheduler_schemas import ScheduleCreate
from vayujit_api.publishing.scheduler_service import create_schedule
from vayujit_api.publishing.scheduler_time import local_to_utc, utcnow
from vayujit_api.social.connectors import SocialConnectorFailure, connector_for
from vayujit_api.social.models import SocialAccount, SocialMetric, SocialPost
from vayujit_api.social.schemas import (
    SocialAccountCreate,
    SocialPostCreate,
    SocialPostUpdate,
    SocialScheduleRequest,
)


def account_response(value: SocialAccount) -> dict[str, object]:
    return {
        "id": value.id,
        "platform": value.platform,
        "identity_type": value.identity_type,
        "display_name": value.display_name,
        "remote_account_id": value.remote_account_id,
        "environment": value.environment,
        "enabled": value.enabled,
        "validation_status": value.validation_status,
        "capabilities": value.capabilities_json,
        "credential_configured": bool(value.encrypted_credentials),
        "credential_version": value.credential_version,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "last_validated_at": value.last_validated_at,
    }


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    hostname = parsed.hostname
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise ValueError("Destination URL must be a configured HTTPS URL without credentials.")
    if hostname.lower() == "localhost":
        raise ValueError("Destination URL must not target a local host.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and (
        address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
    ):
        raise ValueError("Destination URL must not target a private or local network.")
    return value


def _owned_account(db: Session, owner: User, account_id: uuid.UUID) -> SocialAccount:
    value = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == account_id, SocialAccount.owner_id == owner.id
        )
    )
    if not value:
        raise HTTPException(404, "Social account not found.")
    return value


def _owned_post(db: Session, owner: User, post_id: uuid.UUID) -> SocialPost:
    value = db.scalar(
        select(SocialPost).where(SocialPost.id == post_id, SocialPost.owner_id == owner.id)
    )
    if not value:
        raise HTTPException(404, "Social post not found.")
    return value


def create_account(db: Session, owner: User, data: SocialAccountCreate) -> SocialAccount:
    timestamp = utcnow()
    encrypted = None
    if data.credentials:
        try:
            encrypted = encrypt_credential(
                json.dumps(data.credentials, sort_keys=True),
                get_settings().credential_encryption_key,
            )
        except Exception:
            encrypted = (
                "local-hash:"
                + hashlib.sha256(json.dumps(data.credentials, sort_keys=True).encode()).hexdigest()
            )
    value = SocialAccount(
        owner_id=owner.id,
        platform=data.platform,
        identity_type=data.identity_type,
        display_name=data.display_name.strip(),
        remote_account_id=data.remote_account_id.strip(),
        environment=data.environment,
        enabled=True,
        validation_status="unknown",
        capabilities_json={
            **data.capabilities,
            "platform": data.platform,
            "connector": "social_fake",
            "supported_content_types": _content_types(data.platform),
        },
        encrypted_credentials=encrypted,
        credential_version=1,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="social.account_created",
        entity_type="social_account",
        entity_id=value.id,
        metadata={"platform": value.platform},
    )
    db.commit()
    db.refresh(value)
    return value


def validate_account(db: Session, owner: User, value: SocialAccount) -> SocialAccount:
    try:
        connector_for(value.platform, value.capabilities_json).validate_account(
            {"remote_account_id": value.remote_account_id}
        )
        value.validation_status = "valid"
    except SocialConnectorFailure:
        value.validation_status = "invalid"
    value.last_validated_at = utcnow()
    value.updated_at = utcnow()
    record_event(
        db,
        actor_id=owner.id,
        action="social.account_validated",
        entity_type="social_account",
        entity_id=value.id,
        metadata={"platform": value.platform, "status": value.validation_status},
    )
    db.commit()
    db.refresh(value)
    return value


def _content_types(platform: str) -> list[str]:
    return {
        "instagram": ["instagram_post", "instagram_story", "instagram_reel"],
        "facebook": ["facebook_post", "facebook_story", "facebook_reel"],
        "youtube": [
            "youtube_video",
            "youtube_short",
            "youtube_community_post",
            "youtube_thumbnail",
        ],
    }[platform]


def _readiness(
    db: Session, owner: User, post: SocialPost, account: SocialAccount
) -> dict[str, object]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == post.content_artifact_id, GeneratedArtifact.owner_id == owner.id
        )
    )
    if (
        not artifact
        or artifact.version_number != post.content_artifact_version
        or artifact.status != "approved"
    ):
        blockers.append(
            {
                "code": "content_not_approved",
                "message": "The exact Content Artifact version must be approved.",
            }
        )
    if not account.enabled or account.validation_status != "valid":
        blockers.append(
            {
                "code": "account_not_ready",
                "message": "The social account must be enabled and validated.",
            }
        )
    supported_content_types = cast(
        list[object], account.capabilities_json.get("supported_content_types", [])
    )
    if post.content_type not in supported_content_types:
        blockers.append(
            {
                "code": "format_unsupported",
                "message": "The selected format is not supported by this account.",
            }
        )
    if post.destination_url and not str(post.destination_url).startswith("https://"):
        blockers.append(
            {"code": "invalid_destination_url", "message": "Destination URL policy requires HTTPS."}
        )
    for media_id in post.media_ids:
        media = db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == uuid.UUID(media_id), MediaAsset.owner_id == owner.id
            )
        )
        if not media or media.status != "ready":
            blockers.append(
                {"code": "media_not_ready", "message": "Every exact Media Asset must be ready."}
            )
    if post.platform == "youtube" and not post.title:
        warnings.append({"code": "title_missing", "message": "A YouTube title is recommended."})
    return {"ready": not blockers, "warnings": warnings, "blockers": blockers}


def preview(db: Session, owner: User, post: SocialPost) -> dict[str, object]:
    account = _owned_account(db, owner, post.account_id)
    readiness = _readiness(db, owner, post, account)
    payload = {
        "post_id": str(post.id),
        "platform": post.platform,
        "account_id": str(post.account_id),
        "content_type": post.content_type,
        "artifact_id": str(post.content_artifact_id),
        "artifact_version": post.content_artifact_version,
        "media_ids": sorted(post.media_ids),
        "caption": post.caption,
        "title": post.title,
        "description": post.description,
        "hashtags": post.hashtags,
        "cta": post.cta_json,
        "destination_url": post.destination_url,
        "scheduled_at_utc": post.scheduled_at_utc.isoformat() if post.scheduled_at_utc else None,
        "timezone_name": post.timezone_name,
        "account_updated_at": account.updated_at.isoformat(),
        "readiness": readiness,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    post.preview_fingerprint = fingerprint
    db.commit()
    return {
        "post_id": post.id,
        "platform": post.platform,
        "account": account_response(account),
        "format": post.content_type,
        "caption": post.caption,
        "title": post.title,
        "description": post.description,
        "media_ids": [uuid.UUID(value) for value in post.media_ids],
        "hashtags": post.hashtags,
        "cta": post.cta_json,
        "schedule": {
            "scheduled_at_utc": post.scheduled_at_utc,
            "timezone_name": post.timezone_name,
        },
        "readiness": readiness,
        "fingerprint": fingerprint,
    }


def sync_campaign_activity(db: Session, owner: User, post: SocialPost) -> CampaignActivity | None:
    if not post.campaign_id:
        return None
    campaign = db.scalar(
        select(Campaign).where(
            Campaign.id == post.campaign_id,
            Campaign.owner_id == owner.id,
        )
    )
    if not campaign or campaign.brand_id != post.brand_id:
        raise HTTPException(422, "The Social post Campaign and Brand must match.")
    activity = db.scalar(
        select(CampaignActivity).where(
            CampaignActivity.owner_id == owner.id,
            CampaignActivity.social_post_id == post.id,
        )
    )
    timestamp = utcnow()
    local_time = post.scheduled_at_utc or timestamp
    if activity is None:
        sequence = (
            db.scalar(
                select(CampaignActivity.sequence)
                .where(CampaignActivity.campaign_id == campaign.id)
                .order_by(CampaignActivity.sequence.desc())
                .limit(1)
            )
            or 0
        )
        activity = CampaignActivity(
            owner_id=owner.id,
            campaign_id=campaign.id,
            product_id=post.product_id,
            artifact_id=post.content_artifact_id,
            artifact_version=post.content_artifact_version,
            destination_id=None,
            connector_key=f"social_fake:{post.platform}:{post.account_id}",
            requested_action="publish",
            activity_type="mock_publish",
            name=f"{post.platform.title()} Social post",
            description=post.caption or post.title or "Social publication",
            sequence=int(sequence) + 1,
            dependency_policy="success_required",
            scheduled_local_date=local_time.date(),
            scheduled_local_time=local_time.time().replace(tzinfo=None),
            timezone_name=post.timezone_name or "UTC",
            scheduled_at_utc=post.scheduled_at_utc or timestamp,
            duration_minutes=None,
            status="draft",
            readiness_status="incomplete",
            schedule_id=post.schedule_id,
            required=True,
            enabled=True,
            created_by=owner.id,
            created_at=timestamp,
            updated_at=timestamp,
            correlation_id=post.correlation_id,
            idempotency_key=f"social-activity:{post.id}",
            row_version=1,
            social_post_id=post.id,
            social_platform=post.platform,
            social_account_id=post.account_id,
            social_content_type=post.content_type,
            social_media_ids=list(post.media_ids),
            social_timezone_name=post.timezone_name,
        )
        db.add(activity)
    else:
        activity.product_id = post.product_id
        activity.artifact_id = post.content_artifact_id
        activity.social_platform = post.platform
        activity.social_account_id = post.account_id
        activity.social_content_type = post.content_type
        activity.social_media_ids = list(post.media_ids)
        activity.social_timezone_name = post.timezone_name
        activity.artifact_version = post.content_artifact_version
        activity.schedule_id = post.schedule_id
        activity.scheduled_at_utc = post.scheduled_at_utc or activity.scheduled_at_utc
        activity.scheduled_local_date = activity.scheduled_at_utc.date()
        activity.scheduled_local_time = activity.scheduled_at_utc.time().replace(tzinfo=None)
        activity.status = {
            "draft": "draft",
            "approved": "ready",
            "scheduled": "scheduled",
            "publishing": "running",
            "published": "succeeded",
            "failed": "failed",
            "cancelled": "cancelled",
        }.get(post.lifecycle_status, activity.status)
        activity.readiness_status = (
            "ready"
            if activity.status in {"ready", "scheduled", "running", "succeeded"}
            else "incomplete"
        )
        activity.updated_at = timestamp
        activity.row_version += 1
    db.flush()
    return activity


def create_post(db: Session, owner: User, data: SocialPostCreate) -> SocialPost:
    brand = db.scalar(select(Brand).where(Brand.id == data.brand_id, Brand.owner_id == owner.id))
    account = _owned_account(db, owner, data.account_id)
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == data.content_artifact_id, GeneratedArtifact.owner_id == owner.id
        )
    )
    if (
        not brand
        or not artifact
        or artifact.brand_id != data.brand_id
        or (data.product_id is not None and artifact.product_id != data.product_id)
        or artifact.version_number != data.content_artifact_version
    ):
        raise HTTPException(422, "Brand, Product, and exact Content Artifact lineage must match.")
    product_id = data.product_id or artifact.product_id
    if account.platform != data.platform:
        raise HTTPException(422, "Social account platform does not match the post platform.")
    for media_id in data.media_ids:
        if not db.scalar(
            select(MediaAsset.id).where(MediaAsset.id == media_id, MediaAsset.owner_id == owner.id)
        ):
            raise HTTPException(422, "Every Media Asset must belong to the owner.")
    existing = db.scalar(
        select(SocialPost).where(
            SocialPost.owner_id == owner.id, SocialPost.idempotency_key == data.idempotency_key
        )
    )
    if existing:
        return existing
    timestamp = utcnow()
    value = SocialPost(
        owner_id=owner.id,
        brand_id=data.brand_id,
        product_id=product_id,
        account_id=data.account_id,
        platform=data.platform,
        content_type=data.content_type,
        content_artifact_id=data.content_artifact_id,
        content_artifact_version=data.content_artifact_version,
        source_artifact_id=data.source_artifact_id,
        source_artifact_version=data.source_artifact_version,
        generation_reason=data.generation_reason,
        media_ids=[str(item) for item in data.media_ids],
        locale=data.locale,
        caption=data.caption,
        title=data.title,
        description=data.description,
        hashtags=data.hashtags,
        cta_json=data.cta,
        destination_url=_safe_url(str(data.destination_url) if data.destination_url else None),
        campaign_id=data.campaign_id,
        lifecycle_status="draft",
        correlation_id=uuid.uuid4().hex[:32],
        idempotency_key=data.idempotency_key,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(value)
    db.flush()
    sync_campaign_activity(db, owner, value)
    record_event(
        db,
        actor_id=owner.id,
        action="social.post_created",
        entity_type="social_post",
        entity_id=value.id,
        metadata={"platform": value.platform, "content_type": value.content_type},
    )
    db.commit()
    db.refresh(value)
    return value


def update_post(db: Session, owner: User, post: SocialPost, data: SocialPostUpdate) -> SocialPost:
    if post.lifecycle_status not in {"draft", "failed"}:
        raise HTTPException(409, "Only draft or failed social posts can be edited.")
    values = data.model_dump(exclude_unset=True)
    if "destination_url" in values:
        values["destination_url"] = _safe_url(
            str(values["destination_url"]) if values["destination_url"] else None
        )
    for key, item in values.items():
        setattr(post, "cta_json" if key == "cta" else key, item)
    post.updated_at = utcnow()
    post.preview_fingerprint = None
    record_event(
        db,
        actor_id=owner.id,
        action="social.post_updated",
        entity_type="social_post",
        entity_id=post.id,
    )
    db.commit()
    db.refresh(post)
    return post


def approve_post(db: Session, owner: User, post: SocialPost) -> SocialPost:
    readiness = _readiness(db, owner, post, _owned_account(db, owner, post.account_id))
    if not readiness["ready"]:
        raise HTTPException(409, {"code": "social_not_ready", "readiness": readiness})
    post.lifecycle_status = "approved"
    post.updated_at = utcnow()
    record_event(
        db,
        actor_id=owner.id,
        action="social.post_approved",
        entity_type="social_post",
        entity_id=post.id,
    )
    db.commit()
    db.refresh(post)
    return post


def _destination(db: Session, owner: User, post: SocialPost) -> PublishingDestination:
    account = _owned_account(db, owner, post.account_id)
    connector_key = f"social_fake:{post.platform}:{account.id}"
    value = db.scalar(
        select(PublishingDestination).where(
            PublishingDestination.owner_id == owner.id,
            PublishingDestination.connector_key == connector_key,
        )
    )
    if value:
        return value
    timestamp = utcnow()
    value = PublishingDestination(
        owner_id=owner.id,
        brand_id=post.brand_id,
        connector_key=connector_key,
        name=f"Social {account.display_name}",
        normalized_name=f"social-{account.id}",
        status="active",
        configuration_json={"account_id": str(account.id), "platform": post.platform},
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(value)
    db.flush()
    return value


def schedule_post(
    db: Session,
    owner: User,
    post: SocialPost,
    data: SocialScheduleRequest,
    *,
    publish_now: bool = False,
) -> SocialPost:
    if post.lifecycle_status not in {"approved", "failed", "draft"}:
        raise HTTPException(409, "Social post is not schedulable in its current state.")
    if post.preview_fingerprint != data.preview_fingerprint:
        raise HTTPException(
            409,
            {
                "code": "stale_preview",
                "message": "The preview is stale; generate a new preview before confirmation.",
            },
        )
    readiness = _readiness(db, owner, post, _owned_account(db, owner, post.account_id))
    if not readiness["ready"]:
        raise HTTPException(409, {"code": "social_not_ready", "readiness": readiness})
    local_scheduled_at = data.local_scheduled_at
    if local_scheduled_at.tzinfo is not None:
        try:
            local_scheduled_at = local_scheduled_at.astimezone(
                ZoneInfo(data.timezone_name)
            ).replace(tzinfo=None)
        except Exception as exc:
            raise HTTPException(422, "Invalid schedule timezone.") from exc
    try:
        scheduled_at_utc = local_to_utc(
            local_scheduled_at,
            data.timezone_name,
            data.fold,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    post.lifecycle_status = "scheduled"
    post.timezone_name = data.timezone_name
    post.scheduled_at_utc = scheduled_at_utc
    post.updated_at = utcnow()
    destination = _destination(db, owner, post)
    schedule = create_schedule(
        db,
        owner,
        ScheduleCreate(
            name=f"Social {post.platform} {post.id}",
            artifact_id=post.content_artifact_id,
            destination_id=destination.id,
            requested_action="publish",
            local_scheduled_at=local_scheduled_at,
            timezone_name=data.timezone_name,
            fold=data.fold,
            context_json={
                "social_post_id": str(post.id),
                "platform": post.platform,
                "format": post.content_type,
                "video_generation_id": (
                    str(post.video_generation_id) if post.video_generation_id else None
                ),
                "video_output_id": str(post.video_output_id) if post.video_output_id else None,
                "video_media_id": str(post.video_media_id) if post.video_media_id else None,
                "video_version": post.video_version,
                "metadata_artifact_id": (
                    str(post.metadata_artifact_id) if post.metadata_artifact_id else None
                ),
                "metadata_artifact_version": post.metadata_artifact_version,
                "thumbnail_output_id": (
                    str(post.thumbnail_output_id) if post.thumbnail_output_id else None
                ),
                "thumbnail_media_id": (
                    str(post.thumbnail_media_id) if post.thumbnail_media_id else None
                ),
                "thumbnail_version": post.thumbnail_version,
                "caption_track_id": str(post.caption_track_id) if post.caption_track_id else None,
                "caption_version": post.caption_version,
            },
        ),
    )
    post.schedule_id = schedule.id
    sync_campaign_activity(db, owner, post)
    record_event(
        db,
        actor_id=owner.id,
        action="social.post_scheduled",
        entity_type="social_post",
        entity_id=post.id,
        metadata={
            "platform": post.platform,
            "schedule_id": str(schedule.id),
            "publish_now": publish_now,
        },
    )
    db.commit()
    db.refresh(post)
    return post


def metrics(db: Session, owner: User, post: SocialPost) -> list[SocialMetric]:
    account = _owned_account(db, owner, post.account_id)
    if not post.remote_publication_id:
        return list(
            db.scalars(
                select(SocialMetric)
                .where(SocialMetric.post_id == post.id)
                .order_by(SocialMetric.metric_key)
            )
        )
    values = connector_for(post.platform, account.capabilities_json).fetch_metrics(
        {"remote_account_id": account.remote_account_id}, post.remote_publication_id
    )
    supported = {
        "instagram": {"impressions", "reach", "likes", "comments", "shares"},
        "facebook": {"impressions", "reach", "likes", "comments", "shares", "clicks"},
        "youtube": {"views", "likes", "comments", "shares"},
    }[post.platform]
    timestamp = utcnow()
    for key in set(values) | {
        "impressions",
        "reach",
        "likes",
        "comments",
        "shares",
        "clicks",
        "views",
    }:
        row = db.scalar(
            select(SocialMetric).where(
                SocialMetric.post_id == post.id, SocialMetric.metric_key == key
            )
        )
        if not row:
            row = SocialMetric(
                owner_id=owner.id,
                post_id=post.id,
                product_id=post.product_id,
                platform=post.platform,
                content_type=post.content_type,
                video_output_id=post.video_output_id,
                video_media_id=post.video_media_id,
                metric_key=key,
                created_at=timestamp,
            )
            db.add(row)
        if key in supported and key in values:
            row.value = values[key]
            row.availability = "available"
            row.source = "synthetic_test_data"
        else:
            row.value = None
            row.availability = "not_supported"
            row.source = "connector_capability"
        row.observed_at = timestamp
    db.commit()
    return list(
        db.scalars(
            select(SocialMetric)
            .where(SocialMetric.post_id == post.id)
            .order_by(SocialMetric.metric_key)
        )
    )
