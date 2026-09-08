from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.shortlisting_closure import (
    contradiction_gate,
    diversity_gate,
    economics_projection,
    freshness_gate,
    landed_cost_projection,
    readiness,
    risk_gate,
    verification_readiness,
)
from vayujit_api.intelligence.shortlisting_models import (
    SupplierShortlistContext,
    SupplierShortlistVersion,
)
from vayujit_api.intelligence.shortlisting_schemas import (
    ShortlistContextCreate,
    ShortlistDecisionRequest,
    ShortlistRequest,
    SourcingHandoffRequest,
)
from vayujit_api.intelligence.shortlisting_service import (
    calendar,
    comparison,
    create_context,
    decide,
    generate_shortlist,
    handoff,
    history,
    integrity,
    operations,
    product_channel,
    report,
    system_doctor,
    version_context,
)

router = APIRouter(
    prefix="/api/v1/intelligence/supplier-shortlisting", tags=["supplier-shortlisting"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _context(db: Session, owner: User, context_id: uuid.UUID) -> SupplierShortlistContext:
    row = db.scalar(
        select(SupplierShortlistContext).where(
            SupplierShortlistContext.id == context_id, SupplierShortlistContext.owner_id == owner.id
        )
    )
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Shortlist context not found.")
    return row


@router.get("/system-doctor")
def doctor() -> dict[str, object]:
    return system_doctor()


@router.get("/operations")
def ops(db: DB, owner: Owner) -> dict[str, object]:
    return operations(db, owner)


@router.get("/calendar")
def events(db: DB, owner: Owner) -> list[dict[str, object]]:
    return calendar(db, owner)


@router.get("/integrity")
def integrity_check(db: DB, owner: Owner) -> dict[str, object]:
    return integrity(db, owner)


@router.post("/contexts")
def contexts(data: ShortlistContextCreate, db: DB, owner: Owner) -> dict[str, object]:
    row, reused = create_context(db, owner, data)
    return {
        "id": str(row.id),
        "version": row.current_version,
        "reused": reused,
        "payload": row.payload,
    }


@router.get("/contexts")
def list_contexts(db: DB, owner: Owner) -> list[dict[str, object]]:
    return [
        {"id": str(x.id), "version": x.current_version, "payload": x.payload}
        for x in db.scalars(
            select(SupplierShortlistContext).where(SupplierShortlistContext.owner_id == owner.id)
        )
    ]


@router.get("/contexts/{context_id}")
def context_detail(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = _context(db, owner, context_id)
    return {"id": str(row.id), "version": row.current_version, "payload": row.payload}


@router.post("/contexts/{context_id}/versions")
def context_version(
    context_id: uuid.UUID, data: ShortlistContextCreate, db: DB, owner: Owner
) -> dict[str, object]:
    row = version_context(db, owner, _context(db, owner, context_id), data)
    return {"id": str(row.id), "version": row.current_version, "payload": row.payload}


@router.post("/contexts/{context_id}/shortlists")
def shortlist(
    context_id: uuid.UUID, data: ShortlistRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return generate_shortlist(db, owner, _context(db, owner, context_id), data)


@router.get("/contexts/{context_id}/shortlists")
def shortlist_history(context_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    _context(db, owner, context_id)
    return [
        {"id": str(x.id), "version": x.version, **x.payload}
        for x in db.scalars(
            select(SupplierShortlistVersion)
            .where(SupplierShortlistVersion.context_id == context_id)
            .order_by(SupplierShortlistVersion.version)
        )
    ]


@router.get("/contexts/{context_id}/suppliers/{supplier_id}/readiness")
def supplier_readiness(
    context_id: uuid.UUID, supplier_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    context = _context(db, owner, context_id)
    supplier = db.scalar(
        select(CrossMarketplaceSupplier).where(
            CrossMarketplaceSupplier.id == supplier_id,
            CrossMarketplaceSupplier.owner_id == owner.id,
        )
    )
    if supplier is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Supplier not found.")
    return {
        "negotiation": readiness(context, supplier),
        "sample": readiness(context, supplier, sample=True),
        "verification": verification_readiness(supplier),
        "landed_cost": landed_cost_projection(context, supplier),
        "economics": economics_projection(context, supplier),
        "gates": {
            "contradiction": contradiction_gate((supplier.view_json or {}).get("contradictions")),
            "risk": risk_gate((supplier.view_json or {}).get("risk")),
            "freshness": freshness_gate(supplier.freshness_status),
        },
    }


@router.get("/contexts/{context_id}/gates")
def context_gates(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    context = _context(db, owner, context_id)
    suppliers = list(
        db.scalars(
            select(CrossMarketplaceSupplier).where(CrossMarketplaceSupplier.owner_id == owner.id)
        )
    )
    return {
        "diversity": diversity_gate(suppliers),
        "suppliers": [
            {
                "id": str(item.id),
                "negotiation": readiness(context, item),
                "sample": readiness(context, item, sample=True),
            }
            for item in suppliers
        ],
    }


@router.get("/compare")
def compare_route(
    db: DB,
    owner: Owner,
    supplier_ids: list[uuid.UUID],
) -> dict[str, object]:
    return comparison(db, owner, supplier_ids)


@router.get("/product-channel/{product_id}")
def product_channel_route(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return product_channel(db, owner, product_id)


@router.post("/contexts/{context_id}/decisions")
def decisions(
    context_id: uuid.UUID, data: ShortlistDecisionRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return decide(db, owner, _context(db, owner, context_id), data)


@router.post("/contexts/{context_id}/handoff")
def sourcing_handoff(
    context_id: uuid.UUID, data: SourcingHandoffRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return handoff(db, owner, _context(db, owner, context_id), data)


@router.get("/contexts/{context_id}/report")
def context_report(
    context_id: uuid.UUID,
    db: DB,
    owner: Owner,
    format: str = Query(default="json", pattern="^(json|markdown|html)$"),
) -> object:
    return report(db, owner, _context(db, owner, context_id), format)


@router.get("/contexts/{context_id}/history")
def context_history(context_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return history(db, owner, _context(db, owner, context_id))
