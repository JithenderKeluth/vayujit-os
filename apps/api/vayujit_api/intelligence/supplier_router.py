from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.supplier_models import SUPPLIER_ACCESS_MODES, SUPPLIER_SOURCE_TYPES
from vayujit_api.intelligence.supplier_schemas import (
    SupplierCertificationClaimCreate,
    SupplierCommercialTermCreate,
    SupplierComparisonRequest,
    SupplierContactCreate,
    SupplierContactUpdate,
    SupplierDecisionRequest,
    SupplierDetailResponse,
    SupplierDocumentReferenceCreate,
    SupplierManualCreate,
    SupplierOverviewResponse,
    SupplierRecoveryRequest,
    SupplierReportResponse,
    SupplierResponse,
    SupplierRuleResponse,
    SupplierScoreCreate,
    SupplierSearchCreate,
    SupplierSearchResponse,
    SupplierSourceRegistryResponse,
    SupplierVerificationRequest,
)
from vayujit_api.intelligence.supplier_service import (
    commercial_term_detail,
    compare_suppliers,
    create_certification_claim,
    create_commercial_term,
    create_contact,
    create_document_reference,
    create_manual_supplier,
    create_score_evaluation,
    create_search,
    decide_supplier,
    execute_search,
    freshness_matrix,
    list_certification_claims,
    list_commercial_terms,
    list_contacts,
    list_suppliers,
    recover_search,
    risk_matrix,
    score_history,
    source_diversity,
    supplier_detail,
    supplier_history,
    supplier_overview,
    supplier_report,
    supplier_table_inventory,
    update_contact,
    verify_supplier,
)

router = APIRouter(prefix="/api/v1/intelligence/suppliers", tags=["intelligence-suppliers"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _row(value: object) -> dict[str, object]:
    return {key: item for key, item in vars(value).items() if key != "_sa_instance_state"}


@router.get("/overview", response_model=SupplierOverviewResponse)
def overview(db: DB, owner: Owner) -> dict[str, object]:
    return supplier_overview(db, owner)


@router.get("/source-registry", response_model=list[SupplierSourceRegistryResponse])
def source_registry() -> list[dict[str, object]]:
    return [
        {
            "source_type": source,
            "access_modes": list(SUPPLIER_ACCESS_MODES),
            "status": (
                "local_fixture"
                if source in {"manufacturer_website", "offline_market", "trade_fair", "referral"}
                else "not_configured"
            ),
            "notes": "External connector is not called; unrestricted scraping is disabled.",
        }
        for source in SUPPLIER_SOURCE_TYPES
    ]


@router.get("/inventory")
def inventory(db: DB, owner: Owner) -> dict[str, object]:
    return {"tables": supplier_table_inventory(db, owner)}


@router.get("/operations")
def operations(db: DB, owner: Owner) -> dict[str, object]:
    from sqlalchemy import func, select

    from vayujit_api.intelligence.supplier_models import SupplierProduct, SupplierSearch

    return {
        "worker": "registered",
        "queue": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierSearch)
                .where(SupplierSearch.owner_id == owner.id, SupplierSearch.status == "pending")
            )
            or 0
        ),
        "failed_searches": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierSearch)
                .where(SupplierSearch.owner_id == owner.id, SupplierSearch.status == "failed")
            )
            or 0
        ),
        "stale_supplier_data": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierProduct)
                .where(
                    SupplierProduct.owner_id == owner.id,
                    SupplierProduct.freshness_status.in_(["stale", "expired"]),
                )
            )
            or 0
        ),
        "recovery": "operator_bounded",
        "external_connectors": "disabled",
    }


