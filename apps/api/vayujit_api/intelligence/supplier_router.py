# ruff: noqa: B008
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
from vayujit_api.intelligence.commerce_journey import project_journey
from vayujit_api.intelligence.cross_marketplace_service import list_canonical
from vayujit_api.intelligence.external_service import provider_preflight
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import SUPPLIER_ACCESS_MODES, SUPPLIER_SOURCE_TYPES
from vayujit_api.intelligence.supplier_research import (
    derive_sourcing_concept,
    execute_provider_neutral_search,
)
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
    SupplierResearchCreate,
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


def _live_discovery_status() -> str:
    status = provider_preflight(get_settings()).get("status")
    return {
        "VALIDATED": "LIVE_READY",
        "BLOCKED_BY_EXTERNAL_CREDENTIALS": "LIVE_CONFIGURATION_INCOMPLETE",
        "BLOCKED_BY_CONFIGURATION": "LIVE_CONFIGURATION_INCOMPLETE",
        "DISABLED": "PENDING_EXTERNAL_PROVIDER",
    }.get(str(status), "LIVE_CONFIGURATION_INCOMPLETE")


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
        "provider_neutral_discovery": "LOCAL_FIXTURE",
        "live_discovery": _live_discovery_status(),
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


@router.get("/research-results")
def research_results(
    db: DB,
    owner: Owner,
    opportunity_id: uuid.UUID | None = Query(default=None),
) -> dict[str, object]:
    """Project supplier research for the canonical, human-selected product."""
    opportunity: ProductOpportunity | IntelligenceOpportunity | None = None
    if opportunity_id is not None:
        opportunity = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.id == opportunity_id,
                ProductOpportunity.owner_id == owner.id,
            )
        )
        if opportunity is None:
            opportunity = db.scalar(
                select(IntelligenceOpportunity).where(
                    IntelligenceOpportunity.id == opportunity_id,
                    IntelligenceOpportunity.owner_id == owner.id,
                )
            )
        if opportunity is None:
            raise HTTPException(404, "Product opportunity not found.")

    from vayujit_api.intelligence.supplier_models import SupplierSearch

    searches = list(
        db.scalars(
            select(SupplierSearch)
            .where(SupplierSearch.owner_id == owner.id)
            .order_by(SupplierSearch.created_at.desc())
            .limit(25)
        )
    )

    def belongs_to_product(search: SupplierSearch) -> bool:
        requirements = search.requirements or {}
        if opportunity_id is None:
            return True
        return search.opportunity_id == opportunity_id or str(
            requirements.get("product_opportunity_id") or ""
        ) == str(opportunity_id)

    search = next((item for item in searches if belongs_to_product(item)), None)
    summary = dict(search.summary_json or {}) if search is not None else {}
    raw_supplier_ids = summary.get("supplier_ids", [])
    supplier_ids = (
        {str(value) for value in raw_supplier_ids if value is not None}
        if isinstance(raw_supplier_ids, (list, tuple, set))
        else set()
    )
    suppliers = list_canonical(db, owner)
    if supplier_ids:
        suppliers = [
            row
            for row in suppliers
            if supplier_ids.intersection(
                str(value) for value in (row.get("identity", {}) or {}).get("supplier_ids", [])
            )
        ]

    if isinstance(opportunity, ProductOpportunity):
        product_context = {
            "opportunity_id": str(opportunity.id),
            "product": opportunity.name,
            "description": opportunity.description,
            "category": opportunity.category,
            "subcategory": opportunity.subcategory,
            "marketplace": opportunity.target_marketplace,
            "region": opportunity.target_region,
            "lifecycle_status": opportunity.lifecycle_status,
        }
    elif opportunity is not None:
        product_context = {
            "opportunity_id": str(opportunity.id),
            "product": opportunity.title,
            "category": opportunity.category,
            "marketplace": opportunity.market,
            "status": opportunity.status,
        }
    else:
        product_context = None

    status = str(summary.get("status") or (search.status if search else "NOT_STARTED"))
    next_action = (
        "Review supplier candidates"
        if suppliers
        else "Start supplier research" if search is None else "Review supplier research gaps"
    )
    return {
        "product_context": product_context,
        "research": {
            "status": status,
            "mode": summary.get("mode")
            or ((search.source_policy or {}).get("mode") if search else "LOCAL_FIXTURE"),
            "provider": summary.get("provider"),
            "search_id": str(search.id) if search else None,
            "summary": summary,
            "checkpoint": (search.checkpoint_state if search else {}),
            "external_calls": bool(summary.get("external_calls", False)),
        },
        "suppliers": suppliers[:20],
        "count": len(suppliers),
        "next_action": next_action,
        "external_write": False,
    }


