# ruff: noqa
"""Bounded deterministic orchestration over existing 9A-9F services."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.business_agent_models import (
    BusinessAgentApproval,
    BusinessAgentArtifact,
    BusinessAgentAttempt,
    BusinessAgentCheckpoint,
    BusinessAgentFinding,
    BusinessAgentGoal,
    BusinessAgentPlan,
    BusinessAgentRun,
    BusinessAgentStep,
    BusinessAgentToolInvocation,
    agent_now,
)
from vayujit_api.intelligence.business_agent_registry import (
    authorize_capability,
    capability_map,
)
from vayujit_api.intelligence.economic_integration_service import (
    ECONOMICS_CAPABILITIES,
    decision_brief_for_opportunity,
    project_economics_for_opportunity,
)
from vayujit_api.intelligence.competitor_agent_service import (
    competitor_decision_brief,
    execute_competitor_capability,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.product_opportunity_scoring_models import ProductOpportunityDecision
from vayujit_api.intelligence.product_discovery import discover_local_product_candidates
from vayujit_api.intelligence.product_research import run_live_product_discovery
from vayujit_api.intelligence.review_business_agent_service import (
    REVIEW_CAPABILITIES,
    execute_review_capability,
    review_artifact_type,
    review_enabled,
)
from vayujit_api.intelligence.trend_business_agent_service import (
    TREND_CAPABILITIES,
    execute_trend_capability,
)
from vayujit_api.intelligence.business_agent_schemas import BusinessGoalCreate, RunCreate
from vayujit_api.intelligence.supplier_research import (
    derive_sourcing_concept,
    execute_provider_neutral_search,
)
from vayujit_api.intelligence.supplier_schemas import SupplierSearchCreate
from vayujit_api.intelligence.supplier_service import create_search


def _audit(
    db: Session,
    owner: User,
    action: str,
    entity_id: uuid.UUID,
    identity: str,
    metadata: Mapping[str, object] | None = None,
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=f"business_agent.{action}",
        entity_type="business_agent",
        entity_id=entity_id,
        metadata=dict(metadata or {}),
        idempotency_key=f"business-agent:{action}:{identity}",
    )


def _bounded_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _supplier_source_policy() -> dict[str, object]:
    """Reuse the configured supplier mode without enabling external writes."""
    return {
        "mode": get_settings().intelligence_external_provider_mode,
        "external_connectors": "disabled",
    }


def _candidate_opportunity_ids(db: Session, owner: User, goal_id: uuid.UUID) -> list[uuid.UUID]:
    runs = list(
        db.scalars(
            select(BusinessAgentRun)
            .where(
                BusinessAgentRun.owner_id == owner.id,
                BusinessAgentRun.goal_id == goal_id,
            )
            .order_by(BusinessAgentRun.updated_at.desc())
        )
    )
    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for candidate_run in runs:
        result = candidate_run.result if isinstance(candidate_run.result, dict) else {}
        candidates = result.get("candidates")
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                opportunity_id = uuid.UUID(str(candidate.get("id")))
            except (TypeError, ValueError):
                continue
            if opportunity_id not in seen:
                seen.add(opportunity_id)
                ids.append(opportunity_id)
    return ids


def _run_has_human_product_selection(db: Session, owner: User, run: BusinessAgentRun) -> bool:
    for opportunity_id in _candidate_opportunity_ids(db, owner, run.goal_id):
        if db.scalar(
            select(ProductOpportunityDecision.id).where(
                ProductOpportunityDecision.owner_id == owner.id,
                ProductOpportunityDecision.opportunity_id == opportunity_id,
                ProductOpportunityDecision.action == "shortlist",
            )
        ):
            return True
    return False


_CAPITAL_PATTERN = re.compile(
    r"(?:\u20b9|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|lakhs)?"
    r"|([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|lakhs)\s*(?:rupees?|inr|\u20b9)?"
    r"|([0-9][0-9,]{3,})\s*(?:rupees?|inr|\u20b9)",
    re.IGNORECASE,
)


def _parse_capital(raw: str) -> int | None:
    for match in _CAPITAL_PATTERN.finditer(raw):
        amount_text = next((value for value in match.groups()[::2] if value), None)
        scale = next((value for value in match.groups()[1::2] if value), "")
        if amount_text is None:
            continue
        try:
            amount = Decimal(amount_text.replace(",", ""))
            if scale.casefold() in {"lakh", "lakhs"}:
                amount *= Decimal(100_000)
            if amount != amount.to_integral_value():
                continue
            value = int(amount)
        except (InvalidOperation, ValueError):
            continue
        if value >= 0:
            return value
    return None


def _parse_currency(raw: str) -> str | None:
    if re.search(r"(?:\u20b9|rs\.?|inr|rupees?)", raw, re.IGNORECASE):
        return "INR"
    return None


def _explicit_goal_category(raw: str) -> str | None:
    """Extract the seller's explicit category constraint from the raw goal."""
    category_match = re.search(
        r"\b(?:in|for|within)\s+(?:the\s+)?([a-z][a-z0-9 &\-/]{1,80}?)\s+categor(?:y|ies)\b",
        raw.casefold(),
    )
    if not category_match:
        return None
    category = re.sub(r"\s+", " ", category_match.group(1)).strip(" .,-")
    return category or None


def _goal_projection(
    raw: str, supplied: dict[str, object] | None
) -> tuple[dict[str, object], list[str], list[str]]:
    lower = raw.casefold()
    injection_markers = ("ignore previous", "system prompt", "developer message", "reveal secrets")
    prompt_injection_detected = any(marker in lower for marker in injection_markers)
    if supplied:
        structured = dict(supplied)
    else:
        candidate_match = re.search(r"(\d+)\s+(?:winning\s+)?products?", lower)
        structured = {
            "objective": "identify and evaluate winning products",
            "marketplace": "AMAZON_IN" if "amazon" in lower else "UNSPECIFIED",
            "currency": _parse_currency(raw),
            "capital": _parse_capital(raw),
            "candidate_count": int(candidate_match.group(1)) if candidate_match else 3,
        }
    assumptions = [
        "Only owner-scoped internal evidence and deterministic local capabilities are used."
    ]
    unresolved: list[str] = []
    if prompt_injection_detected:
        assumptions.append("Untrusted instructions in goal text are isolated and ignored.")
        structured["untrusted_instructions_ignored"] = True
    if not structured.get("marketplace") or structured.get("marketplace") == "UNSPECIFIED":
        unresolved.append("target marketplace")
    if not structured.get("capital"):
        unresolved.append("available capital")
    explicit_category = _explicit_goal_category(raw)
    # A category explicitly stated in the seller's current goal outranks stale
    # structured values supplied by an older client or cached form state.
    if explicit_category:
        structured["category"] = explicit_category
    if "target_candidate_count" not in structured and not re.search(
        r"\b\d+\s+(?:winning\s+)?products?\b", lower
    ):
        current_count = _bounded_int(structured.get("candidate_count"), 3)
        if current_count < 2:
            structured["candidate_count"] = 3
    return structured, assumptions, unresolved


def _validate_plan_steps(steps: list[dict[str, object]]) -> None:
    """Validate a proposed plan against the bounded capability registry before persistence."""
    registry = capability_map()
    keys = {str(item.get("key")) for item in steps}
    dependencies: dict[str, list[str]] = {}
    for item in steps:
        key = str(item.get("key") or "")
        capability = str(item.get("capability") or "")
        if not key or not capability:
            raise ValueError("Research plans require a step key and capability.")
        spec = registry.get(capability)
        if spec is None:
            raise ValueError(f"Unsupported research capability: {capability}.")
        authorize_capability(capability, {})
        raw_dependencies = item.get("deps")
        deps = (
            [str(value) for value in raw_dependencies] if isinstance(raw_dependencies, list) else []
        )
        if key in deps or any(value not in keys for value in deps):
            raise ValueError(f"Invalid dependency for research step: {key}.")
        dependencies[key] = deps
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError("Research plan dependencies contain a cycle.")
        if key in visited:
            return
        visiting.add(key)
        for dependency in dependencies.get(key, []):
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in dependencies:
        visit(key)