@router.get("/rules", response_model=list[SupplierRuleResponse])
def rules() -> list[dict[str, object]]:
    return [
        {
            "key": "maximum_moq",
            "label": "Maximum MOQ",
            "action": "REVIEW_REQUIRED",
            "hard_block": False,
            "description": "Reject or review offerings above the configured MOQ.",
        },
        {
            "key": "maximum_lead_time",
            "label": "Maximum lead time",
            "action": "REVIEW_REQUIRED",
            "hard_block": False,
            "description": "Review offerings beyond the configured lead-time limit.",
        },
        {
            "key": "minimum_verification",
            "label": "Minimum verification",
            "action": "WARN",
            "hard_block": False,
            "description": "Never auto-escalate an unverified supplier.",
        },
        {
            "key": "blocked_country",
            "label": "Blocked country",
            "action": "BLOCK",
            "hard_block": True,
            "description": "Country policy blocks the match.",
        },
        {
            "key": "required_certification",
            "label": "Required certification",
            "action": "REVIEW_REQUIRED",
            "hard_block": False,
            "description": "Supplier claim requires evidence review.",
        },
    ]


@router.post("/searches", response_model=SupplierSearchResponse)
def add_search(data: SupplierSearchCreate, db: DB, owner: Owner) -> object:
    search = create_search(db, owner, data)
    db.commit()
    db.refresh(search)
    return search


@router.get("/searches", response_model=list[SupplierSearchResponse])
def searches(db: DB, owner: Owner) -> list[object]:
    from sqlalchemy import select

    from vayujit_api.intelligence.supplier_models import SupplierSearch

    return list(
        db.scalars(
            select(SupplierSearch)
            .where(SupplierSearch.owner_id == owner.id)
            .order_by(SupplierSearch.created_at.desc())
        )
    )


@router.post("/searches/{search_id}/run", response_model=SupplierSearchResponse)
def run_search(search_id: uuid.UUID, db: DB, owner: Owner) -> object:
    from fastapi import HTTPException
    from sqlalchemy import select

    from vayujit_api.intelligence.supplier_models import SupplierSearch

    search = db.scalar(
        select(SupplierSearch).where(
            SupplierSearch.id == search_id, SupplierSearch.owner_id == owner.id
        )
    )
    if search is None:
        raise HTTPException(404, "Supplier search not found.")
    execute_search(db, owner, search)
    db.commit()
    db.refresh(search)
    return search


@router.post("/manual", response_model=SupplierResponse, status_code=201)
def add_manual(data: SupplierManualCreate, db: DB, owner: Owner) -> object:
    supplier = create_manual_supplier(db, owner, data)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("", response_model=list[SupplierResponse])
def list_all(
    db: DB,
    owner: Owner,
    source: str | None = None,
    country: str | None = None,
    verification: str | None = None,
    offline: bool | None = None,
) -> list[dict[str, object]]:
    return list_suppliers(
        db, owner, source=source, country=country, verification=verification, offline=offline
    )


@router.post("/compare", response_model=list[SupplierResponse])
def compare(data: SupplierComparisonRequest, db: DB, owner: Owner) -> list[dict[str, object]]:
    return compare_suppliers(db, owner, data)


@router.get("/{supplier_id}/freshness")
def freshness(supplier_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, str]:
    return freshness_matrix(db, owner, supplier_id)


