"""PR-5B readiness-gated explainable landed-cost orchestration.

This adapter reuses PR-5A commercial readiness and the existing 13A/13B
immutable snapshot/calculation authorities. It never turns unknown inputs into
zero and never performs an external write.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.economic_calculation_models import EconomicCalculation
from vayujit_api.intelligence.economic_calculation_service import (
    PR5B_CALCULATION_VERSION,
    PR5B_POLICY_VERSION,
    calculate_from_snapshot,
    list_breakdown,
)
from vayujit_api.intelligence.economic_fx_models import FXRateSnapshot
from vayujit_api.intelligence.economic_schemas import (
    EconomicAssumptionCreate,
    EconomicCalculationRequest,
    EconomicContextCreate,
    EconomicCostComponentCreate,
    EconomicQuoteInputCreate,
)
from vayujit_api.intelligence.economic_service import (
    create_assumption,
    create_component,
    create_context,
    create_quote,
    create_snapshot,
)
from vayujit_api.intelligence.landed_cost_schemas import LandedCostCalculateRequest
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)

REQUIRED = (
    "supplier_unit_price",
    "supplier_currency",
    "freight_cost",
    "freight_currency",
    "origin",
    "destination",
)
UNKNOWN_COMPONENTS = (
    ("PACKAGING", "Packaging"),
    ("INSURANCE", "Insurance"),
    ("CUSTOMS_DUTY", "Customs duty"),
    ("IMPORT_TAX", "Import tax (treatment not established)"),
    ("BROKERAGE", "Brokerage"),
    ("PORT_HANDLING", "Port handling"),
    ("LOCAL_TRANSPORT", "Local transport"),
    ("WAREHOUSING", "Warehousing"),
    ("FULFILMENT", "Fulfilment / marketplace costs (outside PR-5B)"),
    ("MARKETPLACE_FEE", "Marketplace fee (outside PR-5B)"),
)
PROVENANCE = {"OBSERVED", "QUOTED", "CONFIGURED", "ASSUMED", "CALCULATED", "UNKNOWN"}


def _json(value: object) -> object:
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _record(records: Sequence[object], key: str) -> dict[str, object] | None:
    for value in records:
        if isinstance(value, dict) and value.get("key") == key and value.get("value") is not None:
            return value
    return None


def _effective(readiness: CommercialReadinessSnapshot, key: str) -> dict[str, object] | None:
    known = [row for row in (readiness.known_inputs or []) if isinstance(row, dict)]
    source = _record(known, key)
    if source is not None:
        return source
    assumptions = [row for row in (readiness.assumptions or []) if isinstance(row, dict)]
    return _record(assumptions, key)


def _text(value: object) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None else None
    except Exception:
        return None


def _basis(value: object, *, freight: bool = False) -> str | None:
    normalized = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {
        "UNIT": "PER_UNIT",
        "EACH": "PER_UNIT",
        "ITEM": "PER_UNIT",
        "PER_ITEM": "PER_UNIT",
        "SHIPMENT": "PER_SHIPMENT",
        "FIXED_QUOTE": "ONE_TIME",
        "FIXED": "ONE_TIME",
        "TOTAL": "ONE_TIME",
    }
    if normalized in {"PER_UNIT", "PER_SHIPMENT", "ONE_TIME"}:
        return normalized
    if freight and normalized in {"PER_CARTON", "PER_KG", "PER_CBM", "PER_CONTAINER"}:
        return None
    return aliases.get(normalized)


def _source_ref(record: dict[str, object] | None) -> uuid.UUID | None:
    if not record:
        return None
    refs = record.get("source_references")
    if not isinstance(refs, list):
        return None
    for item in refs:
        if isinstance(item, dict) and item.get("id"):
            try:
                return uuid.UUID(str(item["id"]))
            except (TypeError, ValueError):
                continue
    return None


def _provenance(record: dict[str, object]) -> str:
    value = str(record.get("provenance") or "UNKNOWN").upper()
    if value == "SOURCE_PROVIDED_CLAIM":
        return value
    return value if value in PROVENANCE else "UNKNOWN"


def _freshness(record: dict[str, object]) -> str:
    """Map supplier-evidence freshness vocabulary to PR-5B's database enum."""
    value = str(record.get("freshness") or "UNKNOWN").upper()
    if value == "FRESH":
        return "CURRENT"
    return value if value in {"CURRENT", "STALE", "UNKNOWN"} else "UNKNOWN"


