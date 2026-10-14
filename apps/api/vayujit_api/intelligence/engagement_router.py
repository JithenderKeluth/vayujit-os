"""Owner-scoped PR-7A engagement and PR-7B controlled EMAIL endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.email_delivery_schemas import (
    RetrySendRequest,
    SendAuthorizationRequest,
    SendRequest,
)
from vayujit_api.intelligence.email_delivery_service import (
    authorize_send,
    process_outbox,
    retry_rfq,
    send_eligibility,
    send_rfq,
)
from vayujit_api.intelligence.engagement_models import SupplierEngagement
from vayujit_api.intelligence.engagement_schemas import (
    ApprovalRequest,
    CancelRequest,
    DraftRevision,
    EngagementCreate,
)
from vayujit_api.intelligence.engagement_service import (
    approve_engagement,
    cancel_engagement,
    create_engagement,
    create_revision,
    engagement_history,
    send_readiness,
    serialize_engagement,
)

router = APIRouter(prefix="/api/v1/intelligence/engagements", tags=["intelligence-engagement"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("", status_code=201)
def engagement_create(data: EngagementCreate, db: DB, owner: Owner) -> dict[str, object]:
    return create_engagement(db, owner, data)


@router.post("/send-commands/{command_id}/process")
def engagement_send_process(command_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return process_outbox(db, owner, command_id)


@router.get("/{engagement_id}")
def engagement_detail(engagement_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = db.scalar(
        select(SupplierEngagement).where(
            SupplierEngagement.id == engagement_id,
            SupplierEngagement.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Engagement not found.")
    return serialize_engagement(db, owner, row)


@router.post("/{engagement_id}/drafts")
def engagement_revision(
    engagement_id: uuid.UUID, data: DraftRevision, db: DB, owner: Owner
) -> dict[str, object]:
    return create_revision(db, owner, engagement_id, data)


@router.post("/{engagement_id}/approve")
def engagement_approve(
    engagement_id: uuid.UUID, data: ApprovalRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return approve_engagement(db, owner, engagement_id, data)


@router.post("/{engagement_id}/cancel")
def engagement_cancel(
    engagement_id: uuid.UUID, data: CancelRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return cancel_engagement(db, owner, engagement_id, data)


@router.get("/{engagement_id}/history")
def engagement_events(engagement_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return engagement_history(db, owner, engagement_id)


@router.get("/{engagement_id}/send-readiness")
def engagement_send_readiness(engagement_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return send_readiness(db, owner, engagement_id)


@router.get("/{engagement_id}/send-eligibility")
def engagement_send_eligibility(
    engagement_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return send_eligibility(db, owner, engagement_id)


@router.post("/{engagement_id}/send-authorize")
def engagement_send_authorize(
    engagement_id: uuid.UUID, data: SendAuthorizationRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return authorize_send(db, owner, engagement_id, data)


@router.post("/{engagement_id}/send-authorization")
def engagement_send_authorization(
    engagement_id: uuid.UUID, data: SendAuthorizationRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return authorize_send(db, owner, engagement_id, data)


@router.post("/{engagement_id}/send")
def engagement_send(
    engagement_id: uuid.UUID, data: SendRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return send_rfq(db, owner, engagement_id, data)


@router.post("/{engagement_id}/send/retry")
def engagement_send_retry(
    engagement_id: uuid.UUID, data: RetrySendRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return retry_rfq(db, owner, engagement_id, data)
