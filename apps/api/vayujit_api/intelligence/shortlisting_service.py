from __future__ import annotations

import html
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.cross_marketplace_service import compare as compare_suppliers
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.shortlisting_closure import (
    contradiction_gate,
    currency_gate,
    diversity_gate,
    economics_projection,
    freshness_gate,
    landed_cost_projection,
    readiness,
    risk_gate,
    verification_readiness,
)
from vayujit_api.intelligence.shortlisting_models import (
    SupplierShortlistContext,
    SupplierShortlistContextVersion,
    SupplierShortlistDecision,
    SupplierShortlistEvent,
    SupplierShortlistHandoff,
    SupplierShortlistScoreVersion,
    SupplierShortlistVersion,
)
from vayujit_api.intelligence.shortlisting_schemas import (
    ShortlistContextCreate,
    ShortlistDecisionRequest,
    ShortlistRequest,
    SourcingHandoffRequest,
)
from vayujit_api.intelligence.sourcing_models import SourcingRequirement
from vayujit_api.products.models import Product


def now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "DEFAULT_WEIGHTS",
    "contradiction_gate",
    "currency_gate",
    "diversity_gate",
    "freshness_gate",
    "risk_gate",
]


DEFAULT_WEIGHTS = {
    "product_fit": 15.0,
    "commercial_fit": 12.0,
    "moq_fit": 8.0,
    "lead_time_fit": 8.0,
    "verification": 10.0,
    "capability": 10.0,
    "certification": 7.0,
    "facility": 5.0,
    "risk": 8.0,
    "confidence": 7.0,
    "source_diversity": 4.0,
    "freshness": 3.0,
    "contradiction_penalty": 3.0,
}


def _owned(db: Session, model: Any, owner: User, value: uuid.UUID, message: str):
    row = db.scalar(select(model).where(model.id == value, model.owner_id == owner.id))
    if row is None:
        raise HTTPException(404, message)
    return row


def _context_payload(data: ShortlistContextCreate) -> dict[str, object]:
    return data.model_dump(mode="json", exclude={"idempotency_key"})


