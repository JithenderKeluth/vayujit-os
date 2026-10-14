"""Authenticated PR-6A decision evidence/readiness APIs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.decision_evidence_models import DecisionEvidenceSnapshot
from vayujit_api.intelligence.decision_readiness_schemas import (
    DecisionReadinessRequest,
    DecisionReadinessResponse,
)
from vayujit_api.intelligence.decision_readiness_service import (
    create_decision_snapshot,
    latest_snapshot,
    project_decision_readiness,
    serialize_snapshot,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["decision-readiness"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/{opportunity_id}/decision-readiness",
    response_model=DecisionReadinessResponse,
    status_code=201,
)
def create_readiness(
    opportunity_id: uuid.UUID,
    data: DecisionReadinessRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    row = create_decision_snapshot(
        db,
        owner,
        opportunity_id,
        target=data.decision_target,
        assessment_id=data.assessment_id,
        goal_id=data.goal_id,
        supplier_id=data.supplier_id,
        idempotency_key=data.idempotency_key,
    )
    return serialize_snapshot(row)


@router.get(
    "/{opportunity_id}/decision-readiness",
    response_model=DecisionReadinessResponse,
)
def read_readiness(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
    persist: bool = Query(default=False),
) -> dict[str, object]:
    if persist:
        row = create_decision_snapshot(db, owner, opportunity_id, target=target)
        return serialize_snapshot(row)
    return project_decision_readiness(db, owner, opportunity_id, target=target)


@router.get(
    "/{opportunity_id}/decision-readiness/history",
    response_model=list[DecisionReadinessResponse],
)
def readiness_history(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(DecisionEvidenceSnapshot)
            .where(
                DecisionEvidenceSnapshot.owner_id == owner.id,
                DecisionEvidenceSnapshot.opportunity_id == opportunity_id,
                DecisionEvidenceSnapshot.decision_target == target.upper(),
            )
            .order_by(DecisionEvidenceSnapshot.decision_version.desc())
        )
    )
    return [serialize_snapshot(row) for row in rows]


@router.get(
    "/{opportunity_id}/decision-readiness/latest",
    response_model=DecisionReadinessResponse,
)
def read_latest(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> dict[str, object]:
    row = latest_snapshot(db, owner, opportunity_id, target)
    if row is None:
        raise HTTPException(404, "Decision evidence snapshot not found.")
    return serialize_snapshot(row)
