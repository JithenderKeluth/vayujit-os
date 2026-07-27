import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.brands.schemas import (
    AuditSummary,
    BrandCreate,
    BrandDetailsResponse,
    BrandListResponse,
    BrandResponse,
    BrandUpdate,
)
from vayujit_api.brands.service import (
    activate_brand,
    archive_brand,
    create_brand,
    owned_brand,
    restore_brand,
    update_brand,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user

router = APIRouter(prefix="/api/v1/brands", tags=["brands"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("", response_model=BrandListResponse)
def list_brands(
    db: DatabaseSession,
    owner: CurrentUser,
    include_archived: bool = False,
    search: Annotated[str | None, Query(max_length=120)] = None,
    status: Literal["active", "archived"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BrandListResponse:
    filters = [Brand.owner_id == owner.id]
    if not include_archived:
        filters.append(Brand.status == BrandStatus.ACTIVE.value)
    if status:
        filters.append(Brand.status == status)
    if search and search.strip():
        filters.append(Brand.normalized_name.contains(" ".join(search.casefold().split())))
    total = db.scalar(select(func.count(Brand.id)).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Brand)
            .where(*filters)
            .order_by(Brand.name.asc(), Brand.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return BrandListResponse(
        items=[BrandResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=BrandResponse, status_code=201)
def create(data: BrandCreate, db: DatabaseSession, owner: CurrentUser) -> Brand:
    return create_brand(db, owner, data)


@router.get("/active", response_model=BrandResponse | None)
def active_brand(db: DatabaseSession, owner: CurrentUser) -> Brand | None:
    return db.scalar(
        select(Brand).where(Brand.owner_id == owner.id, Brand.is_active_context.is_(True))
    )


@router.get("/{brand_id}", response_model=BrandDetailsResponse)
def get_brand(brand_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> BrandDetailsResponse:
    brand = owned_brand(db, owner.id, brand_id)
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "brand", AuditEvent.entity_id == brand.id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(10)
        )
    )
    response = BrandDetailsResponse.model_validate(brand)
    response.recent_audit_events = [
        AuditSummary(action=event.action, occurred_at=event.occurred_at) for event in events
    ]
    return response


@router.patch("/{brand_id}", response_model=BrandResponse)
def patch_brand(
    brand_id: uuid.UUID, data: BrandUpdate, db: DatabaseSession, owner: CurrentUser
) -> Brand:
    return update_brand(db, owner, owned_brand(db, owner.id, brand_id), data)


@router.post("/{brand_id}/archive", response_model=BrandResponse)
def archive(brand_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> Brand:
    return archive_brand(db, owner, owned_brand(db, owner.id, brand_id))


@router.post("/{brand_id}/restore", response_model=BrandResponse)
def restore(brand_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> Brand:
    return restore_brand(db, owner, owned_brand(db, owner.id, brand_id))


@router.post("/{brand_id}/activate", response_model=BrandResponse)
def activate(brand_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> Brand:
    return activate_brand(db, owner, owned_brand(db, owner.id, brand_id))
