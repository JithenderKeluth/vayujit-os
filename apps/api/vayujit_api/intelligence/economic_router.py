from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
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
    EconomicContextCreate,
    EconomicContextUpdate,
    EconomicCostComponentCreate,
    EconomicQuoteInputCreate,
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