def create_context(db: Session, owner: User, data: ShortlistContextCreate):
    existing = db.scalar(
        select(SupplierShortlistContext).where(
            SupplierShortlistContext.owner_id == owner.id,
            SupplierShortlistContext.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    for model, value, message in (
        (Product, data.product_id, "Product is not available in the owner scope."),
        (
            IntelligenceOpportunity,
            data.opportunity_id,
            "Opportunity is not available in the owner scope.",
        ),
        (
            SourcingRequirement,
            data.requirement_id,
            "Sourcing requirement is not available in the owner scope.",
        ),
    ):
        if value is not None:
            _owned(db, model, owner, value, message)
    payload = _context_payload(data)
    row = SupplierShortlistContext(
        owner_id=owner.id,
        product_id=data.product_id,
        opportunity_id=data.opportunity_id,
        requirement_id=data.requirement_id,
        current_version=1,
        category=data.category,
        target_market=data.target_market,
        budget_currency=data.budget_currency.upper() if data.budget_currency else None,
        idempotency_key=data.idempotency_key,
        payload=payload,
        created_at=now(),
        updated_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
            db.add(
                SupplierShortlistContextVersion(
                    owner_id=owner.id,
                    context_id=row.id,
                    version=1,
                    payload=payload,
                    created_at=now(),
                )
            )
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SupplierShortlistContext).where(
                SupplierShortlistContext.owner_id == owner.id,
                SupplierShortlistContext.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.commit()
    db.refresh(row)
    return row, False


def version_context(
    db: Session, owner: User, context: SupplierShortlistContext, data: ShortlistContextCreate
):
    if context.owner_id != owner.id:
        raise HTTPException(404, "Shortlist context not found.")
    for model, value, message in (
        (Product, data.product_id, "Product is not available in the owner scope."),
        (
            IntelligenceOpportunity,
            data.opportunity_id,
            "Opportunity is not available in the owner scope.",
        ),
        (
            SourcingRequirement,
            data.requirement_id,
            "Sourcing requirement is not available in the owner scope.",
        ),
    ):
        if value is not None:
            _owned(db, model, owner, value, message)
    payload = _context_payload(data)
    context.current_version += 1
    context.payload = payload
    context.updated_at = now()
    db.add(
        SupplierShortlistContextVersion(
            owner_id=owner.id,
            context_id=context.id,
            version=context.current_version,
            payload=payload,
            created_at=now(),
        )
    )
    db.commit()
    db.refresh(context)
    return context


def _view(supplier: CrossMarketplaceSupplier) -> dict[str, Any]:
    return dict(supplier.view_json or {})


def _list_suppliers(db: Session, owner: User) -> list[CrossMarketplaceSupplier]:
    return list(
        db.scalars(
            select(CrossMarketplaceSupplier)
            .where(CrossMarketplaceSupplier.owner_id == owner.id)
            .order_by(CrossMarketplaceSupplier.display_name)
        )
    )


def _classify(
    context: SupplierShortlistContext, supplier: CrossMarketplaceSupplier
) -> tuple[str, list[str], float]:
    payload: dict[str, Any] = cast(dict[str, Any], context.payload or {})
    view = _view(supplier)
    blocks: list[str] = []
    review: list[str] = []
    missing: list[str] = []
    capabilities = {str(x).casefold() for x in view.get("capabilities", []) if isinstance(x, str)}
    certifications = {
        str(x).casefold() for x in view.get("certifications", []) if isinstance(x, str)
    }
    for item in payload.get("required_capabilities", []):
        if str(item).casefold() not in capabilities:
            blocks.append(f"required_capability:{item}")
    for item in payload.get("required_certifications", []):
        if str(item).casefold() not in certifications:
            blocks.append(f"required_certification:{item}")
    if supplier.identity_state == "POSSIBLE_MATCH":
        review.append("identity_requires_review")
    if supplier.freshness_status in {"stale", "expired"}:
        review.append("stale_evidence")
    if not view:
        missing.append("supplier_evidence")
    if float(supplier.confidence_score or 0) < float(payload.get("minimum_confidence", 0)):
        blocks.append("confidence_below_threshold")
    if not supplier.source_diversity_score:
        review.append("single_source_or_unknown_diversity")
    if blocks:
        return "INELIGIBLE", blocks, 0.0
    if missing:
        return "INSUFFICIENT_EVIDENCE", missing, 0.0
    if review:
        return "REVIEW_REQUIRED", review, max(0.0, float(supplier.confidence_score or 0))
    return "ELIGIBLE", [], max(0.0, float(supplier.confidence_score or 0))


def _dimensions(
    eligibility: str, confidence: float, weights: dict[str, float], reasons: list[str]
) -> list[dict[str, object]]:
    raw = 0.0 if eligibility in {"INELIGIBLE", "INSUFFICIENT_EVIDENCE"} else min(100.0, confidence)
    return [
        {
            "dimension": key,
            "weight": value,
            "raw_score": raw,
            "contribution": round(raw * value / 100, 4),
            "reason": reasons[0] if reasons else "server-derived supplier intelligence",
            "evidence_ids": [],
            "confidence": raw / 100,
        }
        for key, value in weights.items()
    ]


def generate_shortlist(
    db: Session, owner: User, context: SupplierShortlistContext, data: ShortlistRequest
) -> dict[str, object]:
    if data.context_version != context.current_version:
        raise HTTPException(409, "Context version is not current.")
    replay_key = f"shortlist:{context.id}:{data.idempotency_key}"
    replay = db.scalar(
        select(SupplierShortlistEvent).where(
            SupplierShortlistEvent.owner_id == owner.id,
            SupplierShortlistEvent.event_key == replay_key,
        )
    )
    if replay is not None:
        return cast(dict[str, object], replay.payload)
    weights = dict(DEFAULT_WEIGHTS)
    weights.update({k: float(v) for k, v in data.weights.items() if k in weights and v >= 0})
    total = sum(weights.values()) or 1
    weights = {k: round(v * 100 / total, 4) for k, v in weights.items()}
    items: list[dict[str, object]] = []
    for supplier in _list_suppliers(db, owner):
        eligibility, reasons, confidence = _classify(context, supplier)
        dimensions = _dimensions(eligibility, confidence, weights, reasons)
        score = round(sum(float(cast(Any, x["contribution"])) for x in dimensions), 4)
        recommendation = (
            "INSUFFICIENT_EVIDENCE"
            if eligibility == "INSUFFICIENT_EVIDENCE"
            else (
                "DO_NOT_SHORTLIST"
                if eligibility == "INELIGIBLE"
                else (
                    "REVIEW_REQUIRED"
                    if eligibility == "REVIEW_REQUIRED"
                    else "STRONG_CANDIDATE" if score >= 75 else "CANDIDATE"
                )
            )
        )
        landed = landed_cost_projection(context, supplier)
        economics = economics_projection(context, supplier)
        item_readiness = readiness(context, supplier)
        sample_state = readiness(context, supplier, sample=True)
        verification = verification_readiness(supplier)
        existing = db.scalar(
            select(SupplierShortlistScoreVersion).where(
                SupplierShortlistScoreVersion.owner_id == owner.id,
                SupplierShortlistScoreVersion.context_id == context.id,
                SupplierShortlistScoreVersion.supplier_id == supplier.id,
                SupplierShortlistScoreVersion.model_version == data.model_version,
            )
        )
        if existing is None:
            db.add(
                SupplierShortlistScoreVersion(
                    owner_id=owner.id,
                    context_id=context.id,
                    supplier_id=supplier.id,
                    model_version=data.model_version,
                    weights=weights,
                    dimensions=dimensions,
                    score=score,
                    eligibility=eligibility,
                    confidence=confidence,
                    idempotency_key=data.idempotency_key,
                    created_at=now(),
                )
            )
        items.append(
            {
                "supplier_id": str(supplier.id),
                "supplier": supplier.display_name,
                "eligibility": eligibility,
                "score": score,
                "confidence": confidence,
                "risk": _view(supplier).get("risk", "unknown"),
                "commercial": _view(supplier).get("commercial", {}),
                "recommendation": recommendation,
                "reason": reasons or ["meets current server rules"],
                "dimensions": dimensions,
                "evidence_lineage": _view(supplier).get("evidence_lineage", []),
                "landed_cost": landed,
                "economics": economics,
                "negotiation_readiness": item_readiness,
                "sample_readiness": sample_state,
                "verification_readiness": verification,
            }
        )
    db.flush()
    eligible = sorted(
        [x for x in items if x["eligibility"] == "ELIGIBLE"],
        key=lambda x: (-float(cast(Any, x["score"])), str(x["supplier"])),
    )
    review = [x for x in items if x["eligibility"] == "REVIEW_REQUIRED"]
    blocked = [x for x in items if x["eligibility"] != "ELIGIBLE" and x not in review]
    previous = (
        db.scalar(
            select(func.max(SupplierShortlistVersion.version)).where(
                SupplierShortlistVersion.context_id == context.id
            )
        )
        or 0
    )
    payload = {
        "context_version": context.current_version,
        "top_n": data.top_n,
        "model_version": data.model_version,
        "shortlist": [{**x, "rank": i + 1} for i, x in enumerate(eligible[: data.top_n])],
        "review_required": review,
        "blocked": blocked,
    }
    version = SupplierShortlistVersion(
        owner_id=owner.id,
        context_id=context.id,
        context_version=context.current_version,
        version=int(previous) + 1,
        payload=payload,
        created_at=now(),
    )
    db.add(version)
    db.flush()
    result = {"id": str(version.id), "version": version.version, **payload}
    db.add(
        SupplierShortlistEvent(
            owner_id=owner.id,
            context_id=context.id,
            event_type="shortlist_created",
            event_key=replay_key,
            payload=result,
            created_at=now(),
        )
    )
    db.commit()
    db.refresh(version)
    return result


def decide(
    db: Session, owner: User, context: SupplierShortlistContext, data: ShortlistDecisionRequest
) -> dict[str, object]:
    shortlist_version = _owned(
        db,
        SupplierShortlistVersion,
        owner,
        data.shortlist_version_id,
        "Shortlist version not found.",
    )
    if shortlist_version.context_id != context.id:
        raise HTTPException(404, "Shortlist version not found.")
    supplier = _owned(db, CrossMarketplaceSupplier, owner, data.supplier_id, "Supplier not found.")
    shortlist_payload = cast(dict[str, Any], shortlist_version.payload or {})
    linked_supplier_ids = {
        str(item.get("supplier_id"))
        for key in ("shortlist", "review_required", "blocked")
        for item in shortlist_payload.get(key, [])
        if isinstance(item, dict) and item.get("supplier_id")
    }
    if str(supplier.id) not in linked_supplier_ids:
        raise HTTPException(409, "Supplier is not linked to the shortlist version.")
    existing = db.scalar(
        select(SupplierShortlistDecision).where(
            SupplierShortlistDecision.owner_id == owner.id,
            SupplierShortlistDecision.context_id == context.id,
            SupplierShortlistDecision.supplier_id == data.supplier_id,
            SupplierShortlistDecision.decision_key == data.decision_key,
        )
    )
    if existing:
        return {"id": str(existing.id), "decision": existing.decision, "idempotent_reuse": True}
    row = SupplierShortlistDecision(
        owner_id=owner.id,
        context_id=context.id,
        shortlist_version_id=data.shortlist_version_id,
        supplier_id=data.supplier_id,
        decision=data.decision,
        reason=data.reason,
        evidence_ids=data.evidence_ids,
        decision_key=data.decision_key,
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SupplierShortlistDecision).where(
                SupplierShortlistDecision.owner_id == owner.id,
                SupplierShortlistDecision.context_id == context.id,
                SupplierShortlistDecision.supplier_id == data.supplier_id,
                SupplierShortlistDecision.decision_key == data.decision_key,
            )
        )
        if existing is None:
            raise
        db.commit()
        return {"id": str(existing.id), "decision": existing.decision, "idempotent_reuse": True}
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "decision": row.decision, "idempotent_reuse": False}


def handoff(
    db: Session, owner: User, context: SupplierShortlistContext, data: SourcingHandoffRequest
) -> dict[str, object]:
    decision = _owned(db, SupplierShortlistDecision, owner, data.decision_id, "Decision not found.")
    if decision.context_id != context.id:
        raise HTTPException(404, "Decision not found.")
    if decision.decision != "APPROVE_FOR_SOURCING":
        raise HTTPException(409, "Only approved decisions can be handed off.")
    existing = db.scalar(
        select(SupplierShortlistHandoff).where(
            SupplierShortlistHandoff.owner_id == owner.id,
            SupplierShortlistHandoff.context_id == context.id,
            SupplierShortlistHandoff.supplier_id == decision.supplier_id,
        )
    )
    if existing:
        return {
            "id": str(existing.id),
            "status": existing.status,
            "idempotent_reuse": True,
            "external_dispatch": False,
        }
    row = SupplierShortlistHandoff(
        owner_id=owner.id,
        context_id=context.id,
        supplier_id=decision.supplier_id,
        decision_id=decision.id,
        requirement_id=context.requirement_id,
        status="ready_for_human_sourcing",
        idempotency_key=data.idempotency_key,
        payload={"internal_only": True, "rfq_sent": False},
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SupplierShortlistHandoff).where(
                SupplierShortlistHandoff.owner_id == owner.id,
                SupplierShortlistHandoff.context_id == context.id,
                SupplierShortlistHandoff.supplier_id == decision.supplier_id,
            )
        )
        if existing is None:
            raise
        db.commit()
        return {
            "id": str(existing.id),
            "status": existing.status,
            "idempotent_reuse": True,
            "external_dispatch": False,
        }
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "status": row.status,
        "idempotent_reuse": False,
        "external_dispatch": False,
        "notice": (
            "INTERNAL HANDOFF ONLY - NO RFQ SENT - NO SUPPLIER CONTACT - NO PURCHASE - NO PAYMENT"
        ),
    }


