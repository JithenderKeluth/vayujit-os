from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import HttpUrl, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.social.connectors import connector_for, deterministic_remote_id
from vayujit_api.social.models import SocialAccount, SocialMetric, SocialPost
from vayujit_api.social.schemas import (
    SocialAccountCreate,
    SocialAccountResponse,
    SocialAccountUpdate,
    SocialBulkRequest,
    SocialBulkScheduleRequest,
    SocialHistoryItem,
    SocialMetricResponse,
    SocialPostCreate,
    SocialPostResponse,
    SocialPostUpdate,
    SocialPreviewResponse,
    SocialRecoveryActionRequest,
    SocialRecoveryActionResult,
    SocialRecoveryProjection,
    SocialRepurposeRequest,
    SocialScheduleRequest,
)
from vayujit_api.social.service import (
    account_response,
    approve_post,
    create_account,
    create_post,
    metrics,
    preview,
    schedule_post,
    update_post,
    validate_account,
)

router = APIRouter(prefix="/api/v1/social", tags=["social"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/platforms")
def platforms() -> list[dict[str, object]]:
    return [
        {
            "key": "instagram",
            "name": "Instagram",
            "connector": "social_fake",
            "status": "fake_certified",
            "formats": ["instagram_post", "instagram_story", "instagram_reel"],
        },
        {
            "key": "facebook",
            "name": "Facebook",
            "connector": "social_fake",
            "status": "fake_certified",
            "formats": ["facebook_post", "facebook_story", "facebook_reel"],
        },
        {
            "key": "youtube",
            "name": "YouTube",
            "connector": "social_fake",
            "status": "fake_certified",
            "formats": [
                "youtube_video",
                "youtube_short",
                "youtube_community_post",
                "youtube_thumbnail",
            ],
        },
    ]


@router.get("/accounts", response_model=list[SocialAccountResponse])
def account_list(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        account_response(value)
        for value in db.scalars(
            select(SocialAccount)
            .where(SocialAccount.owner_id == owner.id)
            .order_by(SocialAccount.created_at.desc())
        )
    ]


@router.post("/accounts", response_model=SocialAccountResponse, status_code=201)
def account_create(data: SocialAccountCreate, db: DB, owner: Owner) -> dict[str, object]:
    try:
        return account_response(create_account(db, owner, data))
    except Exception as error:
        db.rollback()
        if "uq_social_account_remote" in str(error):
            raise HTTPException(409, "This social account is already configured.") from error
        raise


@router.post("/accounts/{account_id}/validate", response_model=SocialAccountResponse)
def account_validate(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return account_response(
        validate_account(
            db,
            owner,
            db.scalar(
                select(SocialAccount).where(
                    SocialAccount.id == account_id, SocialAccount.owner_id == owner.id
                )
            )
            or (_ for _ in ()).throw(HTTPException(404, "Social account not found.")),
        )
    )


@router.patch("/accounts/{account_id}", response_model=SocialAccountResponse)
def account_update(
    account_id: uuid.UUID, data: SocialAccountUpdate, db: DB, owner: Owner
) -> dict[str, object]:
    value = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == account_id, SocialAccount.owner_id == owner.id
        )
    )
    if not value:
        raise HTTPException(404, "Social account not found.")
    if data.display_name is not None:
        value.display_name = data.display_name.strip()
    if data.capabilities is not None:
        value.capabilities_json = {**value.capabilities_json, **data.capabilities}
    if data.credentials is not None:
        import json

        from vayujit_api.ai.credentials import encrypt_credential

        try:
            value.encrypted_credentials = encrypt_credential(
                json.dumps(data.credentials, sort_keys=True),
                get_settings().credential_encryption_key,
            )
        except Exception:
            value.encrypted_credentials = (
                "local-hash:"
                + __import__("hashlib")
                .sha256(json.dumps(data.credentials, sort_keys=True).encode())
                .hexdigest()
            )
        value.credential_version += 1
        value.validation_status = "unknown"
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    record_event(
        db,
        actor_id=owner.id,
        action="social.account_updated",
        entity_type="social_account",
        entity_id=value.id,
        metadata={"credential_replaced": data.credentials is not None},
    )
    db.commit()
    db.refresh(value)
    return account_response(value)


@router.post("/accounts/{account_id}/archive", response_model=SocialAccountResponse)
def account_archive(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == account_id, SocialAccount.owner_id == owner.id
        )
    )
    if not value:
        raise HTTPException(404, "Social account not found.")
    value.enabled = False
    value.capabilities_json = {**value.capabilities_json, "archived": True}
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    record_event(
        db,
        actor_id=owner.id,
        action="social.account_archived",
        entity_type="social_account",
        entity_id=value.id,
    )
    db.commit()
    db.refresh(value)
    return account_response(value)


