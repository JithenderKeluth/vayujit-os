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
from vayujit_api.intelligence.economic_customs_models import (
    ClassificationEvidence,
    CustomsRateEvidence,
    CustomsTaxContext,
    CustomsTaxSnapshot,
    RegulatoryCostEvidence,
)
from vayujit_api.intelligence.economic_customs_schemas import (
    ClassificationEvidenceCreate,
    CustomsRateEvidenceCreate,
    CustomsTaxContextCreate,
    CustomsTaxSnapshotCreate,
    RegulatoryCostEvidenceCreate,
)
from vayujit_api.intelligence.economic_customs_service import (
    create_classification,
    create_rate,
    create_regulatory_cost,
)
from vayujit_api.intelligence.economic_customs_service import (
    create_context as create_customs_context,
)
from vayujit_api.intelligence.economic_customs_service import (
    create_snapshot as create_customs_snapshot,
)
from vayujit_api.intelligence.economic_customs_service import (
    get_row as get_customs_row,
)
from vayujit_api.intelligence.economic_customs_service import (
    list_rows as list_customs_rows,
)
from vayujit_api.intelligence.economic_freight_models import (
    FreightObservation,
    FreightSnapshot,
)
from vayujit_api.intelligence.economic_freight_service import (
    create_logistics_context,
    get_logistics_context,
    list_logistics_contexts,
)
from vayujit_api.intelligence.economic_freight_service import (
    create_observation as create_freight_observation,
)
from vayujit_api.intelligence.economic_freight_service import (
    create_snapshot as create_freight_snapshot,
)
from vayujit_api.intelligence.economic_freight_service import (
    get_observation as get_freight_observation,
)
from vayujit_api.intelligence.economic_freight_service import (
    get_snapshot as get_freight_snapshot,
)
from vayujit_api.intelligence.economic_freight_service import (
    list_observations as list_freight_observations,
)
from vayujit_api.intelligence.economic_freight_service import (
    list_snapshots as list_freight_snapshots,
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
    FreightObservationCreate,
    FreightSnapshotCreate,
    FXObservationCreate,
    FXSnapshotCreate,
    LogisticsContextCreate,
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


@router.post("/logistics/contexts", status_code=201)
def logistics_context_create(data: LogisticsContextCreate, db: DB, owner: Owner):
    row, reused = create_logistics_context(db, owner, data)
    return {"context": row, "idempotent_reuse": reused}


@router.get("/logistics/contexts")
def logistics_context_list(db: DB, owner: Owner):
    return {"items": list_logistics_contexts(db, owner)}


@router.get("/logistics/contexts/{context_id}")
def logistics_context_detail(context_id: uuid.UUID, db: DB, owner: Owner):
    row = get_logistics_context(db, owner, context_id)
    return {
        "context": row,
        "observations": db.scalars(
            select(FreightObservation)
            .where(
                FreightObservation.owner_id == owner.id,
                FreightObservation.logistics_context_id == row.id,
            )
            .order_by(FreightObservation.created_at.desc())
        ).all(),
        "snapshots": db.scalars(
            select(FreightSnapshot)
            .where(
                FreightSnapshot.owner_id == owner.id,
                FreightSnapshot.logistics_context_id == row.id,
            )
            .order_by(FreightSnapshot.created_at.desc())
        ).all(),
    }


@router.post("/freight/observations", status_code=201)
def freight_observation_create(data: FreightObservationCreate, db: DB, owner: Owner):
    row, reused = create_freight_observation(db, owner, data)
    return {"observation": row, "idempotent_reuse": reused}


@router.get("/freight/observations")
def freight_observation_list(db: DB, owner: Owner):
    return {"items": list_freight_observations(db, owner)}


@router.get("/freight/observations/{observation_id}")
def freight_observation_detail(observation_id: uuid.UUID, db: DB, owner: Owner):
    return {"observation": get_freight_observation(db, owner, observation_id)}


@router.post("/freight/snapshots", status_code=201)
def freight_snapshot_create(data: FreightSnapshotCreate, db: DB, owner: Owner):
    row, reused = create_freight_snapshot(db, owner, data)
    return {"snapshot": row, "idempotent_reuse": reused}


@router.get("/freight/snapshots")
def freight_snapshot_list(db: DB, owner: Owner):
    return {"items": list_freight_snapshots(db, owner)}


@router.get("/freight/snapshots/{freight_snapshot_id}")
def freight_snapshot_detail(freight_snapshot_id: uuid.UUID, db: DB, owner: Owner):
    return {"snapshot": get_freight_snapshot(db, owner, freight_snapshot_id)}


@router.post("/customs-tax/contexts", status_code=201)
def customs_context_create(data: CustomsTaxContextCreate, db: DB, owner: Owner):
    row, reused = create_customs_context(db, owner, data)
    return {"context": row, "idempotent_reuse": reused}


@router.get("/customs-tax/contexts")
def customs_context_list(db: DB, owner: Owner):
    return {"items": list_customs_rows(db, owner, CustomsTaxContext)}


@router.get("/customs-tax/contexts/{context_id}")
def customs_context_detail(context_id: uuid.UUID, db: DB, owner: Owner):
    row = get_customs_row(db, owner, CustomsTaxContext, context_id, "Customs/tax context")
    return {
        "context": row,
        "classifications": list_customs_rows(db, owner, ClassificationEvidence, row.id),
        "rates": list_customs_rows(db, owner, CustomsRateEvidence, row.id),
        "regulatory_costs": list_customs_rows(db, owner, RegulatoryCostEvidence, row.id),
        "snapshots": list_customs_rows(db, owner, CustomsTaxSnapshot, row.id),
    }


@router.post("/customs-tax/classifications", status_code=201)
def customs_classification_create(data: ClassificationEvidenceCreate, db: DB, owner: Owner):
    row, reused = create_classification(db, owner, data)
    return {"classification": row, "idempotent_reuse": reused}


@router.get("/customs-tax/classifications")
def customs_classification_list(db: DB, owner: Owner, context_id: uuid.UUID | None = None):
    return {"items": list_customs_rows(db, owner, ClassificationEvidence, context_id)}


@router.get("/customs-tax/classifications/{evidence_id}")
def customs_classification_detail(evidence_id: uuid.UUID, db: DB, owner: Owner):
    return {
        "classification": get_customs_row(
            db, owner, ClassificationEvidence, evidence_id, "Classification evidence"
        )
    }


@router.post("/customs-tax/rates", status_code=201)
def customs_rate_create(data: CustomsRateEvidenceCreate, db: DB, owner: Owner):
    row, reused = create_rate(db, owner, data)
    return {"rate": row, "idempotent_reuse": reused}


@router.get("/customs-tax/rates")
def customs_rate_list(db: DB, owner: Owner, context_id: uuid.UUID | None = None):
    return {"items": list_customs_rows(db, owner, CustomsRateEvidence, context_id)}


@router.get("/customs-tax/rates/{rate_id}")
def customs_rate_detail(rate_id: uuid.UUID, db: DB, owner: Owner):
    return {
        "rate": get_customs_row(db, owner, CustomsRateEvidence, rate_id, "Customs rate evidence")
    }


@router.post("/customs-tax/regulatory-costs", status_code=201)
def regulatory_cost_create(data: RegulatoryCostEvidenceCreate, db: DB, owner: Owner):
    row, reused = create_regulatory_cost(db, owner, data)
    return {"regulatory_cost": row, "idempotent_reuse": reused}


@router.get("/customs-tax/regulatory-costs")
def regulatory_cost_list(db: DB, owner: Owner, context_id: uuid.UUID | None = None):
    return {"items": list_customs_rows(db, owner, RegulatoryCostEvidence, context_id)}


@router.get("/customs-tax/regulatory-costs/{cost_id}")
def regulatory_cost_detail(cost_id: uuid.UUID, db: DB, owner: Owner):
    return {
        "regulatory_cost": get_customs_row(
            db, owner, RegulatoryCostEvidence, cost_id, "Regulatory cost evidence"
        )
    }


@router.post("/customs-tax/snapshots", status_code=201)
def customs_snapshot_create(data: CustomsTaxSnapshotCreate, db: DB, owner: Owner):
    row, reused = create_customs_snapshot(db, owner, data)
    return {"snapshot": row, "idempotent_reuse": reused}


@router.get("/customs-tax/snapshots")
def customs_snapshot_list(db: DB, owner: Owner, context_id: uuid.UUID | None = None):
    return {"items": list_customs_rows(db, owner, CustomsTaxSnapshot, context_id)}


@router.get("/customs-tax/snapshots/{snapshot_id}")
def customs_snapshot_detail(snapshot_id: uuid.UUID, db: DB, owner: Owner):
    return {
        "snapshot": get_customs_row(
            db, owner, CustomsTaxSnapshot, snapshot_id, "Customs/tax snapshot"
        )
    }
