from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.media.models import MediaAsset
from vayujit_api.publishing.models import PublishingJob
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.social.connectors import SocialConnectorFailure, connector_for
from vayujit_api.social.models import SocialAccount, SocialPost
from vayujit_api.social.service import sync_campaign_activity
from vayujit_api.video.models import VideoGeneration, VideoOutput


def _video_error_code(post: SocialPost, code: str) -> str:
    if post.video_generation_id is None:
        return code
    return {
        "social.invalid_credentials": "social.video.invalid_credentials",
        "social.account_disabled": "social.video.account_disabled",
        "social.policy_rejected": "social.video.policy_rejection",
        "social.throttled": "social.video.throttled",
        "social.timeout": "social.video.timeout",
        "social.provider_unavailable": "social.video.connector_unavailable",
        "social.ambiguous_result": "social.video.ambiguous_publication",
        "social.remote_missing": "social.video.ambiguous_publication",
        "social.worker_error": "social.video.connector_unavailable",
    }.get(code, code if code.startswith("social.video.") else "social.video.connector_unavailable")


def _video_not_ready(db: Session, post: SocialPost) -> str | None:
    if post.video_generation_id is None:
        return None
    generation = db.get(VideoGeneration, post.video_generation_id)
    output = db.get(VideoOutput, post.video_output_id) if post.video_output_id else None
    media = db.get(MediaAsset, post.video_media_id) if post.video_media_id else None
    if generation is None or output is None or media is None:
        return "social.video.video_not_ready"
    if generation.status != "succeeded" or output.status != "approved" or media.status != "ready":
        return "social.video.video_not_ready"
    if output.generation_id != generation.id or output.media_id != media.id:
        return "social.video.stale_video"
    return None


class SocialJobResult:
    def __init__(
        self,
        *,
        status: str,
        retryable: bool = False,
        error_code: str | None = None,
        safe_message: str | None = None,
    ) -> None:
        self.status = status
        self.retryable = retryable
        self.error_code = error_code
        self.safe_message = safe_message


def post_for_job(db: Session, job: PublishingJob) -> SocialPost | None:
    post_id: uuid.UUID | None = None
    if job.idempotency_key.startswith("social-post:"):
        with suppress(ValueError):
            post_id = uuid.UUID(job.idempotency_key.split(":", 1)[1])
    if post_id:
        return db.scalar(
            select(SocialPost).where(SocialPost.id == post_id, SocialPost.owner_id == job.owner_id)
        )
    return None


