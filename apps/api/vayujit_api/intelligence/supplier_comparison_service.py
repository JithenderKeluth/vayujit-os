"""PR-8B supplier comparison orchestration.

This service is intentionally a projection layer.  It never calculates landed
cost or unit economics itself and never creates a supplier decision outside the
canonical PR-4.2 ``SupplierShortlistDecision`` authority.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_reassessment_models import CommercialReassessment
from vayujit_api.intelligence.cross_marketplace_models import (
    CrossMarketplaceSupplier,
    CrossMarketplaceSupplierLink,
)
from vayujit_api.intelligence.cross_marketplace_service import reconcile
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.shortlisting_models import (
    SupplierShortlistContext,
    SupplierShortlistEvent,
    SupplierShortlistVersion,
)
from vayujit_api.intelligence.shortlisting_schemas import (
    ShortlistContextCreate,
    ShortlistDecisionRequest,
)
from vayujit_api.intelligence.shortlisting_service import create_context, decide
from vayujit_api.intelligence.supplier_comparison_models import SupplierComparisonSnapshot
from vayujit_api.intelligence.supplier_comparison_schemas import (
    SupplierComparisonCreate,
    SupplierComparisonShortlistCreate,
)
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCommercialTerm,
    SupplierProduct,
)

MAX_SUPPLIERS = 5
COMPARISON_METRICS = (
    "supplier_unit_price",
    "moq",
    "order_quantity",
    "landed_cost_per_unit",
    "total_landed_cost",
    "selling_cost_per_unit",
    "contribution_per_unit",
    "contribution_margin",
    "capital_required",
    "capital_headroom",
    "lead_time_days",
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


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(_json(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _owned_context(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[ProductOpportunity, ProductOpportunityAssessment]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id,
            ProductOpportunity.owner_id == owner.id,
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
    return opportunity, assessment


def _product_signature(product: SupplierProduct) -> dict[str, object]:
    specs = product.specifications if isinstance(product.specifications, dict) else {}
    normalized_specs: dict[str, object] = {}
    for key in sorted(specs, key=lambda item: str(item).casefold()):
        value = specs[key]
        if value is None or value == "":
            continue
        normalized_specs[str(key).casefold().strip()] = _json(value)
    return {
        "title": " ".join((product.title or "").casefold().split()),
        "category": " ".join((product.category or "").casefold().split()),
        "specifications": normalized_specs,
        "moq_unit": product.moq_unit,
    }


def _product_comparability(products: list[SupplierProduct]) -> tuple[str, str]:
    if not products:
        return "NEEDS_EVIDENCE", "No supplier products were retained."
    signatures = [_product_signature(item) for item in products]
    if any(not item["title"] or not item["category"] for item in signatures):
        return (
            "COMPARABILITY_UNCONFIRMED",
            "A supplier product is missing title or category evidence.",
        )
    if all(item == signatures[0] for item in signatures[1:]):
        return "COMPARABLE", "SupplierProduct characteristics match across the selected candidates."

    # Category alone is never sufficient.  A product with a different type,
    # material, size, capacity, pack, use, or unit remains visibly non-comparable.
    meaningful_keys = {
        "product_type",
        "material",
        "size",
        "capacity",
        "pack_quantity",
        "intended_use",
        "unit_of_measure",
    }
    values: dict[str, set[str]] = {key: set() for key in meaningful_keys}
    for signature in signatures:
        specs = cast(dict[str, object], signature["specifications"])
        for key in meaningful_keys:
            if key in specs:
                values[key].add(str(specs[key]).casefold())
    differing = sorted(key for key, seen in values.items() if len(seen) > 1)
    if differing:
        return "NOT_COMPARABLE", "Materially different product specifications: " + ", ".join(
            differing
        )
    return (
        "COMPARABILITY_UNCONFIRMED",
        "Available SupplierProduct characteristics do not establish equivalence.",
    )


def _term_scope(
    db: Session, owner: User, row: CommercialReassessment
) -> SupplierCommercialTerm | None:
    return db.scalar(
        select(SupplierCommercialTerm).where(
            SupplierCommercialTerm.id == row.commercial_term_id,
            SupplierCommercialTerm.owner_id == owner.id,
            SupplierCommercialTerm.supplier_id == row.supplier_id,
            SupplierCommercialTerm.supplier_product_id == row.supplier_product_id,
        )
    )


def _current_parts(row: CommercialReassessment) -> tuple[dict[str, object], dict[str, object]]:
    current = row.current if isinstance(row.current, dict) else {}
    landed = current.get("landed_cost")
    economics = current.get("unit_economics")
    return (
        cast(dict[str, object], landed) if isinstance(landed, dict) else {},
        cast(dict[str, object], economics) if isinstance(economics, dict) else {},
    )


def _calculation(landed: dict[str, object]) -> dict[str, object]:
    value = landed.get("calculation")
    return cast(dict[str, object], value) if isinstance(value, dict) else landed


def _order_economics(economics: dict[str, object]) -> dict[str, object]:
    value = economics.get("order_economics")
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _scenario_scope(
    landed: dict[str, object], economics: dict[str, object], calculation: dict[str, object]
) -> dict[str, object]:
    breakdown = calculation.get("breakdown") or landed.get("breakdown")
    items = breakdown if isinstance(breakdown, list) else []

    def component_scope(categories: set[str]) -> list[dict[str, object]] | str:
        selected = [
            {
                "category": item.get("category"),
                "inclusion_status": item.get("inclusion_status"),
                "currency": item.get("currency"),
                "basis": item.get("basis"),
            }
            for item in items
            if isinstance(item, dict) and str(item.get("category")) in categories
        ]
        return selected if selected else "UNKNOWN"

    return {
        "currency": calculation.get("currency") or economics.get("base_currency"),
        "target_quantity": (
            calculation.get("target_quantity")
            or economics.get("quantity")
            or economics.get("target_quantity")
        ),
        "quantity_unit": calculation.get("quantity_unit") or economics.get("quantity_unit"),
        "selling_price": economics.get("selling_price"),
        "selling_price_currency": economics.get("selling_price_currency"),
        "selling_price_provenance": economics.get("selling_price_provenance"),
        "freight_scope": component_scope({"FREIGHT", "FREIGHT_COST"}),
        "tax_scope": component_scope({"IMPORT_TAX", "TAX", "GST"}),
        "duty_scope": component_scope({"CUSTOMS_DUTY", "DUTY"}),
    }


def _metric_value(
    name: str,
    row: CommercialReassessment,
    product: SupplierProduct,
    term: SupplierCommercialTerm | None,
) -> tuple[object | None, str | None, str | None]:
    landed, economics = _current_parts(row)
    calculation = _calculation(landed)
    order = _order_economics(economics)
    if name == "supplier_unit_price":
        return (
            term.unit_price if term and term.unit_price is not None else product.observed_price,
            term.currency if term else product.currency,
            "per_unit",
        )
    if name == "moq":
        return (
            term.moq if term and term.moq is not None else product.moq,
            None,
            product.moq_unit,
        )
    if name == "lead_time_days":
        lead_time_value = (
            term.production_lead_days
            if term and term.production_lead_days is not None
            else product.production_lead_days
        )
        return lead_time_value, None, "days"
    if name == "order_quantity":
        order_quantity_value: object | None = (
            economics.get("quantity")
            or order.get("order_quantity")
            or calculation.get("target_quantity")
        )
        return (
            order_quantity_value,
            None,
            "unit",
        )
    mapping = {
        "landed_cost_per_unit": "per_unit_cost",
        "total_landed_cost": "total_included_cost",
    }
    if name in mapping:
        return (
            calculation.get(mapping[name]),
            cast(str | None, calculation.get("currency")),
            "per_unit" if name.endswith("per_unit") else None,
        )
    if name in {
        "selling_cost_per_unit",
        "contribution_per_unit",
        "contribution_margin",
        "capital_required",
        "capital_headroom",
    }:
        key = {
            "selling_cost_per_unit": "per_unit_selling_cost",
            "contribution_per_unit": "per_unit_contribution",
            "contribution_margin": "contribution_margin",
            "capital_required": "capital_required",
            "capital_headroom": "capital_headroom",
        }[name]
        value = economics.get(key)
        # PR-5C stores a positive ``capital_shortfall`` and leaves
        # ``capital_headroom`` NULL when the scenario does not fit.  Expose
        # the canonical shortfall as negative headroom for a truthful,
        # like-for-like comparison; never treat it as zero.
        if name == "capital_headroom" and value is None:
            shortfall = economics.get("capital_shortfall")
            if shortfall is not None:
                try:
                    value = -Decimal(str(shortfall))
                except (InvalidOperation, ValueError, TypeError):
                    value = None
        return (
            value,
            cast(str | None, economics.get("base_currency") or economics.get("currency")),
            "ratio" if name == "contribution_margin" else None,
        )
    return None, None, None


def _row_scope(
    db: Session,
    owner: User,
    row: CommercialReassessment,
    canonical: CrossMarketplaceSupplier,
    product: SupplierProduct,
    term: SupplierCommercialTerm | None,
) -> dict[str, object]:
    supplier = db.scalar(
        select(Supplier).where(Supplier.id == row.supplier_id, Supplier.owner_id == owner.id)
    )
    landed, economics = _current_parts(row)
    calc = _calculation(landed)
    source_evidence = (
        row.quote_evidence.get("source_evidence_id")
        if isinstance(row.quote_evidence, dict)
        else None
    )
    trust = {
        "source_environment": (row.quote_evidence or {}).get("evidence_environment", "UNKNOWN"),
        "trust_environment": (row.quote_evidence or {}).get("trust_environment", "UNKNOWN"),
        "claim_semantics": (row.quote_evidence or {}).get(
            "claim_semantics", "SOURCE_PROVIDED_CLAIM"
        ),
        "human_extraction_review": (
            "HUMAN" if (row.quote_evidence or {}).get("review_id") else "UNKNOWN"
        ),
        "supplier_verification": supplier.verification_state if supplier else "UNKNOWN",
    }
    readiness = (row.current or {}).get("readiness")
    readiness_data = cast(dict[str, object], readiness) if isinstance(readiness, dict) else {}
    unknown_inputs = readiness_data.get("unknown_inputs")
    unknown_input_values = unknown_inputs if isinstance(unknown_inputs, list) else []
    unknowns = sorted({str(item) for item in (row.blockers or [])})
    unknowns.extend(sorted(str(item) for item in unknown_input_values if item))
    contradictions = _json(readiness_data.get("contradictions", []))
    if not isinstance(contradictions, list):
        contradictions = []
    status = "READY" if row.status == "READY_FOR_HUMAN_REVIEW" else "BLOCKED"
    return {
        "reassessment_id": str(row.id),
        "supplier_id": str(row.supplier_id),
        "canonical_supplier_id": str(canonical.id),
        "supplier": canonical.display_name,
        "supplier_identity_state": canonical.identity_state,
        "supplier_verification": supplier.verification_state if supplier else "UNKNOWN",
        "supplier_product_id": str(product.id),
        "product": {
            "title": product.title,
            "category": product.category,
            "specifications": _json(product.specifications or {}),
            "signature": _product_signature(product),
        },
        "quote": {
            "version": row.quote_version,
            "term_id": str(row.commercial_term_id),
            "valid_until": term.valid_until.isoformat() if term and term.valid_until else None,
            "is_current": term.is_current if term else False,
            "source_evidence_id": str(source_evidence) if source_evidence else None,
        },
        "status": status,
        "reassessment_status": row.status,
        "commercial_readiness": (row.current or {}).get("readiness", "UNKNOWN"),
        "metrics": {
            name: {
                "value": _json(_metric_value(name, row, product, term)[0]),
                "currency": _metric_value(name, row, product, term)[1],
                "unit": _metric_value(name, row, product, term)[2],
                "state": (
                    "AVAILABLE"
                    if _metric_value(name, row, product, term)[0] is not None
                    else "UNKNOWN"
                ),
            }
            for name in COMPARISON_METRICS
        },
        "calculation_versions": {
            "landed_cost": calc.get("calculation_version"),
            "unit_economics": economics.get("calculation_version"),
        },
        "assumptions": _json(row.assumptions or []),
        "scenario_scope": _scenario_scope(landed, economics, calc),
        "unknowns": sorted(set(unknowns)),
        "blockers": sorted({str(item) for item in (row.blockers or [])}),
        "contradictions": contradictions,
        "trust": trust,
        "provenance": {
            "reassessment_input_fingerprint": row.input_fingerprint,
            "lineage": _json(row.lineage or {}),
            "quote_evidence": _json(row.quote_evidence or {}),
        },
    }


def _canonical_updated_at(
    canonical_rows: dict[uuid.UUID, CrossMarketplaceSupplier], canonical_id: uuid.UUID
) -> datetime:
    canonical = canonical_rows.get(canonical_id)
    return canonical.updated_at if canonical is not None else datetime.min.replace(tzinfo=UTC)


def _scope_rows(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    reassessment_ids: list[uuid.UUID],
) -> tuple[list[CommercialReassessment], list[dict[str, object]], dict[str, object]]:
    if len(set(reassessment_ids)) != len(reassessment_ids):
        raise HTTPException(422, "Each PR-8A reassessment may appear only once.")
    if not 2 <= len(reassessment_ids) <= MAX_SUPPLIERS:
        raise HTTPException(422, "Compare between two and five supplier reassessments.")
    rows = list(
        db.scalars(
            select(CommercialReassessment).where(
                CommercialReassessment.owner_id == owner.id,
                CommercialReassessment.opportunity_id == opportunity_id,
                CommercialReassessment.assessment_id == assessment_id,
                CommercialReassessment.id.in_(reassessment_ids),
            )
        )
    )
    by_id = {row.id: row for row in rows}
    if len(rows) != len(reassessment_ids):
        raise HTTPException(404, "One or more reassessments are not in this owner/product context.")
    # Request ordering is a UI concern; canonical ordering is part of the
    # comparison identity and keeps equal logical requests deterministic.
    rows = sorted((by_id[item] for item in reassessment_ids), key=lambda item: str(item.id))
    supplier_ids = sorted({row.supplier_id for row in rows}, key=str)
    if len(supplier_ids) < 2:
        raise HTTPException(422, "A multi-supplier comparison requires two distinct suppliers.")
    # Reconciliation is the existing canonical supplier identity authority.
    reconcile(db, owner, supplier_ids)
    links = list(
        db.scalars(
            select(CrossMarketplaceSupplierLink).where(
                CrossMarketplaceSupplierLink.owner_id == owner.id,
                CrossMarketplaceSupplierLink.supplier_id.in_(supplier_ids),
            )
        )
    )
    links_by_supplier: dict[uuid.UUID, list[CrossMarketplaceSupplierLink]] = {}
    for link in links:
        links_by_supplier.setdefault(link.supplier_id, []).append(link)
    if len(links_by_supplier) != len(supplier_ids):
        raise HTTPException(409, "Canonical supplier identity is incomplete for comparison.")
    all_canonical = {
        item.id: item
        for item in db.scalars(
            select(CrossMarketplaceSupplier).where(
                CrossMarketplaceSupplier.owner_id == owner.id,
                CrossMarketplaceSupplier.id.in_({link.canonical_supplier_id for link in links}),
            )
        )
    }
    # Older PR-4 fixtures can leave more than one canonical projection linked
    # to a source Supplier.  Reconciliation is authoritative; choose its
    # newest projection deterministically instead of leaking every historical
    # link into the comparison candidate set.
    link_by_supplier: dict[uuid.UUID, CrossMarketplaceSupplierLink] = {}
    for supplier_id, candidates in links_by_supplier.items():
        link_by_supplier[supplier_id] = max(
            candidates,
            key=lambda link: (
                _canonical_updated_at(all_canonical, link.canonical_supplier_id),
                str(link.canonical_supplier_id),
            ),
        )
    canonical_ids = {link.canonical_supplier_id for link in link_by_supplier.values()}
    if len(canonical_ids) < 2:
        raise HTTPException(422, "The selected supplier records resolve to one canonical supplier.")
    canonical_rows = {
        item.id: item
        for item in db.scalars(
            select(CrossMarketplaceSupplier).where(
                CrossMarketplaceSupplier.owner_id == owner.id,
                CrossMarketplaceSupplier.id.in_(canonical_ids),
            )
        )
    }
    products: list[SupplierProduct] = []
    resolved: list[dict[str, object]] = []
    for row in rows:
        product = db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.id == row.supplier_product_id,
                SupplierProduct.owner_id == owner.id,
                SupplierProduct.supplier_id == row.supplier_id,
            )
        )
        canonical = canonical_rows.get(link_by_supplier[row.supplier_id].canonical_supplier_id)
        term = _term_scope(db, owner, row)
        if product is None or canonical is None or term is None:
            raise HTTPException(
                409,
                "Supplier, SupplierProduct, canonical identity, or quote lineage is incomplete.",
            )
        products.append(product)
        resolved.append(_row_scope(db, owner, row, canonical, product, term))
    resolved.sort(
        key=lambda item: (str(item["canonical_supplier_id"]), str(item["supplier_product_id"]))
    )
    product_status, product_reason = _product_comparability(products)
    context: dict[str, object] = {
        "product_status": product_status,
        "product_reason": product_reason,
        "supplier_ids": [str(item) for item in supplier_ids],
        "canonical_supplier_ids": sorted(str(item) for item in canonical_ids),
        "goal_ids": sorted({str(row.goal_id) for row in rows if row.goal_id}, key=str),
    }
    return rows, resolved, context


def _metric_comparisons(
    rows: list[dict[str, object]], product_status: str
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name in COMPARISON_METRICS:
        values: list[dict[str, object]] = []
        for row in rows:
            metric = cast(dict[str, object], cast(dict[str, object], row["metrics"])[name])
            values.append(
                {
                    "canonical_supplier_id": row["canonical_supplier_id"],
                    "supplier": row["supplier"],
                    "value": metric.get("value"),
                    "currency": metric.get("currency"),
                    "unit": metric.get("unit"),
                    "state": metric.get("state"),
                    "evidence": row["provenance"],
                }
            )
        state = "AVAILABLE"
        reason = ""
        delta: str | None = None
        available = [item for item in values if item.get("value") is not None]
        currencies = {str(item.get("currency")) for item in available if item.get("currency")}
        units = {str(item.get("unit")) for item in available if item.get("unit")}
        quantities = {
            str(
                cast(
                    dict[str, object], cast(dict[str, object], row["metrics"])["order_quantity"]
                ).get("value")
            )
            for row in rows
            if cast(
                dict[str, object], cast(dict[str, object], row["metrics"])["order_quantity"]
            ).get("value")
            is not None
        }
        scope_rows = [cast(dict[str, object], row.get("scenario_scope", {})) for row in rows]
        derived_metrics = {
            "landed_cost_per_unit",
            "total_landed_cost",
            "selling_cost_per_unit",
            "contribution_per_unit",
            "contribution_margin",
            "capital_required",
            "capital_headroom",
        }
        scope_fields = {"freight_scope", "tax_scope", "duty_scope"}
        calculation_versions = {
            str(cast(dict[str, object], row.get("calculation_versions", {})).get("landed_cost"))
            for row in rows
            if cast(dict[str, object], row.get("calculation_versions", {})).get("landed_cost")
        }
        selling_scopes = {
            (
                scope.get("selling_price"),
                scope.get("selling_price_currency"),
                scope.get("selling_price_provenance"),
            )
            for scope in scope_rows
        }
        if product_status == "NOT_COMPARABLE":
            state, reason = (
                "NOT_DIRECTLY_COMPARABLE",
                "SupplierProduct characteristics are materially different.",
            )
        elif len(available) != len(values):
            state, reason = (
                "UNKNOWN",
                "One or more supplier inputs are missing; no zero was assumed.",
            )
        elif any(
            name
            in {
                "supplier_unit_price",
                "moq",
                "landed_cost_per_unit",
                "total_landed_cost",
                "selling_cost_per_unit",
                "contribution_per_unit",
                "capital_required",
                "capital_headroom",
            }
            and not item.get("currency")
            for item in available
        ):
            state, reason = (
                "UNKNOWN",
                "Currency is unknown for one or more monetary values; "
                "no direct delta was calculated.",
            )
        elif len(currencies) > 1 or len(units) > 1:
            state, reason = (
                "NOT_DIRECTLY_COMPARABLE",
                "Currency or unit basis differs and no canonical conversion was supplied.",
            )
        elif name in derived_metrics and len(calculation_versions) > 1:
            state, reason = (
                "NOT_DIRECTLY_COMPARABLE",
                "Calculation versions differ; refresh the scenarios under one canonical version.",
            )
        elif name in derived_metrics and any(
            len({_fingerprint({"scope": scope.get(field)}) for scope in scope_rows}) > 1
            for field in scope_fields
        ):
            state, reason = (
                "NOT_DIRECTLY_COMPARABLE",
                "Freight, tax, or duty inclusion scope differs between scenarios.",
            )
        elif name in derived_metrics and any(
            scope.get(field) == "UNKNOWN" for scope in scope_rows for field in scope_fields
        ):
            state, reason = (
                "UNKNOWN",
                "Freight, tax, or duty inclusion scope is unknown; "
                "no favorable assumption was made.",
            )
        elif (
            name in {"selling_cost_per_unit", "contribution_per_unit", "contribution_margin"}
            and len(selling_scopes) > 1
        ):
            state, reason = (
                "NOT_DIRECTLY_COMPARABLE",
                "Selling-price assumptions differ between scenarios.",
            )
        elif (
            name in {"total_landed_cost", "capital_required", "capital_headroom"}
            and len(quantities) > 1
        ):
            state, reason = (
                "NOT_DIRECTLY_COMPARABLE",
                "Order quantities differ; total capital values are scenario-specific.",
            )
        else:
            try:
                numbers = [Decimal(str(item["value"])) for item in available]
                if len(numbers) >= 2:
                    delta = str(numbers[1] - numbers[0])
            except (InvalidOperation, ValueError, TypeError):
                state, reason = (
                    "NOT_DIRECTLY_COMPARABLE",
                    "Values are not numeric under the canonical metric contract.",
                )
        result.append(
            {"metric": name, "values": values, "delta": delta, "state": state, "reason": reason}
        )
    return result


def _comparison_status(
    rows: list[dict[str, object]], product_status: str, metrics: list[dict[str, object]]
) -> str:
    if product_status == "NOT_COMPARABLE":
        return "NOT_COMPARABLE"
    if all(row["status"] == "READY" for row in rows) and any(
        item["state"] == "AVAILABLE" for item in metrics
    ):
        return (
            "COMPARABLE"
            if all(
                item["state"] == "AVAILABLE"
                for item in metrics
                if item["metric"] in {"landed_cost_per_unit", "contribution_per_unit"}
            )
            else "PARTIALLY_COMPARABLE"
        )
    if any(row["status"] == "BLOCKED" for row in rows):
        return "NEEDS_EVIDENCE"
    return "PARTIALLY_COMPARABLE"


def _scope_fingerprint(
    rows: list[CommercialReassessment], resolved: list[dict[str, object]]
) -> str:
    payload = {
        "reassessments": [
            {
                "id": str(row.id),
                "input_fingerprint": row.input_fingerprint,
                "status": row.status,
                "current": _json(row.current),
                "blockers": _json(row.blockers),
                "quote_version": row.quote_version,
                "term_id": str(row.commercial_term_id),
            }
            for row in rows
        ],
        "supplier_rows": [
            {
                "canonical_supplier_id": item["canonical_supplier_id"],
                "supplier_product_id": item["supplier_product_id"],
                "product": item["product"],
                "quote": item["quote"],
                "metrics": item["metrics"],
                "calculation_versions": item["calculation_versions"],
                "assumptions": item["assumptions"],
                "scenario_scope": item["scenario_scope"],
                "trust": item["trust"],
                "unknowns": item["unknowns"],
                "blockers": item["blockers"],
                "contradictions": item["contradictions"],
                "provenance": item["provenance"],
            }
            for item in resolved
        ],
    }
    return _fingerprint(payload)


def _view(
    db: Session, owner: User, snapshot: SupplierComparisonSnapshot, *, reuse: bool = False
) -> dict[str, object]:
    decisions = []
    if snapshot.shortlist_context_id:
        from vayujit_api.intelligence.shortlisting_models import SupplierShortlistDecision

        decisions = [
            {
                "id": str(item.id),
                "canonical_supplier_id": str(item.supplier_id),
                "decision": item.decision,
                "reason": item.reason,
                "evidence_ids": item.evidence_ids,
                "provenance": "HUMAN",
                "created_at": item.created_at.isoformat(),
            }
            for item in db.scalars(
                select(SupplierShortlistDecision)
                .where(
                    SupplierShortlistDecision.owner_id == owner.id,
                    SupplierShortlistDecision.context_id == snapshot.shortlist_context_id,
                )
                .order_by(SupplierShortlistDecision.created_at, SupplierShortlistDecision.id)
            )
        ]
    return {
        "id": str(snapshot.id),
        "owner_id": str(snapshot.owner_id),
        "goal_id": str(snapshot.goal_id) if snapshot.goal_id else None,
        "opportunity_id": str(snapshot.opportunity_id),
        "assessment_id": str(snapshot.assessment_id),
        "snapshot_version": snapshot.snapshot_version,
        "status": snapshot.status,
        "idempotency_key": snapshot.idempotency_key,
        "input_fingerprint": snapshot.input_fingerprint,
        "canonical_supplier_ids": snapshot.canonical_supplier_ids,
        "supplier_ids": snapshot.supplier_ids,
        "supplier_product_ids": snapshot.supplier_product_ids,
        "reassessment_ids": snapshot.reassessment_ids,
        "quote_versions": snapshot.quote_versions,
        "input_fingerprints": snapshot.input_fingerprints,
        "calculation_versions": snapshot.calculation_versions,
        "suppliers": snapshot.suppliers,
        "metrics": snapshot.metrics,
        "unknowns": snapshot.unknowns,
        "blockers": snapshot.blockers,
        "contradictions": snapshot.contradictions,
        "provenance": snapshot.provenance,
        "lineage": snapshot.lineage,
        "shortlist_context_id": (
            str(snapshot.shortlist_context_id) if snapshot.shortlist_context_id else None
        ),
        "shortlist_version_id": (
            str(snapshot.shortlist_version_id) if snapshot.shortlist_version_id else None
        ),
        "human_decisions": decisions,
        "created_at": snapshot.created_at.isoformat(),
        "notes": snapshot.notes,
        "idempotent_reuse": reuse,
    }


def _check_goal(db: Session, owner: User, goal_id: uuid.UUID | None) -> None:
    if goal_id is None:
        return
    from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal

    if (
        db.scalar(
            select(BusinessAgentGoal).where(
                BusinessAgentGoal.id == goal_id, BusinessAgentGoal.owner_id == owner.id
            )
        )
        is None
    ):
        raise HTTPException(404, "Business goal is not available in the owner scope.")


def _ensure_shortlist_bridge(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    resolved: list[dict[str, object]],
    fingerprint: str,
) -> tuple[SupplierShortlistContext, SupplierShortlistVersion]:
    context, _ = create_context(
        db,
        owner,
        ShortlistContextCreate(
            opportunity_id=opportunity.id,
            category=opportunity.category,
            target_market=opportunity.target_marketplace or opportunity.target_region,
            idempotency_key=f"pr8b-context:{fingerprint}",
        ),
    )
    existing = db.scalar(
        select(SupplierShortlistVersion)
        .where(
            SupplierShortlistVersion.context_id == context.id,
            SupplierShortlistVersion.owner_id == owner.id,
        )
        .order_by(SupplierShortlistVersion.version.desc())
    )
    if existing is not None:
        return context, existing
    payload_items = [
        {
            "supplier_id": item["canonical_supplier_id"],
            "supplier": item["supplier"],
            "eligibility": "ELIGIBLE" if item["status"] == "READY" else "REVIEW_REQUIRED",
            "recommendation": "REVIEW_REQUIRED",
            "reason": ["PR-8B comparison requires explicit HUMAN review."],
            "comparison_snapshot_fingerprint": fingerprint,
        }
        for item in resolved
    ]
    version = SupplierShortlistVersion(
        owner_id=owner.id,
        context_id=context.id,
        context_version=context.current_version,
        version=1,
        payload={"shortlist": [], "review_required": payload_items, "blocked": [], "pr8b": True},
        created_at=datetime.now(UTC),
    )
    db.add(version)
    db.flush()
    db.add(
        SupplierShortlistEvent(
            owner_id=owner.id,
            context_id=context.id,
            event_type="comparison_shortlist_bridge_created",
            event_key=f"pr8b:shortlist-bridge:{fingerprint}",
            payload={
                "shortlist_version_id": str(version.id),
                "comparison_fingerprint": fingerprint,
            },
            created_at=datetime.now(UTC),
        )
    )
    db.flush()
    return context, version


def create_comparison(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: SupplierComparisonCreate,
) -> dict[str, object]:
    opportunity, _ = _owned_context(db, owner, opportunity_id, assessment_id)
    _check_goal(db, owner, data.goal_id)
    rows, resolved, scope = _scope_rows(
        db, owner, opportunity_id, assessment_id, data.reassessment_ids
    )
    scope_goal_ids = cast(list[str], scope["goal_ids"])
    if data.goal_id is not None and scope_goal_ids and str(data.goal_id) not in scope_goal_ids:
        raise HTTPException(
            409, "The requested goal is not the canonical goal for these reassessments."
        )
    comparison_goal_id = data.goal_id
    if comparison_goal_id is None and len(scope_goal_ids) == 1:
        comparison_goal_id = uuid.UUID(scope_goal_ids[0])
    fingerprint = _scope_fingerprint(rows, resolved)
    by_key = db.scalar(
        select(SupplierComparisonSnapshot).where(
            SupplierComparisonSnapshot.owner_id == owner.id,
            SupplierComparisonSnapshot.idempotency_key == data.idempotency_key,
        )
    )
    if by_key is not None:
        if by_key.input_fingerprint != fingerprint:
            raise HTTPException(
                409, "The comparison idempotency key was used for different inputs."
            )
        return _view(db, owner, by_key, reuse=True)
    existing = db.scalar(
        select(SupplierComparisonSnapshot).where(
            SupplierComparisonSnapshot.owner_id == owner.id,
            SupplierComparisonSnapshot.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return _view(db, owner, existing, reuse=True)
    metrics = _metric_comparisons(resolved, str(scope["product_status"]))
    status = _comparison_status(resolved, str(scope["product_status"]), metrics)
    unknowns = sorted(
        {unknown for item in resolved for unknown in cast(list[str], item["unknowns"])}
    )
    blockers = sorted(
        {blocker for item in resolved for blocker in cast(list[str], item["blockers"])}
    )
    contradictions = [
        {"canonical_supplier_id": item["canonical_supplier_id"], "items": item["contradictions"]}
        for item in resolved
        if item["contradictions"]
    ]
    context, shortlist_version = _ensure_shortlist_bridge(
        db, owner, opportunity, resolved, fingerprint
    )
    previous_version = (
        db.scalar(
            select(func.max(SupplierComparisonSnapshot.snapshot_version)).where(
                SupplierComparisonSnapshot.owner_id == owner.id,
                SupplierComparisonSnapshot.opportunity_id == opportunity_id,
                SupplierComparisonSnapshot.assessment_id == assessment_id,
            )
        )
        or 0
    )
    snapshot = SupplierComparisonSnapshot(
        owner_id=owner.id,
        goal_id=comparison_goal_id,
        opportunity_id=opportunity_id,
        assessment_id=assessment_id,
        snapshot_version=int(previous_version) + 1,
        status=status,
        idempotency_key=data.idempotency_key,
        input_fingerprint=fingerprint,
        canonical_supplier_ids=sorted(
            str(item) for item in cast(list[object], scope["canonical_supplier_ids"])
        ),
        supplier_ids=sorted(str(item) for item in cast(list[object], scope["supplier_ids"])),
        supplier_product_ids=sorted(str(item["supplier_product_id"]) for item in resolved),
        reassessment_ids=[str(row.id) for row in rows],
        quote_versions=[int(row.quote_version) for row in rows],
        input_fingerprints=sorted(row.input_fingerprint for row in rows),
        calculation_versions=sorted(
            {
                str(version)
                for item in resolved
                for version in cast(dict[str, object], item["calculation_versions"]).values()
                if version
            }
        ),
        suppliers=resolved,
        metrics=metrics,
        unknowns=unknowns,
        blockers=blockers,
        contradictions=contradictions,
        provenance={
            "authority": "PR-8A/PR-5A/PR-5B/PR-5C",
            "comparison": "VAYUJIT_PR8B",
            "automatic_winner": None,
            "product_comparability": scope,
        },
        lineage={
            "opportunity_id": str(opportunity_id),
            "assessment_id": str(assessment_id),
            "reassessment_ids": [str(row.id) for row in rows],
        },
        shortlist_context_id=context.id,
        shortlist_version_id=shortlist_version.id,
        created_at=datetime.now(UTC),
        notes=(
            "Comparison is a neutral trade-off view. No supplier was selected, approved, "
            "contacted, or ranked as a winner."
        ),
    )
    db.add(snapshot)
    db.flush()
    db.add(
        SupplierShortlistEvent(
            owner_id=owner.id,
            context_id=context.id,
            event_type="comparison_snapshot_created",
            event_key=f"pr8b:comparison:{snapshot.id}",
            payload={"comparison_id": str(snapshot.id), "status": status, "automatic_winner": None},
            created_at=datetime.now(UTC),
        )
    )
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.supplier_comparison_created",
        entity_type="supplier_comparison",
        entity_id=snapshot.id,
        metadata={"status": status, "supplier_count": len(resolved)},
        idempotency_key=f"pr8b:comparison:{snapshot.id}",
    )
    db.commit()
    db.refresh(snapshot)
    return _view(db, owner, snapshot)


def list_comparisons(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> list[dict[str, object]]:
    _owned_context(db, owner, opportunity_id, assessment_id)
    rows = list(
        db.scalars(
            select(SupplierComparisonSnapshot)
            .where(
                SupplierComparisonSnapshot.owner_id == owner.id,
                SupplierComparisonSnapshot.opportunity_id == opportunity_id,
                SupplierComparisonSnapshot.assessment_id == assessment_id,
            )
            .order_by(SupplierComparisonSnapshot.created_at, SupplierComparisonSnapshot.id)
        )
    )
    return [_view(db, owner, row) for row in rows]


def get_comparison(db: Session, owner: User, comparison_id: uuid.UUID) -> dict[str, object]:
    row = db.scalar(
        select(SupplierComparisonSnapshot).where(
            SupplierComparisonSnapshot.id == comparison_id,
            SupplierComparisonSnapshot.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Supplier comparison not found.")
    return _view(db, owner, row)


def _fresh_scope(db: Session, owner: User, snapshot: SupplierComparisonSnapshot) -> bool:
    reassessment_ids = [uuid.UUID(str(item)) for item in snapshot.reassessment_ids]
    rows, resolved, _ = _scope_rows(
        db, owner, snapshot.opportunity_id, snapshot.assessment_id, reassessment_ids
    )
    return _scope_fingerprint(rows, resolved) == snapshot.input_fingerprint


def shortlist_supplier(
    db: Session,
    owner: User,
    comparison_id: uuid.UUID,
    data: SupplierComparisonShortlistCreate,
) -> dict[str, object]:
    snapshot = db.scalar(
        select(SupplierComparisonSnapshot).where(
            SupplierComparisonSnapshot.id == comparison_id,
            SupplierComparisonSnapshot.owner_id == owner.id,
        )
    )
    if snapshot is None:
        raise HTTPException(404, "Supplier comparison not found.")
    if snapshot.shortlist_context_id is None or snapshot.shortlist_version_id is None:
        raise HTTPException(409, "The comparison has no canonical shortlist context.")
    if not _fresh_scope(db, owner, snapshot):
        raise HTTPException(
            409, "This comparison is stale; refresh the comparison before HUMAN shortlisting."
        )
    if str(data.canonical_supplier_id) not in {
        str(item) for item in snapshot.canonical_supplier_ids
    }:
        raise HTTPException(409, "Supplier is not part of this comparison snapshot.")
    context = db.get(SupplierShortlistContext, snapshot.shortlist_context_id)
    if context is None or context.owner_id != owner.id:
        raise HTTPException(
            409, "The comparison shortlist context is not available in this owner scope."
        )
    result = decide(
        db,
        owner,
        context,
        ShortlistDecisionRequest(
            shortlist_version_id=snapshot.shortlist_version_id,
            supplier_id=data.canonical_supplier_id,
            decision=data.decision,
            reason=data.reason,
            evidence_ids=data.evidence_ids,
            decision_key=data.decision_key,
            comparison_snapshot_id=snapshot.id,
        ),
    )
    result.update(
        {
            "comparison_id": snapshot.id,
            "canonical_supplier_id": data.canonical_supplier_id,
            "human_provenance": "HUMAN",
        }
    )
    return result
