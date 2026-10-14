"""Authenticated PR-6B explainable decision-synthesis APIs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.decision_synthesis_schemas import (
    DecisionSynthesisRequest,
    DecisionSynthesisResponse,
)
from vayujit_api.intelligence.decision_synthesis_service import (
    create_synthesis,
    latest_synthesis,
    serialize_synthesis,
    synthesis_history,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["decision-synthesis"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/{opportunity_id}/decision-synthesis",
    response_model=DecisionSynthesisResponse,
    status_code=201,
)
def create_decision_synthesis(
    opportunity_id: uuid.UUID,
    data: DecisionSynthesisRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    row = create_synthesis(
        db,
        owner,
        opportunity_id,
        target=data.decision_target,
        snapshot_id=data.decision_evidence_snapshot_id,
        assessment_id=data.assessment_id,
        goal_id=data.goal_id,
        supplier_id=data.supplier_id,
        idempotency_key=data.idempotency_key,
    )
    return serialize_synthesis(row)


@router.get(
    "/{opportunity_id}/decision-synthesis/latest",
    response_model=DecisionSynthesisResponse,
)
def read_latest_synthesis(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> dict[str, object]:
    row = latest_synthesis(db, owner, opportunity_id, target)
    if row is None:
        raise HTTPException(404, "Decision synthesis snapshot not found.")
    return serialize_synthesis(row)


@router.get(
    "/{opportunity_id}/decision-synthesis/history",
    response_model=list[DecisionSynthesisResponse],
)
def read_synthesis_history(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> list[dict[str, object]]:
    return synthesis_history(db, owner, opportunity_id, target)