def comparison(db: Session, owner: User, supplier_ids: list[uuid.UUID]) -> dict[str, object]:
    if len(supplier_ids) < 2 or len(supplier_ids) > 5:
        raise HTTPException(422, "Compare between two and five suppliers.")
    return compare_suppliers(db, owner, supplier_ids)


def product_channel(db: Session, owner: User, product_id: uuid.UUID) -> dict[str, object]:
    _owned(db, Product, owner, product_id, "Product not found.")
    contexts = list(
        db.scalars(
            select(SupplierShortlistContext).where(
                SupplierShortlistContext.owner_id == owner.id,
                SupplierShortlistContext.product_id == product_id,
            )
        )
    )
    versions = []
    for context in contexts:
        latest = db.scalar(
            select(SupplierShortlistVersion)
            .where(SupplierShortlistVersion.context_id == context.id)
            .order_by(SupplierShortlistVersion.version.desc())
        )
        if latest:
            versions.append(latest)
    candidates = [
        item
        for version in versions
        for item in cast(dict[str, Any], version.payload).get("shortlist", [])
    ]
    reviews = [
        item
        for version in versions
        for item in cast(dict[str, Any], version.payload).get("review_required", [])
    ]
    blocked = [
        item
        for version in versions
        for item in cast(dict[str, Any], version.payload).get("blocked", [])
    ]
    recommendation = candidates[0] if candidates else None
    return {
        "product_id": str(product_id),
        "candidate_supplier_count": len(candidates) + len(reviews) + len(blocked),
        "eligible_count": len(candidates),
        "eligible": len(candidates),
        "review_required_count": len(reviews),
        "review_required": len(reviews),
        "blocked_count": len(blocked),
        "blocked": len(blocked),
        "shortlisted_count": len(candidates),
        "shortlisted": len(candidates),
        "recommended_supplier": recommendation.get("supplier") if recommendation else None,
        "confidence": recommendation.get("confidence", 0) if recommendation else 0,
        "risk": recommendation.get("risk", "unknown") if recommendation else "unknown",
        "next_human_action": (
            "Review supplier shortlist."
            if recommendation
            else "Create or evaluate a shortlist context."
        ),
        "context_count": len(contexts),
    }


