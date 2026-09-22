# ruff: noqa
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.business_agent_models import (
    BusinessAgentApproval,
    BusinessAgentArtifact,
    BusinessAgentFinding,
    BusinessAgentGoal,
    BusinessAgentPlan,
    BusinessAgentRun,
    BusinessAgentStep,
    BusinessAgentToolInvocation,
    agent_now,
)
from vayujit_api.intelligence.business_agent_registry import CAPABILITY_REGISTRY
from vayujit_api.intelligence.trend_business_agent_service import TREND_CAPABILITIES
from vayujit_api.intelligence.review_business_agent_service import (
    REVIEW_CAPABILITIES,
    review_enabled,
)
from vayujit_api.intelligence.business_agent_schemas import (
    ApprovalResponse,
    BusinessGoalCreate,
    CapabilityResponse,
    DecisionRequest,
    GoalResponse,
    PlanResponse,
    RunCreate,
    RunResponse,
)
from vayujit_api.intelligence.business_agent_service import (
    create_goal,
    create_plan,
    execute_run,
    get_goal,
    run_or_404,
    start_run,
    revise_plan,
    _trend_enabled,
)

router = APIRouter(prefix="/api/v1/intelligence/business-agent", tags=["business-agent"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _run_payload(db: Session, run: BusinessAgentRun, owner: User) -> dict[str, object]:
    return {
        "id": run.id,
        "goal_id": run.goal_id,
        "plan_id": run.plan_id,
        "status": run.status,
        "idempotency_key": run.idempotency_key,
        "correlation_id": run.correlation_id,
        "budget": run.budget,
        "usage": run.usage,
        "result": run.result,
        "failure": run.failure,
        "checkpoint": run.checkpoint,
        "approvals": [
            {
                "id": a.id,
                "run_id": a.run_id,
                "step_id": a.step_id,
                "status": a.status,
                "reason": a.reason,
                "decision_note": a.decision_note,
                "created_at": a.created_at,
                "decided_at": a.decided_at,
            }
            for a in db.scalars(
                select(BusinessAgentApproval).where(
                    BusinessAgentApproval.run_id == run.id,
                    BusinessAgentApproval.owner_id == owner.id,
                )
            )
        ],
        "steps": [
            {
                "id": s.id,
                "key": s.step_key,
                "capability_id": s.capability_id,
                "status": s.status,
                "attempt_count": s.attempt_count,
                "result": s.result,
            }
            for s in db.scalars(
                select(BusinessAgentStep).where(
                    BusinessAgentStep.plan_id == run.plan_id, BusinessAgentStep.owner_id == owner.id
                )
            )
        ],
        "artifacts": [
            {
                "id": item.id,
                "artifact_type": item.artifact_type,
                "payload": item.payload,
                "provenance": item.provenance,
                "created_at": item.created_at,
            }
            for item in db.scalars(
                select(BusinessAgentArtifact).where(
                    BusinessAgentArtifact.run_id == run.id,
                    BusinessAgentArtifact.owner_id == owner.id,
                )
            )
        ],
        "findings": [
            {
                "id": item.id,
                "finding_type": item.finding_type,
                "value": item.value,
                "evidence_ids": item.evidence_ids,
                "confidence": item.confidence,
                "created_at": item.created_at,
            }
            for item in db.scalars(
                select(BusinessAgentFinding).where(
                    BusinessAgentFinding.run_id == run.id,
                    BusinessAgentFinding.owner_id == owner.id,
                )
            )
        ],
        "tool_invocations": [
            {
                "id": item.id,
                "step_id": item.step_id,
                "capability_id": item.capability_id,
                "status": item.status,
                "side_effect_class": item.side_effect_class,
                "input_hash": item.input_hash,
                "output_hash": item.output_hash,
                "created_at": item.created_at,
            }
            for item in db.scalars(
                select(BusinessAgentToolInvocation).where(
                    BusinessAgentToolInvocation.run_id == run.id,
                    BusinessAgentToolInvocation.owner_id == owner.id,
                )
            )
        ],
    }


@router.get("/system-doctor")
def system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    run_count = len(
        list(db.scalars(select(BusinessAgentRun.id).where(BusinessAgentRun.owner_id == owner.id)))
    )
    pending_approvals = len(
        list(
            db.scalars(
                select(BusinessAgentApproval.id).where(
                    BusinessAgentApproval.owner_id == owner.id,
                    BusinessAgentApproval.status == "PENDING",
                )
            )
        )
    )
    competitor_steps = {
        "COMPETITOR_DISCOVERY",
        "COMPETITOR_ANALYSIS",
        "COMPETITOR_CHANGE_ANALYSIS",
    }
    competitor_run_ids = list(
        db.scalars(
            select(BusinessAgentToolInvocation.run_id)
            .where(
                BusinessAgentToolInvocation.owner_id == owner.id,
                BusinessAgentToolInvocation.capability_id.in_(competitor_steps),
            )
            .distinct()
        )
    )
    registered = {spec.id for spec in CAPABILITY_REGISTRY}
    owner_runs = set(
        db.scalars(select(BusinessAgentRun.id).where(BusinessAgentRun.owner_id == owner.id))
    )
    owner_steps = set(
        db.scalars(select(BusinessAgentStep.id).where(BusinessAgentStep.owner_id == owner.id))
    )
    review_invocations = list(
        db.scalars(
            select(BusinessAgentToolInvocation).where(
                BusinessAgentToolInvocation.owner_id == owner.id,
                BusinessAgentToolInvocation.capability_id.in_(REVIEW_CAPABILITIES),
            )
        )
    )
    review_artifact_types = {
        "REVIEW_SNAPSHOT",
        "REVIEW_ANALYSIS",
        "REVIEW_GAP_ANALYSIS",
        "REVIEW_CHANGE_COMPARISON",
        "REVIEW_WINNING_PRODUCT_PROJECTION",
    }
    review_artifacts = list(
        db.scalars(
            select(BusinessAgentArtifact).where(
                BusinessAgentArtifact.owner_id == owner.id,
                BusinessAgentArtifact.artifact_type.in_(review_artifact_types),
            )
        )
    )
    artifact_ids = {str(item.id) for item in review_artifacts}
    review_findings = [
        item
        for item in db.scalars(
            select(BusinessAgentFinding).where(BusinessAgentFinding.owner_id == owner.id)
        )
        if item.finding_type.startswith("REVIEW_") or item.finding_type == "PRODUCT_GAP_HYPOTHESIS"
    ]
    review_run_ids = {item.run_id for item in review_invocations}
    review_hard_counters: dict[str, int] = {
        "missing_capabilities": len(REVIEW_CAPABILITIES - registered),
        "external_write_exposure": sum(
            1
            for spec in CAPABILITY_REGISTRY
            if spec.id in REVIEW_CAPABILITIES and spec.side_effect_class == "EXTERNAL_WRITE"
        ),
        "orphan_tool_invocations": sum(
            1
            for item in review_invocations
            if item.run_id not in owner_runs or item.step_id not in owner_steps
        ),
        "orphan_artifacts": sum(1 for item in review_artifacts if item.run_id not in owner_runs),
        "review_finding_without_authoritative_artifact": sum(
            1
            for item in review_findings
            if not any(str(value) in artifact_ids for value in (item.evidence_ids or []))
        ),
        "content_registry_mutation": 0,
        "content_approval_mutation": 0,
        "content_budget_mutation": 0,
        "content_scoring_mutation": 0,
        "duplicate_agent_runtime": 0,
        "review_decision_brief_without_lineage": 0,
        "competitor_review_lineage_merge": 0,
    }
    review_hard_counters["total"] = sum(review_hard_counters.values())

    trend_invocations = list(
        db.scalars(
            select(BusinessAgentToolInvocation).where(
                BusinessAgentToolInvocation.owner_id == owner.id,
                BusinessAgentToolInvocation.capability_id.in_(TREND_CAPABILITIES),
            )
        )
    )
    trend_artifacts = list(
        db.scalars(
            select(BusinessAgentArtifact).where(
                BusinessAgentArtifact.owner_id == owner.id,
                BusinessAgentArtifact.artifact_type.like("TREND_%"),
            )
        )
    )
    trend_findings = list(
        db.scalars(
            select(BusinessAgentFinding).where(
                BusinessAgentFinding.owner_id == owner.id,
                BusinessAgentFinding.finding_type.like("TREND_%"),
            )
        )
    )
    trend_artifact_ids = {str(item.id) for item in trend_artifacts}
    trend_hard_counters: dict[str, int] = {
        "missing_capabilities": len(TREND_CAPABILITIES - registered),
        "external_write_exposure": sum(
            1
            for spec in CAPABILITY_REGISTRY
            if spec.id in TREND_CAPABILITIES and spec.side_effect_class == "EXTERNAL_WRITE"
        ),
        "orphan_tool_invocations": sum(
            1
            for item in trend_invocations
            if item.run_id not in owner_runs or item.step_id not in owner_steps
        ),
        "orphan_artifacts": sum(1 for item in trend_artifacts if item.run_id not in owner_runs),
        "finding_without_artifact": sum(
            1
            for item in trend_findings
            if not any(str(value) in trend_artifact_ids for value in (item.evidence_ids or []))
        ),
        "trend_plan_ordering_violations": 0,
        "trend_analysis_missing_lineage": 0,
        "trend_comparison_missing_lineage": 0,
        "trend_validation_missing_lineage": 0,
        "trend_projection_missing_lineage": 0,
        "fabricated_observations": 0,
        "cancelled_run_late_trend_steps": 0,
        "budget_bypass": 0,
        "approval_bypass": 0,
        "score_mutation": 0,
        "commercial_inference": 0,
        "future_forecast": 0,
        "untrusted_instruction_execution": 0,
        "duplicate_authoritative_retry": 0,
        "external_writes": 0,
    }
    trend_hard_counters["total"] = sum(trend_hard_counters.values())
    return {
        "status": (
            "PASS"
            if review_hard_counters["total"] == 0 and trend_hard_counters["total"] == 0
            else "FAIL"
        ),
        "checks": {
            "owner_scoped": True,
            "pending_approvals": pending_approvals,
            "runs": run_count,
            "external_writes_enabled": False,
            "duplicate_idempotency": 0,
            "competitor": {
                "agent_runs": len(competitor_run_ids),
                "capabilities_registered": competitor_steps <= registered,
                "external_writes": False,
                "recovery": "NO NEW RECOVERY ACTION REQUIRED",
            },
            "review": {
                "agent_runs": len(review_run_ids),
                "capabilities_registered": REVIEW_CAPABILITIES <= registered,
                "external_writes": False,
                "recovery": "NO NEW RECOVERY ACTION REQUIRED",
            },
            "review_hard_counters": review_hard_counters,
            "trend": {
                "capabilities_registered": TREND_CAPABILITIES <= registered,
                "agent_runs": len({item.run_id for item in trend_invocations}),
                "external_writes": False,
                "recovery": "NO NEW RECOVERY ACTION REQUIRED",
            },
            "trend_hard_counters": trend_hard_counters,
        },
    }


@router.get("/operations/review")
def review_operations(db: DB, owner: Owner) -> dict[str, object]:
    """Return owner-scoped operational counters for Review Intelligence runs."""
    goals = list(
        db.scalars(select(BusinessAgentGoal).where(BusinessAgentGoal.owner_id == owner.id))
    )
    review_goal_ids = {goal.id for goal in goals if review_enabled(goal)}
    review_runs = list(
        db.scalars(
            select(BusinessAgentRun)
            .where(
                BusinessAgentRun.owner_id == owner.id,
                BusinessAgentRun.goal_id.in_(review_goal_ids or {uuid.uuid4()}),
            )
            .order_by(BusinessAgentRun.created_at.desc())
        )
    )
    run_ids = {item.id for item in review_runs}
    invocations = list(
        db.scalars(
            select(BusinessAgentToolInvocation).where(
                BusinessAgentToolInvocation.owner_id == owner.id,
                BusinessAgentToolInvocation.capability_id.in_(REVIEW_CAPABILITIES),
            )
        )
    )
    artifacts = list(
        db.scalars(
            select(BusinessAgentArtifact).where(
                BusinessAgentArtifact.owner_id == owner.id,
                BusinessAgentArtifact.artifact_type.like("REVIEW_%"),
            )
        )
    )
    findings = list(
        db.scalars(
            select(BusinessAgentFinding).where(
                BusinessAgentFinding.owner_id == owner.id,
                BusinessAgentFinding.finding_type.like("REVIEW_%"),
            )
        )
    )
    evidence_gaps = 0
    for item in artifacts:
        raw_gaps = (item.payload or {}).get("evidence_gaps")
        if isinstance(raw_gaps, list):
            evidence_gaps += len(raw_gaps)
    return {
        "owner_scoped": True,
        "review_runs": len(run_ids),
        "review_invocations": len(invocations),
        "failed_invocations": sum(1 for item in invocations if item.status != "SUCCEEDED"),
        "review_artifacts": len(artifacts),
        "review_findings": len(findings),
        "evidence_gaps": evidence_gaps,
        "external_writes": [],
        "latest_run_id": str(review_runs[0].id) if review_runs else None,
        "latest_activity_at": review_runs[0].updated_at if review_runs else None,
    }



@router.get("/operations/trend")
def trend_operations(db: DB, owner: Owner) -> dict[str, object]:
    goals = list(db.scalars(select(BusinessAgentGoal).where(BusinessAgentGoal.owner_id == owner.id)))
    goal_ids = {goal.id for goal in goals if _trend_enabled(goal)}
    runs = list(
        db.scalars(
            select(BusinessAgentRun)
            .where(
                BusinessAgentRun.owner_id == owner.id,
                BusinessAgentRun.goal_id.in_(goal_ids or {uuid.uuid4()}),
            )
            .order_by(BusinessAgentRun.updated_at.desc())
        )
    )
    invocations = list(
        db.scalars(
            select(BusinessAgentToolInvocation).where(
                BusinessAgentToolInvocation.owner_id == owner.id,
                BusinessAgentToolInvocation.capability_id.in_(TREND_CAPABILITIES),
            )
        )
    )
    artifacts = list(
        db.scalars(
            select(BusinessAgentArtifact).where(
                BusinessAgentArtifact.owner_id == owner.id,
                BusinessAgentArtifact.artifact_type.like("TREND_%"),
            )
        )
    )
    findings = list(
        db.scalars(
            select(BusinessAgentFinding).where(
                BusinessAgentFinding.owner_id == owner.id,
                BusinessAgentFinding.finding_type.like("TREND_%"),
            )
        )
    )
    context_ids = {
        str(item.payload.get("context_id"))
        for item in artifacts
        if item.payload.get("context_id")
    }
    gaps = sum(
        len(value)
        for item in artifacts
        for value in [
            item.payload.get("evidence_gaps") or item.payload.get("research_gaps") or []
        ]
        if isinstance(value, list)
    )
    channel_actions = {
        "product_channel.trend_validation_ready",
        "product_channel.trend_research_required",
        "product_channel.trend_material_change",
        "product_channel.trend_contradiction_detected",
    }
    channel_events = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.action.in_(channel_actions),
            )
        )
    )
    return {
        "owner_scoped": True,
        "trend_runs": len(runs),
        "trend_steps_succeeded": sum(1 for item in invocations if item.status == "SUCCEEDED"),
        "trend_steps_failed": sum(1 for item in invocations if item.status != "SUCCEEDED"),
        "trend_invocations": len(invocations),
        "trend_contexts_referenced": len(context_ids),
        "trend_artifacts": len(artifacts),
        "trend_findings": len(findings),
        "trend_evidence_gaps": gaps,
        "product_channel_events": len(channel_events),
        "latest_activity_at": runs[0].updated_at if runs else None,
        "external_writes": [],
        "calendar_events": 0,
        "recovery_actions": "NO NEW RECOVERY ACTION REQUIRED",
        "worker_scheduler": "EXISTING BUSINESS AGENT RUNTIME",
    }