@router.post("/searches", response_model=SupplierSearchResponse)
def add_search(data: SupplierSearchCreate, db: DB, owner: Owner) -> object:
    search = create_search(db, owner, data)
    db.commit()
    db.refresh(search)
    return search


@router.post("/research")
def research_suppliers(data: SupplierResearchCreate, db: DB, owner: Owner) -> dict[str, object]:
    """Run bounded supplier discovery scoped to the selected product when available."""
    selected: ProductOpportunity | None = None
    selected_id = data.product_opportunity_id
    if selected_id is None:
        journey = project_journey(db, owner)
        values = (journey or {}).get("values", {}) if isinstance(journey, dict) else {}
        raw_selected_id = values.get("selected_product_opportunity_id")
        if raw_selected_id:
            try:
                selected_id = uuid.UUID(str(raw_selected_id))
            except ValueError:
                selected_id = None
    if selected_id is not None:
        selected = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.id == selected_id,
                ProductOpportunity.owner_id == owner.id,
            )
        )
        if selected is None:
            raise HTTPException(404, "Selected product opportunity not found.")

    sourcing_concept = ""
    sourcing_method = ""
    sourcing_provenance: dict[str, object] = {}
    if selected is not None:
        sourcing_concept, sourcing_method, sourcing_provenance = derive_sourcing_concept(selected)
    product_query = (
        sourcing_concept
        or data.product_query
        or (selected.category if selected is not None else "")
    ).strip()
    if not product_query:
        raise HTTPException(409, "Select a product before starting supplier research.")

    category = (data.category or (selected.category if selected is not None else "")).strip()
    country = (data.country or (selected.target_region if selected is not None else "")).strip()
    requirements: dict[str, object] = {
        "product_query": product_query,
        "product_opportunity_id": str(selected.id) if selected is not None else None,
        "product_name": selected.name if selected is not None else product_query,
        "retail_product_identity": selected.name if selected is not None else product_query,
        "retail_product_concept": selected.product_concept if selected is not None else "",
        "product_concept": sourcing_concept
        or (selected.product_concept if selected is not None else ""),
        "sourcing_concept": sourcing_concept or product_query,
        "sourcing_concept_method": sourcing_method or "API_INPUT",
        "sourcing_concept_provenance": sourcing_provenance,
        "category": category,
        "subcategory": selected.subcategory if selected is not None else "",
        "country": country,
        "marketplace": selected.target_marketplace if selected is not None else "",
        "region": selected.target_region if selected is not None else "",
        "supplier_type": data.supplier_type,
        "manufacturer_preferred": data.manufacturer_preferred,
        "keywords": data.keywords,
        "excluded_terms": data.excluded_terms,
        "max_candidates": data.max_candidates,
        "research_depth": data.research_depth,
        "approved_domains": data.approved_domains,
    }
    search_data = SupplierSearchCreate(
        opportunity_id=None,
        product_id=selected.product_id if selected is not None else None,
        requirements=requirements,
        source_policy={"mode": data.mode, "external_connectors": "disabled"},
        ruleset_version="supplier-research-14f-v1",
        idempotency_key=data.idempotency_key,
    )
    search = create_search(db, owner, search_data)
    execute_provider_neutral_search(db, owner, search)
    db.commit()
    db.refresh(search)
    return {
        "request": _row(search),
        "result": search.summary_json,
        "status": search.status,
        "selected_product": (
            {
                "id": str(selected.id),
                "name": selected.name,
                "category": selected.category,
                "subcategory": selected.subcategory,
                "marketplace": selected.target_marketplace,
                "region": selected.target_region,
            }
            if selected is not None
            else None
        ),
        "live_discovery": (
            "LIVE_READY"
            if data.mode == "LIVE_READ_ONLY" and search.status == "completed"
            else ("LIVE_CONFIGURATION_INCOMPLETE" if data.mode == "LIVE_READ_ONLY" else "PENDING")
        ),
        "external_calls": bool((search.summary_json or {}).get("external_calls", False)),
    }


@router.get("/searches", response_model=list[SupplierSearchResponse])
def searches(db: DB, owner: Owner) -> list[object]:

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
