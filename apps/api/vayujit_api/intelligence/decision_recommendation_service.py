"""PR-6C controlled recommendation and explicit human-decision authorities."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.decision_recommendation_models import (
    HUMAN_DECISIONS,
    RECOMMENDATION_POLICY_VERSION,
    HumanDecision,
    RecommendationAssessment,
)
from vayujit_api.intelligence.decision_synthesis_models import DecisionSynthesisSnapshot
from vayujit_api.intelligence.decision_synthesis_service import (
    create_synthesis,
    latest_synthesis,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _opportunity(db: Session, owner: User, opportunity_id: uuid.UUID) -> ProductOpportunity:
    row = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "Product opportunity not found.")
    return row


def _goal(db: Session, owner: User, goal_id: uuid.UUID | None) -> BusinessAgentGoal | None:
    if goal_id is not None:
        row = db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.id == goal_id, BusinessAgentGoal.owner_id == owner.id
            )
        )
        if row is None:
            raise HTTPException(404, "Business Agent goal not found.")
        return row
    return db.scalar(
        select(BusinessAgentGoal)
        .where(BusinessAgentGoal.owner_id == owner.id)
        .order_by(BusinessAgentGoal.updated_at.desc(), BusinessAgentGoal.created_at.desc())
    )


def _synthesis(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str,
    synthesis_id: uuid.UUID | None,
    goal_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
) -> DecisionSynthesisSnapshot:
    _opportunity(db, owner, opportunity_id)
    if synthesis_id is not None:
        row = db.scalar(
            select(DecisionSynthesisSnapshot).where(
                DecisionSynthesisSnapshot.id == synthesis_id,
                DecisionSynthesisSnapshot.owner_id == owner.id,
                DecisionSynthesisSnapshot.opportunity_id == opportunity_id,
            )
        )
        if row is None:
            raise HTTPException(404, "Decision synthesis is not available in the owner scope.")
        if row.decision_target != target.upper():
            raise HTTPException(409, "Recommendation target does not match the synthesis target.")
        if supplier_id is not None and row.supplier_id != supplier_id:
            raise HTTPException(409, "Recommendation supplier does not match the synthesis scope.")
        return row
    row = latest_synthesis(db, owner, opportunity_id, target)
    if row is not None and (supplier_id is None or row.supplier_id == supplier_id):
        return row
    # The POST recommendation action is the explicit boundary that may create
    # the missing PR-6B snapshot. It still delegates all readiness work to PR-6A.
    return create_synthesis(
        db,
        owner,
        opportunity_id,
        target=target,
        goal_id=goal_id,
        supplier_id=supplier_id,
    )


def recommendation_policy(target: str) -> dict[str, Any]:
    target = target.upper()
    if target not in {
        "PRODUCT_SELECTION",
        "SUPPLIER_SELECTION",
        "COMMERCIAL_ASSESSMENT",
        "LAUNCH_DECISION",
    }:
        raise HTTPException(422, "Unsupported decision target.")
    return {
        "version": RECOMMENDATION_POLICY_VERSION,
        "target": target,
        "eligible_postures": ["READY_FOR_HUMAN_DECISION"],
        "positive_state": (
            "READY_FOR_REVIEW" if target == "LAUNCH_DECISION" else "SYSTEM_SUPPORTS_PROCEEDING"
        ),
        "human_review_required": True,
        "decision_values": list(HUMAN_DECISIONS),
        "external_actions": [],
    }


def _recommendation_state(synthesis: DecisionSynthesisSnapshot, target: str) -> str:
    if synthesis.posture != "READY_FOR_HUMAN_DECISION":
        return "NOT_ELIGIBLE"
    return str(recommendation_policy(target)["positive_state"])


def serialize_recommendation(row: RecommendationAssessment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "decision_evidence_snapshot_id": str(row.decision_evidence_snapshot_id),
        "synthesis_id": str(row.synthesis_id),
        "decision_target": row.decision_target,
        "recommendation_policy_version": row.recommendation_policy_version,
        "recommendation_state": row.recommendation_state,
        "recommendation_eligible": row.recommendation_state
        in {"SYSTEM_SUPPORTS_PROCEEDING", "SYSTEM_SUPPORTS_NOT_PROCEEDING"},
        "supporting_reasons": row.supporting_reasons,
        "counter_reasons": row.counter_reasons,
        "warnings": row.warnings,
        "unknowns": row.unknowns,
        "contradictions": row.contradictions,
        "limitations": row.limitations,
        "trust_summary": row.trust_summary,
        "economics_summary": row.economics_summary,
        "capital_fit_state": row.capital_fit_state,
        "human_review_required": row.human_review_required,
        "input_fingerprint": row.input_fingerprint,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at.isoformat(),
        "explanation": row.explanation,
        "policy": recommendation_policy(row.decision_target),
        "external_writes": [],
    }


def serialize_human_decision(row: HumanDecision) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "actor_id": str(row.actor_id),
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "opportunity_id": str(row.opportunity_id),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "decision_evidence_snapshot_id": str(row.decision_evidence_snapshot_id),
        "synthesis_id": str(row.synthesis_id),
        "recommendation_id": str(row.recommendation_id),
        "supersedes_decision_id": (
            str(row.supersedes_decision_id) if row.supersedes_decision_id else None
        ),
        "decision_target": row.decision_target,
        "decision": row.decision,
        "reason": row.reason,
        "provenance": row.provenance,
        "actor_type": "HUMAN",
        "context_fingerprint": row.context_fingerprint,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at.isoformat(),
        "external_writes": [],
    }


def create_recommendation(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str = "COMMERCIAL_ASSESSMENT",
    synthesis_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> RecommendationAssessment:
    target = target.upper()
    policy = recommendation_policy(target)
    synthesis = _synthesis(
        db,
        owner,
        opportunity_id,
        target=target,
        synthesis_id=synthesis_id,
        goal_id=goal_id,
        supplier_id=supplier_id,
    )
    if goal_id is not None and synthesis.goal_id not in {None, goal_id}:
        raise HTTPException(409, "Recommendation goal does not match the synthesis scope.")
    fingerprint = _fingerprint(
        {
            "owner_id": str(owner.id),
            "opportunity_id": str(opportunity_id),
            "supplier_id": str(synthesis.supplier_id) if synthesis.supplier_id else None,
            "target": target,
            "synthesis_id": str(synthesis.id),
            "synthesis_fingerprint": synthesis.input_fingerprint,
            "policy": policy["version"],
        }
    )
    existing = db.scalar(
        select(RecommendationAssessment).where(
            RecommendationAssessment.owner_id == owner.id,
            RecommendationAssessment.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    reasons = _list(synthesis.reasons)
    supporting = [item for item in reasons if not bool(item.get("blocking"))]
    counter = _list(synthesis.blockers) + _list(synthesis.contradictions)
    counter += _list(synthesis.warnings) + _list(synthesis.unknowns)
    state = _recommendation_state(synthesis, target)
    row = RecommendationAssessment(
        owner_id=owner.id,
        goal_id=synthesis.goal_id,
        opportunity_id=opportunity_id,
        supplier_id=synthesis.supplier_id,
        decision_evidence_snapshot_id=synthesis.decision_evidence_snapshot_id,
        synthesis_id=synthesis.id,
        decision_target=target,
        recommendation_policy_version=policy["version"],
        recommendation_state=state,
        supporting_reasons=supporting,
        counter_reasons=counter,
        warnings=_list(synthesis.warnings),
        unknowns=_list(synthesis.unknowns),
        contradictions=_list(synthesis.contradictions),
        limitations=_list(synthesis.limitations),
        trust_summary=synthesis.trust_summary,
        economics_summary=synthesis.economics_summary,
        capital_fit_state=synthesis.capital_fit_state,
        human_review_required=True,
        input_fingerprint=fingerprint,
        idempotency_key=idempotency_key or f"recommendation:{fingerprint}",
        created_at=_now(),
        explanation=(
            "The system supports human review for this bounded evidence state; "
            "it does not approve, launch, or guarantee an outcome."
            if state != "NOT_ELIGIBLE"
            else (
                "The canonical synthesis is not eligible for a positive recommendation; "
                "review the blockers and evidence gaps."
            )
        ),
        notes="PR-6C immutable advisory assessment; not a human decision or external action.",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(RecommendationAssessment).where(
                RecommendationAssessment.owner_id == owner.id,
                RecommendationAssessment.input_fingerprint == fingerprint,
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(row)
    return row


def latest_recommendation(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    target: str = "COMMERCIAL_ASSESSMENT",
    supplier_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
) -> RecommendationAssessment | None:
    query = select(RecommendationAssessment).where(
        RecommendationAssessment.owner_id == owner.id,
        RecommendationAssessment.opportunity_id == opportunity_id,
        RecommendationAssessment.decision_target == target.upper(),
    )
    if supplier_id is not None:
        query = query.where(RecommendationAssessment.supplier_id == supplier_id)
    if goal_id is not None:
        query = query.where(RecommendationAssessment.goal_id == goal_id)
    return db.scalars(query.order_by(RecommendationAssessment.created_at.desc())).first()


def recommendation_history(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    target: str = "COMMERCIAL_ASSESSMENT",
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(RecommendationAssessment)
            .where(
                RecommendationAssessment.owner_id == owner.id,
                RecommendationAssessment.opportunity_id == opportunity_id,
                RecommendationAssessment.decision_target == target.upper(),
            )
            .order_by(RecommendationAssessment.created_at.desc())
        )
    )
    return [serialize_recommendation(row) for row in rows]


def _resolve_recommendation(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str,
    recommendation_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
) -> RecommendationAssessment:
    if recommendation_id is not None:
        row = db.scalar(
            select(RecommendationAssessment).where(
                RecommendationAssessment.id == recommendation_id,
                RecommendationAssessment.owner_id == owner.id,
                RecommendationAssessment.opportunity_id == opportunity_id,
            )
        )
    else:
        row = latest_recommendation(db, owner, opportunity_id, target, supplier_id)
    if row is None:
        raise HTTPException(409, "Create or review a recommendation assessment before deciding.")
    if row.decision_target != target.upper():
        raise HTTPException(409, "Human decision target does not match the recommendation.")
    if supplier_id is not None and row.supplier_id != supplier_id:
        raise HTTPException(409, "Human decision supplier does not match the recommendation.")
    return row


def create_human_decision(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    *,
    target: str,
    decision: str,
    recommendation_id: uuid.UUID | None = None,
    synthesis_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    reason: str = "",
    idempotency_key: str,
    provenance: str = "HUMAN",
) -> HumanDecision:
    if decision not in HUMAN_DECISIONS:
        raise HTTPException(422, "Unsupported human decision.")
    if provenance != "HUMAN":
        raise HTTPException(403, "Only authenticated human actions may create a HUMAN decision.")
    _opportunity(db, owner, opportunity_id)
    existing = db.scalar(
        select(HumanDecision).where(
            HumanDecision.owner_id == owner.id,
            HumanDecision.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        same = (
            existing.opportunity_id == opportunity_id
            and existing.decision_target == target.upper()
            and existing.decision == decision
            and existing.supplier_id == supplier_id
        )
        if not same:
            raise HTTPException(409, "Idempotency key is already bound to another decision.")
        return existing
    recommendation = _resolve_recommendation(
        db,
        owner,
        opportunity_id,
        target=target,
        recommendation_id=recommendation_id,
        supplier_id=supplier_id,
    )
    if synthesis_id is not None and recommendation.synthesis_id != synthesis_id:
        raise HTTPException(
            409, "Human decision synthesis does not match the reviewed recommendation."
        )
    if goal_id is not None and recommendation.goal_id not in {None, goal_id}:
        raise HTTPException(409, "Human decision goal does not match the reviewed recommendation.")
    if target.upper() == "SUPPLIER_SELECTION" and recommendation.supplier_id is None:
        raise HTTPException(409, "A supplier-scoped human decision requires an explicit supplier.")
    latest_query = select(DecisionSynthesisSnapshot).where(
        DecisionSynthesisSnapshot.owner_id == owner.id,
        DecisionSynthesisSnapshot.opportunity_id == opportunity_id,
        DecisionSynthesisSnapshot.decision_target == target.upper(),
        DecisionSynthesisSnapshot.supplier_id == recommendation.supplier_id,
    )
    latest = db.scalars(latest_query.order_by(DecisionSynthesisSnapshot.created_at.desc())).first()
    if latest is not None and latest.id != recommendation.synthesis_id:
        raise HTTPException(
            409,
            {
                "code": "STALE_REVIEW_CONTEXT",
                "message": (
                    "Evidence changed after this recommendation; refresh the review "
                    "before deciding."
                ),
                "recommendation_synthesis_id": str(recommendation.synthesis_id),
                "latest_synthesis_id": str(latest.id),
            },
        )
    if (
        decision == "PROCEED"
        and recommendation.recommendation_state != "SYSTEM_SUPPORTS_PROCEEDING"
    ):
        raise HTTPException(
            409,
            "PROCEED is unavailable because the canonical recommendation is not eligible "
            "for proceeding.",
        )
    prior = db.scalars(
        select(HumanDecision)
        .where(
            HumanDecision.owner_id == owner.id,
            HumanDecision.opportunity_id == opportunity_id,
            HumanDecision.decision_target == target.upper(),
            HumanDecision.supplier_id == recommendation.supplier_id,
        )
        .order_by(HumanDecision.created_at.desc())
    ).first()
    row = HumanDecision(
        owner_id=owner.id,
        actor_id=owner.id,
        goal_id=recommendation.goal_id,
        opportunity_id=opportunity_id,
        supplier_id=recommendation.supplier_id,
        decision_evidence_snapshot_id=recommendation.decision_evidence_snapshot_id,
        synthesis_id=recommendation.synthesis_id,
        recommendation_id=recommendation.id,
        supersedes_decision_id=prior.id if prior else None,
        decision_target=target.upper(),
        decision=decision,
        reason=reason,
        provenance="HUMAN",
        context_fingerprint=recommendation.input_fingerprint,
        idempotency_key=idempotency_key,
        created_at=_now(),
        external_writes=[],
    )
    db.add(row)
    try:
        db.flush()
        record_event(
            db,
            actor_id=owner.id,
            action="intelligence.human_decision_recorded",
            entity_type="human_decision",
            entity_id=row.id,
            metadata={
                "opportunity_id": str(opportunity_id),
                "decision_target": target.upper(),
                "decision": decision,
                "provenance": "HUMAN",
            },
            idempotency_key=f"human-decision:{idempotency_key}",
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(HumanDecision).where(
                HumanDecision.owner_id == owner.id,
                HumanDecision.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing
    db.refresh(row)
    return row


def latest_human_decision(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    target: str = "COMMERCIAL_ASSESSMENT",
    supplier_id: uuid.UUID | None = None,
    goal_id: uuid.UUID | None = None,
) -> HumanDecision | None:
    query = select(HumanDecision).where(
        HumanDecision.owner_id == owner.id,
        HumanDecision.opportunity_id == opportunity_id,
        HumanDecision.decision_target == target.upper(),
    )
    if supplier_id is not None:
        query = query.where(HumanDecision.supplier_id == supplier_id)
    if goal_id is not None:
        query = query.where(HumanDecision.goal_id == goal_id)
    return db.scalars(query.order_by(HumanDecision.created_at.desc())).first()


def human_decision_history(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    target: str = "COMMERCIAL_ASSESSMENT",
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(HumanDecision)
            .where(
                HumanDecision.owner_id == owner.id,
                HumanDecision.opportunity_id == opportunity_id,
                HumanDecision.decision_target == target.upper(),
            )
            .order_by(HumanDecision.created_at.desc())
        )
    )
    return [serialize_human_decision(row) for row in rows]


def project_recommendation_and_decision(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    target: str = "COMMERCIAL_ASSESSMENT",
    *,
    goal_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    recommendation = latest_recommendation(db, owner, opportunity_id, target, goal_id=goal_id)
    decision = latest_human_decision(db, owner, opportunity_id, target, goal_id=goal_id)
    return {
        "recommendation": serialize_recommendation(recommendation) if recommendation else None,
        "human_decision": serialize_human_decision(decision) if decision else None,
        "human_review_required": True,
        "external_writes": [],
    }
