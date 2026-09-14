"""Authenticated scenario decision-support API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence import scenario_service as service
from vayujit_api.intelligence.scenario_generation import generate
from vayujit_api.intelligence.scenario_models import (
    SourcingScenario,
    SourcingScenarioContext,
    SourcingScenarioEvent,
    SourcingScenarioVersion,
)
from vayujit_api.intelligence.scenario_projection import calendar, doctor, overview
from vayujit_api.intelligence.scenario_research import request_research
from vayujit_api.intelligence.scenario_schemas import (
    Command,
    ContextCreate,
    DecisionRequest,
    GenerateRequest,
    ScenarioCreate,
    SensitivityRequest,
    VersionCommand,
)

router = APIRouter(prefix="/api/v1/intelligence/sourcing-scenarios", tags=["sourcing-scenarios"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/contexts", status_code=201)
def create_context(data: ContextCreate, db: DB, owner: Owner) -> dict[str, Any]:
    return service.create_context(db, owner, data)


@router.get("/operations")
def operations(db: DB, owner: Owner) -> dict[str, Any]:
    return overview(db, owner)


@router.get("/system-doctor")
def system_doctor(db: DB, owner: Owner) -> dict[str, Any]:
    return doctor(db, owner)


@router.get("/calendar")
def calendar_items(db: DB, owner: Owner) -> list[dict[str, Any]]:
    return calendar(db, owner)


@router.get("/contexts")
def contexts(db: DB, owner: Owner) -> list[dict[str, Any]]:
    return [
        {
            "id": str(c.id),
            "product_id": str(c.product_id) if c.product_id else None,
            "opportunity_id": str(c.opportunity_id) if c.opportunity_id else None,
            "shortlist_version_id": str(c.shortlist_version_id),
            "settings": c.settings,
            "status": c.status,
            "current_version": c.current_version,
        }
        for c in db.scalars(
            select(SourcingScenarioContext)
            .where(
                SourcingScenarioContext.owner_id == owner.id,
            )
            .order_by(SourcingScenarioContext.created_at.desc())
            .limit(200)
        )
    ]


@router.get("/contexts/{context_id}")
def context(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    c = service.owned(db, SourcingScenarioContext, owner, context_id)
    rows = list(
        db.scalars(
            select(SourcingScenario)
            .where(
                SourcingScenario.owner_id == owner.id,
                SourcingScenario.context_id == c.id,
            )
            .order_by(SourcingScenario.created_at)
        )
    )
    return {
        "id": str(c.id),
        "settings": c.settings,
        "status": c.status,
        "scenarios": [
            {
                "id": str(s.id),
                "name": s.name,
                "status": s.status,
                "version": s.current_version,
                "scenario_type": s.scenario_type,
            }
            for s in rows
        ],
    }


@router.post("/contexts/{context_id}/scenarios", status_code=201)
def create_scenario(
    context_id: uuid.UUID, data: ScenarioCreate, db: DB, owner: Owner
) -> dict[str, Any]:
    return service.create_scenario(db, owner, context_id, data)


@router.post("/contexts/{context_id}/generate", status_code=201)
def generate_baselines(
    context_id: uuid.UUID, data: GenerateRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    return generate(db, owner, context_id, data)


@router.get("/contexts/{context_id}/comparison")
def comparison(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    return service.comparison(db, owner, context_id)


@router.post("/contexts/{context_id}/recommendations")
def recommend(context_id: uuid.UUID, data: Command, db: DB, owner: Owner) -> dict[str, Any]:
    return service.recommend(db, owner, context_id, data)


@router.get("/scenarios/{scenario_id}")
def scenario(scenario_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    return service.detail(db, owner, scenario_id)


@router.get("/scenarios/{scenario_id}/versions")
def versions(scenario_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, Any]]:
    service.owned(db, SourcingScenario, owner, scenario_id)
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "snapshot": v.snapshot,
            "result": v.result,
            "created_at": v.created_at.isoformat(),
            "calculation_version": v.calculation_version,
            "scoring_version": v.scoring_version,
            "landed_cost_version": v.landed_cost_version,
        }
        for v in db.scalars(
            select(SourcingScenarioVersion)
            .where(
                SourcingScenarioVersion.owner_id == owner.id,
                SourcingScenarioVersion.scenario_id == scenario_id,
            )
            .order_by(SourcingScenarioVersion.version)
        )
    ]


@router.get("/versions/{version_id}")
def version(version_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    v = service.owned(db, SourcingScenarioVersion, owner, version_id)
    return {
        "id": str(v.id),
        "scenario_id": str(v.scenario_id),
        "version": v.version,
        "snapshot": v.snapshot,
        "result": v.result,
    }


@router.post("/scenarios/{scenario_id}/recalculate")
def recalculate(
    scenario_id: uuid.UUID, data: VersionCommand, db: DB, owner: Owner
) -> dict[str, Any]:
    return service.recalculate(db, owner, scenario_id, data)


@router.post("/scenarios/{scenario_id}/decisions")
def decide(scenario_id: uuid.UUID, data: DecisionRequest, db: DB, owner: Owner) -> dict[str, Any]:
    return service.decide(db, owner, scenario_id, data)


@router.post("/scenarios/{scenario_id}/handoffs")
def handoff(scenario_id: uuid.UUID, data: VersionCommand, db: DB, owner: Owner) -> dict[str, Any]:
    return service.handoff(db, owner, scenario_id, data)


@router.post("/scenarios/{scenario_id}/sensitivity")
def what_if(
    scenario_id: uuid.UUID, data: SensitivityRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    return service.what_if(db, owner, scenario_id, data)


@router.post("/scenarios/{scenario_id}/research")
def research(scenario_id: uuid.UUID, data: VersionCommand, db: DB, owner: Owner) -> dict[str, Any]:
    return request_research(db, owner, scenario_id, data)


@router.get("/contexts/{context_id}/history")
def history(context_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, Any]]:
    service.owned(db, SourcingScenarioContext, owner, context_id)
    return [
        {
            "id": str(e.id),
            "event": e.event_type,
            "actor": str(e.owner_id),
            "created_at": e.created_at.isoformat(),
            "payload": e.payload,
        }
        for e in db.scalars(
            select(SourcingScenarioEvent)
            .where(
                SourcingScenarioEvent.owner_id == owner.id,
                SourcingScenarioEvent.context_id == context_id,
            )
            .order_by(SourcingScenarioEvent.created_at, SourcingScenarioEvent.id)
        )
    ]


@router.get("/contexts/{context_id}/report")
def report(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    return {
        "classification": "ESTIMATED_INTERNAL_PLANNING_ONLY",
        "context": context(context_id, db, owner),
        "comparison": comparison(context_id, db, owner),
        "history": history(context_id, db, owner),
    }
