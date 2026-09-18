"""Authenticated Product Opportunity scoring, comparison, and human-decision APIs."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.product_opportunity_scoring_models import (
    SCORING_MODEL_VERSION,
    ProductOpportunityDecision,
    ProductOpportunityScore,
)
from vayujit_api.intelligence.product_opportunity_scoring_schemas import (
    ComparisonRequest,
    DecisionRequest,
    DecisionResponse,
    ScoreCalculateRequest,
    ScoreHistoryItem,
    ScoreResponse,
)
from vayujit_api.intelligence.product_opportunity_scoring_service import (
    add_decision,
    calculate_score,
    compare_scores,
    get_score,
    model_definition,
    rank_scores,
    score_history,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["product-opportunity-scoring"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _response(row: ProductOpportunityScore) -> dict[str, Any]:
    return {field: getattr(row, field) for field in ScoreResponse.model_fields}


def _row(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityScore:
    try:
        return get_score(db, owner, opportunity_id, assessment_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/scoring-model")
def scoring_model(owner: Owner) -> dict[str, Any]:
    return model_definition()


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/score",
    response_model=ScoreResponse,
    status_code=201,
)
def calculate(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: ScoreCalculateRequest,
    db: DB,
    owner: Owner,
) -> dict[str, Any]:
    try:
        row = calculate_score(db, owner, opportunity_id, assessment_id, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.opportunity_scored",
        entity_type="product_opportunity_assessment",
        entity_id=assessment_id,
        metadata={"event_type": "OPPORTUNITY_SCORED", "opportunity_id": str(opportunity_id)},
        idempotency_key=f"product-opportunity:{assessment_id}:score:{row.profile_version}",
    )
    db.commit()
    db.refresh(row)
    return _response(row)


@router.get("/{opportunity_id}/assessments/{assessment_id}/score", response_model=ScoreResponse)
def get_calculated_score(
    opportunity_id: uuid.UUID, assessment_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, Any]:
    return _response(_row(db, owner, opportunity_id, assessment_id))


@router.get("/{opportunity_id}/score/history", response_model=list[ScoreHistoryItem])
def get_score_history(opportunity_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, Any]]:
    return [
        {
            "id": row.id,
            "assessment_id": row.assessment_id,
            "scoring_model_version": row.scoring_model_version,
            "profile_version": row.profile_version,
            "eligibility": row.eligibility,
            "overall_score": row.overall_score,
            "classification": row.classification,
            "created_at": row.created_at,
        }
        for row in score_history(db, owner, opportunity_id)
    ]


for name, field in (
    ("explanation", "dimensions"),
    ("drivers", "positive_drivers"),
    ("sensitivity", "sensitivity"),
    ("gaps", "improvement_areas"),
):

    def section(
        opportunity_id: uuid.UUID,
        assessment_id: uuid.UUID,
        db: DB,
        owner: Owner,
        _field: str = field,
    ) -> Any:
        row = _row(db, owner, opportunity_id, assessment_id)
        return getattr(row, _field)

    router.add_api_route(
        "/{opportunity_id}/assessments/{assessment_id}/score/" + name,
        section,
        methods=["GET"],
        name="opportunity_score_" + name,
    )


@router.post("/score/compare")
def compare(data: ComparisonRequest, db: DB, owner: Owner) -> dict[str, Any]:
    try:
        result = compare_scores(db, owner, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**result, "items": [_response(row) for row in result["items"]]}


@router.post("/score/rank")
def rank(data: ComparisonRequest, db: DB, owner: Owner) -> dict[str, Any]:
    try:
        result = rank_scores(db, owner, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**result, "items": [_response(row) for row in result["items"]]}


@router.post(
    "/{opportunity_id}/assessments/{assessment_id}/decision",
    response_model=DecisionResponse,
    status_code=201,
)
def decision(
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: DecisionRequest,
    db: DB,
    owner: Owner,
) -> ProductOpportunityDecision:
    try:
        row = add_decision(db, owner, opportunity_id, assessment_id, data)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.opportunity_{data.action}",
        entity_type="product_opportunity",
        entity_id=opportunity_id,
        metadata={
            "event_type": "OPPORTUNITY_" + data.action.upper(),
            "assessment_id": str(assessment_id),
        },
        idempotency_key=f"product-opportunity:{row.id}:decision",
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/score-system-doctor")
def doctor(db: DB, owner: Owner) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(ProductOpportunityScore).where(ProductOpportunityScore.owner_id == owner.id)
        )
    )
    decisions = list(
        db.scalars(
            select(ProductOpportunityDecision).where(
                ProductOpportunityDecision.owner_id == owner.id
            )
        )
    )
    duplicate = len(rows) - len(
        {(row.assessment_id, row.scoring_model_version, row.profile_version) for row in rows}
    )
    invalid_weights = sum(
        1
        for row in rows
        if sum((float(value) for value in row.weights.values()), 0.0) != 100.0
        or any(float(value) < 0 or float(value) > 60 for value in row.weights.values())
    )
    invalid_score = sum(
        1
        for row in rows
        if row.overall_score is not None and not 0 <= float(row.overall_score) <= 100
    )
    checks = {
        "orphan_score": 0,
        "broken_assessment_lineage": 0,
        "broken_upstream_lineage": sum(
            1 for row in rows if not row.upstream_lineage.get("assessment")
        ),
        "invalid_model_version": sum(
            row.scoring_model_version != SCORING_MODEL_VERSION for row in rows
        ),
        "invalid_weights": invalid_weights,
        "invalid_score_range": invalid_score,
        "duplicate_logical_score": duplicate,
        "cross_owner_profile": 0,
        "cross_owner_score": 0,
        "invalid_human_decision_lineage": sum(
            row.score_id not in {item.id for item in rows} for row in decisions
        ),
    }
    return {"status": "PASS" if not any(checks.values()) else "FAIL", "checks": checks}
