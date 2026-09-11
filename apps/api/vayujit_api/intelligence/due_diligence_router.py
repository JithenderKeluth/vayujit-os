from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission
from vayujit_api.intelligence.autonomous_schemas import AutonomousRecoveryRequest
from vayujit_api.intelligence.autonomous_service import execute_mission, recover_mission
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
    SupplierResearchPlan,
    SupplierResearchTask,
)
from vayujit_api.intelligence.due_diligence_schemas import (
    DueDiligenceContextCreate,
    HumanGapAction,
    ResearchPlanCreate,
)
from vayujit_api.intelligence.due_diligence_service import (
    _gap_lineage,
    assess,
    context_json,
    create_context,
    create_plan,
    history,
    human_action,
    integrity_report,
    operations,
    render_report,
    serialize_plan,
    sourcing_guard,
)

router = APIRouter(
    prefix="/api/v1/intelligence/supplier-due-diligence", tags=["supplier-due-diligence"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _context(db: Session, owner: User, ident: uuid.UUID) -> SupplierDueDiligenceContext:
    row = db.scalar(
        select(SupplierDueDiligenceContext).where(
            SupplierDueDiligenceContext.id == ident,
            SupplierDueDiligenceContext.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Due diligence context not found.")
    return row


@router.get("/operations")
def ops(db: DB, owner: Owner) -> dict[str, int]:
    return operations(db, owner)


@router.get("/system-doctor")
def doctor() -> dict[str, object]:
    return {
        "status": "healthy",
        "runtime": "shared_autonomous_research",
        "provider_modes": "inherited",
        "external_calls": "bounded_and_configured",
        "storage": "ready",
        "verifier": "shared",
        "contact_supplier": False,
    }


@router.post("/contexts")
def contexts(data: DueDiligenceContextCreate, db: DB, owner: Owner) -> dict[str, object]:
    row, reused = create_context(db, owner, data)
    return {"id": str(row.id), "status": row.status, "reused": reused}


@router.get("/contexts")
def list_contexts(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        context_json(db, owner, row)
        for row in db.scalars(
            select(SupplierDueDiligenceContext)
            .where(SupplierDueDiligenceContext.owner_id == owner.id)
            .order_by(SupplierDueDiligenceContext.created_at.desc())
        )
    ]


@router.get("/contexts/{context_id}")
def detail(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return context_json(db, owner, _context(db, owner, context_id))


@router.post("/contexts/{context_id}/assess")
def reassess(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return assess(db, owner, _context(db, owner, context_id))


@router.get("/contexts/{context_id}/gaps")
def gaps(context_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return context_json(db, owner, _context(db, owner, context_id))["gaps"]  # type: ignore[return-value]


@router.get("/contexts/{context_id}/gaps/{gap_id}")
def gap_detail(context_id: uuid.UUID, gap_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    _context(db, owner, context_id)
    gap = db.scalar(
        select(SupplierEvidenceGap).where(
            SupplierEvidenceGap.id == gap_id,
            SupplierEvidenceGap.context_id == context_id,
            SupplierEvidenceGap.owner_id == owner.id,
        )
    )
    if gap is None:
        raise HTTPException(404, "Evidence gap not found.")
    return {
        "id": str(gap.id),
        "context_id": str(gap.context_id),
        "assessment_version": gap.assessment_version,
        "dimension": gap.dimension,
        "status": gap.status,
        "severity": gap.severity,
        "classification": gap.classification,
        "reason": gap.reason,
        "required_evidence": gap.required_evidence,
        "evidence_refs": gap.evidence_refs,
        "resolution_evidence_refs": gap.resolution_evidence_refs,
        "resolution_type": gap.resolution_type,
        "resolution_observation_ids": gap.resolution_observation_ids,
        "resolved_at": gap.resolved_at.isoformat() if gap.resolved_at else None,
        "resolved_by": str(gap.resolved_by) if gap.resolved_by else None,
        "confidence": float(gap.confidence or 0),
        "freshness": gap.freshness_state,
        "contradiction": gap.contradiction_state,
        "priority_score": float(gap.priority_score or 0),
        "evidence_count": len((gap.evidence_refs or []) + (gap.resolution_evidence_refs or [])),
        "verification_state": _gap_lineage(db, owner, gap)["verification_state"],
        "lineage": _gap_lineage(db, owner, gap),
    }


@router.post("/contexts/{context_id}/plans")
def plan(
    context_id: uuid.UUID, data: ResearchPlanCreate, db: DB, owner: Owner
) -> dict[str, object]:
    value, reused = create_plan(db, owner, _context(db, owner, context_id), data)
    return {**value, "reused": reused}


@router.get("/contexts/{context_id}/plans")
def plans(context_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    _context(db, owner, context_id)
    return [
        serialize_plan(row)
        for row in db.scalars(
            select(SupplierResearchPlan)
            .where(
                SupplierResearchPlan.owner_id == owner.id,
                SupplierResearchPlan.context_id == context_id,
            )
            .order_by(SupplierResearchPlan.created_at.desc())
        )
    ]


@router.post("/plans/{plan_id}/run")
def run_plan(plan_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    mission = next(
        (
            row
            for row in db.scalars(
                select(AutonomousResearchMission).where(
                    AutonomousResearchMission.owner_id == owner.id,
                    AutonomousResearchMission.mission_type == "SUPPLIER_VERIFICATION",
                )
            )
            if row.scope.get("plan_id") == str(plan_id)
        ),
        None,
    )
    if mission is None:
        raise HTTPException(404, "Research plan execution not found.")
    return execute_mission(db, owner, mission)


@router.get("/plans/{plan_id}/tasks")
def tasks(plan_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    plan = db.scalar(
        select(SupplierResearchPlan).where(
            SupplierResearchPlan.id == plan_id,
            SupplierResearchPlan.owner_id == owner.id,
        )
    )
    if plan is None:
        raise HTTPException(404, "Research plan not found.")
    return [
        {
            "id": str(row.id),
            "gap_id": str(row.gap_id),
            "task_type": row.task_type,
            "status": row.status,
            "priority": float(row.priority or 0),
        }
        for row in db.scalars(
            select(SupplierResearchTask).where(
                SupplierResearchTask.owner_id == owner.id, SupplierResearchTask.plan_id == plan_id
            )
        )
    ]


@router.post("/gaps/{gap_id}/{action}")
def gap_action(
    gap_id: uuid.UUID, action: str, data: HumanGapAction, db: DB, owner: Owner
) -> dict[str, object]:
    gap = db.scalar(
        select(SupplierEvidenceGap).where(
            SupplierEvidenceGap.id == gap_id, SupplierEvidenceGap.owner_id == owner.id
        )
    )
    if gap is None:
        raise HTTPException(404, "Evidence gap not found.")
    return human_action(db, owner, gap, action, data)


@router.post("/contexts/{context_id}/recovery")
def recover_context(
    context_id: uuid.UUID, data: AutonomousRecoveryRequest, db: DB, owner: Owner
) -> dict[str, object]:
    context = _context(db, owner, context_id)
    mission = next(
        (
            row
            for row in db.scalars(
                select(AutonomousResearchMission).where(
                    AutonomousResearchMission.owner_id == owner.id,
                    AutonomousResearchMission.mission_type == "SUPPLIER_VERIFICATION",
                )
            )
            if row.scope.get("due_diligence_context_id") == str(context.id)
        ),
        None,
    )
    if mission is None:
        raise HTTPException(404, "Research execution not found.")
    return recover_mission(db, owner, mission, data)


@router.get("/contexts/{context_id}/sourcing-guard")
def sourcing_guard_status(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return sourcing_guard(db, owner, context_id)


@router.get("/contexts/{context_id}/readiness")
def readiness(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    value = context_json(db, owner, _context(db, owner, context_id))
    return {
        "readiness": value["readiness"],
        "summary": value["summary"],
        "blocking_gaps": [
            g
            for g in value["gaps"]
            if g["severity"] in {"CRITICAL", "HIGH"}
            and g["status"] not in {"RESOLVED", "WAIVED_BY_HUMAN"}
        ],
    }


@router.get("/contexts/{context_id}/history")
def context_history(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return history(db, owner, _context(db, owner, context_id))


@router.get("/contexts/{context_id}/report", response_model=None)
def report(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    format_name: str = Query("json", alias="format"),
) -> dict[str, object] | PlainTextResponse | HTMLResponse:
    value = context_json(db, owner, _context(db, owner, context_id))
    payload = {
        "report_version": "due-diligence-v1",
        **value,
        "recommendations": (
            ["Review unresolved required evidence before sourcing."]
            if value["readiness"] != "SUFFICIENT"
            else ["Continue human review before sourcing."]
        ),
    }
    rendered = render_report(payload, format_name.casefold())
    if isinstance(rendered, str):
        if format_name.casefold() == "html":
            return HTMLResponse(rendered)
        return PlainTextResponse(rendered)
    return rendered


@router.get("/integrity")
def integrity(db: DB, owner: Owner) -> dict[str, int]:
    return integrity_report(db, owner)