@router.post("/accounts/{account_id}/disable", response_model=SocialAccountResponse)
def account_disable(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == account_id, SocialAccount.owner_id == owner.id
        )
    )
    if not value:
        raise HTTPException(404, "Social account not found.")
    value.enabled = False
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
    return account_response(value)


@router.post("/accounts/{account_id}/enable", response_model=SocialAccountResponse)
def account_enable(account_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == account_id, SocialAccount.owner_id == owner.id
        )
    )
    if not value:
        raise HTTPException(404, "Social account not found.")
    value.enabled = True
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
    return account_response(value)


@router.get("/posts", response_model=list[SocialPostResponse])
def post_list(
    db: DB, owner: Owner, platform: str | None = None, status: str | None = None
) -> list[SocialPost]:
    filters = [SocialPost.owner_id == owner.id]
    if platform:
        filters.append(SocialPost.platform == platform)
    if status:
        filters.append(SocialPost.lifecycle_status == status)
    return list(
        db.scalars(select(SocialPost).where(*filters).order_by(SocialPost.created_at.desc()))
    )


@router.post("/posts", response_model=SocialPostResponse, status_code=201)
def post_create(data: SocialPostCreate, db: DB, owner: Owner) -> SocialPost:
    try:
        return create_post(db, owner, data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/posts/{post_id}", response_model=SocialPostResponse)
def post_get(post_id: uuid.UUID, db: DB, owner: Owner) -> SocialPost:
    value = db.scalar(
        select(SocialPost).where(SocialPost.id == post_id, SocialPost.owner_id == owner.id)
    )
    if not value:
        raise HTTPException(404, "Social post not found.")
    return value


@router.patch("/posts/{post_id}", response_model=SocialPostResponse)
def post_patch(post_id: uuid.UUID, data: SocialPostUpdate, db: DB, owner: Owner) -> SocialPost:
    value = post_get(post_id, db, owner)
    try:
        return update_post(db, owner, value, data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/posts/{post_id}/preview", response_model=SocialPreviewResponse)
def post_preview(post_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return preview(db, owner, post_get(post_id, db, owner))


@router.post("/posts/{post_id}/approve", response_model=SocialPostResponse)
def post_approve(post_id: uuid.UUID, db: DB, owner: Owner) -> SocialPost:
    return approve_post(db, owner, post_get(post_id, db, owner))


@router.post("/posts/{post_id}/schedule", response_model=SocialPostResponse)
def post_schedule(
    post_id: uuid.UUID, data: SocialScheduleRequest, db: DB, owner: Owner
) -> SocialPost:
    return schedule_post(db, owner, post_get(post_id, db, owner), data)


@router.post("/posts/{post_id}/publish-now", response_model=SocialPostResponse)
def post_publish_now(
    post_id: uuid.UUID, data: SocialScheduleRequest, db: DB, owner: Owner
) -> SocialPost:
    return schedule_post(db, owner, post_get(post_id, db, owner), data, publish_now=True)


@router.post("/posts/{post_id}/reconcile", response_model=SocialPostResponse)
def post_reconcile(post_id: uuid.UUID, db: DB, owner: Owner) -> SocialPost:
    value = post_get(post_id, db, owner)
    if not value.remote_publication_id:
        raise HTTPException(409, "This social post has no remote publication to reconcile.")
    value.lifecycle_status = "published"
    value.failure_code = None
    value.safe_failure_message = None
    value.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    db.commit()
    return value


@router.get("/posts/{post_id}/metrics", response_model=list[SocialMetricResponse])
def post_metrics(post_id: uuid.UUID, db: DB, owner: Owner) -> list[SocialMetric]:
    return metrics(db, owner, post_get(post_id, db, owner))


@router.get("/analytics/summary")
def analytics_summary(
    db: DB,
    owner: Owner,
    platform: str | None = None,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    content_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, object]:
    filters = [SocialPost.owner_id == owner.id]
    if platform:
        filters.append(SocialPost.platform == platform)
    if brand_id:
        filters.append(SocialPost.brand_id == brand_id)
    if product_id:
        filters.append(SocialPost.product_id == product_id)
    if campaign_id:
        filters.append(SocialPost.campaign_id == campaign_id)
    if content_type:
        filters.append(SocialPost.content_type == content_type)
    if start:
        filters.append(SocialPost.created_at >= start)
    if end:
        filters.append(SocialPost.created_at < end)
    rows = list(db.scalars(select(SocialPost).where(*filters)))
    metric_rows = list(db.scalars(select(SocialMetric).where(SocialMetric.owner_id == owner.id)))
    totals: dict[str, float] = {}
    for row in metric_rows:
        if row.availability == "available" and row.value is not None:
            totals[row.metric_key] = totals.get(row.metric_key, 0.0) + row.value
    return {
        "publications": len(rows),
        "published": sum(row.lifecycle_status == "published" for row in rows),
        "failed": sum(row.lifecycle_status == "failed" for row in rows),
        "scheduled": sum(row.lifecycle_status == "scheduled" for row in rows),
        "metrics": totals,
        "synthetic": any(row.source == "synthetic_test_data" for row in metric_rows),
    }


@router.get("/recovery", response_model=list[SocialRecoveryProjection])
def recovery_projection(db: DB, owner: Owner) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(SocialPost)
            .where(
                SocialPost.owner_id == owner.id,
                SocialPost.lifecycle_status.in_(["failed", "publishing"]),
            )
            .order_by(SocialPost.updated_at.desc())
        )
    )
    return [
        {
            "post_id": row.id,
            "platform": row.platform,
            "content_type": row.content_type,
            "lifecycle_status": row.lifecycle_status,
            "failure_code": row.failure_code,
            "safe_failure_message": row.safe_failure_message,
            "remote_publication_id": row.remote_publication_id,
            "available_actions": (
                ["reconcile", "cancel"]
                if row.remote_publication_id
                else ["retry", "reconcile", "cancel"]
            ),
        }
        for row in rows
    ]


@router.post("/recovery/actions", response_model=dict[str, object])
def recovery_action(data: SocialRecoveryActionRequest, db: DB, owner: Owner) -> dict[str, object]:
    post = db.scalar(
        select(SocialPost).where(SocialPost.id == data.post_id, SocialPost.owner_id == owner.id)
    )
    if not post:
        raise HTTPException(404, "Social post not found.")
    if not data.confirm:
        raise HTTPException(422, "Confirmation is required for a recovery action.")
    if data.idempotency_key:
        previous = db.scalars(
            select(AuditEvent).where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.entity_type == "social_post",
                AuditEvent.entity_id == post.id,
                AuditEvent.action == f"social.post_{data.action}",
            )
        )
        for event in previous:
            metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
            if metadata.get("idempotency_key") == data.idempotency_key:
                return {
                    "result": SocialRecoveryActionResult(
                        post_id=post.id,
                        action=data.action,
                        status=post.lifecycle_status,
                        idempotent_reuse=True,
                        safe_message="The recovery action was already applied safely.",
                        remote_publication_id=post.remote_publication_id,
                    ).model_dump(mode="json")
                }
    if data.action == "retry":
        if post.lifecycle_status in {"approved", "scheduled"} and not post.failure_code:
            return {
                "result": SocialRecoveryActionResult(
                    post_id=post.id,
                    action=data.action,
                    status=post.lifecycle_status,
                    idempotent_reuse=True,
                    safe_message="The social post is already ready for retry.",
                ).model_dump(mode="json")
            }
        if post.remote_publication_id:
            raise HTTPException(
                409, "This post has an ambiguous remote result; reconcile it before retrying."
            )
        post.lifecycle_status = "scheduled" if post.schedule_id else "approved"
        post.failure_code = None
        post.safe_failure_message = None
        message = "The social post was safely requeued for retry."
    elif data.action == "reconcile":
        account = db.scalar(
            select(SocialAccount).where(
                SocialAccount.id == post.account_id, SocialAccount.owner_id == owner.id
            )
        )
        if not account:
            raise HTTPException(404, "Social account not found.")
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
        remote_id = post.remote_publication_id or deterministic_remote_id(
            post.platform,
            {"remote_account_id": account.remote_account_id},
            payload,
            post.idempotency_key,
        )
        try:
            remote = connector_for(
                post.platform, account.capabilities_json
            ).fetch_publication_status({"remote_account_id": account.remote_account_id}, remote_id)
        except Exception as error:
            from vayujit_api.social.connectors import SocialConnectorFailure

            if not isinstance(error, SocialConnectorFailure):
                raise
            post.lifecycle_status = "failed"
            post.failure_code = error.code
            post.safe_failure_message = error.safe_message
            if error.code == "social.remote_missing":
                post.remote_publication_id = None
            message = "The remote publication was not found; retry is available safely."
        else:
            post.remote_publication_id = remote_id
            post.lifecycle_status = (
                "published" if remote.get("status") == "published" else "publishing"
            )
            post.failure_code = None
            post.safe_failure_message = None
            message = "The social publication was reconciled safely."
    else:
        if post.lifecycle_status == "cancelled":
            return {
                "result": SocialRecoveryActionResult(
                    post_id=post.id,
                    action=data.action,
                    status="cancelled",
                    idempotent_reuse=True,
                    safe_message="The social post is already cancelled.",
                ).model_dump(mode="json")
            }
        post.lifecycle_status = "cancelled"
        post.failure_code = "social.cancelled"
        post.safe_failure_message = "The social post was cancelled by the owner."
        message = "The social post was cancelled safely."
    post.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    record_event(
        db,
        actor_id=owner.id,
        action=f"social.post_{data.action}",
        entity_type="social_post",
        entity_id=post.id,
        metadata={"idempotency_key": data.idempotency_key} if data.idempotency_key else {},
    )
    db.commit()
    result = SocialRecoveryActionResult(
        post_id=post.id,
        action=data.action,
        status=post.lifecycle_status,
        safe_message=message,
        remote_publication_id=post.remote_publication_id,
    )
    return {"result": result.model_dump(mode="json")}