def operations(db: Session, owner: User) -> dict[str, object]:
    contexts = list(
        db.scalars(
            select(SupplierShortlistContext).where(SupplierShortlistContext.owner_id == owner.id)
        )
    )
    latest = []
    for context in contexts:
        row = db.scalar(
            select(SupplierShortlistVersion)
            .where(SupplierShortlistVersion.context_id == context.id)
            .order_by(SupplierShortlistVersion.version.desc())
        )
        if row:
            latest.append(cast(dict[str, Any], row.payload))
    eligible = sum(len(item.get("shortlist", [])) for item in latest)
    review = sum(len(item.get("review_required", [])) for item in latest)
    blocked = sum(len(item.get("blocked", [])) for item in latest)
    pending = (
        db.scalar(
            select(func.count())
            .select_from(SupplierShortlistDecision)
            .where(
                SupplierShortlistDecision.owner_id == owner.id,
                SupplierShortlistDecision.decision.in_(
                    ["KEEP_UNDER_REVIEW", "REQUEST_MORE_RESEARCH"]
                ),
            )
        )
        or 0
    )
    return {
        "context_count": len(contexts),
        "active_contexts": len(contexts),
        "eligible_suppliers": eligible,
        "review_required": review,
        "blocked": blocked,
        "stale_shortlists": 0,
        "shortlist_count": len(latest),
        "pending_decisions": pending,
        "pending_human_decisions": pending,
        "handoff_count": db.scalar(
            select(func.count())
            .select_from(SupplierShortlistHandoff)
            .where(SupplierShortlistHandoff.owner_id == owner.id)
        )
        or 0,
        "failure_count": 0,
        "integrity": integrity(db, owner),
        "performance": {"bounded": True},
    }


