from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.bulk_models import AIStudioBulkOperation, AIStudioBulkOutput
from vayujit_api.ai.bulk_service import (
    _output_response,
    _sync_operation,
    cancel_outputs,
    create_bulk,
    preview_bulk,
    retry_outputs,
    status_response,
)
from vayujit_api.ai.studio_schemas import (
    StudioBulkCancelRequest,
    StudioBulkPreviewResponse,
    StudioBulkRequest,
    StudioBulkRetryRequest,
    StudioBulkStatusResponse,
)
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user

router = APIRouter(prefix="/api/v1/ai/studio", tags=["ai-studio-bulk"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


def _operation(db: Session, owner: User, bulk_id: uuid.UUID) -> AIStudioBulkOperation:
    row = db.scalar(
        select(AIStudioBulkOperation).where(
            AIStudioBulkOperation.id == bulk_id, AIStudioBulkOperation.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Bulk generation not found.")
    return row


@router.post("/bulk/preview", response_model=StudioBulkPreviewResponse)
def preview_bulk_generation(
    data: StudioBulkRequest, db: DatabaseSession, owner: CurrentUser
) -> StudioBulkPreviewResponse:
    return preview_bulk(db, owner, data)


@router.post("/bulk", response_model=StudioBulkStatusResponse, status_code=202)
@router.post("/bulk/generate", response_model=StudioBulkStatusResponse, status_code=202)
def create_bulk_generation(
    data: StudioBulkRequest, db: DatabaseSession, owner: CurrentUser
) -> StudioBulkStatusResponse:
    operation = create_bulk(db, owner, data)
    record_event(
        db,
        actor_id=owner.id,
        action="ai.bulk_generation_previewed",
        entity_type="ai_studio_bulk_operation",
        entity_id=operation.id,
        metadata={"total_outputs": operation.total_outputs},
    )
    db.commit()
    return status_response(db, operation)


@router.get("/bulk", response_model=list[StudioBulkStatusResponse])
def list_bulk_generations(
    db: DatabaseSession, owner: CurrentUser, status: str | None = None
) -> list[StudioBulkStatusResponse]:
    query = select(AIStudioBulkOperation).where(AIStudioBulkOperation.owner_id == owner.id)
    if status:
        query = query.where(AIStudioBulkOperation.status == status)
    rows = db.scalars(query.order_by(AIStudioBulkOperation.created_at.desc()).limit(100)).all()
    return [status_response(db, row) for row in rows]


@router.get("/bulk/{bulk_id}", response_model=StudioBulkStatusResponse)
def get_bulk_generation(
    bulk_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> StudioBulkStatusResponse:
    return status_response(db, _operation(db, owner, bulk_id))


@router.get("/bulk/{bulk_id}/outputs")
def list_bulk_outputs(
    bulk_id: uuid.UUID,
    db: DatabaseSession,
    owner: CurrentUser,
    product_id: uuid.UUID | None = None,
    channel: str | None = None,
    content_type: str | None = None,
    state: str | None = None,
    failure_category: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    _sync_operation(db, operation)
    query = select(AIStudioBulkOutput).where(AIStudioBulkOutput.bulk_operation_id == bulk_id)
    if product_id:
        query = query.where(AIStudioBulkOutput.product_id == product_id)
    if channel:
        query = query.where(AIStudioBulkOutput.channel == channel)
    if content_type:
        query = query.where(AIStudioBulkOutput.content_type == content_type)
    if state:
        query = query.where(AIStudioBulkOutput.status == state)
    if failure_category:
        query = query.where(AIStudioBulkOutput.failure_category == failure_category)
    safe_limit = min(100, max(1, limit))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(AIStudioBulkOutput.created_at).offset(max(0, offset)).limit(safe_limit)
    ).all()
    db.commit()
    return {
        "items": [_output_response(db, row) for row in rows],
        "total": total,
        "offset": max(0, offset),
        "limit": safe_limit,
    }


@router.post("/bulk/{bulk_id}/retry-failed")
def retry_bulk_failed(
    bulk_id: uuid.UUID,
    db: DatabaseSession,
    owner: CurrentUser,
    data: StudioBulkRetryRequest | None = None,
) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    retried, rejected = retry_outputs(db, owner, operation, data.output_ids if data else [])
    return {
        "status": "queued" if retried else operation.status,
        "retried_count": retried,
        "rejected_count": rejected,
        "bulk_id": str(operation.id),
    }


@router.post("/bulk/{bulk_id}/cancel")
def cancel_bulk_generation(
    bulk_id: uuid.UUID,
    db: DatabaseSession,
    owner: CurrentUser,
    data: StudioBulkCancelRequest | None = None,
) -> dict[str, object]:
    operation = _operation(db, owner, bulk_id)
    cancelled = cancel_outputs(db, owner, operation, data.output_ids if data else [])
    if not data or not data.output_ids:
        operation.cancellation_requested = True
        record_event(
            db,
            actor_id=owner.id,
            action="ai.bulk_generation_cancelled",
            entity_type="ai_studio_bulk_operation",
            entity_id=operation.id,
            metadata={"cancelled_count": cancelled},
        )
        db.commit()
    return {
        "status": operation.status,
        "cancelled_count": cancelled,
        "bulk_id": str(operation.id),
    }


@router.post("/bulk/outputs/{output_id}/retry")
def retry_single_bulk_output(
    output_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> dict[str, object]:
    output = db.scalar(
        select(AIStudioBulkOutput).where(
            AIStudioBulkOutput.id == output_id, AIStudioBulkOutput.owner_id == owner.id
        )
    )
    if output is None:
        raise HTTPException(404, "Bulk output not found.")
    operation = _operation(db, owner, output.bulk_operation_id)
    retried, rejected = retry_outputs(db, owner, operation, [output.id])
    return {
        "status": "queued" if retried else output.status,
        "retried_count": retried,
        "rejected_count": rejected,
    }


@router.post("/bulk/outputs/{output_id}/cancel")
def cancel_single_bulk_output(
    output_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> dict[str, object]:
    output = db.scalar(
        select(AIStudioBulkOutput).where(
            AIStudioBulkOutput.id == output_id, AIStudioBulkOutput.owner_id == owner.id
        )
    )
    if output is None:
        raise HTTPException(404, "Bulk output not found.")
    operation = _operation(db, owner, output.bulk_operation_id)
    cancelled = cancel_outputs(db, owner, operation, [output.id])
    return {
        "status": "cancelled" if cancelled else output.status,
        "cancelled_count": cancelled,
    }