@router.get("/posts/{post_id}/history", response_model=list[SocialHistoryItem])
def post_history(post_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    post_get(post_id, db, owner)
    rows = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.actor_id == owner.id,
            AuditEvent.entity_type == "social_post",
            AuditEvent.entity_id == post_id,
        )
        .order_by(AuditEvent.occurred_at.desc())
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "occurred_at": row.occurred_at,
            "metadata": row.metadata_json,
        }
        for row in rows
    ]


@router.post("/posts/{post_id}/repurpose", response_model=SocialPostResponse, status_code=201)
def repurpose_post(
    post_id: uuid.UUID, data: SocialRepurposeRequest, db: DB, owner: Owner
) -> SocialPost:
    source = post_get(post_id, db, owner)
    account = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == data.account_id, SocialAccount.owner_id == owner.id
        )
    )
    if not account:
        raise HTTPException(404, "Social account not found.")
    supported = account.capabilities_json.get("supported_content_types", [])
    if data.content_type not in (supported if isinstance(supported, list) else []):
        raise HTTPException(422, "The selected format is not supported by this account.")
    created = SocialPostCreate(
        brand_id=source.brand_id,
        product_id=source.product_id,
        account_id=account.id,
        platform=cast(Any, account.platform),
        content_type=data.content_type,
        content_artifact_id=source.content_artifact_id,
        content_artifact_version=source.content_artifact_version,
        source_artifact_id=source.content_artifact_id,
        source_artifact_version=source.content_artifact_version,
        generation_reason="social_repurpose",
        media_ids=[uuid.UUID(value) for value in source.media_ids],
        locale=source.locale,
        caption=source.caption,
        title=source.title,
        description=source.description,
        hashtags=source.hashtags,
        cta=source.cta_json,
        destination_url=(
            TypeAdapter(HttpUrl).validate_python(source.destination_url)
            if source.destination_url
            else None
        ),
        campaign_id=source.campaign_id,
        idempotency_key=data.idempotency_key,
    )
    return create_post(db, owner, created)