@router.get("/{supplier_id}/source-diversity")
def diversity(supplier_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return source_diversity(db, owner, supplier_id)


@router.get("/{supplier_id}/history")
def history(supplier_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return {"events": supplier_history(db, owner, supplier_id)}


@router.get("/{supplier_id}/risk-matrix")
def risk(supplier_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return risk_matrix(db, owner, supplier_id)


@router.post("/{supplier_id}/documents", status_code=201)
def document_reference(
    supplier_id: uuid.UUID, data: SupplierDocumentReferenceCreate, db: DB, owner: Owner
) -> object:
    value = create_document_reference(db, owner, supplier_id, data)
    db.commit()
    db.refresh(value)
    return _row(value)


@router.get("/{supplier_id}/commercial-terms/{product_id}/{version}")
def commercial_version(
    supplier_id: uuid.UUID, product_id: uuid.UUID, version: int, db: DB, owner: Owner
) -> object:
    return _row(commercial_term_detail(db, owner, supplier_id, product_id, version))


@router.post("/{supplier_id}/certifications", status_code=201)
def certification_create(
    supplier_id: uuid.UUID, data: SupplierCertificationClaimCreate, db: DB, owner: Owner
) -> object:
    value = create_certification_claim(db, owner, supplier_id, data)
    db.commit()
    db.refresh(value)
    return _row(value)


@router.get("/{supplier_id}/certifications")
def certification_list(supplier_id: uuid.UUID, db: DB, owner: Owner) -> list[object]:
    return [_row(item) for item in list_certification_claims(db, owner, supplier_id)]


@router.post("/{supplier_id}/scores", status_code=201)
def score_create(supplier_id: uuid.UUID, data: SupplierScoreCreate, db: DB, owner: Owner) -> object:
    value = create_score_evaluation(db, owner, supplier_id, data)
    db.commit()
    db.refresh(value)
    return _row(value)


@router.get("/{supplier_id}/scores")
def score_list(supplier_id: uuid.UUID, db: DB, owner: Owner) -> list[object]:
    return [_row(item) for item in score_history(db, owner, supplier_id)]


@router.post("/{supplier_id}/contacts", status_code=201)
def contact_create(
    supplier_id: uuid.UUID, data: SupplierContactCreate, db: DB, owner: Owner
) -> object:
    value = create_contact(db, owner, supplier_id, data)
    db.commit()
    db.refresh(value)
    return _row(value)


@router.get("/{supplier_id}/contacts")
def contact_list(supplier_id: uuid.UUID, db: DB, owner: Owner) -> list[object]:
    return [_row(item) for item in list_contacts(db, owner, supplier_id)]


@router.patch("/{supplier_id}/contacts/{contact_id}")
def contact_update(
    supplier_id: uuid.UUID, contact_id: uuid.UUID, data: SupplierContactUpdate, db: DB, owner: Owner
) -> object:
    value = update_contact(db, owner, supplier_id, contact_id, data)
    db.commit()
    db.refresh(value)
    return _row(value)


@router.post("/{supplier_id}/commercial-terms", status_code=201)
def commercial_create(
    supplier_id: uuid.UUID, data: SupplierCommercialTermCreate, db: DB, owner: Owner
) -> object:
    value = create_commercial_term(db, owner, supplier_id, data)
    db.commit()
    db.refresh(value)
    return _row(value)


@router.get("/{supplier_id}/commercial-terms/{product_id}")
def commercial_list(
    supplier_id: uuid.UUID, product_id: uuid.UUID, db: DB, owner: Owner
) -> list[object]:
    return [_row(item) for item in list_commercial_terms(db, owner, supplier_id, product_id)]


@router.post("/searches/{search_id}/recovery")
def recovery(search_id: uuid.UUID, data: SupplierRecoveryRequest, db: DB, owner: Owner) -> object:
    value = recover_search(db, owner, search_id, data)
    db.commit()
    db.refresh(value)
    return {
        "id": value.id,
        "search_id": value.search_id,
        "action": value.action,
        "status": value.status,
        "idempotent_reuse": bool(getattr(value, "idempotent_reuse", False)),
        "reason_code": value.reason_code,
        "correlation_id": value.correlation_id,
    }


@router.get("/{supplier_id}", response_model=SupplierDetailResponse)
def detail(supplier_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return supplier_detail(db, owner, supplier_id)


@router.post("/{supplier_id}/decisions")
def decision(
    supplier_id: uuid.UUID, data: SupplierDecisionRequest, db: DB, owner: Owner
) -> dict[str, object]:
    value = decide_supplier(db, owner, supplier_id, data)
    db.commit()
    return {
        "id": value.id,
        "supplier_id": value.supplier_id,
        "decision": value.decision,
        "reason": value.reason,
        "idempotent_reuse": bool(getattr(value, "idempotent_reuse", False)),
    }


@router.post("/{supplier_id}/verification")
def verification(
    supplier_id: uuid.UUID, data: SupplierVerificationRequest, db: DB, owner: Owner
) -> dict[str, object]:
    value = verify_supplier(db, owner, supplier_id, data)
    db.commit()
    return {
        "id": value.id,
        "supplier_id": value.supplier_id,
        "state": value.state,
        "reason": value.reason,
    }


@router.get("/{supplier_id}/report", response_model=SupplierReportResponse)
def report(supplier_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    return supplier_report(db, owner, supplier_id)