def execute_social_job(db: Session, job: PublishingJob) -> SocialJobResult:
    post = post_for_job(db, job)
    if not post and job.schedule_id:
        post = db.scalar(
            select(SocialPost).where(
                SocialPost.schedule_id == job.schedule_id, SocialPost.owner_id == job.owner_id
            )
        )
    if not post:
        return SocialJobResult(
            status="failed",
            error_code="social_post_missing",
            safe_message="The social post could not be found safely.",
        )
    account = db.get(SocialAccount, post.account_id)
    if not account or account.owner_id != job.owner_id or not account.enabled:
        post.lifecycle_status = "failed"
        post.failure_code = _video_error_code(post, "social.account_disabled")
        post.safe_failure_message = "The social account is disabled or unavailable."
        post.updated_at = utcnow()
        if post.campaign_id:
            owner = db.get(User, job.owner_id)
            if owner:
                sync_campaign_activity(db, owner, post)
        db.commit()
        return SocialJobResult(
            status="failed", error_code=post.failure_code, safe_message=post.safe_failure_message
        )
    if account.validation_status != "valid":
        post.lifecycle_status = "failed"
        post.failure_code = _video_error_code(post, "social.invalid_credentials")
        post.safe_failure_message = "The social account credentials are not validated."
        post.updated_at = utcnow()
        db.commit()
        return SocialJobResult(
            status="failed", error_code=post.failure_code, safe_message=post.safe_failure_message
        )
    video_failure = _video_not_ready(db, post)
    if video_failure:
        post.lifecycle_status = "failed"
        post.failure_code = video_failure
        post.safe_failure_message = "The approved Video is no longer ready for publication."
        post.updated_at = utcnow()
        db.commit()
        return SocialJobResult(
            status="failed", error_code=post.failure_code, safe_message=post.safe_failure_message
        )
    if post.remote_publication_id:
        post.lifecycle_status = "published"
        post.failure_code = None
        post.safe_failure_message = None
        post.updated_at = utcnow()
        if post.campaign_id:
            owner = db.get(User, job.owner_id)
            if owner:
                sync_campaign_activity(db, owner, post)
        already_audited = db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.actor_id == job.owner_id,
                AuditEvent.action == "social.post_published",
                AuditEvent.entity_type == "social_post",
                AuditEvent.entity_id == post.id,
            )
        )
        if not already_audited:
            record_event(
                db,
                actor_id=job.owner_id,
                action="social.post_published",
                entity_type="social_post",
                entity_id=post.id,
                metadata={"platform": post.platform, "synthetic_test_data": True},
            )
        db.commit()
        return SocialJobResult(status="succeeded")
    post.lifecycle_status = "publishing"
    post.updated_at = utcnow()
    db.flush()
    connector = connector_for(post.platform, account.capabilities_json)
    payload = {
        "platform": post.platform,
        "content_type": post.content_type,
        "artifact_id": str(post.content_artifact_id),
        "artifact_version": post.content_artifact_version,
        "video_generation_id": str(post.video_generation_id) if post.video_generation_id else None,
        "video_output_id": str(post.video_output_id) if post.video_output_id else None,
        "video_media_id": str(post.video_media_id) if post.video_media_id else None,
        "video_version": post.video_version,
        "metadata_artifact_id": (
            str(post.metadata_artifact_id) if post.metadata_artifact_id else None
        ),
        "metadata_artifact_version": post.metadata_artifact_version,
        "title_artifact_id": str(post.title_artifact_id) if post.title_artifact_id else None,
        "title_artifact_version": post.title_artifact_version,
        "description_artifact_id": (
            str(post.description_artifact_id) if post.description_artifact_id else None
        ),
        "description_artifact_version": post.description_artifact_version,
        "copy_artifact_id": str(post.copy_artifact_id) if post.copy_artifact_id else None,
        "copy_artifact_version": post.copy_artifact_version,
        "cta_artifact_id": str(post.cta_artifact_id) if post.cta_artifact_id else None,
        "cta_artifact_version": post.cta_artifact_version,
        "tags_artifact_id": str(post.tags_artifact_id) if post.tags_artifact_id else None,
        "tags_artifact_version": post.tags_artifact_version,
        "thumbnail_output_id": str(post.thumbnail_output_id) if post.thumbnail_output_id else None,
        "thumbnail_media_id": str(post.thumbnail_media_id) if post.thumbnail_media_id else None,
        "thumbnail_version": post.thumbnail_version,
        "caption_track_id": str(post.caption_track_id) if post.caption_track_id else None,
        "caption_version": post.caption_version,
        "media_ids": post.media_ids,
        "caption": post.caption,
        "title": post.title,
        "description": post.description,
        "hashtags": post.hashtags,
        "cta": post.cta_json,
        "destination_url": post.destination_url,
    }
    operation_fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    try:
        result = connector.publish_post(
            {"remote_account_id": account.remote_account_id}, payload, post.idempotency_key
        )
    except SocialConnectorFailure as error:
        normalized_code = _video_error_code(post, error.code)
        post.lifecycle_status = "failed"
        post.failure_code = normalized_code
        post.safe_failure_message = error.safe_message
        if error.ambiguous and error.remote_publication_id:
            post.remote_publication_id = error.remote_publication_id
            post.remote_checkpoint_json = {
                "connector_request_fingerprint": operation_fingerprint,
                "remote_publication_id": error.remote_publication_id,
                "state": "ambiguous",
                "classification": "remote_succeeded_unknown_local_state",
                "platform": post.platform,
                "format": post.content_type,
                "social_post_id": str(post.id),
                "video_output_id": str(post.video_output_id) if post.video_output_id else None,
                "video_media_id": str(post.video_media_id) if post.video_media_id else None,
                "video_version": post.video_version,
                "completed_at": utcnow().isoformat(),
            }
        post.updated_at = utcnow()
        if post.campaign_id:
            owner = db.get(User, job.owner_id)
            if owner:
                sync_campaign_activity(db, owner, post)
        db.commit()
        if error.ambiguous:
            record_event(
                db,
                actor_id=job.owner_id,
                action="social.post_ambiguous",
                entity_type="social_post",
                entity_id=post.id,
                metadata={"remote_publication_id": error.remote_publication_id},
            )
            db.commit()
        record_event(
            db,
            actor_id=job.owner_id,
            action="social.post_failed",
            entity_type="social_post",
            entity_id=post.id,
            metadata={
                "code": normalized_code,
                "retryable": error.retryable,
                "ambiguous": error.ambiguous,
                "remote_publication_id": bool(error.remote_publication_id),
            },
        )
        return SocialJobResult(
            status="failed",
            retryable=error.retryable,
            error_code=normalized_code,
            safe_message=error.safe_message,
        )
    except Exception:
        post.lifecycle_status = "failed"
        post.failure_code = _video_error_code(post, "social.worker_error")
        post.safe_failure_message = (
            "The local social worker stopped before confirming publication. "
            "Reconcile or retry safely."
        )
        post.updated_at = utcnow()
        if post.campaign_id:
            owner = db.get(User, job.owner_id)
            if owner:
                sync_campaign_activity(db, owner, post)
        db.commit()
        record_event(
            db,
            actor_id=job.owner_id,
            action="social.post_failed",
            entity_type="social_post",
            entity_id=post.id,
            metadata={"code": "social.worker_error", "retryable": True},
        )
        return SocialJobResult(
            status="failed",
            retryable=True,
            error_code=_video_error_code(post, "social.worker_error"),
            safe_message=post.safe_failure_message,
        )
    post.remote_publication_id = str(result["remote_publication_id"])
    post.remote_checkpoint_json = {
        "connector_request_fingerprint": operation_fingerprint,
        "remote_publication_id": post.remote_publication_id,
        "state": "remote_succeeded",
        "classification": "remote_success_local_finalization_pending",
        "platform": post.platform,
        "format": post.content_type,
        "social_post_id": str(post.id),
        "video_output_id": str(post.video_output_id) if post.video_output_id else None,
        "video_media_id": str(post.video_media_id) if post.video_media_id else None,
        "video_version": post.video_version,
        "completed_at": utcnow().isoformat(),
    }
    post.failure_code = "social.remote_checkpoint"
    post.safe_failure_message = (
        "Remote publication checkpoint persisted; local finalization pending."
    )
    post.updated_at = utcnow()
    db.commit()
    record_event(
        db,
        actor_id=job.owner_id,
        action="social.post_checkpointed",
        entity_type="social_post",
        entity_id=post.id,
        metadata={"state": "remote_succeeded", "remote_publication_id": post.remote_publication_id},
    )
    post.lifecycle_status = "published" if result["status"] == "published" else "publishing"
    post.failure_code = None
    post.safe_failure_message = None
    post.updated_at = utcnow()
    if post.campaign_id:
        owner = db.get(User, job.owner_id)
        if owner:
            sync_campaign_activity(db, owner, post)
    record_event(
        db,
        actor_id=job.owner_id,
        action="social.post_published",
        entity_type="social_post",
        entity_id=post.id,
        metadata={"platform": post.platform, "synthetic_test_data": True},
    )
    db.commit()
    return SocialJobResult(status="succeeded")
