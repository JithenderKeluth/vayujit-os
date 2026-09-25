"""Owner-scoped 13F economic scenario and sensitivity API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.economic_scenario_models import (
    EconomicSensitivityRun,
)
from vayujit_api.intelligence.economic_scenario_schemas import (
    EconomicScenarioCreate,
    EconomicScenarioRun,
    EconomicSensitivityCreate,
)
from vayujit_api.intelligence.economic_scenario_service import (
    create_scenario,
    list_results,
    list_scenarios,
    run_scenario,
    scenario_detail,
    sensitivity,
)

router = APIRouter(
    prefix="/api/v1/intelligence/sourcing-economics/scenarios",
    tags=["intelligence-sourcing-economics-scenarios"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/contexts/{context_id}", status_code=201)
def scenario_create(
    context_id: uuid.UUID, data: EconomicScenarioCreate, db: DB, owner: Owner
) -> dict[str, Any]:
    return create_scenario(db, owner, context_id, data)


@router.get("")
def scenario_list(db: DB, owner: Owner, context_id: uuid.UUID | None = None) -> dict[str, object]:
    return {"items": list_scenarios(db, owner, context_id)}


@router.get("/results/all")
def all_results(db: DB, owner: Owner) -> dict[str, object]:
    return {"items": list_results(db, owner)}


@router.get("/{scenario_id}")
def scenario_get(scenario_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    return scenario_detail(db, owner, scenario_id)


@router.post("/{scenario_id}/run", status_code=201)
def scenario_run(
    scenario_id: uuid.UUID, data: EconomicScenarioRun, db: DB, owner: Owner
) -> dict[str, Any]:
    return run_scenario(db, owner, scenario_id, data)


@router.post("/{scenario_id}/sensitivity", status_code=201)
def scenario_sensitivity(
    scenario_id: uuid.UUID, data: EconomicSensitivityCreate, db: DB, owner: Owner
) -> dict[str, Any]:
    return sensitivity(db, owner, scenario_id, data)


@router.get("/{scenario_id}/results")
def scenario_results(scenario_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return {"items": list_results(db, owner, scenario_id)}


@router.get("/{scenario_id}/sensitivity-runs")
def sensitivity_runs(scenario_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    rows = db.scalars(
        select(EconomicSensitivityRun)
        .where(
            EconomicSensitivityRun.owner_id == owner.id,
            EconomicSensitivityRun.scenario_id == scenario_id,
        )
        .order_by(EconomicSensitivityRun.created_at.desc())
        .limit(100)
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "dimension": row.dimension,
                "points": row.points,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }
