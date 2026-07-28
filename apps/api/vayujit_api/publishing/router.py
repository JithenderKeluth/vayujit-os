import math
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.publishing.connector import connector
from vayujit_api.publishing.models import PublishingDestination, PublishingExecution
from vayujit_api.publishing.schemas import (
    CreateExecution,
    DestinationResponse,
    DestinationUpdate,
    DestinationWrite,
    ExecutionResponse,
    Page,
)
from vayujit_api.publishing.service import (
    create_destination,
    create_execution,
    destination_response,
    execution_response,
    owned_destination,
    retry_execution,
    set_destination_status,
    update_destination,
)

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/connectors")
def connectors(owner: Owner) -> list[dict[str, object]]:
    return [
        {
            "key": connector.key,
            "name": connector.name,
            "connector_type": connector.connector_type,
            "available": connector.available(),
            "deterministic": True,
            "local": True,
        }
    ]


@router.get("/destinations", response_model=Page)
def destinations(
    db: DB,
    owner: Owner,
    brand_id: uuid.UUID | None = None,
    connector_key: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page:
    filters = [PublishingDestination.owner_id == owner.id]
    if brand_id:
        filters.append(PublishingDestination.brand_id == brand_id)
    if connector_key:
        filters.append(PublishingDestination.connector_key == connector_key)
    if status:
        filters.append(PublishingDestination.status == status)
    if search:
        filters.append(
            or_(
                PublishingDestination.name.ilike(f"%{search}%"),
                PublishingDestination.normalized_name.ilike(f"%{search.casefold()}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(PublishingDestination).where(*filters)) or 0
    values = db.scalars(
        select(PublishingDestination)
        .where(*filters)
        .order_by(PublishingDestination.name, PublishingDestination.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[destination_response(db, value) for value in values],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/destinations", response_model=DestinationResponse, status_code=201)
def destination_create(data: DestinationWrite, db: DB, owner: Owner) -> DestinationResponse:
    return create_destination(db, owner, data)


@router.get("/destinations/{destination_id}", response_model=DestinationResponse)
def destination_get(destination_id: uuid.UUID, db: DB, owner: Owner) -> DestinationResponse:
    return destination_response(db, owned_destination(db, owner.id, destination_id))


@router.patch("/destinations/{destination_id}", response_model=DestinationResponse)
def destination_patch(
    destination_id: uuid.UUID, data: DestinationUpdate, db: DB, owner: Owner
) -> DestinationResponse:
    return update_destination(db, owner, owned_destination(db, owner.id, destination_id), data)


@router.post("/destinations/{destination_id}/disable", response_model=DestinationResponse)
def destination_disable(destination_id: uuid.UUID, db: DB, owner: Owner) -> DestinationResponse:
    return set_destination_status(
        db, owner, owned_destination(db, owner.id, destination_id), "disabled"
    )


@router.post("/destinations/{destination_id}/enable", response_model=DestinationResponse)
def destination_enable(destination_id: uuid.UUID, db: DB, owner: Owner) -> DestinationResponse:
    return set_destination_status(
        db, owner, owned_destination(db, owner.id, destination_id), "active"
    )


@router.post("/executions", response_model=ExecutionResponse, status_code=201)
def execution_create(data: CreateExecution, db: DB, owner: Owner) -> ExecutionResponse:
    return create_execution(db, owner, data)


@router.get("/executions", response_model=Page)
def executions(
    db: DB,
    owner: Owner,
    product_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    artifact_id: uuid.UUID | None = None,
    destination_id: uuid.UUID | None = None,
    connector_key: str | None = None,
    status: str | None = None,
    retryable: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page:
    filters = [PublishingExecution.owner_id == owner.id]
    for column, value in (
        (PublishingExecution.product_id, product_id),
        (PublishingExecution.brand_id, brand_id),
        (PublishingExecution.artifact_id, artifact_id),
        (PublishingExecution.destination_id, destination_id),
        (PublishingExecution.connector_key, connector_key),
        (PublishingExecution.status, status),
        (PublishingExecution.retryable, retryable),
    ):
        if value is not None:
            filters.append(column == value)
    if date_from:
        filters.append(PublishingExecution.created_at >= date_from)
    if date_to:
        filters.append(PublishingExecution.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(PublishingExecution).where(*filters)) or 0
    values = db.scalars(
        select(PublishingExecution)
        .where(*filters)
        .order_by(PublishingExecution.created_at.desc(), PublishingExecution.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[execution_response(db, value) for value in values],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
def execution_get(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    value = db.scalar(
        select(PublishingExecution).where(
            PublishingExecution.id == execution_id, PublishingExecution.owner_id == owner.id
        )
    )
    if not value:
        from fastapi import HTTPException

        raise HTTPException(404, "Publishing execution not found.")
    return execution_response(db, value)


@router.post("/executions/{execution_id}/retry", response_model=ExecutionResponse)
def execution_retry(execution_id: uuid.UUID, db: DB, owner: Owner) -> ExecutionResponse:
    return retry_execution(db, owner, execution_id)
