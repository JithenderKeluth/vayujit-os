"""PR-8C procurement-readiness assessment and HUMAN acknowledgement endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.procurement_readiness_schemas import (
    ProcurementReadinessAcknowledgement,
    ProcurementReadinessCreate,
    ProcurementReadinessResponse,
)
from vayujit_api.intelligence.procurement_readiness_service import (
    acknowledge_assessment,
    create_assessment,
    get_assessment,
    list_assessments,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities", tags=["procurement-readiness"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/procurement-readiness",
    response_model=ProcurementReadinessResponse,
    status_code=201,
)
def create(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: ProcurementReadinessCreate,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return create_assessment(db, owner, opportunity_id, assessment_id, data)


@router.get(
    "/{opportunity_id}/assessments/{assessment_id}/procurement-readiness",
    response_model=list[ProcurementReadinessResponse],
)
def list_items(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: DB,
    owner: Owner,
) -> list[dict[str, object]]:
    return list_assessments(db, owner, opportunity_id, assessment_id)


@router.get(
    "/procurement-readiness/{readiness_id}",
    response_model=ProcurementReadinessResponse,
)
def detail(readiness_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return get_assessment(db, owner, readiness_id)


@router.post(
    "/procurement-readiness/{readiness_id}/acknowledge",
)
def acknowledge(
    readiness_id: uuid.UUID,
    data: ProcurementReadinessAcknowledgement,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return acknowledge_assessment(db, owner, readiness_id, data)
