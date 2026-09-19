"""Authenticated APIs for the 10A Competitor Intelligence foundation."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorEntity,
    CompetitorObservation,
    CompetitorProduct,
    CompetitorSnapshot,
)
from vayujit_api.intelligence.competitor_schemas import (
    CompetitorIntegrityResponse,
    CompetitorProductCreate,
    CompetitorProductDetailResponse,
    CompetitorProductIdentityUpdate,
    CompetitorProductResponse,
    ContextCreate,
    ContextResponse,
    EntityCreate,
    EntityResponse,
    ObservationCreate,
    ObservationResponse,
    SnapshotCreate,
    SnapshotResponse,
)
from vayujit_api.intelligence.competitor_service import (
    archive_context,
    create_context,
    create_entity,
    create_observation,
    create_product,
    create_snapshot,
    get_competitor_product,
    get_context,
    get_entity,
    integrity_report,
    update_identity,
)

router = APIRouter(prefix="/api/v1/intelligence/competitors", tags=["competitor-intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/contexts", response_model=ContextResponse, status_code=201)
def context_create(data: ContextCreate, db: DB, owner: Owner) -> CompetitorContext:
    return create_context(db, owner, data)


@router.get("/contexts", response_model=list[ContextResponse])
def context_list(
    db: DB,
    owner: Owner,
    status: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompetitorContext]:
    query = select(CompetitorContext).where(CompetitorContext.owner_id == owner.id)
    if status:
        query = query.where(CompetitorContext.status == status.upper())
    if marketplace:
        query = query.where(CompetitorContext.marketplace == marketplace)
    return list(
        db.scalars(query.order_by(CompetitorContext.updated_at.desc()).offset(offset).limit(limit))
    )


@router.get("/contexts/{context_id}", response_model=ContextResponse)
def context_get(context_id: uuid.UUID, db: DB, owner: Owner) -> CompetitorContext:
    return get_context(db, owner, context_id)


@router.post("/contexts/{context_id}/archive", response_model=ContextResponse)
def context_archive(context_id: uuid.UUID, db: DB, owner: Owner) -> CompetitorContext:
    return archive_context(db, owner, get_context(db, owner, context_id))


@router.post("/entities", response_model=EntityResponse, status_code=201)
def entity_create(data: EntityCreate, db: DB, owner: Owner) -> CompetitorEntity:
    return create_entity(db, owner, data)


@router.get("/entities", response_model=list[EntityResponse])
def entity_list(
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompetitorEntity]:
    return list(
        db.scalars(
            select(CompetitorEntity)
            .where(CompetitorEntity.owner_id == owner.id)
            .order_by(CompetitorEntity.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/entities/{entity_id}", response_model=EntityResponse)
def entity_get(entity_id: uuid.UUID, db: DB, owner: Owner) -> CompetitorEntity:
    return get_entity(db, owner, entity_id)


@router.post(
    "/contexts/{context_id}/products", response_model=CompetitorProductResponse, status_code=201
)
def product_create(
    context_id: uuid.UUID, data: CompetitorProductCreate, db: DB, owner: Owner
) -> CompetitorProduct:
    return create_product(db, owner, get_context(db, owner, context_id), data)


@router.get("/contexts/{context_id}/products", response_model=list[CompetitorProductResponse])
def product_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompetitorProduct]:
    get_context(db, owner, context_id)
    return list(
        db.scalars(
            select(CompetitorProduct)
            .where(
                CompetitorProduct.owner_id == owner.id, CompetitorProduct.context_id == context_id
            )
            .order_by(CompetitorProduct.last_observed.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/products/{product_id}", response_model=CompetitorProductDetailResponse)
def product_detail(product_id: uuid.UUID, db: DB, owner: Owner) -> CompetitorProductDetailResponse:
    product = get_competitor_product(db, owner, product_id)
    observations = list(
        db.scalars(
            select(CompetitorObservation)
            .where(
                CompetitorObservation.owner_id == owner.id,
                CompetitorObservation.competitor_product_id == product.id,
            )
            .order_by(CompetitorObservation.observed_at.desc())
            .limit(200)
        )
    )
    snapshots = list(
        db.scalars(
            select(CompetitorSnapshot)
            .where(
                CompetitorSnapshot.owner_id == owner.id, CompetitorSnapshot.product_id == product.id
            )
            .order_by(CompetitorSnapshot.snapshot_version.desc())
            .limit(100)
        )
    )
    return CompetitorProductDetailResponse(
        product=CompetitorProductResponse.model_validate(product),
        observations=[ObservationResponse.model_validate(item) for item in observations],
        snapshots=[SnapshotResponse.model_validate(item) for item in snapshots],
    )


@router.patch("/products/{product_id}/identity", response_model=CompetitorProductResponse)
def product_identity(
    product_id: uuid.UUID, data: CompetitorProductIdentityUpdate, db: DB, owner: Owner
) -> CompetitorProduct:
    return update_identity(db, owner, get_competitor_product(db, owner, product_id), data)


@router.post(
    "/products/{product_id}/observations", response_model=ObservationResponse, status_code=201
)
def observation_create(
    product_id: uuid.UUID, data: ObservationCreate, db: DB, owner: Owner
) -> CompetitorObservation:
    return create_observation(db, owner, get_competitor_product(db, owner, product_id), data)


@router.get("/products/{product_id}/observations", response_model=list[ObservationResponse])
def observation_list(
    product_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompetitorObservation]:
    get_competitor_product(db, owner, product_id)
    return list(
        db.scalars(
            select(CompetitorObservation)
            .where(
                CompetitorObservation.owner_id == owner.id,
                CompetitorObservation.competitor_product_id == product_id,
            )
            .order_by(CompetitorObservation.observed_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.post("/contexts/{context_id}/snapshots", response_model=SnapshotResponse, status_code=201)
def snapshot_create(
    context_id: uuid.UUID, data: SnapshotCreate, db: DB, owner: Owner
) -> CompetitorSnapshot:
    return create_snapshot(db, owner, get_context(db, owner, context_id), data)


@router.get("/contexts/{context_id}/snapshots", response_model=list[SnapshotResponse])
def snapshot_list(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompetitorSnapshot]:
    get_context(db, owner, context_id)
    return list(
        db.scalars(
            select(CompetitorSnapshot)
            .where(
                CompetitorSnapshot.owner_id == owner.id, CompetitorSnapshot.context_id == context_id
            )
            .order_by(CompetitorSnapshot.snapshot_version.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/system-doctor", response_model=CompetitorIntegrityResponse)
def competitor_system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    return integrity_report(db, owner)
