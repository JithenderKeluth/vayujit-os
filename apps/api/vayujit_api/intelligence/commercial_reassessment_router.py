"""Owner-scoped PR-8A commercial reassessment endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.commercial_reassessment_schemas import (
    CommercialReassessmentCreate,
    CommercialReassessmentResponse,
    CommercialReassessmentReviewCreate,
)
from vayujit_api.intelligence.commercial_reassessment_service import (
    create_reassessment,
    get_reassessment,
    list_reassessments,
    review_reassessment,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["product-opportunity-commercial-reassessment"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/commercial-reassessments",
    response_model=CommercialReassessmentResponse,
    status_code=201,
)
def create(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: CommercialReassessmentCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return create_reassessment(db, owner, opportunity_id, assessment_id, data)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/commercial-reassessments",
    response_model=list[CommercialReassessmentResponse],
)
def list_items(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> list[dict[str, object]]:
    return list_reassessments(db, owner, opportunity_id, assessment_id)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/commercial-reassessments/{reassessment_id}",
    response_model=CommercialReassessmentResponse,
)
def detail(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    reassessment_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    value = get_reassessment(db, owner, reassessment_id)
    if value["opportunity_id"] != str(opportunity_id) or value["assessment_id"] != str(
        assessment_id
    ):
        raise HTTPException(404, "Commercial reassessment not found.")
    return value


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/commercial-reassessments/{reassessment_id}/review",
    response_model=CommercialReassessmentResponse,
)
def review(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    reassessment_id: uuid.UUID,
    data: CommercialReassessmentReviewCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    value = get_reassessment(db, owner, reassessment_id)
    if value["opportunity_id"] != str(opportunity_id) or value["assessment_id"] != str(
        assessment_id
    ):
        raise HTTPException(404, "Commercial reassessment not found.")
    return review_reassessment(db, owner, reassessment_id, data)


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/commercial/reassess",
    response_model=CommercialReassessmentResponse,
    status_code=201,
)
def reassess_alias(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: CommercialReassessmentCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return create_reassessment(db, owner, opportunity_id, assessment_id, data)