def _failure_classification(error: Exception) -> str:
    if isinstance(error, PermissionError):
        return "AUTH_FAILURE"
    if isinstance(error, TimeoutError):
        return "TIMEOUT"
    if isinstance(error, ConnectionError):
        return "PROVIDER_UNAVAILABLE"
    if isinstance(error, (ValueError, TypeError)):
        return "VALIDATION_FAILURE"
    if isinstance(error, LookupError):
        return "PREREQUISITE_MISSING"
    return "UNEXPECTED_FAILURE"


def _candidate_cards(db: Session, owner: User, limit: int = 20) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(ProductOpportunity)
            .where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.lifecycle_status != "archived",
            )
            .order_by(ProductOpportunity.updated_at.desc())
            .limit(limit)
        )
    )
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "status": row.lifecycle_status,
            "description": row.description,
            "product_concept": row.product_concept,
            "category": row.category,
            "subcategory": row.subcategory,
            "target_marketplace": row.target_marketplace,
            "target_region": row.target_region,
            "evidence_state": row.evidence_state,
            "research_state": row.research_state,
            "origin": row.origin,
            "intelligence_profile": row.intelligence_profile or {},
        }
        for row in rows
    ]


def get_goal(db: Session, owner: User, goal_id: uuid.UUID) -> BusinessAgentGoal:
    value = db.scalar(
        select(BusinessAgentGoal).where(
            BusinessAgentGoal.id == goal_id, BusinessAgentGoal.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Business goal not found.")
    return value


def delete_goal(db: Session, owner: User, goal_id: uuid.UUID) -> None:
    """Delete an owner-scoped historical goal and its durable run history."""
    goal = get_goal(db, owner, goal_id)
    latest = db.scalar(
        select(BusinessAgentGoal)
        .where(BusinessAgentGoal.owner_id == owner.id)
        .order_by(BusinessAgentGoal.updated_at.desc(), BusinessAgentGoal.created_at.desc())
    )
    if latest is not None and latest.id == goal.id:
        raise HTTPException(
            409, "The active research goal cannot be deleted. Start another goal first."
        )
    _audit(db, owner, "goal.deleted", goal.id, str(goal.id))
    db.delete(goal)
    db.commit()


def create_goal(db: Session, owner: User, data: BusinessGoalCreate) -> BusinessAgentGoal:
    db.refresh(owner, with_for_update=True)
    existing = db.scalar(
        select(BusinessAgentGoal).where(
            BusinessAgentGoal.owner_id == owner.id,
            BusinessAgentGoal.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing
    structured, assumptions, unresolved = _goal_projection(data.raw_goal, data.structured_goal)
    if data.include_trend_intelligence:
        structured["include_trend_intelligence"] = True
    value = BusinessAgentGoal(
        owner_id=owner.id,
        raw_goal=data.raw_goal.strip(),
        structured_goal=structured,
        provenance={"source": "owner_input", **data.provenance},
        assumptions=assumptions,
        unresolved_questions=unresolved,
        idempotency_key=data.idempotency_key,
        status="DRAFT",
        created_at=agent_now(),
        updated_at=agent_now(),
    )
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.owner_id == owner.id,
                BusinessAgentGoal.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing
    _audit(
        db,
        owner,
        "goal.created",
        value.id,
        str(value.id),
        {"extraction_version": value.extraction_version},
    )
    db.commit()
    db.refresh(value)
    return value


def _trend_enabled(goal: BusinessAgentGoal) -> bool:
    structured = goal.structured_goal or {}
    return bool(
        structured.get("include_trend_intelligence")
        or structured.get("trend_intelligence")
        or "trend intelligence" in goal.raw_goal.casefold()
    )


def _competitor_enabled(goal: BusinessAgentGoal) -> bool:
    structured = goal.structured_goal or {}
    return bool(
        structured.get("include_competitor_intelligence")
        or structured.get("competitor_intelligence")
        or "competitor" in goal.raw_goal.casefold()
    )


def _economics_enabled(goal: BusinessAgentGoal) -> bool:
    structured = goal.structured_goal or {}
    return bool(
        structured.get("include_sourcing_economics")
        or structured.get("sourcing_economics")
        or "sourcing economics" in goal.raw_goal.casefold()
    )


def _economics_context_id(goal: BusinessAgentGoal) -> uuid.UUID | None:
    value = (goal.structured_goal or {}).get("economic_context_id")
    try:
        return uuid.UUID(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _steps(goal: BusinessAgentGoal) -> list[dict[str, object]]:
    enabled = _competitor_enabled(goal)
    reviews = review_enabled(goal)
    trend = _trend_enabled(goal)
    steps: list[dict[str, object]] = [
        {"key": "opportunity", "capability": "product_opportunity.create", "deps": []},
        {"key": "demand", "capability": "demand.intelligence", "deps": ["opportunity"]},
    ]
    if trend:
        steps.extend(
            [
                {
                    "key": "trend_context",
                    "capability": "TREND_CONTEXT_RESOLUTION",
                    "deps": ["opportunity"],
                },
                {
                    "key": "trend_ingestion",
                    "capability": "TREND_INGESTION",
                    "deps": ["trend_context"],
                },
                {
                    "key": "trend_analysis",
                    "capability": "TREND_ANALYSIS",
                    "deps": ["trend_ingestion"],
                },
                {
                    "key": "trend_change",
                    "capability": "TREND_CHANGE_ANALYSIS",
                    "deps": ["trend_analysis"],
                },
                {
                    "key": "trend_validation",
                    "capability": "TREND_VALIDATION",
                    "deps": ["trend_change"],
                },
                {
                    "key": "trend_projection",
                    "capability": "TREND_WINNING_PRODUCT_PROJECTION",
                    "deps": ["trend_validation"],
                },
            ]
        )
    if enabled:
        steps.extend(
            [
                {
                    "key": "competitor_discovery",
                    "capability": "COMPETITOR_DISCOVERY",
                    "deps": ["opportunity"],
                },
                {
                    "key": "competitor_analysis",
                    "capability": "COMPETITOR_ANALYSIS",
                    "deps": ["competitor_discovery"],
                },
                {
                    "key": "competitor_change",
                    "capability": "COMPETITOR_CHANGE_ANALYSIS",
                    "deps": ["competitor_analysis"],
                },
            ]
        )
    steps.extend(
        [
            {
                "key": "competition",
                "capability": "competition.intelligence",
                "deps": ["opportunity", "competitor_analysis"] if enabled else ["opportunity"],
            },
            {"key": "commercial", "capability": "commercial.assessment", "deps": ["opportunity"]},
            {"key": "supplier", "capability": "supplier.discovery", "deps": ["opportunity"]},
            {"key": "feasibility", "capability": "supplier.feasibility", "deps": ["supplier"]},
            {
                "key": "score",
                "capability": "winning_product.score",
                "deps": ["demand", "competition", "commercial", "feasibility"],
            },
            {"key": "rank", "capability": "winning_product.rank", "deps": ["score"]},
        ]
    )
    if reviews:
        steps.extend(
            [
                {
                    "key": "review_ingestion",
                    "capability": "REVIEW_INGESTION",
                    "deps": ["opportunity"],
                },
                {
                    "key": "review_analysis",
                    "capability": "REVIEW_ANALYSIS",
                    "deps": ["review_ingestion"],
                },
                {
                    "key": "review_gap_analysis",
                    "capability": "REVIEW_GAP_ANALYSIS",
                    "deps": ["review_analysis"],
                },
                {
                    "key": "review_change_analysis",
                    "capability": "REVIEW_CHANGE_ANALYSIS",
                    "deps": ["review_gap_analysis"],
                },
                {
                    "key": "review_winning_product_projection",
                    "capability": "REVIEW_WINNING_PRODUCT_PROJECTION",
                    "deps": ["review_change_analysis"],
                },
            ]
        )
    if _economics_enabled(goal):
        steps.append(
            {
                "key": "sourcing_economics",
                "capability": "sourcing_economics.inspect",
                "deps": ["opportunity"],
            }
        )
    brief_deps = ["rank"]
    if reviews:
        brief_deps.append("review_winning_product_projection")
    if trend:
        brief_deps.append("trend_projection")
    if _economics_enabled(goal):
        brief_deps.append("sourcing_economics")
    steps.append(
        {
            "key": "brief",
            "capability": "decision_brief.generate",
            "deps": brief_deps,
        }
    )
    return steps


def create_plan(db: Session, owner: User, goal: BusinessAgentGoal) -> BusinessAgentPlan:
    db.refresh(owner, with_for_update=True)
    current = db.scalar(
        select(BusinessAgentPlan)
        .where(BusinessAgentPlan.goal_id == goal.id)
        .order_by(BusinessAgentPlan.version.desc())
    )
    if current and current.status != "SUPERSEDED":
        return current
    steps = _steps(goal)
    _validate_plan_steps(steps)
    encoded = json.dumps(steps, sort_keys=True, separators=(",", ":"))
    plan = BusinessAgentPlan(
        owner_id=owner.id,
        goal_id=goal.id,
        version=1,
        status="READY",
        plan_hash=hashlib.sha256(encoded.encode()).hexdigest(),
        created_at=agent_now(),
    )
    db.add(plan)
    db.flush()
    registry = capability_map()
    for item in steps:
        spec = registry[str(item["capability"])]
        db.add(
            BusinessAgentStep(
                owner_id=owner.id,
                plan_id=plan.id,
                step_key=str(item["key"]),
                capability_id=spec.id,
                dependency_keys=(
                    [str(value) for value in item["deps"]] if isinstance(item["deps"], list) else []
                ),
                input_contract={"schema": spec.input_schema},
                output_contract={"schema": spec.output_schema},
                execution_mode=spec.execution_class,
                side_effect_class=spec.side_effect_class,
                status="QUEUED",
                created_at=agent_now(),
                updated_at=agent_now(),
            )
        )
    goal.status = "PLANNED"
    goal.updated_at = agent_now()
    _audit(
        db,
        owner,
        "plan.created",
        plan.id,
        str(plan.id),
        {"version": plan.version, "step_count": len(steps)},
    )
    db.commit()
    db.refresh(plan)
    return plan


def start_run(
    db: Session, owner: User, goal: BusinessAgentGoal, data: RunCreate
) -> BusinessAgentRun:
    db.refresh(owner, with_for_update=True)
    plan = create_plan(db, owner, goal)
    existing = db.scalar(
        select(BusinessAgentRun).where(
            BusinessAgentRun.owner_id == owner.id,
            BusinessAgentRun.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing
    run = BusinessAgentRun(
        owner_id=owner.id,
        goal_id=goal.id,
        plan_id=plan.id,
        status="QUEUED",
        idempotency_key=data.idempotency_key,
        correlation_id=hashlib.sha256(data.idempotency_key.encode()).hexdigest()[:32],
        budget={
            "max_steps": data.max_steps,
            "max_provider_calls": data.max_provider_calls,
            "max_elapsed_seconds": data.max_elapsed_seconds,
            "max_gap_loops": 2,
        },
        usage={"steps": 0, "provider_calls": 0, "gap_loops": 0},
        result={},
        failure={},
        checkpoint={},
        created_at=agent_now(),
        updated_at=agent_now(),
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(BusinessAgentRun).where(
                BusinessAgentRun.owner_id == owner.id,
                BusinessAgentRun.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing
    goal.status = "RUNNING"
    goal.updated_at = agent_now()
    _audit(db, owner, "run.created", run.id, str(run.id), {"plan_version": plan.version})
    db.commit()
    db.refresh(run)
    return run


def _persist_review_artifact(
    db: Session,
    owner: User,
    run: BusinessAgentRun,
    capability: str,
    output: dict[str, object],
) -> tuple[uuid.UUID, uuid.UUID | None]:
    """Store references and bounded finding metadata, never raw review text."""
    artifact = BusinessAgentArtifact(
        owner_id=owner.id,
        run_id=run.id,
        artifact_type=review_artifact_type(capability),
        payload={
            key: output[key]
            for key in (
                "capability",
                "status",
                "context_id",
                "batch_id",
                "snapshot_id",
                "analysis_id",
                "gap_analysis_id",
                "comparison_id",
                "projection_id",
                "readiness",
                "evidence_gaps",
                "research_gaps",
                "accepted_count",
                "rejected_count",
                "gap_count",
                "signal_count",
                "event_count",
            )
            if key in output
        },
        provenance={
            "source": "review-intelligence",
            "authoritative_services": ["11A", "11B", "11C", "11D", "11E", "11F"],
            "external_mutation": False,
        },
        created_at=agent_now(),
    )
    db.add(artifact)
    db.flush()
    gaps = output.get("evidence_gaps") or output.get("research_gaps") or []
    finding_type: str | None = None
    if output.get("status") == "EVIDENCE_GAP" or gaps:
        finding_type = "REVIEW_EVIDENCE_INSUFFICIENT"
    elif capability == "REVIEW_GAP_ANALYSIS" and _bounded_int(output.get("gap_count"), 0):
        finding_type = "PRODUCT_GAP_HYPOTHESIS"
    elif capability == "REVIEW_CHANGE_ANALYSIS" and _bounded_int(output.get("event_count"), 0):
        finding_type = "MEANINGFUL_REVIEW_CHANGE"
    elif capability == "REVIEW_WINNING_PRODUCT_PROJECTION":
        finding_type = "REVIEW_VALIDATION_REQUIRED"
    if finding_type is None:
        return artifact.id, None
    finding = BusinessAgentFinding(
        owner_id=owner.id,
        run_id=run.id,
        finding_type=finding_type,
        value={
            "status": output.get("status"),
            "capability": capability,
            "labels": [
                "CUSTOMER-FEEDBACK EVIDENCE",
                "REVIEW-DERIVED HYPOTHESIS",
                "REQUIRES VALIDATION",
            ],
            "evidence_gap_count": len(gaps) if isinstance(gaps, list) else 0,
        },
        evidence_ids=[str(artifact.id)],
        confidence=0.0 if output.get("status") == "EVIDENCE_GAP" else 0.5,
        created_at=agent_now(),
    )
    db.add(finding)
    db.flush()
    return artifact.id, finding.id


def _persist_trend_artifact(
    db: Session,
    owner: User,
    run: BusinessAgentRun,
    capability: str,
    output: dict[str, object],
) -> tuple[uuid.UUID, uuid.UUID | None]:
    """Persist bounded Trend references in the existing 9G artifact/finding tables."""
    artifact_type = {
        "TREND_ANALYSIS": "TREND_ANALYSIS_SUMMARY",
        "TREND_CHANGE_ANALYSIS": "TREND_CHANGE_SUMMARY",
        "TREND_VALIDATION": "TREND_VALIDATION_SUMMARY",
        "TREND_WINNING_PRODUCT_PROJECTION": "TREND_EVIDENCE_BRIEF",
    }.get(capability, "TREND_EVIDENCE_BRIEF")
    payload_keys = (
        "capability",
        "status",
        "gap_code",
        "context_id",
        "snapshot_id",
        "analysis_id",
        "baseline_analysis_id",
        "comparison_id",
        "validation_id",
        "projection_id",
        "readiness",
        "confidence",
        "freshness",
        "agreement",
        "contradictions",
        "research_gaps",
        "evidence_gaps",
        "event_count",
        "observation_count",
        "reason",
    )
    payload = {key: output[key] for key in payload_keys if key in output}
    existing = next(
        (
            item
            for item in db.scalars(
                select(BusinessAgentArtifact).where(
                    BusinessAgentArtifact.owner_id == owner.id,
                    BusinessAgentArtifact.run_id == run.id,
                    BusinessAgentArtifact.artifact_type == artifact_type,
                )
            )
            if item.payload.get("capability") == capability
            and item.payload.get("context_id") == payload.get("context_id")
        ),
        None,
    )
    artifact = existing
    if artifact is None:
        artifact = BusinessAgentArtifact(
            owner_id=owner.id,
            run_id=run.id,
            artifact_type=artifact_type,
            payload=payload,
            provenance={
                "source": "trend-intelligence",
                "authoritative_services": ["12A", "12B", "12C", "12D", "12E", "12F"],
                "external_mutation": False,
            },
            created_at=agent_now(),
        )
        db.add(artifact)
        db.flush()
    gaps = output.get("evidence_gaps") or output.get("research_gaps") or []
    finding_id: uuid.UUID | None = None
    if output.get("status") == "EVIDENCE_GAP" or gaps:
        finding_type = "TREND_RESEARCH_GAP"
    elif capability == "TREND_CHANGE_ANALYSIS" and _bounded_int(output.get("event_count"), 0):
        finding_type = "TREND_MATERIAL_CHANGE"
    elif capability == "TREND_VALIDATION":
        finding_type = "TREND_VALIDATED_HYPOTHESIS"
    else:
        finding_type = "TREND_OBSERVED_SIGNAL"
    if output.get("status") in {"EVIDENCE_GAP", "SUCCEEDED"}:
        finding = next(
            (
                item
                for item in db.scalars(
                    select(BusinessAgentFinding).where(
                        BusinessAgentFinding.owner_id == owner.id,
                        BusinessAgentFinding.run_id == run.id,
                        BusinessAgentFinding.finding_type == finding_type,
                    )
                )
                if str(artifact.id) in (item.evidence_ids or [])
            ),
            None,
        )
        if finding is None:
            finding = BusinessAgentFinding(
                owner_id=owner.id,
                run_id=run.id,
                finding_type=finding_type,
                value={
                    "status": output.get("status"),
                    "capability": capability,
                    "labels": [
                        "OBSERVED SIGNAL EVIDENCE",
                        "DERIVED DETERMINISTIC TREND INTELLIGENCE",
                        "REQUIRES HUMAN REVIEW",
                    ],
                    "gap_code": output.get("gap_code"),
                    "readiness": output.get("readiness"),
                    "research_gaps": gaps if isinstance(gaps, list) else [],
                },
                evidence_ids=[str(artifact.id)],
                confidence=0.0,
                created_at=agent_now(),
            )
            db.add(finding)
            db.flush()
        finding_id = finding.id
    return artifact.id, finding_id


def _emit_trend_channel_event(
    db: Session,
    owner: User,
    run: BusinessAgentRun,
    output: dict[str, object],
) -> None:
    context_id = output.get("context_id")
    if not isinstance(context_id, str):
        return
    action: str | None = None
    capability = output.get("capability")
    if capability == "TREND_VALIDATION":
        action = (
            "product_channel.trend_validation_ready"
            if output.get("readiness") == "READY_FOR_DOWNSTREAM"
            else "product_channel.trend_research_required"
        )
    elif capability == "TREND_CHANGE_ANALYSIS":
        materialities = output.get("materialities")
        if isinstance(materialities, list) and any(
            str(value).upper() in {"MODERATE", "HIGH"} for value in materialities
        ):
            action = "product_channel.trend_material_change"
    if action is not None:
        record_event(
            db,
            actor_id=owner.id,
            action=action,
            entity_type="trend_context",
            entity_id=uuid.UUID(context_id),
            metadata={
                "owner_id": str(owner.id),
                "context_id": context_id,
                "source_subsystem": "trend-intelligence",
                "run_id": str(run.id),
                "analysis_id": output.get("analysis_id"),
                "comparison_id": output.get("comparison_id"),
                "validation_id": output.get("validation_id"),
                "lineage": "authoritative-trend-services",
                "external_writes": [],
            },
            idempotency_key=f"business-agent:{run.id}:{action}:{context_id}",
        )


def execute_run(db: Session, owner: User, run: BusinessAgentRun) -> BusinessAgentRun:
    locked_run = db.scalar(
        select(BusinessAgentRun)
        .where(BusinessAgentRun.id == run.id, BusinessAgentRun.owner_id == owner.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_run is None:
        raise HTTPException(404, "Business agent run not found.")
    run = locked_run
    if run.status in {"CANCELLED", "COMPLETED", "PAUSED", "BUDGET_EXHAUSTED"}:
        return run
    if run.status == "WAITING_APPROVAL" and not _run_has_human_product_selection(db, owner, run):
        return run
    run.status = "RUNNING"
    run.started_at = run.started_at or agent_now()
    steps = list(
        db.scalars(
            select(BusinessAgentStep)
            .where(BusinessAgentStep.plan_id == run.plan_id, BusinessAgentStep.owner_id == owner.id)
            .order_by(BusinessAgentStep.created_at)
        )
    )
    max_steps = _bounded_int(run.budget.get("max_steps"), 20)
    usage = dict(run.usage)
    goal_record = db.get(BusinessAgentGoal, run.goal_id)
    if goal_record is None:
        raise HTTPException(404, "Business goal not found.")
    structured_goal = dict(goal_record.structured_goal or {})
    projected_goal, _assumptions, _unresolved = _goal_projection(
        goal_record.raw_goal, structured_goal
    )
    if projected_goal != structured_goal:
        goal_record.structured_goal = projected_goal
        structured_goal = projected_goal
        db.flush()
    execution_mode = get_settings().intelligence_external_provider_mode
    goal_provenance = dict(goal_record.provenance or {})
    if goal_provenance.get("mode") != execution_mode:
        goal_provenance["mode"] = execution_mode
        goal_record.provenance = goal_provenance
        db.flush()
    explicit_opportunity_id = structured_goal.get("product_opportunity_id")
    opportunity = None
    if explicit_opportunity_id:
        try:
            opportunity = db.scalar(
                select(ProductOpportunity).where(
                    ProductOpportunity.id == uuid.UUID(str(explicit_opportunity_id)),
                    ProductOpportunity.owner_id == owner.id,
                )
            )
        except (TypeError, ValueError):
            opportunity = None
    if opportunity is None:
        opportunity = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.idempotency_key == f"business-agent:{run.id}",
            )
        )
    if opportunity is None:
        opportunity_step = next(
            (item for item in steps if item.step_key == "opportunity"),
            None,
        )
        prior_result = (
            opportunity_step.result
            if opportunity_step is not None and isinstance(opportunity_step.result, dict)
            else {}
        )
        prior_opportunity_id = prior_result.get("opportunity_id")
        if prior_opportunity_id:
            try:
                opportunity = db.scalar(
                    select(ProductOpportunity).where(
                        ProductOpportunity.id == uuid.UUID(str(prior_opportunity_id)),
                        ProductOpportunity.owner_id == owner.id,
                    )
                )
            except (TypeError, ValueError):
                opportunity = None
    if opportunity is None:
        for selected_opportunity_id in _candidate_opportunity_ids(db, owner, run.goal_id):
            if not db.scalar(
                select(ProductOpportunityDecision.id).where(
                    ProductOpportunityDecision.owner_id == owner.id,
                    ProductOpportunityDecision.opportunity_id == selected_opportunity_id,
                    ProductOpportunityDecision.action == "shortlist",
                )
            ):
                continue
            opportunity = db.scalar(
                select(ProductOpportunity).where(
                    ProductOpportunity.id == selected_opportunity_id,
                    ProductOpportunity.owner_id == owner.id,
                )
            )
            if opportunity is not None:
                break
    live_discovery_output: dict[str, object] | None = None
    if opportunity is None:
        if execution_mode == "LIVE_READ_ONLY":
            try:
                live_discovery_output = run_live_product_discovery(
                    db,
                    owner,
                    raw_goal=goal_record.raw_goal,
                    structured_goal=structured_goal,
                    max_results=_bounded_int(structured_goal.get("candidate_count"), 5),
                    correlation_id=f"business-agent:{run.id}:product-discovery",
                    run_id=run.id,
                    goal_id=run.goal_id,
                )
            except Exception as error:
                live_discovery_output = {
                    "mode": "LIVE_READ_ONLY",
                    "status": "PROVIDER_UNAVAILABLE",
                    "query_count": 0,
                    "result_count": 0,
                    "fetch_count": 0,
                    "candidate_ids": [],
                    "candidates": [],
                    "failures": [{"code": "PROVIDER_UNAVAILABLE", "message": str(error)}],
                }
            candidate_ids = live_discovery_output.get("candidate_ids", [])
            if isinstance(candidate_ids, list) and candidate_ids:
                try:
                    opportunity = db.scalar(
                        select(ProductOpportunity).where(
                            ProductOpportunity.id == uuid.UUID(str(candidate_ids[0])),
                            ProductOpportunity.owner_id == owner.id,
                        )
                    )
                except (TypeError, ValueError):
                    opportunity = None
            if opportunity is None:
                opportunity_step = next(
                    (item for item in steps if item.step_key == "opportunity"), None
                )
                live_failure_code = str(live_discovery_output.get("status", "PROVIDER_UNAVAILABLE"))
                live_failure_message = (
                    "Brave search quota is exhausted or unavailable. Check the configured "
                    "Brave credential/quota, then retry discovery."
                    if live_failure_code == "PROVIDER_QUOTA_EXHAUSTED"
                    else "Live product research returned no canonical product opportunity. "
                    "Review the evidence and retry discovery before comparing products."
                )
                live_failure: dict[str, object] = {
                    "code": live_failure_code,
                    "message": live_failure_message,
                    "mode": "LIVE_READ_ONLY",
                    "details": live_discovery_output,
                }
                if opportunity_step is not None:
                    opportunity_step.status = "FAILED"
                    opportunity_step.result = live_failure
                    opportunity_step.updated_at = agent_now()
                    db.add(
                        BusinessAgentCheckpoint(
                            owner_id=owner.id,
                            run_id=run.id,
                            step_key=opportunity_step.step_key,
                            state={"status": "FAILED", "failure": live_failure},
                            created_at=agent_now(),
                        )
                    )
                run.status = "PARTIAL"
                run.failure = {
                    "code": live_failure["code"],
                    "message": live_failure["message"],
                    "mode": "LIVE_READ_ONLY",
                }
                run.checkpoint = {"completed_steps": [], "last_step": None}
            run.result = {
                "outcome": "RESEARCH_BLOCKED",
                "mode": execution_mode,
                "external_writes": [],
            }
            db.commit()
            db.refresh(run)
            return run
        else:
            candidate_limit = _bounded_int(structured_goal.get("candidate_count"), 5)
            definitions = discover_local_product_candidates(
                goal_record.raw_goal,
                structured_goal,
                limit=candidate_limit,
            )
            discovered: list[ProductOpportunity] = []
            for definition in definitions:
                candidate_key = f"business-agent:{run.id}:candidate:{definition['fingerprint']}"
                candidate = db.scalar(
                    select(ProductOpportunity).where(
                        ProductOpportunity.owner_id == owner.id,
                        ProductOpportunity.idempotency_key == candidate_key,
                    )
                )
                if candidate is None:
                    profile = definition["profile"]
                    candidate = ProductOpportunity(
                        owner_id=owner.id,
                        name=str(definition["name"]),
                        description=str(definition["description"]),
                        product_concept=str(definition["product_concept"]),
                        category=str(definition["category"]),
                        subcategory=str(definition["subcategory"]),
                        target_marketplace=str(definition["target_marketplace"]),
                        target_region=str(definition["target_region"]),
                        customer_segment=str(definition["customer_segment"]),
                        research_objective="Identify and evaluate distinct product concepts through authoritative research.",
                        origin="ai_research",
                        lifecycle_status="researching",
                        research_state="discovered",
                        evidence_state="partial",
                        tags=["business-agent", "LOCAL_DETERMINISTIC_RESEARCH_FIXTURE"],
                        notes="Local deterministic product identity only; marketplace and commercial evidence remain unknown until authoritative research runs.",
                        intelligence_profile=profile if isinstance(profile, dict) else {},
                        idempotency_key=candidate_key,
                    )
                    db.add(candidate)
                    db.flush()
                discovered.append(candidate)
            if not discovered:
                raise LookupError("No meaningful product candidates were discovered.")
            opportunity = discovered[0]
    steps_by_key = {step.step_key: step for step in steps}
    ordered_steps: list[BusinessAgentStep] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def append_dependencies(step: BusinessAgentStep) -> None:
        if step.step_key in visited:
            return
        if step.step_key in visiting:
            raise ValueError("Persisted research plan contains a dependency cycle.")
        visiting.add(step.step_key)
        for dependency_key in step.dependency_keys:
            dependency = steps_by_key.get(dependency_key)
            if dependency is not None:
                append_dependencies(dependency)
        visiting.remove(step.step_key)
        visited.add(step.step_key)
        ordered_steps.append(step)

    for step in steps:
        append_dependencies(step)

    for index, step in enumerate(ordered_steps):
        if index >= max_steps:
            break
        if step.status == "COMPLETED":
            continue
        blocked_dependencies = [
            key
            for key in step.dependency_keys
            if steps_by_key.get(key) is None or steps_by_key[key].status != "COMPLETED"
        ]
        if (
            step.capability_id == "supplier.discovery"
            and execution_mode == "LIVE_READ_ONLY"
            and structured_goal.get("category")
        ):
            human_selection = db.scalar(
                select(ProductOpportunityDecision.id).where(
                    ProductOpportunityDecision.owner_id == owner.id,
                    ProductOpportunityDecision.opportunity_id == opportunity.id,
                    ProductOpportunityDecision.action == "shortlist",
                )
            )
            if human_selection is None:
                blocked_dependencies.append("human_product_selection")
        if blocked_dependencies:
            step.status = "BLOCKED"
            step.result = {
                "code": "PREREQUISITE_MISSING",
                "message": "This research step is waiting for an earlier evidence step.",
                "missing": blocked_dependencies,
            }
            step.updated_at = agent_now()
            db.add(
                BusinessAgentCheckpoint(
                    owner_id=owner.id,
                    run_id=run.id,
                    step_key=step.step_key,
                    state={"status": "BLOCKED", "missing": blocked_dependencies},
                    created_at=agent_now(),
                )
            )
            continue
        step.status = "RUNNING"
        step.attempt_count += 1
        attempt = BusinessAgentAttempt(
            owner_id=owner.id,
            run_id=run.id,
            step_id=step.id,
            attempt_number=step.attempt_count,
            status="RUNNING",
            created_at=agent_now(),
        )
        db.add(attempt)
        db.flush()
        try:
            output: dict[str, object]
            if step.capability_id == "product_opportunity.create":
                output = {
                    "capability": step.capability_id,
                    "mode": (
                        str(live_discovery_output.get("mode"))
                        if live_discovery_output is not None
                        else "LOCAL_DETERMINISTIC"
                    ),
                    "opportunity_id": str(opportunity.id),
                    "research": live_discovery_output,
                    "external_mutation": False,
                }
            elif step.capability_id in TREND_CAPABILITIES:
                output = execute_trend_capability(
                    db,
                    owner,
                    opportunity,
                    step.capability_id,
                )
                output["opportunity_id"] = str(opportunity.id)
                artifact_id, finding_id = _persist_trend_artifact(
                    db, owner, run, step.capability_id, output
                )
                output["artifact_id"] = str(artifact_id)
                if finding_id is not None:
                    output["finding_id"] = str(finding_id)
                _emit_trend_channel_event(db, owner, run, output)
                _audit(
                    db,
                    owner,
                    "trend.capability_invoked",
                    run.id,
                    f"{run.id}:{step.id}:{step.attempt_count}",
                    {
                        "capability": step.capability_id,
                        "opportunity_id": str(opportunity.id),
                        "context_id": output.get("context_id"),
                        "external_mutation": False,
                    },
                )
            elif step.capability_id in REVIEW_CAPABILITIES:
                output = execute_review_capability(
                    db,
                    owner,
                    goal_record,
                    opportunity,
                    step.capability_id,
                )
                output["mode"] = "LOCAL_DETERMINISTIC"
                output["opportunity_id"] = str(opportunity.id)
                output["external_mutation"] = False
                artifact_id, finding_id = _persist_review_artifact(
                    db, owner, run, step.capability_id, output
                )
                output["artifact_id"] = str(artifact_id)
                if finding_id is not None:
                    output["finding_id"] = str(finding_id)
                _audit(
                    db,
                    owner,
                    "review.capability_invoked",
                    run.id,
                    f"{run.id}:{step.id}:{step.attempt_count}",
                    {
                        "capability": step.capability_id,
                        "opportunity_id": str(opportunity.id),
                        "artifact_id": str(artifact_id),
                        "external_mutation": False,
                    },
                )
            elif step.capability_id in ECONOMICS_CAPABILITIES:
                context_id = _economics_context_id(goal_record)
                if context_id is None:
                    output = {
                        "status": "RESEARCH_GAP",
                        "readiness": "NOT_EVALUATED",
                        "code": "ECONOMIC_CONTEXT_REQUIRED",
                        "research_gaps": [
                            {
                                "code": "ECONOMICS_RESEARCH_GAP",
                                "message": "An explicit economic_context_id is required for Business Agent sourcing economics.",
                            }
                        ],
                        "external_writes": [],
                    }
                else:
                    output = project_economics_for_opportunity(
                        db, owner, opportunity.id, economic_context_id=context_id
                    )
                output["capability"] = step.capability_id
                output["opportunity_id"] = str(opportunity.id)
                output["external_writes"] = []
                _audit(
                    db,
                    owner,
                    "sourcing_economics.capability_invoked",
                    run.id,
                    f"{run.id}:{step.id}:{step.attempt_count}",
                    {
                        "capability": step.capability_id,
                        "opportunity_id": str(opportunity.id),
                        "economic_context_id": str(context_id) if context_id else None,
                        "external_mutation": False,
                    },
                )
            elif _competitor_enabled(goal_record) and (
                step.capability_id
                in {
                    "COMPETITOR_DISCOVERY",
                    "COMPETITOR_ANALYSIS",
                    "COMPETITOR_CHANGE_ANALYSIS",
                    "competition.intelligence",
                    "winning_product.score",
                }
            ):
                output = execute_competitor_capability(
                    db,
                    owner,
                    opportunity,
                    step.capability_id,
                    goal_record.structured_goal,
                )
                output["mode"] = "LOCAL_DETERMINISTIC"
                output["opportunity_id"] = str(opportunity.id)
                output["external_mutation"] = False
                _audit(
                    db,
                    owner,
                    "competitor.capability_invoked",
                    run.id,
                    f"{run.id}:{step.id}:{step.attempt_count}",
                    {"capability": step.capability_id, "opportunity_id": str(opportunity.id)},
                )
            elif step.capability_id == "supplier.discovery":
                selected_product_name = str(opportunity.name or "").strip()
                (
                    sourcing_concept,
                    sourcing_method,
                    sourcing_provenance,
                ) = derive_sourcing_concept(opportunity, goal_id=run.goal_id)
                product_query = (
                    sourcing_concept
                    or str(opportunity.product_concept or "").strip()
                    or str(opportunity.category or "").strip()
                )[:240]
                sourcing_provenance["goal_id"] = str(run.goal_id)
                supplier_requirements = {
                    "product_query": product_query,
                    "product_opportunity_id": str(opportunity.id),
                    "product_name": selected_product_name,
                    "retail_product_identity": selected_product_name,
                    "retail_product_concept": str(opportunity.product_concept or ""),
                    "product_concept": sourcing_concept,
                    "sourcing_concept": sourcing_concept,
                    "sourcing_concept_method": sourcing_method,
                    "sourcing_concept_provenance": sourcing_provenance,
                    "category": str(opportunity.category or ""),
                    "subcategory": str(opportunity.subcategory or ""),
                    "country": str(
                        opportunity.target_region or structured_goal.get("country") or ""
                    ),
                    "region": str(opportunity.target_region or structured_goal.get("region") or ""),
                    "marketplace": str(
                        opportunity.target_marketplace or structured_goal.get("marketplace") or ""
                    ),
                    "manufacturer_preferred": True,
                    "max_candidates": min(_bounded_int(run.budget.get("max_candidates"), 10), 20),
                }
                supplier_search = create_search(
                    db,
                    owner,
                    SupplierSearchCreate(
                        opportunity_id=None,
                        product_id=opportunity.product_id,
                        requirements=supplier_requirements,
                        source_policy=_supplier_source_policy(),
                        ruleset_version="supplier-research-14f-v1",
                        idempotency_key=f"business-agent:{run.id}:supplier-discovery",
                    ),
                )
                execute_provider_neutral_search(db, owner, supplier_search)
                supplier_summary = supplier_search.summary_json or {}
                supplier_next_action = (
                    "Review supplier candidates"
                    if _bounded_int(supplier_summary.get("accepted_candidate_count"), 0) > 0
                    else "Review supplier research gaps"
                )
                supplier_summary["next_action"] = supplier_next_action
                output = {
                    "capability": step.capability_id,
                    "mode": str(
                        supplier_summary.get("mode") or supplier_search.source_policy.get("mode")
                    ),
                    "opportunity_id": str(opportunity.id),
                    "research_request_id": str(supplier_search.id),
                    "result": supplier_summary,
                    "external_writes": [],
                    "external_mutation": False,
                }
                _audit(
                    db,
                    owner,
                    "supplier.discovery_invoked",
                    run.id,
                    f"{run.id}:{step.id}:{step.attempt_count}",
                    {
                        "capability": step.capability_id,
                        "research_request_id": str(supplier_search.id),
                        "mode": output["mode"],
                        "product_opportunity_id": str(opportunity.id),
                    },
                )
            else:
                output = {
                    "capability": step.capability_id,
                    "mode": "LOCAL_DETERMINISTIC",
                    "opportunity_id": str(opportunity.id),
                    "external_mutation": False,
                }
        except Exception as error:
            legacy_code = (
                "ECONOMICS_EXECUTION_FAILED"
                if step.capability_id in ECONOMICS_CAPABILITIES
                else (
                    "TREND_EXECUTION_FAILED"
                    if step.capability_id in TREND_CAPABILITIES
                    else (
                        "REVIEW_EXECUTION_FAILED"
                        if step.capability_id in REVIEW_CAPABILITIES
                        else "COMPETITOR_EXECUTION_FAILED"
                    )
                )
            )
            safe_message = (
                "Sourcing Economics execution could not be completed safely."
                if step.capability_id in ECONOMICS_CAPABILITIES
                else (
                    "Trend Intelligence execution could not be completed safely."
                    if step.capability_id in TREND_CAPABILITIES
                    else (
                        "Review Intelligence execution could not be completed safely."
                        if step.capability_id in REVIEW_CAPABILITIES
                        else "This research step could not be completed safely."
                    )
                )
            )
            classification = _failure_classification(error)
            failure: dict[str, object] = {
                "code": classification,
                "legacy_code": legacy_code,
                "message": safe_message,
                "retryable": classification
                in {"PROVIDER_UNAVAILABLE", "RATE_LIMITED", "TIMEOUT", "UNEXPECTED_FAILURE"},
            }
            step.status = "FAILED"
            step.result = failure
            step.updated_at = agent_now()
            attempt.status = "FAILED"
            attempt.output = failure
            attempt.error_code = classification
            attempt.completed_at = agent_now()
            db.add(
                BusinessAgentCheckpoint(
                    owner_id=owner.id,
                    run_id=run.id,
                    step_key=step.step_key,
                    state={"status": "FAILED", "attempt": step.attempt_count, "failure": failure},
                    created_at=agent_now(),
                )
            )
            run.status = "PARTIAL"
            run.failure = {
                "code": "PARTIAL_RESEARCH_FAILURE",
                "message": "Research continued, but one or more evidence steps need attention.",
                "last_step": step.step_key,
                "classification": classification,
            }
            _audit(
                db,
                owner,
                "run.partial",
                run.id,
                f"{run.id}:capability-failure:{step.step_key}",
                run.failure,
            )
            continue
        step.result = output
        step.status = "COMPLETED"
        step.updated_at = agent_now()
        attempt.status = "COMPLETED"
        attempt.output = output
        attempt.completed_at = agent_now()
        db.add(
            BusinessAgentCheckpoint(
                owner_id=owner.id,
                run_id=run.id,
                step_key=step.step_key,
                state={"status": "COMPLETED", "attempt": step.attempt_count},
                created_at=agent_now(),
            )
        )
        db.add(
            BusinessAgentToolInvocation(
                owner_id=owner.id,
                run_id=run.id,
                step_id=step.id,
                capability_id=step.capability_id,
                input_hash=hashlib.sha256(step.step_key.encode()).hexdigest(),
                output_hash=hashlib.sha256(
                    json.dumps(step.result, sort_keys=True).encode()
                ).hexdigest(),
                status="SUCCEEDED",
                side_effect_class=step.side_effect_class,
                created_at=agent_now(),
            )
        )
        usage["steps"] = _bounded_int(usage.get("steps"), 0) + 1
    run.usage = usage
    run.checkpoint = {
        "completed_steps": [step.step_key for step in steps if step.status == "COMPLETED"],
        "last_step": next(
            (step.step_key for step in reversed(steps) if step.status == "COMPLETED"),
            None,
        ),
    }
    failed_steps = [step for step in steps if step.status == "FAILED"]
    blocked_steps = [step for step in steps if step.status == "BLOCKED"]
    if failed_steps or blocked_steps:
        run.status = "PARTIAL"
        failed_commercial_readiness_payload: dict[str, object] | None = None
        readiness_row = db.scalar(
            select(CommercialReadinessSnapshot)
            .where(
                CommercialReadinessSnapshot.owner_id == owner.id,
                CommercialReadinessSnapshot.opportunity_id == opportunity.id,
            )
            .order_by(CommercialReadinessSnapshot.created_at.desc())
        )
        if readiness_row is not None:
            failed_commercial_readiness_payload = {
                "id": str(readiness_row.id),
                "readiness": readiness_row.readiness,
                "known_inputs": readiness_row.known_inputs,
                "claims": readiness_row.claims,
                "assumptions": readiness_row.assumptions,
                "unknown_inputs": readiness_row.unknown_inputs,
                "missing_inputs": readiness_row.missing_inputs,
                "optional_gaps": readiness_row.optional_gaps,
                "contradictions": readiness_row.contradictions,
                "lineage": readiness_row.lineage,
            }
        run.result = {
            "outcome": "RESEARCH_COMPLETED_WITH_GAPS",
            "completed_steps": run.checkpoint["completed_steps"],
            "failed_steps": [
                {"key": step.step_key, "failure": step.result} for step in failed_steps
            ],
            "data_gaps": [
                {
                    "code": "PREREQUISITE_MISSING",
                    "step": step.step_key,
                    "missing": step.result.get("missing", []),
                }
                for step in blocked_steps
            ],
            "external_writes": [],
            "candidates": _candidate_cards(db, owner),
            "commercial_readiness": failed_commercial_readiness_payload,
        }
    if (
        not all(step.status == "COMPLETED" for step in steps)
        and _bounded_int(usage.get("steps"), 0) >= max_steps
    ):
        run.status = "BUDGET_EXHAUSTED"
        run.failure = {
            "code": "BUDGET_EXHAUSTED",
            "message": "The configured Business Agent step budget was exhausted.",
        }
        _audit(db, owner, "run.budget_exhausted", run.id, str(run.id), run.failure)
        db.commit()
        db.refresh(run)
        return run
    if all(step.status == "COMPLETED" for step in steps):
        run.status = "WAITING_APPROVAL"
        competitor_enabled = _competitor_enabled(goal_record)
        integrated_slices = ["9A", "9B", "9C", "9D", "9E", "9F"]
        if competitor_enabled:
            integrated_slices.extend(["10A", "10B", "10C", "10D", "10E", "10F"])
        review_enabled_run = review_enabled(goal_record)
        if review_enabled_run:
            integrated_slices.extend(["11A", "11B", "11C", "11D", "11E", "11F"])
        trend_enabled_run = _trend_enabled(goal_record)
        economics_enabled_run = _economics_enabled(goal_record)
        if trend_enabled_run:
            integrated_slices.extend(["12A", "12B", "12C", "12D", "12E", "12F"])
        if economics_enabled_run:
            integrated_slices.append("13G")
        economics_steps = [step for step in steps if step.capability_id in ECONOMICS_CAPABILITIES]
        economics_outputs = [step.result for step in economics_steps]
        review_steps = [step for step in steps if step.capability_id in REVIEW_CAPABILITIES]
        trend_steps = [step for step in steps if step.capability_id in TREND_CAPABILITIES]
        trend_outputs = [step.result for step in trend_steps]
        trend_artifacts = [
            output.get("artifact_id") for output in trend_outputs if output.get("artifact_id")
        ]
        trend_findings = [
            output.get("finding_id") for output in trend_outputs if output.get("finding_id")
        ]
        trend_gaps: list[dict[str, object]] = []
        for output in trend_outputs:
            raw_gaps = output.get("evidence_gaps") or output.get("research_gaps") or []
            if isinstance(raw_gaps, list):
                trend_gaps.extend(gap for gap in raw_gaps if isinstance(gap, dict))
        review_outputs = [step.result for step in review_steps]
        review_artifacts = [
            output.get("artifact_id") for output in review_outputs if output.get("artifact_id")
        ]
        review_findings = [
            output.get("finding_id") for output in review_outputs if output.get("finding_id")
        ]
        review_gaps: list[dict[str, object]] = []
        for output in review_outputs:
            raw_gaps = output.get("evidence_gaps") or output.get("research_gaps") or []
            if isinstance(raw_gaps, list):
                review_gaps.extend(gap for gap in raw_gaps if isinstance(gap, dict))
        commercial_readiness_payload: dict[str, object] | None = None
        readiness_row = db.scalar(
            select(CommercialReadinessSnapshot)
            .where(
                CommercialReadinessSnapshot.owner_id == owner.id,
                CommercialReadinessSnapshot.opportunity_id == opportunity.id,
            )
            .order_by(CommercialReadinessSnapshot.created_at.desc())
        )
        if readiness_row is not None:
            commercial_readiness_payload = {
                "id": str(readiness_row.id),
                "readiness": readiness_row.readiness,
                "known_inputs": readiness_row.known_inputs,
                "claims": readiness_row.claims,
                "assumptions": readiness_row.assumptions,
                "unknown_inputs": readiness_row.unknown_inputs,
                "missing_inputs": readiness_row.missing_inputs,
                "optional_gaps": readiness_row.optional_gaps,
                "contradictions": readiness_row.contradictions,
                "lineage": readiness_row.lineage,
            }
        run.result = {
            "opportunity_id": str(opportunity.id),
            "candidates": _candidate_cards(db, owner),
            "decision": "REVIEW_REQUIRED",
            "evidence_gap_loops": _bounded_int(usage.get("gap_loops"), 0),
            "external_writes": [],
            "integrated_slices": integrated_slices,
            "review_enabled": review_enabled_run,
            "review_capabilities": [step.capability_id for step in review_steps],
            "review_artifacts": review_artifacts,
            "review_findings": review_findings,
            "review_evidence_gaps": review_gaps,
            "trend_enabled": trend_enabled_run,
            "trend_capabilities": [step.capability_id for step in trend_steps],
            "trend_artifacts": trend_artifacts,
            "trend_findings": trend_findings,
            "trend_evidence_gaps": trend_gaps,
            "economics_enabled": economics_enabled_run,
            "economics_capabilities": [step.capability_id for step in economics_steps],
            "economics_projection": economics_outputs[-1] if economics_outputs else None,
            "commercial_readiness": commercial_readiness_payload,
            "external_writes": [],
        }
        brief_payload: dict[str, object] = {
            "summary": "Evidence-first opportunity brief ready for human decision.",
            "opportunity_id": str(opportunity.id),
            "assumptions": goal_record.assumptions,
            "unresolved_questions": goal_record.unresolved_questions,
            "commercial_readiness": commercial_readiness_payload,
        }
        if competitor_enabled:
            brief_payload["competitor_intelligence"] = competitor_decision_brief(
                db, owner, opportunity
            )
        if review_enabled_run:
            brief_payload["review_intelligence"] = {
                "label": "CUSTOMER-FEEDBACK EVIDENCE / REVIEW-DERIVED HYPOTHESIS",
                "capabilities": [step.capability_id for step in review_steps],
                "artifacts": review_artifacts,
                "findings": review_findings,
                "evidence_gaps": review_gaps,
                "requires_validation": True,
                "external_writes": [],
            }
        if trend_enabled_run:
            latest_trend: dict[str, object] = next(
                (
                    output
                    for output in reversed(trend_outputs)
                    if output.get("status") in {"SUCCEEDED", "EVIDENCE_GAP", "NOT_APPLICABLE"}
                ),
                {},
            )
            brief_payload["trend_intelligence"] = {
                "label": "OBSERVED SIGNAL EVIDENCE / DETERMINISTIC TREND INTELLIGENCE",
                "context_id": latest_trend.get("context_id"),
                "analysis_id": next(
                    (
                        output.get("analysis_id")
                        for output in trend_outputs
                        if output.get("analysis_id")
                    ),
                    None,
                ),
                "comparison_id": next(
                    (
                        output.get("comparison_id")
                        for output in trend_outputs
                        if output.get("comparison_id")
                    ),
                    None,
                ),
                "validation_id": next(
                    (
                        output.get("validation_id")
                        for output in trend_outputs
                        if output.get("validation_id")
                    ),
                    None,
                ),
                "projection_id": next(
                    (
                        output.get("projection_id")
                        for output in trend_outputs
                        if output.get("projection_id")
                    ),
                    None,
                ),
                "readiness": latest_trend.get("readiness", "INSUFFICIENT_EVIDENCE"),
                "confidence": latest_trend.get("confidence", "UNKNOWN"),
                "freshness": latest_trend.get("freshness", "UNKNOWN"),
                "agreement": latest_trend.get("agreement", "UNKNOWN"),
                "research_gaps": trend_gaps,
                "capabilities": [step.capability_id for step in trend_steps],
                "artifacts": trend_artifacts,
                "findings": trend_findings,
                "requires_validation": True,
                "external_writes": [],
                "semantic_boundary": "Trend evidence is not a forecast, sales, revenue, or product-success claim.",
            }
        if economics_enabled_run:
            latest_economics = economics_outputs[-1] if economics_outputs else {}
            decision_brief: dict[str, object] | None = None
            try:
                decision_brief = decision_brief_for_opportunity(db, owner, opportunity.id)
            except HTTPException:
                decision_brief = None
            brief_payload["sourcing_economics"] = {
                "label": "SOURCING ECONOMICS / FACTUAL COST EVIDENCE",
                "readiness": latest_economics.get("readiness", "NOT_EVALUATED"),
                "status": latest_economics.get("status", "RESEARCH_GAP"),
                "projection": latest_economics,
                "decision_brief": decision_brief,
                "requires_human_review": True,
                "external_writes": [],
                "semantic_boundary": "Cost evidence does not rank suppliers or products and is not a profitability or forecast claim.",
            }
        db.add(
            BusinessAgentArtifact(
                owner_id=owner.id,
                run_id=run.id,
                artifact_type="BUSINESS_DECISION_BRIEF",
                payload=brief_payload,
                provenance={"source": "business-agent", "provider": "LOCAL_DETERMINISTIC"},
                created_at=agent_now(),
            )
        )
        db.add(
            BusinessAgentFinding(
                owner_id=owner.id,
                run_id=run.id,
                finding_type="opportunity",
                value={"opportunity_id": str(opportunity.id), "status": "review_required"},
                evidence_ids=[],
                confidence=0.5,
                created_at=agent_now(),
            )
        )
        if (
            db.scalar(
                select(BusinessAgentApproval).where(
                    BusinessAgentApproval.run_id == run.id,
                    BusinessAgentApproval.owner_id == owner.id,
                    BusinessAgentApproval.status == "PENDING",
                )
            )
            is None
        ):
            brief_step = next((item for item in steps if item.step_key == "brief"), None)
            db.add(
                BusinessAgentApproval(
                    owner_id=owner.id,
                    run_id=run.id,
                    step_id=brief_step.id if brief_step else None,
                    status="PENDING",
                    reason="Business Decision Brief requires explicit owner approval before any downstream action.",
                    created_at=agent_now(),
                )
            )
    db.commit()
    db.refresh(run)
    return run


def run_or_404(
    db: Session, owner: User, run_id: uuid.UUID, *, for_update: bool = False
) -> BusinessAgentRun:
    query = select(BusinessAgentRun).where(
        BusinessAgentRun.id == run_id, BusinessAgentRun.owner_id == owner.id
    )
    value = db.scalar(query.with_for_update() if for_update else query)
    if value is None:
        raise HTTPException(404, "Business agent run not found.")
    return value


def revise_plan(db: Session, owner: User, goal: BusinessAgentGoal) -> BusinessAgentPlan:
    db.refresh(owner, with_for_update=True)
    current = db.scalar(
        select(BusinessAgentPlan)
        .where(BusinessAgentPlan.goal_id == goal.id, BusinessAgentPlan.owner_id == owner.id)
        .order_by(BusinessAgentPlan.version.desc())
    )
    if current is None:
        return create_plan(db, owner, goal)
    current.status = "SUPERSEDED"
    steps = _steps(goal)
    _validate_plan_steps(steps)
    encoded = json.dumps(steps, sort_keys=True, separators=(",", ":"))
    plan = BusinessAgentPlan(
        owner_id=owner.id,
        goal_id=goal.id,
        version=current.version + 1,
        status="READY",
        plan_hash=hashlib.sha256(encoded.encode()).hexdigest(),
        created_at=agent_now(),
    )
    db.add(plan)
    db.flush()
    registry = capability_map()
    for item in steps:
        spec = registry[str(item["capability"])]
        db.add(
            BusinessAgentStep(
                owner_id=owner.id,
                plan_id=plan.id,
                step_key=str(item["key"]),
                capability_id=spec.id,
                dependency_keys=(
                    [str(value) for value in item["deps"]] if isinstance(item["deps"], list) else []
                ),
                input_contract={"schema": spec.input_schema},
                output_contract={"schema": spec.output_schema},
                execution_mode=spec.execution_class,
                side_effect_class=spec.side_effect_class,
                status="QUEUED",
                created_at=agent_now(),
                updated_at=agent_now(),
            )
        )
    _audit(
        db,
        owner,
        "plan.revised",
        plan.id,
        str(plan.id),
        {"version": plan.version, "previous_plan_id": str(current.id)},
    )
    db.commit()
    db.refresh(plan)
    return plan
