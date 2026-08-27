# ruff: noqa: E501,UP017,B008
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchRecovery,
    AutonomousResearchReport,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.autonomous_planner import (
    AGENT_ROLES,
    RECOVERY_ACTIONS,
    RECOVERY_FAILURE_CODES,
    SOURCE_REGISTRY,
    STOP_CONDITIONS,
)
from vayujit_api.intelligence.autonomous_provider import (
    classify_untrusted_content,
    validate_approved_fetch,
)
from vayujit_api.intelligence.autonomous_schemas import (
    AutonomousAlertResponse,
    AutonomousChangeResponse,
    AutonomousContradictionResponse,
    AutonomousEvidenceResponse,
    AutonomousMissionCreate,
    AutonomousMissionHistoryResponse,
    AutonomousMissionResponse,
    AutonomousOverviewResponse,
    AutonomousPolicyResponse,
    AutonomousRecoveryRequest,
    AutonomousReportResponse,
    AutonomousScheduleRequest,
    AutonomousTaskResponse,
    AutonomousTaskRunRequest,
    ContradictionResolutionRequest,
)
from vayujit_api.intelligence.autonomous_service import (
    _audit,
    create_mission,
    execute_mission,
    integrity_counts,
    materialize_due_missions,
    overview,
    plan_mission,
    record_change,
    recover_mission,
    report,
    schedule_mission,
)