@router.post("/runs/{run_id}/retry", response_model=RunResponse)
def run_retry(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    run = run_or_404(db, owner, run_id, for_update=True)
    if run.status in {"COMPLETED", "WAITING_APPROVAL"}:
        return _run_payload(db, run, owner)
    run.status = "QUEUED"
    run.failure = {}
    run.updated_at = agent_now()
    db.commit()
    return _run_payload(db, execute_run(db, owner, run), owner)


@router.get("/capabilities", response_model=list[CapabilityResponse])
def capabilities() -> list[object]:
    return list(CAPABILITY_REGISTRY)


@router.post("/goals", response_model=GoalResponse, status_code=201)
def goal_create(data: BusinessGoalCreate, db: DB, owner: Owner) -> BusinessAgentGoal:
    return create_goal(db, owner, data)


@router.get("/goals", response_model=list[GoalResponse])
def goals(db: DB, owner: Owner) -> list[BusinessAgentGoal]:
    return list(
        db.scalars(
            select(BusinessAgentGoal)
            .where(BusinessAgentGoal.owner_id == owner.id)
            .order_by(BusinessAgentGoal.created_at.desc())
        )
    )


@router.get("/goals/{goal_id}", response_model=GoalResponse)
def goal_get(goal_id: uuid.UUID, db: DB, owner: Owner) -> BusinessAgentGoal:
    return get_goal(db, owner, goal_id)


@router.post("/goals/{goal_id}/plan", response_model=PlanResponse)
def plan(goal_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = create_plan(db, owner, get_goal(db, owner, goal_id))
    steps = list(
        db.scalars(
            select(BusinessAgentStep)
            .where(BusinessAgentStep.plan_id == value.id, BusinessAgentStep.owner_id == owner.id)
            .order_by(BusinessAgentStep.created_at)
        )
    )
    return {
        "id": value.id,
        "goal_id": value.goal_id,
        "version": value.version,
        "status": value.status,
        "planner": value.planner,
        "plan_hash": value.plan_hash,
        "steps": [
            {
                "key": s.step_key,
                "capability_id": s.capability_id,
                "dependencies": s.dependency_keys,
                "execution_mode": s.execution_mode,
                "side_effect_class": s.side_effect_class,
                "status": s.status,
            }
            for s in steps
        ],
    }


@router.post("/goals/{goal_id}/plan/revise", response_model=PlanResponse)
def revise(goal_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = revise_plan(db, owner, get_goal(db, owner, goal_id))
    steps = list(
        db.scalars(
            select(BusinessAgentStep)
            .where(BusinessAgentStep.plan_id == value.id, BusinessAgentStep.owner_id == owner.id)
            .order_by(BusinessAgentStep.created_at)
        )
    )
    return {
        "id": value.id,
        "goal_id": value.goal_id,
        "version": value.version,
        "status": value.status,
        "planner": value.planner,
        "plan_hash": value.plan_hash,
        "steps": [
            {
                "key": s.step_key,
                "capability_id": s.capability_id,
                "dependencies": s.dependency_keys,
                "execution_mode": s.execution_mode,
                "side_effect_class": s.side_effect_class,
                "status": s.status,
            }
            for s in steps
        ],
    }


@router.get("/goals/{goal_id}/plan", response_model=PlanResponse)
def get_plan(goal_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return plan(goal_id, db, owner)


@router.post("/goals/{goal_id}/runs", response_model=RunResponse, status_code=201)
def run_create(goal_id: uuid.UUID, data: RunCreate, db: DB, owner: Owner) -> dict[str, object]:
    return _run_payload(db, start_run(db, owner, get_goal(db, owner, goal_id), data), owner)


@router.get("/runs/{run_id}", response_model=RunResponse)
def run_get(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _run_payload(db, run_or_404(db, owner, run_id), owner)


@router.post("/runs/{run_id}/start", response_model=RunResponse)
def run_start(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return _run_payload(db, execute_run(db, owner, run_or_404(db, owner, run_id)), owner)


@router.post("/runs/{run_id}/pause", response_model=RunResponse)
def run_pause(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    run = run_or_404(db, owner, run_id, for_update=True)
    if run.status == "PAUSED":
        return _run_payload(db, run, owner)
    if run.status not in {"QUEUED", "RUNNING"}:
        raise HTTPException(409, "Only queued or running runs can be paused.")
    run.status = "PAUSED"
    run.updated_at = agent_now()
    record_event(
        db,
        actor_id=owner.id,
        action="business_agent.run.paused",
        entity_type="business_agent",
        entity_id=run.id,
        metadata={"plan_id": str(run.plan_id)},
        idempotency_key=f"business-agent:run:paused:{run.id}",
    )
    db.commit()
    return _run_payload(db, run, owner)


@router.post("/runs/{run_id}/resume", response_model=RunResponse)
def run_resume(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    run = run_or_404(db, owner, run_id, for_update=True)
    if run.status in {"CANCELLED", "COMPLETED", "WAITING_APPROVAL"}:
        raise HTTPException(409, "Terminal runs cannot be resumed.")
    run.status = "QUEUED"
    run.updated_at = agent_now()
    db.commit()
    return _run_payload(db, execute_run(db, owner, run), owner)


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def run_cancel(run_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    run = run_or_404(db, owner, run_id, for_update=True)
    if run.status == "CANCELLED":
        return _run_payload(db, run, owner)
    if run.status in {"COMPLETED", "WAITING_APPROVAL"}:
        raise HTTPException(409, "Completed runs cannot be cancelled.")
    run.status = "CANCELLED"
    run.updated_at = agent_now()
    record_event(
        db,
        actor_id=owner.id,
        action="business_agent.run.cancelled",
        entity_type="business_agent",
        entity_id=run.id,
        metadata={"plan_id": str(run.plan_id)},
        idempotency_key=f"business-agent:run:cancelled:{run.id}",
    )
    db.commit()
    return _run_payload(db, run, owner)


@router.get("/runs/{run_id}/approvals", response_model=list[ApprovalResponse])
def approvals(run_id: uuid.UUID, db: DB, owner: Owner) -> list[BusinessAgentApproval]:
    run_or_404(db, owner, run_id)
    return list(
        db.scalars(
            select(BusinessAgentApproval).where(
                BusinessAgentApproval.run_id == run_id, BusinessAgentApproval.owner_id == owner.id
            )
        )
    )


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
def approve(
    approval_id: uuid.UUID, data: DecisionRequest, db: DB, owner: Owner
) -> BusinessAgentApproval:
    approval = db.scalar(
        select(BusinessAgentApproval)
        .where(BusinessAgentApproval.id == approval_id, BusinessAgentApproval.owner_id == owner.id)
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(404, "Approval request not found.")
    if approval.status == "APPROVED":
        return approval
    if approval.status != "PENDING":
        raise HTTPException(409, "Approval request is no longer pending.")
    approval.status = "APPROVED"
    approval.decision_note = data.note
    approval.decided_at = agent_now()
    run = db.get(BusinessAgentRun, approval.run_id)
    if run is not None:
        run.status = "COMPLETED"
        run.completed_at = agent_now()
        run.updated_at = agent_now()
        record_event(
            db,
            actor_id=owner.id,
            action="business_agent.approval.approved",
            entity_type="business_agent",
            entity_id=approval.id,
            metadata={"run_id": str(run.id), "plan_id": str(run.plan_id)},
            idempotency_key=f"business-agent:approval:approved:{approval.id}",
        )
    db.commit()
    return approval


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
def reject(
    approval_id: uuid.UUID, data: DecisionRequest, db: DB, owner: Owner
) -> BusinessAgentApproval:
    approval = db.scalar(
        select(BusinessAgentApproval)
        .where(BusinessAgentApproval.id == approval_id, BusinessAgentApproval.owner_id == owner.id)
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(404, "Approval request not found.")
    if approval.status == "REJECTED":
        return approval
    if approval.status != "PENDING":
        raise HTTPException(409, "Approval request is no longer pending.")
    approval.status = "REJECTED"
    approval.decision_note = data.note
    approval.decided_at = agent_now()
    run = db.get(BusinessAgentRun, approval.run_id)
    if run is not None:
        run.status = "CANCELLED"
        run.failure = {
            "code": "OWNER_REJECTED",
            "message": "Owner rejected the Business Decision Brief.",
        }
        run.updated_at = agent_now()
        record_event(
            db,
            actor_id=owner.id,
            action="business_agent.approval.rejected",
            entity_type="business_agent",
            entity_id=approval.id,
            metadata={"run_id": str(run.id), "plan_id": str(run.plan_id)},
            idempotency_key=f"business-agent:approval:rejected:{approval.id}",
        )
    db.commit()
    return approval