def _trust_metadata(record: dict[str, object]) -> dict[str, object]:
    return {
        "commercial_readiness_provenance": record.get("provenance"),
        "trust_state": record.get("trust_state"),
        "marker": record.get("marker"),
        "source_references": record.get("source_references", []),
    }


def _readiness_payload(row: CommercialReadinessSnapshot) -> dict[str, object]:
    return {
        "id": str(row.id),
        "readiness": row.readiness,
        "known_inputs": row.known_inputs,
        "claims": row.claims,
        "assumptions": row.assumptions,
        "unknown_inputs": row.unknown_inputs,
        "missing_inputs": row.missing_inputs,
        "optional_gaps": row.optional_gaps,
        "contradictions": row.contradictions,
        "lineage": row.lineage,
    }


def _blocked(
    row: CommercialReadinessSnapshot, missing: list[str], reason: str
) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "calculable": False,
        "readiness": _readiness_payload(row),
        "calculation": None,
        "breakdown": [],
        "missing_inputs": list(dict.fromkeys(missing)),
        "safe_next_action": reason,
        "limitations": ["No landed acquisition cost was calculated."],
        "external_writes": [],
    }


def _calculation_view(db: Session, owner: User, row: EconomicCalculation) -> dict[str, object]:
    return {
        "id": str(row.id),
        "product_opportunity_id": (
            str(row.product_opportunity_id) if row.product_opportunity_id else None
        ),
        "assessment_id": str(row.assessment_id) if row.assessment_id else None,
        "commercial_readiness_snapshot_id": (
            str(row.commercial_readiness_snapshot_id)
            if row.commercial_readiness_snapshot_id
            else None
        ),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "scenario_key": row.scenario_key,
        "context_id": str(row.context_id),
        "snapshot_id": str(row.snapshot_id),
        "calculation_version": row.calculation_version,
        "policy_version": row.policy_version,
        "status": row.status,
        "currency": row.currency,
        "reporting_currency": row.reporting_currency,
        "target_quantity": _json(row.target_quantity),
        "total_included_cost": _json(row.total_included_cost),
        "per_unit_cost": _json(row.per_unit_cost),
        "included_component_count": row.included_component_count,
        "excluded_component_count": row.excluded_component_count,
        "missing_inputs": row.missing_inputs,
        "warnings": row.warnings,
        "assumptions": row.assumptions,
        "stale_inputs": row.stale_inputs,
        "explanation": row.explanation,
        "created_at": row.created_at.isoformat(),
        "breakdown": [
            {
                "id": str(item.id),
                "source_kind": item.source_kind,
                "source_id": str(item.source_id) if item.source_id else None,
                "category": item.category,
                "original_amount": _json(item.original_amount),
                "currency": item.currency,
                "basis": item.basis,
                "multiplier": _json(item.multiplier),
                "included_amount": _json(item.included_amount),
                "converted_amount": _json(item.converted_amount),
                "provenance": item.provenance,
                "freshness": item.freshness,
                "assumption_reason": item.assumption_reason,
                "evidence_ref": str(item.evidence_ref) if item.evidence_ref else None,
                "inclusion_status": item.inclusion_status,
                "exclusion_reason": item.exclusion_reason,
                "lineage": item.lineage,
                "line_order": item.line_order,
            }
            for item in list_breakdown(db, owner, row.id)
        ],
    }


