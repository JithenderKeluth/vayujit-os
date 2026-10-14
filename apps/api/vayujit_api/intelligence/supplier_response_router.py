"""Owner-scoped PR-7C supplier-response evidence endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.supplier_response_schemas import (
    SupplierResponseCreate,
    SupplierResponseListResponse,
    SupplierResponseResponse,
    SupplierResponseReviewRequest,
)
from vayujit_api.intelligence.supplier_response_service import (
    create_response,
    get_response,
    list_responses,
    promote_response,
    review_response,
)

router = APIRouter(
    prefix="/api/v1/intelligence/supplier-responses",
    tags=["intelligence-supplier-responses"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("", response_model=SupplierResponseResponse, status_code=status.HTTP_201_CREATED)
def record_supplier_response(
    data: SupplierResponseCreate, db: DB, owner: Owner
) -> dict[str, object]:
    value, _reused = create_response(db, owner, data)
    return value


@router.get("", response_model=SupplierResponseListResponse)
def supplier_response_list(
    db: DB, owner: Owner, opportunity_id: uuid.UUID | None = None
) -> dict[str, object]:
    return list_responses(db, owner, opportunity_id=opportunity_id)


@router.get("/{response_id}", response_model=SupplierResponseResponse)
def supplier_response_detail(response_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return get_response(db, owner, response_id)


@router.post("/{response_id}/review", response_model=SupplierResponseResponse)
def supplier_response_review(
    response_id: uuid.UUID,
    data: SupplierResponseReviewRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return review_response(db, owner, response_id, data)


@router.post("/{response_id}/promote", response_model=SupplierResponseResponse)
def supplier_response_promote(response_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return promote_response(db, owner, response_id)