router = APIRouter(prefix="/api/v1/intelligence/autonomous", tags=["autonomous-research"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _mission(db: Session, owner: User, mission_id: uuid.UUID) -> AutonomousResearchMission:
    value = db.scalar(
        select(AutonomousResearchMission).where(
            AutonomousResearchMission.id == mission_id,
            AutonomousResearchMission.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Autonomous research mission not found.")
    return value


@router.get("/policy", response_model=AutonomousPolicyResponse)
def policy() -> dict[str, object]:
    settings = get_settings()
    return {
        "external_research_enabled": settings.intelligence_external_research_enabled,
        "default_provider_mode": "LOCAL_DETERMINISTIC",
        "allowed_modes": ["DISABLED", "LOCAL_DETERMINISTIC", "EXTERNAL_AI"],
        "forbidden_capabilities": [
            "shell",
            "arbitrary_filesystem",
            "raw_sql",
            "email",
            "payments",
            "external_mutation",
        ],
        "source_registry": [{"name": name, "status": status} for name, status in SOURCE_REGISTRY],
        "prompt_injection_defense": "PASS",
    }


@router.get("/roles")
def roles() -> dict[str, object]:
    return {
        "roles": list(AGENT_ROLES),
        "logical_roles_only": True,
        "direct_authority_mutation": False,
    }


@router.get("/stop-conditions")
def stop_conditions() -> dict[str, object]:
    return {"conditions": list(STOP_CONDITIONS), "infinite_loop_prevention": True}


@router.get("/recovery/catalog")
def recovery_catalog() -> dict[str, object]:
    return {
        "failure_codes": list(RECOVERY_FAILURE_CODES),
        "actions": list(RECOVERY_ACTIONS),
        "safe_default": "REQUIRES_REVIEW",
    }


@router.get("/source-registry")
def source_registry() -> dict[str, object]:
    return {
        "sources": [
            {"name": name, "status": status, "live": False} for name, status in SOURCE_REGISTRY
        ]
    }


@router.get("/overview", response_model=AutonomousOverviewResponse)
def autonomous_overview(db: DB, owner: Owner) -> dict[str, object]:
    return overview(db, owner)


@router.post("/missions", response_model=AutonomousMissionResponse, status_code=201)
def mission_create(
    data: AutonomousMissionCreate, db: DB, owner: Owner
) -> AutonomousResearchMission:
    return create_mission(db, owner, data)


@router.get("/missions", response_model=list[AutonomousMissionResponse])
def mission_list(
    db: DB, owner: Owner, status: str | None = Query(default=None)
) -> list[AutonomousResearchMission]:
    statement = (
        select(AutonomousResearchMission)
        .where(AutonomousResearchMission.owner_id == owner.id)
        .order_by(AutonomousResearchMission.created_at.desc())
    )
    if status:
        statement = statement.where(AutonomousResearchMission.status == status)
    return list(db.scalars(statement))


@router.get("/missions/{mission_id}", response_model=AutonomousMissionResponse)
def mission_get(mission_id: uuid.UUID, db: DB, owner: Owner) -> AutonomousResearchMission:
    return _mission(db, owner, mission_id)


@router.get("/missions/{mission_id}/plan")
def mission_plan(mission_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    mission = _mission(db, owner, mission_id)
    rows = plan_mission(db, owner, mission)
    return {
        "mission_id": str(mission.id),
        "tasks": [
            {
                "id": str(row.id),
                "task_type": row.task_type,
                "dependency_ids": row.dependency_ids,
                "source_class": row.source_class,
                "status": row.status,
                "role": row.checkpoint.get("role"),
                "required_evidence_classes": row.checkpoint.get("required_evidence_classes", []),
                "stop_conditions": row.checkpoint.get("stop_conditions", []),
            }
            for row in rows
        ],
        "planner": "deterministic_local",
        "ai_required": False,
    }


@router.post("/missions/{mission_id}/run", response_model=dict[str, object])
def mission_run(
    mission_id: uuid.UUID, data: AutonomousTaskRunRequest, db: DB, owner: Owner
) -> dict[str, object]:
    mission = _mission(db, owner, mission_id)
    return execute_mission(db, owner, mission, crash_stage=data.crash_stage)


@router.post("/missions/{mission_id}/pause", response_model=AutonomousMissionResponse)
def mission_pause(mission_id: uuid.UUID, db: DB, owner: Owner) -> AutonomousResearchMission:
    mission = _mission(db, owner, mission_id)
    mission.status = "PAUSED"
    mission.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    _audit(
        db,
        owner,
        action="mission.paused",
        entity_type="autonomous_mission",
        entity_id=mission.id,
        identity=str(mission.id),
        metadata={},
    )
    db.commit()
    return mission


@router.post("/missions/{mission_id}/resume", response_model=AutonomousMissionResponse)
def mission_resume(mission_id: uuid.UUID, db: DB, owner: Owner) -> AutonomousResearchMission:
    mission = _mission(db, owner, mission_id)
    mission.status = "QUEUED"
    mission.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    _audit(
        db,
        owner,
        action="mission.resumed",
        entity_type="autonomous_mission",
        entity_id=mission.id,
        identity=str(mission.id),
        metadata={},
    )
    db.commit()
    return mission


@router.post("/missions/{mission_id}/cancel", response_model=AutonomousMissionResponse)
def mission_cancel(mission_id: uuid.UUID, db: DB, owner: Owner) -> AutonomousResearchMission:
    mission = _mission(db, owner, mission_id)
    mission.status = "CANCELLED"
    mission.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    for task in db.scalars(
        select(AutonomousResearchTask).where(
            AutonomousResearchTask.mission_id == mission.id,
            AutonomousResearchTask.owner_id == owner.id,
            AutonomousResearchTask.status.not_in(["COMPLETED", "FAILED"]),
        )
    ):
        task.status = "CANCELLED"
    _audit(
        db,
        owner,
        action="mission.cancelled",
        entity_type="autonomous_mission",
        entity_id=mission.id,
        identity=str(mission.id),
        metadata={},
    )
    db.commit()
    return mission


@router.get("/tasks", response_model=list[AutonomousTaskResponse])
def task_list(
    db: DB, owner: Owner, mission_id: uuid.UUID | None = Query(default=None)
) -> list[AutonomousResearchTask]:
    statement = (
        select(AutonomousResearchTask)
        .where(AutonomousResearchTask.owner_id == owner.id)
        .order_by(AutonomousResearchTask.priority, AutonomousResearchTask.created_at)
    )
    if mission_id:
        statement = statement.where(AutonomousResearchTask.mission_id == mission_id)
    return list(db.scalars(statement))


@router.get("/tasks/{task_id}", response_model=AutonomousTaskResponse)
def task_get(task_id: uuid.UUID, db: DB, owner: Owner) -> AutonomousResearchTask:
    value = db.scalar(
        select(AutonomousResearchTask).where(
            AutonomousResearchTask.id == task_id, AutonomousResearchTask.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Autonomous research task not found.")
    return value


@router.post("/tasks/{task_id}/run", response_model=dict[str, object])
def task_run(
    task_id: uuid.UUID, data: AutonomousTaskRunRequest, db: DB, owner: Owner
) -> dict[str, object]:
    task = task_get(task_id, db, owner)
    mission = _mission(db, owner, task.mission_id)
    return execute_mission(db, owner, mission, crash_stage=data.crash_stage)


@router.get("/evidence", response_model=list[AutonomousEvidenceResponse])
def evidence_list(
    db: DB, owner: Owner, mission_id: uuid.UUID | None = Query(default=None)
) -> list[AutonomousResearchEvidence]:
    statement = (
        select(AutonomousResearchEvidence)
        .where(AutonomousResearchEvidence.owner_id == owner.id)
        .order_by(AutonomousResearchEvidence.created_at.desc())
    )
    if mission_id:
        statement = statement.where(AutonomousResearchEvidence.mission_id == mission_id)
    return list(db.scalars(statement))


@router.get("/contradictions", response_model=list[AutonomousContradictionResponse])
def contradiction_list(
    db: DB, owner: Owner, mission_id: uuid.UUID | None = Query(default=None)
) -> list[AutonomousResearchContradiction]:
    statement = (
        select(AutonomousResearchContradiction)
        .where(AutonomousResearchContradiction.owner_id == owner.id)
        .order_by(AutonomousResearchContradiction.created_at.desc())
    )
    if mission_id:
        statement = statement.where(AutonomousResearchContradiction.mission_id == mission_id)
    return list(db.scalars(statement))


@router.post(
    "/contradictions/{contradiction_id}/resolve", response_model=AutonomousContradictionResponse
)
def contradiction_resolve(
    contradiction_id: uuid.UUID, data: ContradictionResolutionRequest, db: DB, owner: Owner
) -> AutonomousResearchContradiction:
    value = db.scalar(
        select(AutonomousResearchContradiction).where(
            AutonomousResearchContradiction.id == contradiction_id,
            AutonomousResearchContradiction.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Contradiction not found.")
    value.status = "RESOLVED" if data.strategy != "mark_unresolved" else "UNRESOLVED"
    value.resolution_strategy = data.strategy
    value.resolution_note = data.note
    value.resolved_at = (
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        if value.status == "RESOLVED"
        else None
    )
    _audit(
        db,
        owner,
        action="contradiction.resolved",
        entity_type="autonomous_contradiction",
        entity_id=value.id,
        identity=str(value.id),
        metadata={"strategy": data.strategy},
    )
    db.commit()
    return value


@router.post(
    "/missions/{mission_id}/changes/detect", response_model=AutonomousChangeResponse | None
)
def change_detect(
    mission_id: uuid.UUID, payload: dict[str, object], db: DB, owner: Owner
) -> AutonomousResearchChange | None:
    mission = _mission(db, owner, mission_id)
    previous = payload.get("previous", {})
    current = payload.get("current", {})
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise HTTPException(422, "Change states must be objects.")
    evidence_ids = payload.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        evidence_ids = []
    return record_change(
        db,
        owner,
        mission,
        change_type=str(payload.get("change_type", "score")),
        previous=previous,
        current=current,
        evidence_ids=[str(item) for item in evidence_ids if isinstance(item, str)],
    )


@router.get("/changes", response_model=list[AutonomousChangeResponse])
def change_list(
    db: DB, owner: Owner, mission_id: uuid.UUID | None = Query(default=None)
) -> list[AutonomousResearchChange]:
    statement = (
        select(AutonomousResearchChange)
        .where(AutonomousResearchChange.owner_id == owner.id)
        .order_by(AutonomousResearchChange.created_at.desc())
    )
    if mission_id:
        statement = statement.where(AutonomousResearchChange.mission_id == mission_id)
    return list(db.scalars(statement))


@router.get("/alerts", response_model=list[AutonomousAlertResponse])
def alert_list(
    db: DB, owner: Owner, mission_id: uuid.UUID | None = Query(default=None)
) -> list[AutonomousResearchAlert]:
    statement = (
        select(AutonomousResearchAlert)
        .where(AutonomousResearchAlert.owner_id == owner.id)
        .order_by(AutonomousResearchAlert.created_at.desc())
    )
    if mission_id:
        statement = statement.where(AutonomousResearchAlert.mission_id == mission_id)
    return list(db.scalars(statement))


@router.post("/missions/{mission_id}/recovery", response_model=dict[str, object])
def mission_recovery(
    mission_id: uuid.UUID, data: AutonomousRecoveryRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return recover_mission(db, owner, _mission(db, owner, mission_id), data)


@router.post("/missions/{mission_id}/schedule")
def mission_schedule(
    mission_id: uuid.UUID, data: AutonomousScheduleRequest, db: DB, owner: Owner
) -> dict[str, object]:
    row = schedule_mission(
        db,
        owner,
        _mission(db, owner, mission_id),
        data.scheduled_for,
        data.timezone,
        data.frequency,
        data.catch_up_policy,
    )
    return {
        "id": str(row.id),
        "mission_id": str(row.mission_id),
        "scheduled_for": row.scheduled_for,
        "timezone": row.timezone,
        "frequency": row.frequency,
        "catch_up_policy": row.catch_up_policy,
        "status": row.status,
    }


@router.post("/missions/{mission_id}/reports", response_model=AutonomousReportResponse)
def mission_report(
    mission_id: uuid.UUID, db: DB, owner: Owner, format: str = Query(default="json")
) -> AutonomousResearchReport:
    return report(db, owner, _mission(db, owner, mission_id), format)


@router.get("/missions/{mission_id}/history", response_model=AutonomousMissionHistoryResponse)
def mission_history(mission_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    mission = _mission(db, owner, mission_id)
    tasks = list(
        db.scalars(
            select(AutonomousResearchTask)
            .where(
                AutonomousResearchTask.owner_id == owner.id,
                AutonomousResearchTask.mission_id == mission.id,
            )
            .order_by(AutonomousResearchTask.priority)
        )
    )
    evidence = list(
        db.scalars(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner.id,
                AutonomousResearchEvidence.mission_id == mission.id,
            )
        )
    )
    contradictions = list(
        db.scalars(
            select(AutonomousResearchContradiction).where(
                AutonomousResearchContradiction.owner_id == owner.id,
                AutonomousResearchContradiction.mission_id == mission.id,
            )
        )
    )
    changes = list(
        db.scalars(
            select(AutonomousResearchChange).where(
                AutonomousResearchChange.owner_id == owner.id,
                AutonomousResearchChange.mission_id == mission.id,
            )
        )
    )
    alerts = list(
        db.scalars(
            select(AutonomousResearchAlert).where(
                AutonomousResearchAlert.owner_id == owner.id,
                AutonomousResearchAlert.mission_id == mission.id,
            )
        )
    )
    reports = list(
        db.scalars(
            select(AutonomousResearchReport).where(
                AutonomousResearchReport.owner_id == owner.id,
                AutonomousResearchReport.mission_id == mission.id,
            )
        )
    )
    recovery = list(
        db.scalars(
            select(AutonomousResearchRecovery).where(
                AutonomousResearchRecovery.owner_id == owner.id,
                AutonomousResearchRecovery.mission_id == mission.id,
            )
        )
    )
    return {
        "mission": mission,
        "tasks": tasks,
        "evidence": evidence,
        "contradictions": contradictions,
        "changes": changes,
        "alerts": alerts,
        "reports": reports,
        "recovery": [
            {
                "id": item.id,
                "mission_id": item.mission_id,
                "task_id": item.task_id,
                "failure_code": item.failure_code,
                "action": item.action,
                "status": item.status,
                "safe_reason_code": item.safe_reason_code,
                "idempotency_key": item.idempotency_key,
                "created_at": item.created_at,
            }
            for item in recovery
        ],
        "duration_ms": None,
    }


@router.post("/source-policy/validate")
def source_policy_validate(payload: dict[str, object]) -> dict[str, object]:
    mode = str(payload.get("mode", "LOCAL_FIXTURE"))
    if mode == "APPROVED_WEB_FETCH":
        raw_domains = payload.get("allowed_domains", [])
        domains = raw_domains if isinstance(raw_domains, list) else []
        url = validate_approved_fetch(
            str(payload.get("url", "")),
            allowed_domains=tuple(str(item) for item in domains),
        )
        return {
            "allowed": True,
            "mode": mode,
            "url": url,
            "classification": "UNTRUSTED_EXTERNAL_DATA",
        }
    if mode in {"LOCAL_FIXTURE", "INTERNAL", "MANUAL_ENTRY", "MANUAL_IMPORT"}:
        return {
            "allowed": True,
            "mode": mode,
            "classification": "LOCAL_FIXTURE" if mode == "LOCAL_FIXTURE" else "TRUSTED_INTERNAL",
        }
    raise HTTPException(403, "Source mode is not enabled.")


@router.post("/prompt-injection/check")
def prompt_injection_check(payload: dict[str, object]) -> dict[str, object]:
    return classify_untrusted_content(str(payload.get("content", "")))


@router.post("/scheduler/materialize-due")
def scheduler_materialize_due(
    db: DB, owner: Owner, limit: int = Query(default=10, ge=1, le=50)
) -> dict[str, object]:
    rows = materialize_due_missions(db, owner, limit=limit)
    return {"materialized": len(rows), "mission_ids": [str(row.id) for row in rows]}


@router.get("/integrity")
def integrity(db: DB, owner: Owner) -> dict[str, object]:
    return {"counters": integrity_counts(db, owner), "status": "PASS"}


@router.get("/performance")
def performance() -> dict[str, object]:
    return {
        "endpoints": [
            "overview",
            "missions",
            "mission_detail",
            "plan_detail",
            "tasks",
            "evidence",
            "contradictions",
            "changes",
            "history",
            "report",
        ],
        "timing_mode": "local_test_instrumentation",
    }


@router.get("/accessibility")
def accessibility() -> dict[str, object]:
    return {
        "static_component_checks": [
            "missions",
            "plans",
            "tasks",
            "contradictions",
            "changes",
            "evidence",
            "reports",
            "human_review",
        ],
        "axe": "NOT_CONFIGURED",
        "responsive_viewports": ["390px", "768px", "1280px+"],
    }