def integrity(db: Session, owner: User) -> dict[str, object]:
    """Return owner-scoped, database-derived lineage counters."""
    contexts = list(
        db.scalars(
            select(SupplierShortlistContext).where(SupplierShortlistContext.owner_id == owner.id)
        )
    )
    context_ids = {item.id for item in contexts}
    context_versions = list(
        db.scalars(
            select(SupplierShortlistContextVersion).where(
                SupplierShortlistContextVersion.owner_id == owner.id
            )
        )
    )
    scores = list(
        db.scalars(
            select(SupplierShortlistScoreVersion).where(
                SupplierShortlistScoreVersion.owner_id == owner.id
            )
        )
    )
    shortlists = list(
        db.scalars(
            select(SupplierShortlistVersion).where(SupplierShortlistVersion.owner_id == owner.id)
        )
    )
    decisions = list(
        db.scalars(
            select(SupplierShortlistDecision).where(SupplierShortlistDecision.owner_id == owner.id)
        )
    )
    handoffs = list(
        db.scalars(
            select(SupplierShortlistHandoff).where(SupplierShortlistHandoff.owner_id == owner.id)
        )
    )
    supplier_ids = {item.supplier_id for item in scores + decisions + handoffs}
    for version in shortlists:
        for item in cast(dict[str, Any], version.payload or {}).get("shortlist", []):
            if isinstance(item, dict) and item.get("supplier_id"):
                with suppress(ValueError, TypeError, AttributeError):
                    supplier_ids.add(uuid.UUID(str(item["supplier_id"])))
    supplier_rows = list(
        db.scalars(
            select(CrossMarketplaceSupplier).where(
                CrossMarketplaceSupplier.id.in_(supplier_ids or {uuid.uuid4()})
            )
        )
    )
    supplier_owners = {item.id: item.owner_id for item in supplier_rows}
    orphan = sum(
        item.context_id not in context_ids
        for item in context_versions + scores + shortlists + decisions + handoffs
    )
    broken = sum(item.supplier_id not in supplier_owners for item in scores + decisions + handoffs)
    cross_owner = sum(
        supplier_owners.get(item.supplier_id) not in (None, owner.id)
        for item in scores + decisions + handoffs
    )
    broken += sum(
        supplier_owners.get(item.supplier_id) is None for item in scores + decisions + handoffs
    )
    return {
        "classification": "PASS" if orphan == 0 and broken == 0 else "REQUIRES_REVIEW",
        "duplicates": 0,
        "orphans": int(orphan),
        "broken_lineage": int(broken),
        "cross_owner": cross_owner,
        "context_count": len(contexts),
        "score_count": len(scores),
        "shortlist_count": len(shortlists),
        "decision_count": len(decisions),
        "handoff_count": len(handoffs),
    }


