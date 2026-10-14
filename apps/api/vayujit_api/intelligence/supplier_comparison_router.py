"""Owner-scoped PR-8B comparison and HUMAN shortlist endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.supplier_comparison_schemas import (
    SupplierComparisonCreate,
    SupplierComparisonResponse,
    SupplierComparisonShortlistCreate,
    SupplierComparisonShortlistResponse,
)
from vayujit_api.intelligence.supplier_comparison_service import (
    create_comparison,
    get_comparison,
    list_comparisons,
    shortlist_supplier,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["supplier-comparison"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/supplier-comparisons",
    response_model=SupplierComparisonResponse,
    status_code=201,
)
def create(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: SupplierComparisonCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return create_comparison(db, owner, opportunity_id, assessment_id, data)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/supplier-comparisons",
    response_model=list[SupplierComparisonResponse],
)
def list_items(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> list[dict[str, object]]:
    return list_comparisons(db, owner, opportunity_id, assessment_id)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/supplier-comparisons/{comparison_id}",
    response_model=SupplierComparisonResponse,
)
def detail(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    result = get_comparison(db, owner, comparison_id)
    if result["opportunity_id"] != str(opportunity_id) or result["assessment_id"] != str(
        assessment_id
    ):
        raise HTTPException(404, "Supplier comparison not found.")
    return result


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/supplier-comparisons/{comparison_id}/shortlist",
    response_model=SupplierComparisonShortlistResponse,
)
def shortlist(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    comparison_id: uuid.UUID,
    data: SupplierComparisonShortlistCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    result = get_comparison(db, owner, comparison_id)
    if result["opportunity_id"] != str(opportunity_id) or result["assessment_id"] != str(
        assessment_id
    ):
        raise HTTPException(404, "Supplier comparison not found.")
    return shortlist_supplier(db, owner, comparison_id, data)