@router.post("/bulk", response_model=list[SocialPostResponse])
def bulk_social(data: SocialBulkRequest, db: DB, owner: Owner) -> list[SocialPost]:
    prior = db.scalars(
        select(AuditEvent).where(
            AuditEvent.actor_id == owner.id,
            AuditEvent.action == "social.bulk",
        )
    )
    for event in prior:
        metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
        if metadata.get("idempotency_key") == data.idempotency_key:
            return [post_get(post_id, db, owner) for post_id in data.post_ids]
    if data.action != "approve":
        raise HTTPException(422, "Bulk Social approval is the only synchronous bulk action.")
    rows: list[SocialPost] = []
    for post_id in data.post_ids:
        post = post_get(post_id, db, owner)
        if post.lifecycle_status in {"draft", "failed"}:
            rows.append(approve_post(db, owner, post))
        else:
            rows.append(post)
    record_event(
        db,
        actor_id=owner.id,
        action="social.bulk",
        entity_type="social_bulk",
        entity_id=uuid.uuid4(),
        metadata={
            "idempotency_key": data.idempotency_key,
            "post_ids": [str(item) for item in data.post_ids],
        },
    )
    db.commit()
    return rows


@router.post("/bulk/schedule", response_model=list[SocialPostResponse])
def bulk_schedule(data: SocialBulkScheduleRequest, db: DB, owner: Owner) -> list[SocialPost]:
    prior = db.scalars(
        select(AuditEvent).where(
            AuditEvent.actor_id == owner.id,
            AuditEvent.action == "social.bulk_scheduled",
        )
    )
    for event in prior:
        metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
        if metadata.get("idempotency_key") == data.idempotency_key:
            post_ids = metadata.get("post_ids")
            if isinstance(post_ids, list) and all(isinstance(value, str) for value in post_ids):
                ids = [uuid.UUID(value) for value in post_ids]
                return [post_get(post_id, db, owner) for post_id in ids]
    scheduled: list[SocialPost] = []
    seen: set[uuid.UUID] = set()
    for item in data.items:
        if item.post_id in seen:
            continue
        seen.add(item.post_id)
        post = post_get(item.post_id, db, owner)
        scheduled.append(
            schedule_post(
                db,
                owner,
                post,
                SocialScheduleRequest(
                    preview_fingerprint=item.preview_fingerprint,
                    local_scheduled_at=item.local_scheduled_at,
                    timezone_name=item.timezone_name,
                    fold=item.fold,
                ),
            )
        )
    record_event(
        db,
        actor_id=owner.id,
        action="social.bulk_scheduled",
        entity_type="social_bulk",
        entity_id=uuid.uuid4(),
        metadata={
            "idempotency_key": data.idempotency_key,
            "post_ids": [str(item.post_id) for item in data.items],
        },
    )
    db.commit()
    return scheduled