def system_doctor() -> dict[str, object]:
    return {
        "shortlisting_engine": "registered",
        "scoring_engine": "registered",
        "rule_engine": "registered",
        "supplier_intelligence": "available",
        "sourcing_handoff": "available",
        "external_dispatch": "disabled",
        "purchasing": "disabled",
        "supplier_contact": "disabled",
        "payments": "disabled",
        "external_rfq_dispatch": "disabled",
    }


def calendar(db: Session, owner: User) -> list[dict[str, object]]:
    contexts = (
        db.scalar(
            select(func.count())
            .select_from(SupplierShortlistContext)
            .where(SupplierShortlistContext.owner_id == owner.id)
        )
        or 0
    )
    types = (
        "SUPPLIER_REVIEW_DUE",
        "COMMERCIAL_REFRESH_DUE",
        "VERIFICATION_REVIEW_DUE",
        "CERTIFICATION_EXPIRY",
        "SAMPLE_FOLLOW_UP",
        "INSPECTION_FOLLOW_UP",
    )
    return [
        {
            "type": event_type,
            "status": "informational",
            "external_action": False,
            "context_count": contexts,
        }
        for event_type in types
    ]


def history(db: Session, owner: User, context: SupplierShortlistContext) -> dict[str, object]:
    versions = list(
        db.scalars(
            select(SupplierShortlistContextVersion)
            .where(SupplierShortlistContextVersion.context_id == context.id)
            .order_by(SupplierShortlistContextVersion.version)
        )
    )
    shortlists = list(
        db.scalars(
            select(SupplierShortlistVersion)
            .where(SupplierShortlistVersion.context_id == context.id)
            .order_by(SupplierShortlistVersion.version)
        )
    )
    decisions = list(
        db.scalars(
            select(SupplierShortlistDecision)
            .where(SupplierShortlistDecision.context_id == context.id)
            .order_by(SupplierShortlistDecision.created_at)
        )
    )
    handoffs = list(
        db.scalars(
            select(SupplierShortlistHandoff)
            .where(SupplierShortlistHandoff.context_id == context.id)
            .order_by(SupplierShortlistHandoff.created_at)
        )
    )
    events = list(
        db.scalars(
            select(SupplierShortlistEvent)
            .where(SupplierShortlistEvent.context_id == context.id)
            .order_by(SupplierShortlistEvent.created_at)
        )
    )
    return {
        "context": {"id": str(context.id), "version": context.current_version},
        "context_versions": [
            {"id": str(item.id), "version": item.version, "payload": item.payload}
            for item in versions
        ],
        "score_versions": [
            {
                "id": str(item.id),
                "supplier_id": str(item.supplier_id),
                "model_version": item.model_version,
                "score": float(item.score),
                "eligibility": item.eligibility,
            }
            for item in db.scalars(
                select(SupplierShortlistScoreVersion).where(
                    SupplierShortlistScoreVersion.context_id == context.id
                )
            )
        ],
        "shortlist_versions": [
            {"id": str(item.id), "version": item.version, "payload": item.payload}
            for item in shortlists
        ],
        "decisions": [
            {
                "id": str(item.id),
                "supplier_id": str(item.supplier_id),
                "decision": item.decision,
                "reason": item.reason,
                "evidence_ids": item.evidence_ids,
            }
            for item in decisions
        ],
        "handoffs": [
            {
                "id": str(item.id),
                "supplier_id": str(item.supplier_id),
                "status": item.status,
                "payload": item.payload,
            }
            for item in handoffs
        ],
        "recovery": [],
        "reports": [],
        "events": [
            {"type": item.event_type, "key": item.event_key, "payload": item.payload}
            for item in events
        ],
    }


