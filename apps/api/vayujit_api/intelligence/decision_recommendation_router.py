"""Authenticated PR-6C recommendation and human-decision APIs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.decision_recommendation_schemas import (
    HumanDecisionRequest,
    HumanDecisionResponse,
    RecommendationAssessmentRequest,
    RecommendationAssessmentResponse,
)
from vayujit_api.intelligence.decision_recommendation_service import (
    create_human_decision,
    create_recommendation,
    human_decision_history,
    latest_human_decision,
    latest_recommendation,
    recommendation_history,
    serialize_human_decision,
    serialize_recommendation,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["decision-recommendation"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post(
    "/{opportunity_id}/recommendation-assessment",
    response_model=RecommendationAssessmentResponse,
    status_code=201,
)
def create_recommendation_assessment(
    opportunity_id: uuid.UUID,
    data: RecommendationAssessmentRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return serialize_recommendation(
        create_recommendation(
            db,
            owner,
            opportunity_id,
            target=data.decision_target,
            synthesis_id=data.synthesis_id,
            goal_id=data.goal_id,
            supplier_id=data.supplier_id,
            idempotency_key=data.idempotency_key,
        )
    )


@router.get(
    "/{opportunity_id}/recommendation-assessment/latest",
    response_model=RecommendationAssessmentResponse,
)
def read_latest_recommendation(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> dict[str, object]:
    row = latest_recommendation(db, owner, opportunity_id, target)
    if row is None:
        raise HTTPException(404, "Recommendation assessment not found.")
    return serialize_recommendation(row)


@router.get(
    "/{opportunity_id}/recommendation-assessment/history",
    response_model=list[RecommendationAssessmentResponse],
)
def read_recommendation_history(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> list[dict[str, object]]:
    return recommendation_history(db, owner, opportunity_id, target)


@router.post(
    "/{opportunity_id}/human-decision",
    response_model=HumanDecisionResponse,
    status_code=201,
)
def create_explicit_human_decision(
    opportunity_id: uuid.UUID,
    data: HumanDecisionRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return serialize_human_decision(
        create_human_decision(
            db,
            owner,
            opportunity_id,
            target=data.decision_target,
            decision=data.decision,
            recommendation_id=data.recommendation_id,
            synthesis_id=data.synthesis_id,
            goal_id=data.goal_id,
            supplier_id=data.supplier_id,
            reason=data.reason,
            idempotency_key=data.idempotency_key,
            provenance=data.provenance,
        )
    )


@router.get(
    "/{opportunity_id}/human-decision/latest",
    response_model=HumanDecisionResponse,
)
def read_latest_human_decision(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> dict[str, object]:
    row = latest_human_decision(db, owner, opportunity_id, target)
    if row is None:
        raise HTTPException(404, "Human decision not found.")
    return serialize_human_decision(row)


@router.get(
    "/{opportunity_id}/human-decision/history",
    response_model=list[HumanDecisionResponse],
)
def read_human_decision_history(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    target: str = Query(default="COMMERCIAL_ASSESSMENT"),
) -> list[dict[str, object]]:
    return human_decision_history(db, owner, opportunity_id, target)
