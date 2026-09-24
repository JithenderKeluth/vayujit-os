from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.economic_calculation_models import EconomicCalculation
from vayujit_api.intelligence.economic_calculation_service import (
    calculate_from_snapshot,
    list_breakdown,
)
from vayujit_api.intelligence.economic_fx_models import FXObservation
from vayujit_api.intelligence.economic_fx_service import (
    create_observation,
    list_observations,
    list_snapshots,
)
from vayujit_api.intelligence.economic_fx_service import (
    create_snapshot as create_fx_snapshot,
)
from vayujit_api.intelligence.economic_fx_service import (
    get_snapshot as get_fx_snapshot,
)
from vayujit_api.intelligence.economic_models import (
    EconomicAssumption,
    EconomicContext,
    EconomicCostComponent,
    EconomicInputSnapshot,
    EconomicQuoteInput,
    EconomicSnapshotComponent,
)
from vayujit_api.intelligence.economic_schemas import (
    EconomicAssumptionCreate,
    EconomicCalculationRequest,
    EconomicContextCreate,
    EconomicContextUpdate,
    EconomicCostComponentCreate,
    EconomicQuoteInputCreate,
    FXObservationCreate,
    FXSnapshotCreate,
)
from vayujit_api.intelligence.economic_service import (
    create_assumption,
    create_component,
    create_context,
    create_quote,
    create_snapshot,
    update_context,
)