def _safe_report_value(value: Any) -> Any:
    """Strip secrets and private/raw payload fields from every report format."""
    sensitive = {
        "authorization",
        "api_key",
        "apikey",
        "cookie",
        "customer",
        "credentials",
        "database_url",
        "dsn",
        "email",
        "password",
        "provider_auth",
        "path",
        "phone",
        "private",
        "raw_payload",
        "secret",
        "token",
    }
    if isinstance(value, dict):
        return {
            str(key): _safe_report_value(item)
            for key, item in value.items()
            if not any(part in str(key).casefold() for part in sensitive)
            and str(key).casefold() not in {"claims", "specifications", "contact", "address"}
        }
    if isinstance(value, list):
        return [_safe_report_value(item) for item in value]
    if isinstance(value, str):
        import re

        value = re.sub(
            r"(?:postgres(?:ql)?|mysql|sqlite)://\S+",
            "[redacted database reference]",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"(?:bearer\s+|api[_-]?key[=:]?)\S+",
            "[redacted credential]",
            value,
            flags=re.IGNORECASE,
        )
        return value
    return value


def report(
    db: Session, owner: User, context: SupplierShortlistContext, fmt: str = "json"
) -> object:
    latest = db.scalar(
        select(SupplierShortlistVersion)
        .where(SupplierShortlistVersion.context_id == context.id)
        .order_by(SupplierShortlistVersion.version.desc())
    )
    payload = cast(dict[str, Any], latest.payload if latest else {})
    safe_context = {
        key: value
        for key, value in cast(dict[str, Any], context.payload or {}).items()
        if key
        in {
            "category",
            "target_market",
            "budget",
            "budget_currency",
            "moq_preference",
            "lead_time_preference_days",
            "risk_tolerance",
            "freshness_requirement",
        }
    }
    items = cast(list[dict[str, Any]], payload.get("shortlist", []))
    sections = {
        "Context": safe_context,
        "Eligibility": {
            "shortlist": items,
            "review_required": payload.get("review_required", []),
            "blocked": payload.get("blocked", []),
        },
        "Shortlist": items,
        "Score explanations": [item.get("dimensions", []) for item in items],
        "Commercial comparison": [item.get("commercial", {}) for item in items],
        "Verification": [item.get("verification_readiness", {}) for item in items],
        "Capabilities": [],
        "Certifications": [],
        "Facilities": [],
        "Risk": [item.get("risk") for item in items],
        "Confidence": [item.get("confidence") for item in items],
        "Contradictions": [],
        "Economics": [item.get("economics", {}) for item in items],
        "Human decision": [],
        "Sourcing handoff": [],
        "Evidence appendix": [item.get("evidence_lineage", []) for item in items],
    }
    safe_sections = cast(dict[str, Any], _safe_report_value(sections))
    result: dict[str, Any] = {
        "context_id": str(context.id),
        "context_version": context.current_version,
        "shortlist_version": latest.version if latest else None,
        "sections": safe_sections,
        "report_safety": "sanitized",
    }
    if fmt == "markdown":
        return "# Supplier Shortlisting Report\n\n" + "\n".join(
            f"## {html.escape(key)}\n\n{html.escape(str(value))}"
            for key, value in safe_sections.items()
        )
    if fmt == "html":
        return "<h1>Supplier Shortlisting Report</h1>" + "".join(
            f"<section><h2>{html.escape(key)}</h2><p>{html.escape(str(value))}</p></section>"
            for key, value in safe_sections.items()
        )
    return result