def _latest_calculation(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> EconomicCalculation | None:
    return db.scalar(
        select(EconomicCalculation)
        .where(
            EconomicCalculation.owner_id == owner.id,
            EconomicCalculation.product_opportunity_id == opportunity_id,
            EconomicCalculation.assessment_id == assessment_id,
        )
        .order_by(EconomicCalculation.created_at.desc())
    )


def calculate_landed_cost(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: LandedCostCalculateRequest,
) -> dict[str, object]:
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
    readiness = db.scalar(
        select(CommercialReadinessSnapshot)
        .where(
            CommercialReadinessSnapshot.owner_id == owner.id,
            CommercialReadinessSnapshot.opportunity_id == opportunity_id,
            CommercialReadinessSnapshot.assessment_id == assessment_id,
        )
        .order_by(CommercialReadinessSnapshot.created_at.desc())
    )
    if (
        data.calculation_version != PR5B_CALCULATION_VERSION
        or data.policy_version != PR5B_POLICY_VERSION
    ):
        raise HTTPException(
            422, "PR-5B requires the readiness-gated calculation and policy versions."
        )
    if readiness is None:
        raise HTTPException(409, "Project commercial readiness before calculating landed cost.")

    gate = (readiness.readiness or {}).get("calculations", {})
    landed_gate = gate.get("LANDED_UNIT_COST") if isinstance(gate, dict) else None
    missing = (
        list(landed_gate.get("missing_inputs", []))
        if isinstance(landed_gate, dict)
        else list(REQUIRED)
    )
    if isinstance(landed_gate, dict) and landed_gate.get("status") != "READY":
        return _blocked(
            readiness,
            missing,
            str(
                (readiness.readiness or {}).get("safe_next_action")
                or "Obtain the missing landed-cost inputs."
            ),
        )
    if readiness.contradictions:
        return _blocked(
            readiness,
            ["unresolved_commercial_contradiction"],
            "Resolve the commercial contradiction before calculating.",
        )

    effective = {key: _effective(readiness, key) for key in REQUIRED}
    missing = [key for key, value in effective.items() if value is None]
    if missing:
        return _blocked(
            readiness,
            missing,
            "Provide every required landed-cost input with its basis and provenance.",
        )
    price = effective["supplier_unit_price"]
    supplier_currency_record = effective["supplier_currency"]
    freight = effective["freight_cost"]
    freight_currency_record = effective["freight_currency"]
    origin_record = effective["origin"]
    destination_record = effective["destination"]
    assert price is not None
    assert supplier_currency_record is not None
    assert freight is not None
    assert freight_currency_record is not None
    assert origin_record is not None
    assert destination_record is not None
    price_currency = _text(supplier_currency_record.get("value"))
    freight_currency = _text(freight_currency_record.get("value"))
    origin = _text(origin_record.get("value"))
    destination = _text(destination_record.get("value"))
    price_basis = _basis(price.get("price_basis") or price.get("unit")) if price else None
    freight_basis = _basis(freight.get("unit") if freight else None, freight=True)
    if price_basis is None:
        return _blocked(
            readiness,
            ["supplier_price_basis"],
            "Specify whether supplier price is per unit, shipment, or one-time.",
        )
    if freight_basis is None:
        return _blocked(
            readiness, ["freight_basis"], "Specify a supported freight basis before calculating."
        )
    moq_record = _effective(readiness, "supplier_moq")
    moq = _decimal(moq_record.get("value") if moq_record else None)
    if moq is not None and data.target_quantity < moq:
        return _blocked(
            readiness,
            ["target_quantity_below_moq"],
            f"Choose an order quantity of at least the known MOQ ({moq}). "
            "The quantity was not changed automatically.",
        )

    source_currencies = {value for value in (price_currency, freight_currency) if value}
    fx = None
    if data.fx_snapshot_id is not None:
        fx = db.scalar(
            select(FXRateSnapshot).where(
                FXRateSnapshot.id == data.fx_snapshot_id, FXRateSnapshot.owner_id == owner.id
            )
        )
        if fx is None:
            raise HTTPException(404, "FX snapshot is not available in the owner scope.")
    for source_currency in source_currencies:
        if source_currency != data.base_currency and (
            fx is None
            or not (fx.base_currency == source_currency and fx.quote_currency == data.base_currency)
        ):
            return _blocked(
                readiness,
                [f"explicit_fx:{source_currency}/{data.base_currency}"],
                "Provide an explicit owner-scoped FX snapshot for every cross-currency component.",
            )

    scenario_key = readiness.scenario_key
    request_material = data.model_dump(mode="json")
    context_key = (
        "pr5b:"
        + hashlib.sha256(
            json.dumps(
                {
                    "opportunity": str(opportunity_id),
                    "assessment": str(assessment_id),
                    "readiness": str(readiness.id),
                    "request": request_material,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
    )
    context, _ = create_context(
        db,
        owner,
        EconomicContextCreate(
            idempotency_key=context_key,
            supplier_id=readiness.supplier_id,
            source_marketplace=opportunity.target_marketplace,
            origin_country=origin,
            destination_country=destination,
            target_channel=opportunity.target_marketplace,
            target_quantity=data.target_quantity,
            quantity_unit=data.quantity_unit,
            base_currency=data.base_currency,
        ),
    )

    # The context idempotency key is scoped to the complete PR-5B request and
    # readiness snapshot. Reuse the immutable calculation before appending
    # another assumption/snapshot version on an exact replay.
    existing_calculation = db.scalar(
        select(EconomicCalculation)
        .where(
            EconomicCalculation.owner_id == owner.id,
            EconomicCalculation.context_id == context.id,
            EconomicCalculation.calculation_version == data.calculation_version,
            EconomicCalculation.policy_version == data.policy_version,
        )
        .order_by(EconomicCalculation.created_at.desc())
    )
    if existing_calculation is not None:
        view = _calculation_view(db, owner, existing_calculation)
        return {
            "status": "CALCULATED" if existing_calculation.per_unit_cost is not None else "PARTIAL",
            "calculable": existing_calculation.per_unit_cost is not None,
            "readiness": _readiness_payload(readiness),
            "calculation": view,
            "breakdown": view["breakdown"],
            "missing_inputs": existing_calculation.missing_inputs,
            "safe_next_action": (
                "Review the immutable landed-cost breakdown and assumptions "
                "before any human decision."
            ),
            "limitations": [
                "Unknown optional acquisition components are excluded, not zero.",
                "Tax treatment and marketplace selling fees are outside PR-5B.",
                (
                    "A calculable result is not profitability, approval, supplier verification, "
                    "or a recommendation."
                ),
            ],
            "idempotent_reuse": True,
            "external_writes": [],
        }

    price_provenance = _provenance(price or {})
    if price_provenance == "SOURCE_PROVIDED_CLAIM":
        price_provenance = "QUOTED"
    if price_provenance not in PROVENANCE:
        price_provenance = "UNKNOWN"
    price_evidence = _source_ref(price)
    if price_evidence is None and price_provenance == "QUOTED":
        return _blocked(
            readiness,
            ["supplier_unit_price_evidence"],
            "Retain an evidence reference for the supplier price claim.",
        )
    quote, _ = create_quote(
        db,
        owner,
        EconomicQuoteInputCreate(
            context_id=context.id,
            idempotency_key=f"{context_key}:quote",
            supplier_id=readiness.supplier_id,
            unit_price=_decimal(price.get("value")) if price else None,
            currency=price_currency,
            unit_basis=price_basis,
            moq=moq,
            moq_unit=_text(moq_record.get("unit")) if moq_record else None,
            provenance=price_provenance,
            freshness=_freshness(price),
            evidence_ref=price_evidence,
            assumption_reason=str(price.get("reason")) if price_provenance == "ASSUMED" else None,
            notes="PR-5B supplier acquisition-cost input; source claims remain claims.",
            metadata_json=_trust_metadata(price or {}),
        ),
    )

    freight_provenance = _provenance(freight or {})
    if freight_provenance == "SOURCE_PROVIDED_CLAIM":
        freight_provenance = "QUOTED"
    if freight_provenance == "QUOTED" and _source_ref(freight) is None:
        freight_provenance = "CONFIGURED"
    freight_component, _ = create_component(
        db,
        owner,
        EconomicCostComponentCreate(
            context_id=context.id,
            category="FREIGHT",
            amount=_decimal(freight.get("value")) if freight else None,
            currency=freight_currency,
            unit_basis=freight_basis,
            provenance=freight_provenance,
            freshness=_freshness(freight),
            evidence_ref=_source_ref(freight),
            assumption_reason=(
                str(freight.get("reason")) if freight_provenance == "ASSUMED" else None
            ),
            notes="PR-5B freight acquisition-cost input; basis is retained.",
            metadata_json=_trust_metadata(freight or {}),
        ),
    )
    for category, label in UNKNOWN_COMPONENTS:
        create_component(
            db,
            owner,
            EconomicCostComponentCreate(
                context_id=context.id,
                category=category,
                amount=None,
                provenance="UNKNOWN",
                unit_basis="ONE_TIME",
                notes=f"{label} is unknown or outside PR-5B and is not included as zero.",
                metadata_json={"pr5b_status": "EXCLUDED_UNKNOWN"},
            ),
        )
    for record in readiness.assumptions or []:
        if isinstance(record, dict) and record.get("key"):
            create_assumption(
                db,
                owner,
                EconomicAssumptionCreate(
                    context_id=context.id,
                    key=str(record["key"]),
                    value={
                        "value": _json(record.get("value")),
                        "unit": record.get("unit"),
                        "currency": record.get("currency"),
                        "provenance": "ASSUMED",
                        "marker": record.get("marker", "DETERMINISTIC_TEST"),
                    },
                    reason=str(record.get("reason") or "Explicit PR-5A scenario assumption."),
                    freshness="UNKNOWN",
                ),
            )

    snapshot, _ = create_snapshot(db, owner, context.id)
    calc_request = EconomicCalculationRequest(
        fx_snapshot_id=data.fx_snapshot_id,
        calculation_version=data.calculation_version or PR5B_CALCULATION_VERSION,
        policy_version=data.policy_version or PR5B_POLICY_VERSION,
        options=data.options,
    )
    calculation, reused = calculate_from_snapshot(
        db,
        owner,
        snapshot.id,
        calc_request,
        scope={
            "product_opportunity_id": opportunity.id,
            "assessment_id": assessment.id,
            "commercial_readiness_snapshot_id": readiness.id,
            "supplier_id": readiness.supplier_id,
            "scenario_key": scenario_key,
        },
    )
    return {
        "status": "CALCULATED" if calculation.per_unit_cost is not None else "PARTIAL",
        "calculable": calculation.per_unit_cost is not None,
        "readiness": _readiness_payload(readiness),
        "calculation": _calculation_view(db, owner, calculation),
        "breakdown": _calculation_view(db, owner, calculation)["breakdown"],
        "missing_inputs": calculation.missing_inputs,
        "safe_next_action": (
            "Review the immutable landed-cost breakdown and assumptions "
            "before any human decision."
        ),
        "limitations": [
            "Unknown optional acquisition components are excluded, not zero.",
            "Tax treatment and marketplace selling fees are outside PR-5B.",
            (
                "A calculable result is not profitability, approval, supplier verification, "
                "or a recommendation."
            ),
        ],
        "idempotent_reuse": reused,
        "external_writes": [],
    }


def get_landed_cost(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> dict[str, object]:
    readiness = db.scalar(
        select(CommercialReadinessSnapshot)
        .where(
            CommercialReadinessSnapshot.owner_id == owner.id,
            CommercialReadinessSnapshot.opportunity_id == opportunity_id,
            CommercialReadinessSnapshot.assessment_id == assessment_id,
        )
        .order_by(CommercialReadinessSnapshot.created_at.desc())
    )
    if readiness is None:
        raise HTTPException(404, "Commercial evidence readiness has not been projected.")
    row = _latest_calculation(db, owner, opportunity_id, assessment_id)
    if row is None:
        return _blocked(
            readiness,
            [],
            "Review PR-5A commercial readiness and provide the required landed-cost inputs.",
        )
    view = _calculation_view(db, owner, row)
    return {
        "status": "CALCULATED" if row.per_unit_cost is not None else "PARTIAL",
        "calculable": row.per_unit_cost is not None,
        "readiness": _readiness_payload(readiness),
        "calculation": view,
        "breakdown": view["breakdown"],
        "missing_inputs": row.missing_inputs,
        "safe_next_action": (
            "Review the immutable landed-cost breakdown and assumptions "
            "before any human decision."
        ),
        "limitations": ["Unknown optional components are excluded, not zero."],
        "external_writes": [],
    }