@router.get("/calendar")
def social_calendar(
    db: DB,
    owner: Owner,
    start: str | None = None,
    end: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    channel: str | None = None,
) -> list[dict[str, object]]:
    filters = [SocialPost.owner_id == owner.id, SocialPost.scheduled_at_utc.is_not(None)]
    if platform:
        filters.append(SocialPost.platform == platform)
    if channel:
        filters.append(SocialPost.platform == channel)
    if status:
        filters.append(SocialPost.lifecycle_status == status)
    if brand_id:
        filters.append(SocialPost.brand_id == brand_id)
    if product_id:
        filters.append(SocialPost.product_id == product_id)
    if campaign_id:
        filters.append(SocialPost.campaign_id == campaign_id)
    if start:
        try:
            filters.append(SocialPost.scheduled_at_utc >= datetime.fromisoformat(start))
        except ValueError as exc:
            raise HTTPException(422, "Invalid calendar start datetime.") from exc
    if end:
        try:
            filters.append(SocialPost.scheduled_at_utc < datetime.fromisoformat(end))
        except ValueError as exc:
            raise HTTPException(422, "Invalid calendar end datetime.") from exc
    rows = list(
        db.scalars(select(SocialPost).where(*filters).order_by(SocialPost.scheduled_at_utc))
    )
    return [
        {
            "id": row.id,
            "type": "social",
            "platform": row.platform,
            "channel": row.platform,
            "content_type": row.content_type,
            "status": row.lifecycle_status,
            "scheduled_at_utc": row.scheduled_at_utc,
            "timezone": row.timezone_name,
            "brand_id": row.brand_id,
            "product_id": row.product_id,
            "campaign_id": row.campaign_id,
            "account_id": row.account_id,
            "artifact_id": row.content_artifact_id,
            "artifact_version": row.content_artifact_version,
            "failure_code": row.failure_code,
            "readiness": "blocked" if row.failure_code else "ready",
        }
        for row in rows
    ]


@router.get("/campaigns/{campaign_id}/posts", response_model=list[SocialPostResponse])
def campaign_social_posts(campaign_id: uuid.UUID, db: DB, owner: Owner) -> list[SocialPost]:
    return list(
        db.scalars(
            select(SocialPost)
            .where(SocialPost.owner_id == owner.id, SocialPost.campaign_id == campaign_id)
            .order_by(SocialPost.scheduled_at_utc)
        )
    )


@router.get("/products/{product_id}/channel")
def product_social_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(SocialPost)
            .where(SocialPost.owner_id == owner.id, SocialPost.product_id == product_id)
            .order_by(SocialPost.updated_at.desc())
        )
    )
    latest = db.scalar(
        select(GeneratedArtifact.version_number)
        .where(
            GeneratedArtifact.owner_id == owner.id,
            GeneratedArtifact.product_id == product_id,
            GeneratedArtifact.status == "approved",
        )
        .order_by(GeneratedArtifact.version_number.desc())
    )
    return {
        "product_id": product_id,
        "channel": "social",
        "posts": rows,
        "update_available": any(latest and row.content_artifact_version < latest for row in rows),
    }
