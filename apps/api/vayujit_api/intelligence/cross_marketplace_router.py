# ruff: noqa: E501
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.cross_marketplace_schemas import (
    CrossMarketplaceCompareRequest,
    CrossMarketplaceHandoffRequest,
    CrossMarketplaceRankingRequest,
    CrossMarketplaceReconcileRequest,
)
from vayujit_api.intelligence.cross_marketplace_service import (
    calendar,
    compare,
    detail,
    history,
    integrity,
    list_canonical,
    operations,
    opportunity_fit,
    product_channel,
    product_fit,
    ranking,
    reconcile,
    report,
    source_inventory,
    sourcing_handoff,
    system_doctor,
)

router = APIRouter(
    prefix="/api/v1/intelligence/cross-marketplace/suppliers",
    tags=["cross-marketplace-supplier-intelligence"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


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


@router.get("/product-channel/{product_id}")
def channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return product_channel(db, owner, product_id)


@router.post("/reconcile")
def reconcile_suppliers(
    data: CrossMarketplaceReconcileRequest, db: DB, owner: Owner
) -> list[dict[str, object]]:
    return [
        {
            "id": str(row.id),
            "display_name": row.display_name,
            "identity_state": row.identity_state,
            "confidence_score": float(row.confidence_score or 0),
            "source_diversity_score": float(row.source_diversity_score or 0),
        }
        for row in reconcile(db, owner, data.supplier_ids)
    ]


@router.get("")
def suppliers(
    db: DB,
    owner: Owner,
    source: str | None = Query(default=None),
    country: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0, le=100),
) -> list[dict[str, object]]:
    return list_canonical(db, owner, source, country, risk, min_confidence)


@router.post("/compare")
def compare_suppliers(
    data: CrossMarketplaceCompareRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return compare(db, owner, data.supplier_ids)


@router.get("/{canonical_id}")
def supplier_detail(canonical_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return detail(db, owner, canonical_id)


@router.get("/{canonical_id}/sources")
def supplier_sources(canonical_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return source_inventory(db, owner, canonical_id)


@router.get("/{canonical_id}/history")
def supplier_history(canonical_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return history(db, owner, canonical_id)


@router.get("/{canonical_id}/ranking")
def supplier_ranking(canonical_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return ranking(db, owner, canonical_id)


@router.post("/{canonical_id}/ranking")
def evaluate_ranking(
    canonical_id: uuid.UUID, data: CrossMarketplaceRankingRequest, db: DB, owner: Owner
) -> dict[str, object]:
    return ranking(db, owner, canonical_id, data.model_version, data.idempotency_key, data.weights)


@router.get("/{canonical_id}/report")
def supplier_report(
    canonical_id: uuid.UUID, db: DB, owner: Owner, format: str = Query(default="json")
) -> object:
    value = report(db, owner, canonical_id, format)
    if format == "html":
        return Response(content=str(value), media_type="text/html")
    if format == "markdown":
        return Response(content=str(value), media_type="text/markdown")
    return value


@router.get("/{canonical_id}/product-fit/{product_id}")
def fit_product(
    canonical_id: uuid.UUID, product_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return product_fit(db, owner, canonical_id, product_id)


@router.get("/{canonical_id}/opportunity-fit/{opportunity_id}")
def fit_opportunity(
    canonical_id: uuid.UUID, opportunity_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    return opportunity_fit(db, owner, canonical_id, opportunity_id)


@router.post("/{canonical_id}/sourcing-handoff")
def handoff(
    canonical_id: uuid.UUID,
    data: CrossMarketplaceHandoffRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return sourcing_handoff(db, owner, canonical_id, data.product_id, data.confirmed)
