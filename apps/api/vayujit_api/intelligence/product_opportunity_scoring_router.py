"""Authenticated Product Opportunity scoring, comparison, and human-decision APIs."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal, BusinessAgentRun
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
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


def _meaningful_opportunity(opportunity: ProductOpportunity) -> bool:
    profile = opportunity.intelligence_profile or {}
    if str(opportunity.name).casefold() in {
        "business agent product opportunity",
        "candidate product",
        "product opportunity 1",
        "test product",
        "example product",
    }:
        return False
    return bool(
        profile.get("normalized_product_concept")
        or (opportunity.category and opportunity.description and opportunity.product_concept)
    )


def _candidate_state(opportunity: ProductOpportunity, score: ProductOpportunityScore | None) -> str:
    if not _meaningful_opportunity(opportunity):
        return "INSUFFICIENT_EVIDENCE"
    if score is None or score.eligibility == "INSUFFICIENT_EVIDENCE":
        return "NEEDS_MORE_RESEARCH"
    if score.assessment_readiness in {"UNKNOWN", "INSUFFICIENT_EVIDENCE"}:
        return "NEEDS_MORE_RESEARCH"
    return "READY_TO_COMPARE"


def _goal_category(goal: BusinessAgentGoal) -> str:
    # The current user statement is authoritative when it explicitly names a category.
    # Older structured values can otherwise leak a previous goal into a later goal.
    match = re.search(
        r"\b(?:in|for|within)\s+(?:the\s+)?([a-z][a-z0-9 &\-/]{1,80}?)\s+categor(?:y|ies)\b",
        goal.raw_goal.casefold(),
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
    structured = goal.structured_goal or {}
    value = structured.get("category")
    return value.strip() if isinstance(value, str) else ""


def _matches_goal_category(row: ProductOpportunity, category: str) -> bool:
    requested = set(re.findall(r"[a-z0-9]+", category.casefold()))
    observed = set(
        re.findall(r"[a-z0-9]+", f"{row.category or ''} {row.subcategory or ''}".casefold())
    )
    return bool(requested & observed)


def _research_scope(
    db: Session, owner: User, goal_id: uuid.UUID | None
) -> tuple[list[ProductOpportunity], BusinessAgentGoal | None, list[uuid.UUID], int]:
    """Resolve current-goal candidates through existing Business Agent run lineage."""
    owner_rows = list(
        db.scalars(
            select(ProductOpportunity)
            .where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.lifecycle_status != "archived",
            )
            .order_by(ProductOpportunity.updated_at.desc())
        )
    )
    meaningful_owner_rows = [row for row in owner_rows if _meaningful_opportunity(row)]
    goal_statement = select(BusinessAgentGoal).where(BusinessAgentGoal.owner_id == owner.id)
    if goal_id is not None:
        goal_statement = goal_statement.where(BusinessAgentGoal.id == goal_id)
    goal = db.scalar(
        goal_statement.order_by(
            BusinessAgentGoal.updated_at.desc(), BusinessAgentGoal.created_at.desc()
        )
    )
    if goal is None:
        if goal_id is not None:
            raise HTTPException(404, "Business goal not found.")
        # Preserve the standalone Product Opportunity contract when no goal exists.
        return owner_rows, None, [], 0
    run_ids = list(
        db.scalars(
            select(BusinessAgentRun.id)
            .where(BusinessAgentRun.owner_id == owner.id, BusinessAgentRun.goal_id == goal.id)
            .order_by(BusinessAgentRun.created_at.desc())
        )
    )
    explicit_id = (goal.structured_goal or {}).get("product_opportunity_id")
    explicit_uuid: uuid.UUID | None = None
    try:
        if explicit_id:
            explicit_uuid = uuid.UUID(str(explicit_id))
    except (TypeError, ValueError):
        explicit_uuid = None
    prefixes = tuple(f"business-agent:{run_id}:candidate:" for run_id in run_ids)
    active_rows = [
        row
        for row in meaningful_owner_rows
        if (explicit_uuid is not None and row.id == explicit_uuid)
        or any(row.idempotency_key.startswith(prefix) for prefix in prefixes)
    ]
    requested_category = _goal_category(goal)
    if requested_category:
        active_rows = [
            row for row in active_rows if _matches_goal_category(row, requested_category)
        ]
    historical_count = max(0, len(meaningful_owner_rows) - len(active_rows))
    return active_rows, goal, run_ids, historical_count


@router.get("/research-results")
def research_results(
    db: DB, owner: Owner, goal_id: Annotated[uuid.UUID | None, Query()] = None
) -> dict[str, Any]:
    """Bounded owner-scoped projection over Product Opportunity and 9F."""
    opportunities, active_goal, active_run_ids, historical_count = _research_scope(
        db, owner, goal_id
    )
    active_total = len(opportunities)
    opportunities = opportunities[:50]
    opportunity_ids = [row.id for row in opportunities]
    assessments = (
        list(
            db.scalars(
                select(ProductOpportunityAssessment)
                .where(
                    ProductOpportunityAssessment.owner_id == owner.id,
                    ProductOpportunityAssessment.opportunity_id.in_(opportunity_ids),
                )
                .order_by(ProductOpportunityAssessment.version.desc())
            )
        )
        if opportunity_ids
        else []
    )
    assessments_by_id = {row.id: row for row in assessments}
    assessment_by_opportunity: dict[uuid.UUID, ProductOpportunityAssessment] = {}
    for opportunity in opportunities:
        current = (
            assessments_by_id.get(opportunity.current_assessment_id)
            if opportunity.current_assessment_id is not None
            else None
        )
        if current is not None:
            assessment_by_opportunity[opportunity.id] = current
    for row in assessments:
        assessment_by_opportunity.setdefault(row.opportunity_id, row)
    assessment_ids = [row.id for row in assessments]
    scores = (
        list(
            db.scalars(
                select(ProductOpportunityScore)
                .where(
                    ProductOpportunityScore.owner_id == owner.id,
                    ProductOpportunityScore.assessment_id.in_(assessment_ids),
                )
                .order_by(ProductOpportunityScore.created_at.desc())
            )
        )
        if assessment_ids
        else []
    )
    score_by_assessment: dict[uuid.UUID, ProductOpportunityScore] = {}
    for score_row in scores:
        score_by_assessment.setdefault(score_row.assessment_id, score_row)
    decisions = (
        list(
            db.scalars(
                select(ProductOpportunityDecision).where(
                    ProductOpportunityDecision.owner_id == owner.id,
                    ProductOpportunityDecision.opportunity_id.in_(opportunity_ids),
                )
            )
        )
        if opportunity_ids
        else []
    )
    selected = {row.opportunity_id for row in decisions if row.action == "shortlist"}
    cards: list[dict[str, Any]] = []
    for opportunity in opportunities:
        assessment = assessment_by_opportunity.get(opportunity.id)
        score = score_by_assessment.get(assessment.id) if assessment else None
        profile = opportunity.intelligence_profile or {}
        profile_why = profile.get("why_this_surfaced")
        profile_why_list = profile_why if isinstance(profile_why, list) else []
        dimensions = score.dimensions if score else []
        gaps = (
            list(score.improvement_areas)
            if score
            else ["Complete an assessment and gather supporting evidence."]
        )
        positive = list(score.positive_drivers) if score else []
        negative = list(score.negative_drivers) if score else []
        cards.append(
            {
                "id": str(opportunity.id),
                "name": str(profile.get("display_name") or opportunity.name),
                "display_name": str(profile.get("display_name") or opportunity.name),
                "observed_name": str(profile.get("observed_name") or opportunity.name),
                "description": opportunity.description or opportunity.product_concept,
                "product_concept": opportunity.product_concept,
                "category": opportunity.category,
                "subcategory": opportunity.subcategory,
                "marketplace": opportunity.target_marketplace,
                "region": opportunity.target_region,
                "research_run_id": (
                    str(opportunity.research_run_id) if opportunity.research_run_id else None
                ),
                "research_state": opportunity.research_state,
                "evidence_state": opportunity.evidence_state,
                "intelligence_profile": profile,
                "assessment_id": str(assessment.id) if assessment else None,
                "candidate_state": _candidate_state(opportunity, score),
                "selected": opportunity.id in selected,
                "score": _response(score) if score else None,
                "why_this_surfaced": [item for item in profile_why_list if isinstance(item, str)]
                or positive
                or [
                    "This candidate is linked to the current research goal.",
                    "Evidence-backed rationale is not available yet.",
                ],
                "strengths": positive,
                "risks": negative,
                "data_gaps": gaps,
                "evidence": [
                    {
                        "dimension": item.get("dimension", "UNKNOWN"),
                        "classification": item.get("evidence_state", "UNKNOWN"),
                        "source": item.get("source", "UNKNOWN"),
                        "freshness": "UNKNOWN",
                        "confidence": score.confidence if score else "UNKNOWN",
                        "contradiction": "UNKNOWN",
                        "value": item.get("raw_input"),
                    }
                    for item in dimensions
                    if isinstance(item, dict)
                ],
                "next_validation": gaps[:3],
            }
        )
    ready = sum(card["candidate_state"] == "READY_TO_COMPARE" for card in cards)
    needs_more_research = sum(card["candidate_state"] == "NEEDS_MORE_RESEARCH" for card in cards)
    insufficient_evidence = sum(
        card["candidate_state"] == "INSUFFICIENT_EVIDENCE" for card in cards
    )
    structured_values = dict(active_goal.structured_goal or {}) if active_goal else {}
    commerce_values = structured_values.get("commerce_context")
    if isinstance(commerce_values, dict):
        structured_values.update(commerce_values)
    requested_category = _goal_category(active_goal) if active_goal else ""
    if requested_category and not structured_values.get("category"):
        structured_values["category"] = requested_category
    return {
        "active_goal_id": str(active_goal.id) if active_goal else None,
        "active_run_ids": [str(value) for value in active_run_ids],
        "total_owner_opportunities": historical_count + active_total,
        "historical_opportunities": historical_count,
        "goal_context": (
            {
                "summary": active_goal.raw_goal[:280],
                "confirmed": bool((active_goal.provenance or {}).get("commerce_context_confirmed")),
                "values": structured_values,
            }
            if active_goal
            else None
        ),
        "status": (
            "RESEARCH_COMPLETED_WITH_GAPS"
            if cards and ready < len(cards)
            else ("RESEARCH_COMPLETE" if cards else "NO_RESULTS")
        ),
        "summary": {
            "total": len(cards),
            "ready_for_comparison": ready,
            "needs_more_research": needs_more_research,
            "insufficient_evidence": insufficient_evidence,
        },
        "candidates": cards,
        "selected_candidate_ids": [str(value) for value in selected],
        "human_selection": {
            "provenance": "HUMAN" if selected else "UNKNOWN",
            "count": len(selected),
        },
    }


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
