"""Transactional scenario orchestration over authoritative supplier/shortlist/diligence services."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.core.database import Base
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.due_diligence_service import sourcing_guard
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.scenario_analysis import (
    CALCULATION_VERSION,
    LANDED_COST_VERSION,
    SCORING_VERSION,
    calculate,
    compare,
    sensitivity,
)
from vayujit_api.intelligence.scenario_models import (
    InternalSourcingHandoff,
    ScenarioSupplierAllocation,
    SourcingScenario,
    SourcingScenarioContext,
    SourcingScenarioDecision,
    SourcingScenarioEvent,
    SourcingScenarioRecommendation,
    SourcingScenarioVersion,
)
from vayujit_api.intelligence.scenario_schemas import (
    Command,
    ContextCreate,
    DecisionRequest,
    ScenarioCreate,
    SensitivityRequest,
    VersionCommand,
)
from vayujit_api.intelligence.shortlisting_closure import evidence
from vayujit_api.intelligence.shortlisting_models import (
    SupplierShortlistContext,
    SupplierShortlistDecision,
    SupplierShortlistVersion,
)
from vayujit_api.products.models import Product


def now() -> datetime:
    return datetime.now(UTC)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def owned[T: Base](db: Session, model: type[T], owner: User, identity: uuid.UUID) -> T:
    row = db.get(model, identity)
    if row is None or getattr(row, "owner_id", None) != owner.id:
        raise HTTPException(404, "Sourcing reference not found.")
    return row


def lock_owner(db: Session, owner: User) -> None:
    # Serialize local scenario writes for this owner. No process-local mutex.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"sourcing-scenario:{owner.id}"},
    )


def replay(db: Session, owner: User, key: str, payload: Any) -> dict[str, Any] | None:
    row = db.scalar(
        select(SourcingScenarioEvent).where(
            SourcingScenarioEvent.owner_id == owner.id,
            SourcingScenarioEvent.event_key == key,
        )
    )
    if row is None:
        return None
    if row.request_hash != digest(payload):
        raise HTTPException(409, "Idempotency key was used for a different request.")
    return {**row.payload, "idempotent_reuse": True}


def record(
    db: Session,
    owner: User,
    context: SourcingScenarioContext,
    key: str,
    kind: str,
    request: Any,
    result: dict[str, Any],
    version: SourcingScenarioVersion | None = None,
) -> dict[str, Any]:
    db.add(
        SourcingScenarioEvent(
            owner_id=owner.id,
            context_id=context.id,
            version_id=version.id if version else None,
            event_key=key,
            event_type=kind,
            request_hash=digest(request),
            payload=result,
        )
    )
    db.commit()
    return {**result, "idempotent_reuse": False}


def create_context(db: Session, owner: User, data: ContextCreate) -> dict[str, Any]:
    lock_owner(db, owner)
    payload = data.model_dump(mode="json")
    found = db.scalar(
        select(SourcingScenarioContext).where(
            SourcingScenarioContext.owner_id == owner.id,
            SourcingScenarioContext.idempotency_key == data.idempotency_key,
        )
    )
    if found:
        if found.request_hash != digest(payload):
            raise HTTPException(409, "Idempotency key was used for a different request.")
        return {"id": str(found.id), "status": found.status, "idempotent_reuse": True}
    version = owned(db, SupplierShortlistVersion, owner, data.shortlist_version_id)
    shortlist = owned(db, SupplierShortlistContext, owner, version.context_id)
    if shortlist.product_id:
        owned(db, Product, owner, shortlist.product_id)
    if shortlist.opportunity_id:
        owned(db, IntelligenceOpportunity, owner, shortlist.opportunity_id)
    if not version.payload.get("shortlist") and not version.payload.get("review_required"):
        raise HTTPException(409, "Shortlist has no eligible or reviewable candidates.")
    row = SourcingScenarioContext(
        owner_id=owner.id,
        shortlist_version_id=version.id,
        product_id=shortlist.product_id,
        opportunity_id=shortlist.opportunity_id,
        settings=payload,
        idempotency_key=data.idempotency_key,
        request_hash=digest(payload),
        updated_at=now(),
    )
    db.add(row)
    db.flush()
    return record(
        db,
        owner,
        row,
        f"context:{data.idempotency_key}",
        "SOURCING_CONTEXT_CREATED",
        payload,
        {"id": str(row.id), "status": row.status},
    )


def lineage(
    db: Session,
    owner: User,
    context: SourcingScenarioContext,
    data: ScenarioCreate,
) -> list[dict[str, Any]]:
    version = owned(db, SupplierShortlistVersion, owner, context.shortlist_version_id)
    shortlist = owned(db, SupplierShortlistContext, owner, version.context_id)
    latest = db.scalar(
        select(func.max(SupplierShortlistVersion.version)).where(
            SupplierShortlistVersion.context_id == shortlist.id,
            SupplierShortlistVersion.owner_id == owner.id,
        )
    )
    if version.context_version != shortlist.current_version or latest != version.version:
        raise HTTPException(
            409, "Shortlist has changed; create a context from its current version."
        )
    candidates = {
        str(item["supplier_id"]): item
        for group in ("shortlist", "review_required")
        for item in cast(list[dict[str, Any]], version.payload.get(group, []))
        if isinstance(item, dict)
    }
    result: list[dict[str, Any]] = []
    for a in sorted(data.allocations, key=lambda a: str(a.supplier_id)):
        supplier = owned(db, CrossMarketplaceSupplier, owner, a.supplier_id)
        due = owned(db, SupplierDueDiligenceContext, owner, a.due_diligence_id)
        if (
            due.supplier_id != a.supplier_id
            or due.product_id != context.product_id
            or due.opportunity_id != context.opportunity_id
            or due.shortlist_context_id not in {None, shortlist.id}
            or due.shortlist_version_id not in {None, version.id}
        ):
            raise HTTPException(404, "Sourcing reference not found.")
        candidate = candidates.get(str(a.supplier_id))
        if not candidate or candidate.get("eligibility") not in {"ELIGIBLE", "REVIEW_REQUIRED"}:
            raise HTTPException(409, "Supplier is not an eligible shortlist candidate.")
        decision = db.scalar(
            select(SupplierShortlistDecision)
            .where(
                SupplierShortlistDecision.owner_id == owner.id,
                SupplierShortlistDecision.shortlist_version_id == version.id,
                SupplierShortlistDecision.supplier_id == a.supplier_id,
            )
            .order_by(
                SupplierShortlistDecision.created_at.desc(), SupplierShortlistDecision.id.desc()
            )
        )
        if decision and decision.decision == "REJECT":
            raise HTTPException(409, "Supplier was rejected from the shortlist.")
        guard = sourcing_guard(db, owner, due.id)
        result.append(
            {
                "supplier_id": str(supplier.id),
                "supplier_name": supplier.display_name,
                "shortlist_version_id": str(version.id),
                "shortlist_version": version.version,
                "eligibility": candidate["eligibility"],
                "shortlist_decision_id": str(decision.id) if decision else None,
                "due_diligence_id": str(due.id),
                "assessment_version": due.current_assessment_version,
                "due_diligence": guard,
                "facts": evidence(supplier),
                "freshness": supplier.freshness_status,
                "confidence": str(supplier.confidence_score),
                "source_diversity": str(supplier.source_diversity_score),
                "supplier_updated_at": supplier.updated_at.isoformat(),
            }
        )
    return result


def persist_version(
    db: Session,
    owner: User,
    context: SourcingScenarioContext,
    scenario: SourcingScenario,
    data: ScenarioCreate,
) -> SourcingScenarioVersion:
    stamp = now()
    sources = lineage(db, owner, context, data)
    request = data.model_dump(mode="json")
    try:
        result = calculate(context.settings, request, sources, at=stamp)
    except ValueError as exc:
        raise HTTPException(422, "Scenario inputs cannot be calculated safely.") from exc
    version = SourcingScenarioVersion(
        owner_id=owner.id,
        scenario_id=scenario.id,
        version=scenario.current_version,
        calculation_version=CALCULATION_VERSION,
        landed_cost_version=LANDED_COST_VERSION,
        scoring_version=SCORING_VERSION,
        lineage_hash=digest(sources),
        result=result,
        snapshot={
            "settings": context.settings,
            "request": request,
            "lineage": sources,
            "calculated_at": stamp.isoformat(),
        },
    )
    db.add(version)
    db.flush()
    for allocation in data.allocations:
        db.add(
            ScenarioSupplierAllocation(
                owner_id=owner.id,
                version_id=version.id,
                supplier_id=allocation.supplier_id,
                due_diligence_id=allocation.due_diligence_id,
                quantity=allocation.quantity,
                snapshot=allocation.model_dump(mode="json"),
            )
        )
    scenario.status = result["status"]
    scenario.updated_at = stamp
    context.status = "REVIEW_REQUIRED"
    context.updated_at = stamp
    db.flush()
    return version


def create_scenario(
    db: Session,
    owner: User,
    context_id: uuid.UUID,
    data: ScenarioCreate,
) -> dict[str, Any]:
    lock_owner(db, owner)
    context = owned(db, SourcingScenarioContext, owner, context_id)
    payload = data.model_dump(mode="json")
    key = f"scenario:{context.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    scenario = SourcingScenario(
        owner_id=owner.id,
        context_id=context.id,
        name=data.name,
        scenario_type=data.scenario_type,
        idempotency_key=data.idempotency_key,
        updated_at=now(),
    )
    db.add(scenario)
    db.flush()
    version = persist_version(db, owner, context, scenario, data)
    return record(
        db,
        owner,
        context,
        key,
        "SOURCING_SCENARIO_CREATED",
        payload,
        {
            "id": str(scenario.id),
            "version_id": str(version.id),
            "version": version.version,
            "result": version.result,
        },
        version,
    )


def current(
    db: Session, owner: User, scenario_id: uuid.UUID
) -> tuple[SourcingScenario, SourcingScenarioVersion]:
    scenario = owned(db, SourcingScenario, owner, scenario_id)
    version = db.scalar(
        select(SourcingScenarioVersion).where(
            SourcingScenarioVersion.owner_id == owner.id,
            SourcingScenarioVersion.scenario_id == scenario.id,
            SourcingScenarioVersion.version == scenario.current_version,
        )
    )
    if version is None:
        raise HTTPException(409, "Scenario current-version integrity failure.")
    return scenario, version


def freshness(
    db: Session, owner: User, scenario: SourcingScenario, version: SourcingScenarioVersion
) -> str:
    context = owned(db, SourcingScenarioContext, owner, scenario.context_id)
    data = ScenarioCreate.model_validate(version.snapshot["request"])
    try:
        source = lineage(db, owner, context, data)
    except HTTPException:
        return "RECALCULATION_REQUIRED"
    if digest(source) != version.lineage_hash or version.landed_cost_version != LANDED_COST_VERSION:
        return "RECALCULATION_REQUIRED"
    if any(f.valid_until <= now() or f.observed_at > now() for f in data.fx):
        return "STALE"
    return "CURRENT"


def detail(db: Session, owner: User, scenario_id: uuid.UUID) -> dict[str, Any]:
    scenario, version = current(db, owner, scenario_id)
    return {
        "id": str(scenario.id),
        "context_id": str(scenario.context_id),
        "name": scenario.name,
        "scenario_type": scenario.scenario_type,
        "status": scenario.status,
        "version": version.version,
        "version_id": str(version.id),
        "snapshot": version.snapshot,
        "result": version.result,
        "freshness": freshness(db, owner, scenario, version),
    }


def recalculate(
    db: Session,
    owner: User,
    scenario_id: uuid.UUID,
    data: VersionCommand,
) -> dict[str, Any]:
    lock_owner(db, owner)
    scenario, version = current(db, owner, scenario_id)
    payload = data.model_dump(mode="json")
    key = f"recalculate:{scenario.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    if scenario.current_version != data.expected_version or scenario.status == "ARCHIVED":
        raise HTTPException(409, "Scenario version is not current or is archived.")
    context = owned(db, SourcingScenarioContext, owner, scenario.context_id)
    scenario.current_version += 1
    updated = persist_version(
        db, owner, context, scenario, ScenarioCreate.model_validate(version.snapshot["request"])
    )
    return record(
        db,
        owner,
        context,
        key,
        "SOURCING_SCENARIO_RECALCULATED",
        payload,
        {
            "id": str(scenario.id),
            "version_id": str(updated.id),
            "version": updated.version,
            "result": updated.result,
        },
        updated,
    )


def comparison(db: Session, owner: User, context_id: uuid.UUID) -> dict[str, Any]:
    owned(db, SourcingScenarioContext, owner, context_id)
    rows = db.execute(
        select(SourcingScenario, SourcingScenarioVersion)
        .join(
            SourcingScenarioVersion,
            (SourcingScenarioVersion.scenario_id == SourcingScenario.id)
            & (SourcingScenarioVersion.version == SourcingScenario.current_version)
            & (SourcingScenarioVersion.owner_id == owner.id),
        )
        .where(SourcingScenario.context_id == context_id, SourcingScenario.owner_id == owner.id)
    )
    values = []
    for scenario, version in rows:
        if scenario.status in {"ARCHIVED", "REJECTED"}:
            continue
        state = freshness(db, owner, scenario, version)
        result = {**version.result}
        if state != "CURRENT":
            result["missing_dimensions"] = [*result["missing_dimensions"], "STALE_LINEAGE"]
            result["classification"] = "INSUFFICIENT_EVIDENCE"
        values.append(
            {
                "id": str(version.id),
                "scenario_id": str(scenario.id),
                "name": scenario.name,
                "version": version.version,
                "freshness": state,
                "result": result,
            }
        )
    return compare(values)


def recommend(db: Session, owner: User, context_id: uuid.UUID, data: Command) -> dict[str, Any]:
    lock_owner(db, owner)
    context = owned(db, SourcingScenarioContext, owner, context_id)
    payload = data.model_dump(mode="json")
    key = f"recommend:{context.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    result = comparison(db, owner, context.id)
    number = (
        db.scalar(
            select(func.max(SourcingScenarioRecommendation.version)).where(
                SourcingScenarioRecommendation.context_id == context.id
            )
        )
        or 0
    ) + 1
    selected = result["recommended_version_id"]
    recommendation = SourcingScenarioRecommendation(
        owner_id=owner.id,
        context_id=context.id,
        version=number,
        scenario_version_id=uuid.UUID(selected) if selected else None,
        payload={
            **result,
            "reason": "Highest complete weighted score within exact compared versions.",
            "limitations": [
                "Relative scores depend on comparison set.",
                "Human review required.",
                "Commercial inputs remain assumptions; no procurement authorization.",
            ],
        },
    )
    db.add(recommendation)
    db.flush()
    return record(
        db,
        owner,
        context,
        key,
        "SOURCING_RECOMMENDATION_CREATED",
        payload,
        {"id": str(recommendation.id), "version": number, **recommendation.payload},
    )


def decide(
    db: Session, owner: User, scenario_id: uuid.UUID, data: DecisionRequest
) -> dict[str, Any]:
    lock_owner(db, owner)
    scenario, version = current(db, owner, scenario_id)
    payload = data.model_dump(mode="json")
    key = f"decision:{scenario.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    if data.expected_version != version.version or scenario.status == "ARCHIVED":
        raise HTTPException(409, "Scenario version is not current or is archived.")
    if data.action == "approve" and (
        freshness(db, owner, scenario, version) != "CURRENT"
        or version.result["missing_dimensions"]
        or version.result["status"] == "BLOCKED"
        or version.result["moq_feasibility"] != "FEASIBLE"
        or {"CAPITAL_LIMIT_EXCEEDED", "MARGIN_BELOW_TARGET"} & set(version.result["warnings"])
    ):
        raise HTTPException(409, "Scenario is not ready for internal sourcing approval.")
    row = SourcingScenarioDecision(
        owner_id=owner.id, version_id=version.id, action=data.action, reason=data.reason
    )
    db.add(row)
    db.flush()
    scenario.status = {
        "approve": "APPROVED_FOR_INTERNAL_SOURCING",
        "reject": "REJECTED",
        "review": "REVIEW_REQUIRED",
        "archive": "ARCHIVED",
    }[data.action]
    scenario.updated_at = now()
    context = owned(db, SourcingScenarioContext, owner, scenario.context_id)
    return record(
        db,
        owner,
        context,
        key,
        f"SOURCING_SCENARIO_{data.action.upper()}",
        payload,
        {
            "decision_id": str(row.id),
            "scenario_id": str(scenario.id),
            "version_id": str(version.id),
            "status": scenario.status,
            "external_dispatch": False,
        },
        version,
    )


def handoff(
    db: Session, owner: User, scenario_id: uuid.UUID, data: VersionCommand
) -> dict[str, Any]:
    lock_owner(db, owner)
    scenario, version = current(db, owner, scenario_id)
    payload = data.model_dump(mode="json")
    key = f"handoff:{scenario.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    if (
        data.expected_version != version.version
        or scenario.status != "APPROVED_FOR_INTERNAL_SOURCING"
        or freshness(db, owner, scenario, version) != "CURRENT"
    ):
        raise HTTPException(409, "Current human approval is required for an internal handoff.")
    decision = db.scalar(
        select(SourcingScenarioDecision)
        .where(
            SourcingScenarioDecision.owner_id == owner.id,
            SourcingScenarioDecision.version_id == version.id,
        )
        .order_by(SourcingScenarioDecision.created_at.desc(), SourcingScenarioDecision.id.desc())
    )
    if decision is None or decision.action != "approve":
        raise HTTPException(409, "Current human approval is required for an internal handoff.")
    row = db.scalar(
        select(InternalSourcingHandoff).where(InternalSourcingHandoff.version_id == version.id)
    )
    if row is None:
        row = InternalSourcingHandoff(
            owner_id=owner.id,
            version_id=version.id,
            decision_id=decision.id,
            payload={
                "snapshot": version.snapshot,
                "result": version.result,
                "external_dispatch": False,
                "approval_actor": str(owner.id),
                "approval_time": decision.created_at.isoformat(),
            },
        )
        db.add(row)
        db.flush()
    context = owned(db, SourcingScenarioContext, owner, scenario.context_id)
    return record(
        db,
        owner,
        context,
        key,
        "INTERNAL_SOURCING_HANDOFF_CREATED",
        payload,
        {"id": str(row.id), "version_id": str(version.id), **row.payload},
        version,
    )


def what_if(
    db: Session, owner: User, scenario_id: uuid.UUID, data: SensitivityRequest
) -> dict[str, Any]:
    lock_owner(db, owner)
    scenario, version = current(db, owner, scenario_id)
    payload = data.model_dump(mode="json")
    key = f"sensitivity:{scenario.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    if data.expected_version != version.version:
        raise HTTPException(409, "Scenario version is not current.")
    try:
        result = sensitivity(version.snapshot, data.dimension, data.change_percent)
    except ValueError as exc:
        raise HTTPException(422, "Sensitivity inputs exceed supported limits.") from exc
    context = owned(db, SourcingScenarioContext, owner, scenario.context_id)
    return record(
        db,
        owner,
        context,
        key,
        "SOURCING_SENSITIVITY_CALCULATED",
        payload,
        {
            "version_id": str(version.id),
            "dimension": data.dimension,
            "change_percent": str(data.change_percent),
            "result": result,
        },
        version,
    )
