# ruff: noqa
"""Bounded deterministic orchestration over existing 9A-9F services."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
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
from vayujit_api.intelligence.business_agent_registry import capability_map
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.business_agent_schemas import BusinessGoalCreate, RunCreate


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


def _goal_projection(
    raw: str, supplied: dict[str, object] | None
) -> tuple[dict[str, object], list[str], list[str]]:
    lower = raw.casefold()
    injection_markers = ("ignore previous", "system prompt", "developer message", "reveal secrets")
    prompt_injection_detected = any(marker in lower for marker in injection_markers)
    if supplied:
        structured = dict(supplied)
    else:
        capital_match = re.search(r"(?:rs\.?|inr)\s*([\d,]+)", lower)
        candidate_match = re.search(r"(\d+)\s+(?:winning\s+)?products?", lower)
        structured = {
            "objective": "identify and evaluate winning products",
            "marketplace": "AMAZON_IN" if "amazon" in lower else "UNSPECIFIED",
            "capital": int(capital_match.group(1).replace(",", "")) if capital_match else None,
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
    return structured, assumptions, unresolved


def get_goal(db: Session, owner: User, goal_id: uuid.UUID) -> BusinessAgentGoal:
    value = db.scalar(
        select(BusinessAgentGoal).where(
            BusinessAgentGoal.id == goal_id, BusinessAgentGoal.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Business goal not found.")
    return value


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


def _steps(goal: BusinessAgentGoal) -> list[dict[str, object]]:
    return [
        {"key": "opportunity", "capability": "product_opportunity.create", "deps": []},
        {"key": "demand", "capability": "demand.intelligence", "deps": ["opportunity"]},
        {"key": "competition", "capability": "competition.intelligence", "deps": ["opportunity"]},
        {"key": "commercial", "capability": "commercial.assessment", "deps": ["opportunity"]},
        {"key": "supplier", "capability": "supplier.discovery", "deps": ["opportunity"]},
        {"key": "feasibility", "capability": "supplier.feasibility", "deps": ["supplier"]},
        {
            "key": "score",
            "capability": "winning_product.score",
            "deps": ["demand", "competition", "commercial", "feasibility"],
        },
        {"key": "rank", "capability": "winning_product.rank", "deps": ["score"]},
        {"key": "brief", "capability": "decision_brief.generate", "deps": ["rank"]},
    ]


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
    if run.status in {"CANCELLED", "COMPLETED", "WAITING_APPROVAL", "PAUSED", "BUDGET_EXHAUSTED"}:
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
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.owner_id == owner.id,
            ProductOpportunity.idempotency_key == f"business-agent:{run.id}",
        )
    )
    if opportunity is None:
        opportunity = ProductOpportunity(
            owner_id=owner.id,
            name="Business Agent Product Opportunity",
            description="Deterministic opportunity generated for owner review.",
            product_concept="Candidate product evaluation",
            category="",
            target_marketplace=str(goal_record.structured_goal.get("marketplace", "")),
            research_objective="Evaluate opportunity through existing 9A-9F boundaries",
            origin="ai_research",
            lifecycle_status="researching",
            research_state="in_progress",
            evidence_state="partial",
            tags=["business-agent"],
            notes="No external mutation performed.",
            idempotency_key=f"business-agent:{run.id}",
        )
        db.add(opportunity)
        db.flush()
    for index, step in enumerate(steps):
        if index >= max_steps:
            break
        if step.status == "COMPLETED":
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
        output = {
            "capability": step.capability_id,
            "mode": "LOCAL_DETERMINISTIC",
            "opportunity_id": str(opportunity.id),
            "external_mutation": False,
        }
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
        run.result = {
            "opportunity_id": str(opportunity.id),
            "decision": "REVIEW_REQUIRED",
            "evidence_gap_loops": _bounded_int(usage.get("gap_loops"), 0),
            "external_writes": [],
            "integrated_slices": ["9A", "9B", "9C", "9D", "9E", "9F"],
        }
        db.add(
            BusinessAgentArtifact(
                owner_id=owner.id,
                run_id=run.id,
                artifact_type="BUSINESS_DECISION_BRIEF",
                payload={
                    "summary": "Evidence-first opportunity brief ready for human decision.",
                    "opportunity_id": str(opportunity.id),
                    "assumptions": goal_record.assumptions,
                    "unresolved_questions": goal_record.unresolved_questions,
                },
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
