"""PR-5C explainable unit economics built on PR-5A/PR-5B authorities."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.economic_calculation_models import EconomicCalculation
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
)
from vayujit_api.intelligence.product_opportunity_unit_economics_models import (
    CALCULATION_VERSION,
    ProductOpportunityUnitEconomics,
)
from vayujit_api.intelligence.product_opportunity_unit_economics_schemas import (
    SellingCostComponent,
    UnitEconomicsCalculateRequest,
)

MONEY_QUANTUM = Decimal("0.00000001")


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _money(value: Decimal | None) -> Decimal | None:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP) if value is not None else None


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_json(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _currency(value: object) -> str | None:
    normalized = str(value).upper() if value is not None else None
    return normalized if normalized and len(normalized) == 3 else None


def _fx_convert(
    amount: Decimal, source: str, target: str, fx: list[dict[str, object]]
) -> tuple[Decimal | None, str | None]:
    if source == target:
        return amount, None
    for row in fx:
        from_currency = _currency(row.get("from_currency"))
        to_currency = _currency(row.get("to_currency"))
        rate = _decimal(row.get("rate"))
        if rate is None or rate <= 0:
            continue
        if from_currency == source and to_currency == target:
            return amount * rate, None
        if from_currency == target and to_currency == source:
            return amount / rate, None
    return None, f"explicit_fx:{source}/{target}"


def _readiness_view(row: CommercialReadinessSnapshot | None) -> dict[str, object]:
    if row is None:
        return {
            "status": "NOT_READY",
            "id": None,
            "missing_inputs": ["commercial_readiness_snapshot"],
            "provenance": "UNKNOWN",
        }
    gate = (row.readiness or {}).get("calculations", {})
    return {
        "status": (row.readiness or {}).get("overall", "UNKNOWN"),
        "id": str(row.id),
        "calculations": gate,
        "missing_inputs": row.missing_inputs,
        "unknown_inputs": row.unknown_inputs,
        "optional_gaps": row.optional_gaps,
        "assumptions": row.assumptions,
        "claims": row.claims,
        "contradictions": row.contradictions,
        "lineage": row.lineage,
    }


def _latest_goal_capital(
    db: Session, owner: User, constraint: ProductOpportunityConstraintVersion
) -> dict[str, object]:
    goals = list(
        db.scalars(
            select(BusinessAgentGoal)
            .where(BusinessAgentGoal.owner_id == owner.id)
            .order_by(BusinessAgentGoal.updated_at.desc(), BusinessAgentGoal.created_at.desc())
        )
    )
    for goal in goals:
        commerce = (goal.structured_goal or {}).get("commerce_context")
        confirmed = bool((goal.provenance or {}).get("commerce_context_confirmed"))
        if not isinstance(commerce, dict) or not confirmed:
            continue
        amount = _decimal(commerce.get("budget_amount"))
        currency = _currency(commerce.get("currency"))
        if amount is not None and currency is not None:
            return {
                "value": amount,
                "currency": currency,
                "source": "BUSINESS_AGENT_GOAL",
                "goal_id": str(goal.id),
                "provenance": "USER_CONFIRMED",
            }
    amount = _decimal(constraint.available_capital)
    currency = _currency(constraint.currency)
    return {
        "value": amount,
        "currency": currency,
        "source": "PRODUCT_OPPORTUNITY_CONSTRAINT",
        "constraint_version_id": str(constraint.id),
        "provenance": "GOAL_CONSTRAINT_SNAPSHOT" if amount is not None else "UNKNOWN",
    }


def _blocked(
    *,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    readiness: dict[str, object],
    missing: list[str],
    limitations: list[str] | None = None,
    selling_price: Decimal | None = None,
    selling_currency: str | None = None,
    quantity: Decimal | None = None,
    input_snapshot: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "calculable": False,
        "id": None,
        "opportunity_id": str(opportunity_id),
        "assessment_id": str(assessment_id),
        "calculation_version": CALCULATION_VERSION,
        "readiness": readiness,
        "selling_price": _json(selling_price),
        "selling_price_currency": selling_currency,
        "selling_price_provenance": "UNKNOWN",
        "quantity": _json(quantity),
        "missing_inputs": list(dict.fromkeys(missing)),
        "unknown_excluded": [],
        "limitations": limitations or ["No unit-economics result was calculated."],
        "input_snapshot": _json(input_snapshot or {}),
        "safe_next_action": "Provide the missing evidence-backed or explicit scenario inputs.",
        "external_writes": [],
    }


def _component_view(
    component: SellingCostComponent,
    *,
    selling_price: Decimal,
    quantity: Decimal,
    base_currency: str,
    fx: list[dict[str, object]],
) -> tuple[dict[str, object], Decimal | None, str | None]:
    currency = _currency(component.currency) or base_currency
    amount = _decimal(component.amount)
    rate = _decimal(component.rate)
    if component.basis == "PERCENT_OF_SELLING_PRICE":
        if rate is None:
            return (
                {
                    "key": component.key,
                    "label": component.label or component.key,
                    "basis": component.basis,
                    "rate": None,
                    "amount": None,
                    "currency": currency,
                    "required": component.required,
                    "provenance": component.provenance,
                    "trust_state": component.trust_state,
                    "marker": component.marker,
                    "inclusion_status": "EXCLUDED",
                    "exclusion_reason": "UNKNOWN_AMOUNT",
                    "reason": component.reason,
                },
                None,
                None,
            )
        amount = selling_price * rate / Decimal("100")
        rate_basis = "SELLING_PRICE"
    else:
        rate_basis = None
        if amount is None:
            return (
                {
                    "key": component.key,
                    "label": component.label or component.key,
                    "basis": component.basis,
                    "rate": None,
                    "amount": None,
                    "currency": currency,
                    "required": component.required,
                    "provenance": component.provenance,
                    "trust_state": component.trust_state,
                    "marker": component.marker,
                    "inclusion_status": "EXCLUDED",
                    "exclusion_reason": "UNKNOWN_AMOUNT",
                    "reason": component.reason,
                },
                None,
                None,
            )
    converted, issue = _fx_convert(amount, currency, base_currency, fx)
    per_unit = converted
    if component.basis in {"PER_ORDER", "PER_SHIPMENT"} and converted is not None:
        per_unit = converted / quantity
    return (
        {
            "key": component.key,
            "label": component.label or component.key,
            "basis": component.basis,
            "rate": _money(rate),
            "rate_basis": rate_basis,
            "amount": _money(amount),
            "converted_amount": _money(converted),
            "per_unit_amount": _money(per_unit),
            "currency": currency,
            "required": component.required,
            "provenance": component.provenance,
            "trust_state": component.trust_state,
            "marker": component.marker,
            "source_reference": component.source_reference,
            "inclusion_status": "INCLUDED" if converted is not None else "EXCLUDED",
            "exclusion_reason": issue,
            "reason": component.reason,
        },
        per_unit,
        issue,
    )


def _view(row: ProductOpportunityUnitEconomics) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "opportunity_id": str(row.opportunity_id),
        "assessment_id": str(row.assessment_id),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "landed_cost_calculation_id": str(row.landed_cost_calculation_id),
        "commercial_readiness_snapshot_id": (
            str(row.commercial_readiness_snapshot_id)
            if row.commercial_readiness_snapshot_id
            else None
        ),
        "scenario_key": row.scenario_key,
        "calculation_version": row.calculation_version,
        "calculation_revision": row.calculation_revision,
        "status": row.status,
        "calculable": row.status == "READY",
        "input_fingerprint": row.input_fingerprint,
        "idempotency_key": row.idempotency_key,
        "input_snapshot": row.input_snapshot,
        "readiness": row.readiness,
        "selling_price": _json(row.selling_price),
        "selling_price_currency": row.selling_price_currency,
        "selling_price_provenance": row.selling_price_provenance,
        "base_currency": row.base_currency,
        "quantity": _json(row.quantity),
        "selling_cost_components": row.selling_cost_components,
        "per_unit_landed_cost": _json(row.per_unit_landed_cost),
        "per_unit_selling_cost": _json(row.per_unit_selling_cost),
        "per_unit_total_cost": _json(row.per_unit_total_cost),
        "per_unit_contribution": _json(row.per_unit_contribution),
        "contribution_margin": _json(row.contribution_margin),
        "order_economics": row.order_economics,
        "capital_available": _json(row.capital_available),
        "capital_currency": row.capital_currency,
        "capital_required": _json(row.capital_required),
        "capital_headroom": _json(row.capital_headroom),
        "capital_shortfall": _json(row.capital_shortfall),
        "capital_fit_status": row.capital_fit_status,
        "unknown_excluded": row.unknown_excluded,
        "contradictions": row.contradictions,
        "limitations": row.limitations,
        "explanation": row.explanation,
        "created_at": row.created_at.isoformat(),
        "notes": row.notes,
        "external_writes": [],
    }


def calculate_unit_economics(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: UnitEconomicsCalculateRequest,
) -> dict[str, object]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    assessment = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.owner_id == owner.id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
        )
    )
    if opportunity is None or assessment is None:
        raise HTTPException(404, "Product opportunity assessment not found.")
    constraint = db.scalar(
        select(ProductOpportunityConstraintVersion).where(
            ProductOpportunityConstraintVersion.id == assessment.constraint_version_id,
            ProductOpportunityConstraintVersion.owner_id == owner.id,
            ProductOpportunityConstraintVersion.opportunity_id == opportunity_id,
        )
    )
    if constraint is None:
        raise HTTPException(409, "Product opportunity constraint is not available.")
    readiness = db.scalar(
        select(CommercialReadinessSnapshot)
        .where(
            CommercialReadinessSnapshot.owner_id == owner.id,
            CommercialReadinessSnapshot.opportunity_id == opportunity_id,
            CommercialReadinessSnapshot.assessment_id == assessment_id,
        )
        .order_by(CommercialReadinessSnapshot.created_at.desc())
    )
    landed_query = select(EconomicCalculation).where(
        EconomicCalculation.owner_id == owner.id,
        EconomicCalculation.product_opportunity_id == opportunity_id,
        EconomicCalculation.assessment_id == assessment_id,
    )
    if request.landed_cost_calculation_id is not None:
        landed_query = landed_query.where(
            EconomicCalculation.id == request.landed_cost_calculation_id
        )
    landed = db.scalar(landed_query.order_by(EconomicCalculation.created_at.desc()))
    readiness_view = _readiness_view(readiness)
    quantity = request.quantity or (_decimal(landed.target_quantity) if landed else None)
    selling_currency = _currency(request.selling_price_currency)
    base_currency = _currency(landed.currency) if landed else None
    input_snapshot = {
        "request": request.model_dump(mode="json"),
        "opportunity_id": str(opportunity_id),
        "assessment_id": str(assessment_id),
        "landed_cost_calculation_id": str(landed.id) if landed else None,
        "commercial_readiness_snapshot_id": str(readiness.id) if readiness else None,
    }
    missing: list[str] = []
    if landed is None:
        missing.append("landed_cost_calculation")
    elif landed.per_unit_cost is None or landed.status not in {"COMPLETE", "PARTIAL"}:
        missing.append("landed_cost_per_unit")
    if request.selling_price is None:
        missing.append("selling_price")
    elif request.selling_price <= 0:
        missing.append("selling_price_positive")
    if selling_currency is None:
        missing.append("selling_price_currency")
    if quantity is None or quantity <= 0:
        missing.append("quantity")
    if base_currency is None:
        missing.append("landed_cost_currency")
    components = request.selling_cost_components
    if not components:
        missing.append("required_selling_cost_components")
    for component in components:
        if component.required and (
            (component.basis == "PERCENT_OF_SELLING_PRICE" and component.rate is None)
            or (component.basis != "PERCENT_OF_SELLING_PRICE" and component.amount is None)
        ):
            missing.append(f"selling_cost:{component.key}")
    capital = _latest_goal_capital(db, owner, constraint)
    if capital["value"] is None:
        missing.append("available_capital")
    if capital["currency"] is None:
        missing.append("capital_currency")
    if missing:
        return _blocked(
            opportunity_id=opportunity_id,
            assessment_id=assessment_id,
            readiness=readiness_view,
            missing=missing,
            selling_price=request.selling_price,
            selling_currency=selling_currency,
            quantity=quantity,
            input_snapshot=input_snapshot,
        )
    assert landed is not None
    assert landed.per_unit_cost is not None
    assert quantity is not None
    assert selling_currency is not None
    assert base_currency is not None
    assert request.selling_price is not None
    fx_rows = [item.model_dump(mode="json") for item in request.fx]
    selling_price_base, fx_issue = _fx_convert(
        request.selling_price, selling_currency, base_currency, fx_rows
    )
    if selling_price_base is None:
        return _blocked(
            opportunity_id=opportunity_id,
            assessment_id=assessment_id,
            readiness=readiness_view,
            missing=[fx_issue or "selling_price_currency_comparability"],
            selling_price=request.selling_price,
            selling_currency=selling_currency,
            quantity=quantity,
            input_snapshot=input_snapshot,
        )
    landed_unit = _money(_decimal(landed.per_unit_cost))
    assert landed_unit is not None
    selling_lines: list[dict[str, object]] = []
    selling_per_unit = Decimal("0")
    unknown_excluded: list[dict[str, object]] = []
    for component in components:
        line, per_unit, issue = _component_view(
            component,
            selling_price=request.selling_price,
            quantity=quantity,
            base_currency=base_currency,
            fx=fx_rows,
        )
        selling_lines.append(line)
        if per_unit is not None and issue is None:
            selling_per_unit += per_unit
        else:
            unknown_excluded.append(
                {
                    "key": component.key,
                    "label": component.label or component.key,
                    "required": component.required,
                    "reason": issue or "UNKNOWN_AMOUNT",
                    "status": "EXCLUDED_UNKNOWN",
                    "provenance": component.provenance,
                }
            )
    for key, label in (
        ("tax", "Tax/GST treatment"),
        ("returns", "Returns impact"),
        ("advertising", "Advertising spend"),
        ("storage", "Storage duration/cost"),
        ("overhead", "Overhead and operating costs"),
    ):
        unknown_excluded.append(
            {
                "key": key,
                "label": label,
                "status": "UNKNOWN_EXCLUDED",
                "reason": "No explicit canonical input was supplied; not treated as zero.",
            }
        )
    if any(item.get("exclusion_reason") and item.get("required") for item in selling_lines):
        return _blocked(
            opportunity_id=opportunity_id,
            assessment_id=assessment_id,
            readiness=readiness_view,
            missing=[
                str(item["exclusion_reason"])
                for item in selling_lines
                if item.get("exclusion_reason") and item.get("required")
            ],
            limitations=[
                "A required selling-cost component could not be converted into the base currency."
            ],
            selling_price=request.selling_price,
            selling_currency=selling_currency,
            quantity=quantity,
            input_snapshot=input_snapshot,
        )
    selling_per_unit = cast(Decimal, _money(selling_per_unit))
    landed_total = cast(Decimal, _money(landed_unit * quantity))
    selling_total = cast(Decimal, _money(selling_per_unit * quantity))
    total_unit = cast(Decimal, _money(landed_unit + selling_per_unit))
    contribution = cast(Decimal, _money(selling_price_base - total_unit))
    margin = _money(contribution / selling_price_base) if selling_price_base > 0 else None
    capital_amount = _decimal(capital["value"])
    capital_currency = _currency(capital["currency"])
    assert capital_amount is not None and capital_currency is not None
    capital_base, capital_fx_issue = _fx_convert(
        capital_amount, capital_currency, base_currency, fx_rows
    )
    if capital_base is None:
        return _blocked(
            opportunity_id=opportunity_id,
            assessment_id=assessment_id,
            readiness=readiness_view,
            missing=[capital_fx_issue or "capital_currency_comparability"],
            limitations=["Available capital and required capital need an explicit FX authority."],
            selling_price=request.selling_price,
            selling_currency=selling_currency,
            quantity=quantity,
            input_snapshot=input_snapshot,
        )
    capital_required = landed_total
    headroom = cast(Decimal, _money(capital_base - capital_required))
    fit_status = "FITS" if headroom is not None and headroom >= 0 else "DOES_NOT_FIT"
    shortfall = _money(-headroom) if headroom is not None and headroom < 0 else None
    snapshot = {
        **input_snapshot,
        "landed_cost_fingerprint": landed.calculation_fingerprint,
        "landed_cost_version": landed.calculation_version,
        "landed_cost_policy": landed.policy_version,
        "base_currency": base_currency,
        "capital": capital,
        "fx": fx_rows,
    }
    fingerprint = _fingerprint(snapshot)
    existing = db.scalar(
        select(ProductOpportunityUnitEconomics).where(
            ProductOpportunityUnitEconomics.owner_id == owner.id,
            ProductOpportunityUnitEconomics.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        result = _view(existing)
        result["idempotent_reuse"] = True
        return result
    result_row = ProductOpportunityUnitEconomics(
        owner_id=owner.id,
        opportunity_id=opportunity_id,
        assessment_id=assessment_id,
        supplier_id=request.supplier_id or landed.supplier_id,
        landed_cost_calculation_id=landed.id,
        commercial_readiness_snapshot_id=readiness.id if readiness else None,
        scenario_key=request.scenario_key,
        calculation_version=request.calculation_version,
        calculation_revision=1,
        status="READY",
        input_fingerprint=fingerprint,
        idempotency_key=request.idempotency_key,
        input_snapshot=_json(snapshot),
        readiness=readiness_view,
        selling_price=_money(request.selling_price),
        selling_price_currency=selling_currency,
        selling_price_provenance=request.selling_price_provenance,
        base_currency=base_currency,
        quantity=_money(quantity),
        selling_cost_components=_json(selling_lines),
        per_unit_landed_cost=landed_unit,
        per_unit_selling_cost=selling_per_unit,
        per_unit_total_cost=total_unit,
        per_unit_contribution=contribution,
        contribution_margin=margin,
        order_economics=_json(
            {
                "order_quantity": quantity,
                "sales_quantity": None,
                "sales_claim": "NOT_INFERRED",
                "landed_acquisition_total": landed_total,
                "modeled_selling_cost_total": selling_total,
                "modeled_total_cost": cast(Decimal, _money(landed_total + selling_total)),
                "modeled_contribution_total_if_all_ordered_units_sell": cast(
                    Decimal, _money(contribution * quantity)
                ),
                "currency": base_currency,
            }
        ),
        capital_available=_money(capital_base),
        capital_currency=base_currency,
        capital_required=capital_required,
        capital_headroom=headroom if fit_status == "FITS" else None,
        capital_shortfall=shortfall,
        capital_fit_status=fit_status,
        unknown_excluded=_json(unknown_excluded),
        contradictions=_json(readiness.contradictions if readiness else []),
        limitations=_json(
            [
                (
                    "Capital required means upfront landed acquisition funding only; "
                    "future selling costs are shown separately."
                ),
                (
                    "Unknown tax, returns, advertising, storage, overhead, and other "
                    "excluded costs are not zero."
                ),
                "Contribution is modeled contribution, not net profit or a recommendation.",
                "Order quantity is not a sales-velocity or sell-through claim.",
                "No automatic safety buffer is applied.",
            ]
        ),
        explanation=_json(
            {
                "formula": (
                    "selling price - landed acquisition cost/unit - " "included selling costs/unit"
                ),
                "selling_price_in_base_currency": selling_price_base,
                "capital_source": capital,
                "capital_fit_formula": "available capital - upfront landed acquisition funding",
                "assumptions": [
                    line.get("key")
                    for line in selling_lines
                    if line.get("provenance")
                    in {"ASSUMED", "DETERMINISTIC_TEST", "SELLER_SCENARIO"}
                ],
            }
        ),
        notes=(
            "PR-5C modeled unit economics; not profitability, recommendation, "
            "or launch approval."
        ),
    )
    db.add(result_row)
    db.commit()
    db.refresh(result_row)
    view = _view(result_row)
    view["idempotent_reuse"] = False
    return view


def latest_unit_economics(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> dict[str, object] | None:
    row = db.scalar(
        select(ProductOpportunityUnitEconomics)
        .where(
            ProductOpportunityUnitEconomics.owner_id == owner.id,
            ProductOpportunityUnitEconomics.opportunity_id == opportunity_id,
            ProductOpportunityUnitEconomics.assessment_id == assessment_id,
        )
        .order_by(ProductOpportunityUnitEconomics.created_at.desc())
    )
    return _view(row) if row is not None else None


def unit_economics_history(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(ProductOpportunityUnitEconomics)
            .where(
                ProductOpportunityUnitEconomics.owner_id == owner.id,
                ProductOpportunityUnitEconomics.opportunity_id == opportunity_id,
                ProductOpportunityUnitEconomics.assessment_id == assessment_id,
            )
            .order_by(ProductOpportunityUnitEconomics.created_at)
        )
    )
    return [_view(row) for row in rows]