router = APIRouter(
    prefix="/api/v1/intelligence/sourcing-economics", tags=["intelligence-sourcing-economics"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/contexts", status_code=201)
def context_create(data: EconomicContextCreate, db: DB, owner: Owner):
    row, reused = create_context(db, owner, data)
    return {"context": row, "idempotent_reuse": reused}


@router.get("/contexts")
def context_list(db: DB, owner: Owner):
    rows = db.scalars(
        select(EconomicContext)
        .where(EconomicContext.owner_id == owner.id)
        .order_by(EconomicContext.updated_at.desc())
    ).all()
    return {"items": rows}


@router.get("/contexts/{context_id}")
def context_detail(context_id: uuid.UUID, db: DB, owner: Owner):
    row = db.scalar(
        select(EconomicContext).where(
            EconomicContext.id == context_id, EconomicContext.owner_id == owner.id
        )
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Economic context not found.")
    return {
        "context": row,
        "quotes": db.scalars(
            select(EconomicQuoteInput)
            .where(EconomicQuoteInput.context_id == row.id, EconomicQuoteInput.owner_id == owner.id)
            .order_by(EconomicQuoteInput.created_at.desc())
        ).all(),
        "components": db.scalars(
            select(EconomicCostComponent)
            .where(
                EconomicCostComponent.context_id == row.id,
                EconomicCostComponent.owner_id == owner.id,
            )
            .order_by(EconomicCostComponent.created_at.desc())
        ).all(),
        "assumptions": db.scalars(
            select(EconomicAssumption)
            .where(EconomicAssumption.context_id == row.id, EconomicAssumption.owner_id == owner.id)
            .order_by(EconomicAssumption.key, EconomicAssumption.version)
        ).all(),
        "snapshots": db.scalars(
            select(EconomicInputSnapshot)
            .where(
                EconomicInputSnapshot.context_id == row.id,
                EconomicInputSnapshot.owner_id == owner.id,
            )
            .order_by(EconomicInputSnapshot.version.desc())
        ).all(),
    }


@router.patch("/contexts/{context_id}")
def context_update(context_id: uuid.UUID, data: EconomicContextUpdate, db: DB, owner: Owner):
    from vayujit_api.intelligence.economic_service import _owned

    return update_context(
        db, owner, _owned(db, EconomicContext, owner.id, context_id, "Economic context"), data
    )


@router.post("/quotes", status_code=201)
def quote_create(data: EconomicQuoteInputCreate, db: DB, owner: Owner):
    row, reused = create_quote(db, owner, data)
    return {"quote": row, "idempotent_reuse": reused}


@router.post("/components", status_code=201)
def component_create(data: EconomicCostComponentCreate, db: DB, owner: Owner):
    row, reused = create_component(db, owner, data)
    return {"component": row, "idempotent_reuse": reused}


@router.post("/assumptions", status_code=201)
def assumption_create(data: EconomicAssumptionCreate, db: DB, owner: Owner):
    return {"assumption": create_assumption(db, owner, data)}


@router.post("/snapshots", status_code=201)
def snapshot_create(context_id: uuid.UUID, db: DB, owner: Owner):
    row, reused = create_snapshot(db, owner, context_id)
    return {"snapshot": row, "idempotent_reuse": reused}


@router.get("/snapshots")
def snapshot_list(db: DB, owner: Owner, context_id: uuid.UUID | None = None):
    query = select(EconomicInputSnapshot).where(EconomicInputSnapshot.owner_id == owner.id)
    if context_id is not None:
        query = query.where(EconomicInputSnapshot.context_id == context_id)
    return {"items": db.scalars(query.order_by(EconomicInputSnapshot.created_at.desc())).all()}


@router.get("/snapshots/{snapshot_id}")
def snapshot_detail(snapshot_id: uuid.UUID, db: DB, owner: Owner):
    from vayujit_api.intelligence.economic_service import _owned

    row = _owned(db, EconomicInputSnapshot, owner.id, snapshot_id, "Economic snapshot")
    components = db.scalars(
        select(EconomicCostComponent)
        .join(
            EconomicInputSnapshot,
            EconomicInputSnapshot.context_id == EconomicCostComponent.context_id,
        )
        .join(
            EconomicSnapshotComponent,
            EconomicSnapshotComponent.component_id == EconomicCostComponent.id,
        )
        .where(
            EconomicInputSnapshot.id == row.id,
            EconomicSnapshotComponent.snapshot_id == row.id,
            EconomicCostComponent.owner_id == owner.id,
        )
    ).all()
    return {"snapshot": row, "components": components}


@router.post("/snapshots/{snapshot_id}/calculate", status_code=201)
def snapshot_calculate(
    snapshot_id: uuid.UUID,
    data: EconomicCalculationRequest,
    db: DB,
    owner: Owner,
):
    row, reused = calculate_from_snapshot(db, owner, snapshot_id, data)
    return {
        "calculation": row,
        "breakdown": list_breakdown(db, owner, row.id),
        "idempotent_reuse": reused,
    }


@router.get("/calculations")
def calculation_list(db: DB, owner: Owner):
    rows = db.scalars(
        select(EconomicCalculation)
        .where(EconomicCalculation.owner_id == owner.id)
        .order_by(EconomicCalculation.created_at.desc())
    ).all()
    return {"items": rows}


@router.get("/calculations/{calculation_id}")
def calculation_detail(calculation_id: uuid.UUID, db: DB, owner: Owner):
    row = db.scalar(
        select(EconomicCalculation).where(
            EconomicCalculation.id == calculation_id,
            EconomicCalculation.owner_id == owner.id,
        )
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Economic calculation is not available in the owner scope.")
    return {"calculation": row, "breakdown": list_breakdown(db, owner, row.id)}


@router.post("/fx/observations", status_code=201)
def fx_observation_create(data: FXObservationCreate, db: DB, owner: Owner):
    row, reused = create_observation(db, owner, data)
    return {"observation": row, "idempotent_reuse": reused}


@router.get("/fx/observations")
def fx_observation_list(db: DB, owner: Owner):
    return {"items": list_observations(db, owner)}


@router.get("/fx/observations/{observation_id}")
def fx_observation_detail(observation_id: uuid.UUID, db: DB, owner: Owner):
    row = db.scalar(
        select(FXObservation).where(
            FXObservation.id == observation_id, FXObservation.owner_id == owner.id
        )
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(404, "FX observation is not available in the owner scope.")
    return {"observation": row}


@router.post("/fx/snapshots", status_code=201)
def fx_snapshot_create(data: FXSnapshotCreate, db: DB, owner: Owner):
    row, reused = create_fx_snapshot(db, owner, data)
    return {"snapshot": row, "idempotent_reuse": reused}


@router.get("/fx/snapshots")
def fx_snapshot_list(db: DB, owner: Owner):
    return {"items": list_snapshots(db, owner)}


@router.get("/fx/snapshots/{fx_snapshot_id}")
def fx_snapshot_detail(fx_snapshot_id: uuid.UUID, db: DB, owner: Owner):
    return {"snapshot": get_fx_snapshot(db, owner, fx_snapshot_id)}
