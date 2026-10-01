"""PR-5A commercial evidence and calculation-readiness projection.

The service reads the existing ProductOpportunity, supplier-search, SupplierProduct,
SupplierEvidence, and SupplierCommercialTerm authorities. It never calculates a
landed cost, margin, capital requirement, or recommendation.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.commercial_readiness_schemas import CommercialReadinessCreate
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplierLink
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
)
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCommercialTerm,
    SupplierEvidence,
    SupplierOpportunityMatch,
    SupplierProduct,
    SupplierSearch,
)

REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "MOQ_AFFORDABILITY": ("supplier_moq", "supplier_unit_price", "supplier_currency"),
    "BASIC_UNIT_MARGIN": (
        "supplier_unit_price",
        "supplier_currency",
        "selling_price",
        "selling_currency",
        "marketplace_fee_per_unit",
    ),
    "LANDED_UNIT_COST": (
        "supplier_unit_price",
        "supplier_currency",
        "freight_cost",
        "freight_currency",
        "origin",
        "destination",
    ),
}

OPTIONAL_FIELDS = (
    "lead_time_days",
    "incoterm",
    "pack_quantity",
    "carton_quantity",
    "payment_terms",
)


def _json(value: Any) -> Any:
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(item) for item in value]
    return value


def _context(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[ProductOpportunity, ProductOpportunityAssessment, ProductOpportunityConstraintVersion]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    assessment = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if opportunity is None or assessment is None:
        raise HTTPException(404, "Product opportunity assessment not found.")
    constraint = db.scalar(
        select(ProductOpportunityConstraintVersion).where(
            ProductOpportunityConstraintVersion.id == assessment.constraint_version_id,
            ProductOpportunityConstraintVersion.opportunity_id == opportunity_id,
            ProductOpportunityConstraintVersion.owner_id == owner.id,
        )
    )
    if constraint is None:
        raise HTTPException(404, "Product opportunity constraint not found.")
    return opportunity, assessment, constraint


def _searches(db: Session, owner: User, opportunity: ProductOpportunity) -> list[SupplierSearch]:
    rows = list(
        db.scalars(
            select(SupplierSearch)
            .where(SupplierSearch.owner_id == owner.id)
            .order_by(SupplierSearch.created_at.desc())
        )
    )
    selected = str(opportunity.id)
    return [
        row
        for row in rows
        if str((row.requirements or {}).get("product_opportunity_id") or "") == selected
        or (opportunity.product_id is not None and row.product_id == opportunity.product_id)
    ]


def _products(
    db: Session, owner: User, opportunity: ProductOpportunity, searches: list[SupplierSearch]
) -> list[SupplierProduct]:
    search_ids = [row.id for row in searches]
    products: list[SupplierProduct] = []
    if search_ids:
        matched_ids = list(
            db.scalars(
                select(SupplierOpportunityMatch.supplier_product_id).where(
                    SupplierOpportunityMatch.owner_id == owner.id,
                    SupplierOpportunityMatch.search_id.in_(search_ids),
                )
            )
        )
        if matched_ids:
            products = list(
                db.scalars(
                    select(SupplierProduct)
                    .where(
                        SupplierProduct.owner_id == owner.id,
                        SupplierProduct.id.in_(matched_ids),
                    )
                    .order_by(SupplierProduct.created_at)
                )
            )
    supplier_ids: set[uuid.UUID] = set()
    for search in searches:
        summary = search.summary_json if isinstance(search.summary_json, dict) else {}
        supplier_values = summary.get("supplier_ids", [])
        if isinstance(supplier_values, list):
            for value in supplier_values:
                try:
                    supplier_ids.add(uuid.UUID(str(value)))
                except (TypeError, ValueError):
                    continue
    if supplier_ids:
        fallback = list(
            db.scalars(
                select(SupplierProduct)
                .where(
                    SupplierProduct.owner_id == owner.id,
                    SupplierProduct.supplier_id.in_(supplier_ids),
                )
                .order_by(SupplierProduct.created_at)
            )
        )
        products.extend(row for row in fallback if row.id not in {item.id for item in products})
    return products


def _evidence_map(
    db: Session, owner: User, supplier_ids: set[uuid.UUID]
) -> dict[uuid.UUID, list[SupplierEvidence]]:
    rows = (
        list(
            db.scalars(
                select(SupplierEvidence).where(
                    SupplierEvidence.owner_id == owner.id,
                    SupplierEvidence.supplier_id.in_(supplier_ids),
                    SupplierEvidence.archived.is_(False),
                )
            )
        )
        if supplier_ids
        else []
    )
    result: dict[uuid.UUID, list[SupplierEvidence]] = defaultdict(list)
    for row in rows:
        result[row.supplier_id].append(row)
    return result


def _source_refs(
    evidence: list[SupplierEvidence], ids: list[str] | None = None
) -> list[dict[str, object]]:
    wanted = set(ids or [])
    selected = [row for row in evidence if not wanted or str(row.id) in wanted]
    return [
        {
            "id": str(row.id),
            "url": row.source_url,
            "reference": row.reference,
            "verification": row.verification_status,
            "freshness": row.freshness_status,
            "observed_at": _json(row.observed_at),
            "retrieved_at": _json(row.retrieved_at),
            "provenance": (
                "SOURCE_PROVIDED_CLAIM"
                if row.evidence_kind in {"observed", "self_reported"}
                else str(row.evidence_kind).upper()
            ),
        }
        for row in selected
    ]


def _input(
    key: str,
    value: object,
    *,
    unit: str | None,
    currency: str | None,
    supplier: SupplierProduct,
    evidence: list[SupplierEvidence],
    evidence_ids: list[str] | None = None,
    provenance: str = "SOURCE_PROVIDED_CLAIM",
) -> dict[str, object]:
    refs = _source_refs(evidence, evidence_ids)
    effective_provenance = provenance if value is not None else "UNKNOWN"
    return {
        "key": key,
        "value": _json(value),
        "unit": unit,
        "currency": currency,
        "quantity_basis": unit,
        "price_basis": supplier.price_kind if key == "supplier_unit_price" else None,
        "source": (
            "SupplierCommercialTerm" if effective_provenance != "UNKNOWN" else "SupplierProduct"
        ),
        "source_references": refs,
        "provenance": effective_provenance,
        "trust_state": (
            "UNVERIFIED_CLAIM"
            if effective_provenance == "SOURCE_PROVIDED_CLAIM"
            else effective_provenance
        ),
        "freshness": (
            refs[0].get("freshness", "UNKNOWN")
            if refs
            else str(supplier.freshness_status or "UNKNOWN")
        ),
        "observed_at": refs[0].get("observed_at") if refs else _json(supplier.observed_at),
        "scope": {
            "supplier_product_id": str(supplier.id),
            "supplier_id": str(supplier.supplier_id),
        },
    }


def _assumption_input(item: dict[str, object], scenario_key: str) -> dict[str, object]:
    return {
        "key": str(item.get("key")),
        "value": _json(item.get("value")),
        "unit": item.get("unit"),
        "currency": item.get("currency"),
        "quantity_basis": item.get("unit"),
        "price_basis": item.get("price_basis"),
        "source": "Seller scenario",
        "source_references": [],
        "provenance": "ASSUMED",
        "trust_state": "EXPLICIT_SCENARIO_ASSUMPTION",
        "freshness": "UNKNOWN",
        "observed_at": None,
        "scope": {"scenario_key": scenario_key},
        "reason": str(item.get("reason")),
        "marker": str(item.get("marker") or "DETERMINISTIC_TEST"),
    }


def _build_candidate(
    db: Session,
    owner: User,
    product: SupplierProduct,
    evidence: list[SupplierEvidence],
    assumptions: list[dict[str, object]],
    scenario_key: str,
) -> dict[str, object]:
    terms = list(
        db.scalars(
            select(SupplierCommercialTerm)
            .where(
                SupplierCommercialTerm.owner_id == owner.id,
                SupplierCommercialTerm.supplier_product_id == product.id,
            )
            .order_by(SupplierCommercialTerm.version)
        )
    )
    current = next((row for row in reversed(terms) if row.is_current), terms[-1] if terms else None)
    term_evidence_ids = [str(value) for value in (current.source_evidence_ids if current else [])]
    records: list[dict[str, object]] = []
    if current:
        records.extend(
            [
                _input(
                    "supplier_unit_price",
                    current.unit_price,
                    unit="unit",
                    currency=current.currency,
                    supplier=product,
                    evidence=evidence,
                    evidence_ids=term_evidence_ids,
                ),
                _input(
                    "supplier_currency",
                    current.currency,
                    unit=None,
                    currency=current.currency,
                    supplier=product,
                    evidence=evidence,
                    evidence_ids=term_evidence_ids,
                ),
                _input(
                    "supplier_moq",
                    current.moq,
                    unit="units",
                    currency=None,
                    supplier=product,
                    evidence=evidence,
                    evidence_ids=term_evidence_ids,
                ),
                _input(
                    "lead_time_days",
                    current.lead_time_days,
                    unit="days",
                    currency=None,
                    supplier=product,
                    evidence=evidence,
                    evidence_ids=term_evidence_ids,
                ),
                _input(
                    "incoterm",
                    current.incoterm,
                    unit=None,
                    currency=None,
                    supplier=product,
                    evidence=evidence,
                    evidence_ids=term_evidence_ids,
                ),
            ]
        )
    else:
        records.extend(
            [
                _input(
                    "supplier_unit_price",
                    product.observed_price,
                    unit="unit",
                    currency=product.currency,
                    supplier=product,
                    evidence=evidence,
                ),
                _input(
                    "supplier_currency",
                    product.currency,
                    unit=None,
                    currency=product.currency,
                    supplier=product,
                    evidence=evidence,
                ),
                _input(
                    "supplier_moq",
                    product.moq,
                    unit=product.moq_unit or "units",
                    currency=None,
                    supplier=product,
                    evidence=evidence,
                ),
                _input(
                    "lead_time_days",
                    product.production_lead_days,
                    unit="days",
                    currency=None,
                    supplier=product,
                    evidence=evidence,
                ),
                _input(
                    "incoterm", None, unit=None, currency=None, supplier=product, evidence=evidence
                ),
            ]
        )
    records.extend(
        [
            {
                "key": "selling_price",
                "value": None,
                "unit": "unit",
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"product_opportunity_id": "selected"},
            },
            {
                "key": "selling_currency",
                "value": None,
                "unit": None,
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"product_opportunity_id": "selected"},
            },
            {
                "key": "marketplace_fee_per_unit",
                "value": None,
                "unit": "unit",
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"product_opportunity_id": "selected"},
            },
            {
                "key": "freight_cost",
                "value": None,
                "unit": "shipment",
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"supplier_id": str(product.supplier_id)},
            },
            {
                "key": "freight_currency",
                "value": None,
                "unit": None,
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"supplier_id": str(product.supplier_id)},
            },
            {
                "key": "origin",
                "value": None,
                "unit": None,
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"supplier_id": str(product.supplier_id)},
            },
            {
                "key": "destination",
                "value": None,
                "unit": None,
                "currency": None,
                "provenance": "UNKNOWN",
                "source": None,
                "source_references": [],
                "trust_state": "UNKNOWN",
                "freshness": "UNKNOWN",
                "scope": {"supplier_id": str(product.supplier_id)},
            },
        ]
    )
    assumption_rows = [_assumption_input(item, scenario_key) for item in assumptions]
    by_key: dict[str, dict[str, object]] = {str(row["key"]): row for row in records}
    for row in assumption_rows:
        # Assumptions never replace source rows; they are separately retained and
        # only fill a missing effective input for this named scenario.
        if by_key.get(str(row["key"]), {}).get("value") is None:
            by_key[str(row["key"])] = row
    effective = list(by_key.values())
    known = [
        row
        for row in records
        if row.get("value") is not None and row.get("provenance") != "UNKNOWN"
    ]
    claims = [row for row in known if row.get("provenance") == "SOURCE_PROVIDED_CLAIM"]
    unknown = [row for row in records if row.get("value") is None]
    missing: dict[str, list[str]] = {}
    for calculation, required in REQUIRED_INPUTS.items():
        missing[calculation] = [
            key
            for key in required
            if next((r for r in effective if r["key"] == key), {}).get("value") is None
        ]
    readiness = {
        calculation: {
            "status": "READY" if not fields else "NEEDS_INPUT",
            "missing_inputs": fields,
            "blocked": False,
        }
        for calculation, fields in missing.items()
    }
    return {
        "supplier_product_id": str(product.id),
        "supplier_id": str(product.supplier_id),
        "inputs": records,
        "effective_inputs": effective,
        "known_inputs": known,
        "claims": claims,
        "assumptions": assumption_rows,
        "unknown_inputs": unknown,
        "missing_inputs": missing,
        "readiness": readiness,
        "optional_gaps": [
            key
            for key in OPTIONAL_FIELDS
            if next((r for r in effective if r["key"] == key), {}).get("value") is None
        ],
        "contradictions": _contradictions(terms),
        "lineage": {
            "supplier_product_id": str(product.id),
            "supplier_id": str(product.supplier_id),
            "evidence_ids": [str(row.id) for row in evidence],
            "commercial_term_ids": [str(row.id) for row in terms],
        },
    }


def _contradictions(terms: list[SupplierCommercialTerm]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for field in ("unit_price", "currency", "moq", "lead_time_days", "incoterm"):
        values = {str(getattr(row, field)) for row in terms if getattr(row, field) is not None}
        if len(values) > 1:
            result.append({"field": field, "values": sorted(values), "state": "UNRESOLVED"})
    return result


def project_readiness(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: CommercialReadinessCreate,
) -> tuple[CommercialReadinessSnapshot, bool]:
    opportunity, assessment, _constraint = _context(db, owner, opportunity_id, assessment_id)
    existing = db.scalar(
        select(CommercialReadinessSnapshot).where(
            CommercialReadinessSnapshot.owner_id == owner.id,
            CommercialReadinessSnapshot.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    searches = _searches(db, owner, opportunity)
    products = _products(db, owner, opportunity, searches)
    if data.supplier_id is not None:
        scoped_products = products
        products = [row for row in scoped_products if row.supplier_id == data.supplier_id]
        if not products:
            link = db.scalar(
                select(CrossMarketplaceSupplierLink).where(
                    CrossMarketplaceSupplierLink.owner_id == owner.id,
                    CrossMarketplaceSupplierLink.canonical_supplier_id == data.supplier_id,
                    CrossMarketplaceSupplierLink.match_state == "MATCH",
                )
            )
            if link:
                products = [row for row in scoped_products if row.supplier_id == link.supplier_id]
    if not products:
        raise HTTPException(
            409, "No supplier commercial evidence is linked to this product opportunity."
        )
    selected = products[0]
    supplier = db.get(Supplier, selected.supplier_id)
    if supplier is None or supplier.owner_id != owner.id:
        raise HTTPException(404, "Supplier is not available in the owner scope.")
    evidence = _evidence_map(db, owner, {selected.supplier_id}).get(selected.supplier_id, [])
    candidate = _build_candidate(
        db,
        owner,
        selected,
        evidence,
        [item.model_dump(mode="json") for item in data.assumptions],
        data.scenario_key,
    )
    contradictions = cast(list[dict[str, object]], candidate["contradictions"])
    readiness_by_calculation = cast(dict[str, dict[str, object]], candidate["readiness"])
    missing_by_calculation = cast(dict[str, list[str]], candidate["missing_inputs"])
    for value in readiness_by_calculation.values():
        if isinstance(value, dict) and contradictions:
            value["status"] = "BLOCKED"
            value["blocked"] = True
            existing_missing = value.get("missing_inputs")
            value["missing_inputs"] = [
                *(existing_missing if isinstance(existing_missing, list) else []),
                "unresolved_commercial_contradiction",
            ]
    overall = (
        "READY"
        if any(
            isinstance(item, dict) and item.get("status") == "READY"
            for item in readiness_by_calculation.values()
        )
        and not contradictions
        else "BLOCKED" if contradictions else "NEEDS_INPUT"
    )
    readiness = {
        "overall": overall,
        "calculations": readiness_by_calculation,
        "safe_next_action": (
            "Obtain a supplier quote with currency and unit basis."
            if overall != "READY"
            else "Review the scenario inputs before any economics calculation."
        ),
        "human_review_required": True,
        "economics_calculated": False,
    }
    row = CommercialReadinessSnapshot(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        supplier_id=selected.supplier_id,
        scenario_key=data.scenario_key,
        readiness=readiness,
        known_inputs=candidate["known_inputs"],
        claims=candidate["claims"],
        assumptions=candidate["assumptions"],
        unknown_inputs=candidate["unknown_inputs"],
        missing_inputs=[
            {"calculation": key, "fields": value} for key, value in missing_by_calculation.items()
        ],
        optional_gaps=candidate["optional_gaps"],
        contradictions=contradictions,
        lineage={
            "search_ids": [str(item.id) for item in searches],
            "candidate": candidate["lineage"],
            "mode": (
                "LOCAL_FIXTURE"
                if any(
                    (item.source_policy or {}).get("mode") == "LOCAL_FIXTURE" for item in searches
                )
                else "LIVE_READ_ONLY"
            ),
        },
        idempotency_key=data.idempotency_key,
        notes=(
            "Readiness projection only; no landed cost, margin, capital, order, payment, "
            "or supplier contact was performed."
        ),
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.commercial_readiness_projected",
        entity_type="commercial_readiness_snapshot",
        entity_id=row.id,
        metadata={
            "opportunity_id": str(opportunity.id),
            "assessment_id": str(assessment.id),
            "supplier_id": str(selected.supplier_id),
            "overall": overall,
        },
        idempotency_key=f"commercial-readiness:{row.id}",
    )
    db.commit()
    db.refresh(row)
    return row, False


def latest_readiness(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> CommercialReadinessSnapshot | None:
    return db.scalar(
        select(CommercialReadinessSnapshot)
        .where(
            CommercialReadinessSnapshot.owner_id == owner.id,
            CommercialReadinessSnapshot.opportunity_id == opportunity_id,
            CommercialReadinessSnapshot.assessment_id == assessment_id,
        )
        .order_by(CommercialReadinessSnapshot.created_at.desc())
    )
