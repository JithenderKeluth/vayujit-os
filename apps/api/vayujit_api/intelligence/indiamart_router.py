from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.indiamart_projection import (
    calendar,
    integrity,
    operational_summary,
    product_channel,
    report,
    storage_inventory,
)
from vayujit_api.intelligence.indiamart_schemas import (
    IndiaMartDiscoveryRequest,
    IndiaMartEvidenceHandoffRequest,
)
from vayujit_api.intelligence.indiamart_service import (
    detail,
    discover,
    handoff_evidence,
    list_discoveries,
    operations,
    preflight,
)

router = APIRouter(prefix="/api/v1/intelligence/indiamart", tags=["indiamart-discovery"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/preflight")
def provider_preflight() -> dict[str, object]:
    return preflight(get_settings())


@router.get("/operations")
def provider_operations(db: DB, owner: Owner) -> dict[str, object]:
    return operations(db, owner, get_settings())


@router.get("/operations/summary")
def provider_operations_summary(db: DB, owner: Owner) -> dict[str, object]:
    return operational_summary(db, owner, get_settings())


@router.get("/integrity")
def provider_integrity(db: DB, owner: Owner) -> dict[str, object]:
    return integrity(db, owner)


@router.get("/product-channel/{product_id}")
def provider_product_channel(product_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return product_channel(db, owner, product_id)


@router.get("/calendar")
def provider_calendar(db: DB, owner: Owner) -> list[dict[str, object]]:
    return calendar(db, owner)


@router.get("/report")
def provider_report(db: DB, owner: Owner) -> dict[str, object]:
    return report(db, owner)


@router.get("/storage/inventory")
def provider_storage_inventory() -> dict[str, object]:
    return storage_inventory()


@router.post("/discover")
def run_discovery(data: IndiaMartDiscoveryRequest, db: DB, owner: Owner) -> dict[str, object]:
    return discover(
        db,
        owner,
        get_settings(),
        query=data.query,
        product_id=data.product_id,
        country_code=data.country_code,
        region=data.region,
        result_limit=data.result_limit,
        correlation_id=data.correlation_id,
        idempotency_key=data.idempotency_key,
        mission_id=data.mission_id,
        task_id=data.task_id,
    )


@router.get("/discoveries")
def discovery_history(
    db: DB, owner: Owner, limit: int = Query(default=100, ge=1, le=500)
) -> list[dict[str, object]]:
    return list_discoveries(db, owner, limit)


@router.post("/discoveries/{result_id}/evidence")
def discovery_evidence_handoff(
    result_id: uuid.UUID,
    data: IndiaMartEvidenceHandoffRequest,
    db: DB,
    owner: Owner,
) -> dict[str, object]:
    return handoff_evidence(db, owner, result_id, data.mission_id, data.task_id)


@router.get("/discoveries/{request_id}")
def discovery_detail(request_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return detail(db, owner, request_id)
