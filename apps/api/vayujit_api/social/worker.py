from __future__ import annotations

import uuid
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.publishing.models import PublishingJob
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.social.connectors import SocialConnectorFailure, connector_for
from vayujit_api.social.models import SocialAccount, SocialPost
from vayujit_api.social.service import sync_campaign_activity


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
        post.failure_code = "social.invalid_credentials"
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
        "media_ids": post.media_ids,
        "caption": post.caption,
        "title": post.title,
        "description": post.description,
        "hashtags": post.hashtags,
        "cta": post.cta_json,
        "destination_url": post.destination_url,
    }
    try:
        result = connector.publish_post(
            {"remote_account_id": account.remote_account_id}, payload, post.idempotency_key
        )
    except SocialConnectorFailure as error:
        post.lifecycle_status = "failed"
        post.failure_code = error.code
        post.safe_failure_message = error.safe_message
        if error.ambiguous and error.remote_publication_id:
            post.remote_publication_id = error.remote_publication_id
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
            metadata={
                "code": error.code,
                "retryable": error.retryable,
                "ambiguous": error.ambiguous,
                "remote_publication_id": bool(error.remote_publication_id),
            },
        )
        return SocialJobResult(
            status="failed",
            retryable=error.retryable,
            error_code=error.code,
            safe_message=error.safe_message,
        )
    except Exception:
        post.lifecycle_status = "failed"
        post.failure_code = "social.worker_error"
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
            error_code="social.worker_error",
            safe_message=post.safe_failure_message,
        )
    post.remote_publication_id = str(result["remote_publication_id"])
    # Persist the remote identity before local finalization so a lease-loss restart
    # can finalize from the durable checkpoint without publishing again.
    post.failure_code = "social.remote_checkpoint"
    post.safe_failure_message = (
        "Remote publication checkpoint persisted; local finalization pending."
    )
    post.updated_at = utcnow()
    db.commit()
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
