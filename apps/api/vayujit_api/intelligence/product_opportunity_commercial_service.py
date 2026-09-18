"""Deterministic assessment-bound commercial viability projections."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.commerce.models import MarketplaceFee, MarketplaceListing, MarketplacePrice
from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_commercial_models import (
    CALCULATION_VERSION,
    ProductOpportunityCommercialOutput,
    commercial_now,
)
from vayujit_api.intelligence.product_opportunity_commercial_schemas import (
    CommercialCalculateRequest,
)
from vayujit_api.intelligence.product_opportunity_intelligence_service import (
    _freshness,
    _price_groups,
)
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
)
from vayujit_api.intelligence.scenario_models import SourcingScenarioVersion
from vayujit_api.intelligence.sourcing_models import CostScenario, LandedCostEstimate, SupplierQuote
from vayujit_api.intelligence.supplier_models import SupplierProduct

FRESHNESS_WINDOWS = ((timedelta(days=30), "fresh"), (timedelta(days=90), "aging"))
PRICE_DELTAS = (Decimal("-0.10"), Decimal("-0.05"), Decimal("0"), Decimal("0.05"), Decimal("0.10"))
COST_DELTAS = (Decimal("0"), Decimal("0.05"), Decimal("0.10"), Decimal("0.20"))


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _json(value: Any) -> Any:
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    return value


def _dimension(
    name: str,
    *,
    value: Any,
    classification: str,
    evidence_state: str,
    explanation: str,
    supporting: list[dict[str, Any]],
    missing: list[str],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dimension": name,
        "value": value,
        "classification": classification,
        "evidence_state": evidence_state,
        "explanation": explanation,
        "supporting_evidence": supporting,
        "missing_evidence": missing,
        "freshness": freshness,
        "calculation_version": CALCULATION_VERSION,
    }


def _context(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
    list[MarketplaceListing],
]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id,
            ProductOpportunity.owner_id == owner.id,
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
        raise LookupError("Product opportunity assessment not found.")
    constraint = db.scalar(
        select(ProductOpportunityConstraintVersion).where(
            ProductOpportunityConstraintVersion.id == assessment.constraint_version_id,
            ProductOpportunityConstraintVersion.owner_id == owner.id,
            ProductOpportunityConstraintVersion.opportunity_id == opportunity_id,
        )
    )
    if constraint is None:
        raise LookupError("Product opportunity constraint not found.")
    listings: list[MarketplaceListing] = []
    if opportunity.product_id is not None:
        listings = list(
            db.scalars(
                select(MarketplaceListing)
                .where(
                    MarketplaceListing.owner_id == owner.id,
                    MarketplaceListing.product_id == opportunity.product_id,
                    MarketplaceListing.status.not_in(("archived", "rejected")),
                )
                .order_by(MarketplaceListing.updated_at.desc())
                .limit(200)
            )
        )
    return opportunity, assessment, constraint, listings


def _prices(db: Session, owner: User, listings: list[MarketplaceListing]) -> list[MarketplacePrice]:
    if not listings:
        return []
    return list(
        db.scalars(
            select(MarketplacePrice).where(
                MarketplacePrice.owner_id == owner.id,
                MarketplacePrice.listing_id.in_([row.id for row in listings]),
                MarketplacePrice.effective_to.is_(None),
            )
        )
    )


def _fees(db: Session, owner: User, listings: list[MarketplaceListing]) -> list[MarketplaceFee]:
    if not listings:
        return []
    return list(
        db.scalars(
            select(MarketplaceFee).where(
                MarketplaceFee.owner_id == owner.id,
                MarketplaceFee.account_id.in_({row.account_id for row in listings}),
            )
        )
    )


def _price_summary(
    prices: list[MarketplacePrice], now: datetime
) -> tuple[dict[str, Any], dict[str, Any]]:
    groups = _price_groups(prices, now)
    refs = [
        {
            "type": "marketplace_price",
            "id": str(row.id),
            "currency": row.currency,
            "amount": str(row.amount),
            "observed_at": row.effective_from.isoformat(),
        }
        for row in prices[:100]
    ]
    return groups, {
        "type": "marketplace_prices",
        "ids": [str(row.id) for row in prices],
        "references": refs,
    }


def _fee_summary(
    fees: list[MarketplaceFee], now: datetime
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    groups: dict[str, dict[str, Decimal]] = {}
    refs: list[dict[str, Any]] = []
    for row in fees[:200]:
        currency = row.currency.upper()
        values = groups.setdefault(currency, {})
        values[row.fee_type] = values.get(row.fee_type, Decimal("0")) + Decimal(row.amount)
        refs.append(
            {
                "type": "marketplace_fee",
                "id": str(row.id),
                "fee_type": row.fee_type,
                "amount": str(row.amount),
                "currency": currency,
                "source": "marketplace_fee",
                "occurred_at": row.occurred_at.isoformat(),
                "freshness": _freshness(row.occurred_at, now),
            }
        )
    result = {
        currency: {
            "currency": currency,
            "by_type": {key: str(value) for key, value in sorted(values.items())},
            "total": str(sum(values.values(), Decimal("0"))),
            "sample_size": sum(1 for row in fees if row.currency.upper() == currency),
        }
        for currency, values in sorted(groups.items())
    }
    return result, refs


def _supplier_summary(
    db: Session,
    owner: User,
    request: CommercialCalculateRequest,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    products: list[SupplierProduct] = []
    if request.supplier_product_ids:
        products = list(
            db.scalars(
                select(SupplierProduct).where(
                    SupplierProduct.owner_id == owner.id,
                    SupplierProduct.id.in_(request.supplier_product_ids),
                )
            )
        )
        if len(products) != len(set(request.supplier_product_ids)):
            raise LookupError("Supplier commercial evidence not found.")
    quotes: list[SupplierQuote] = []
    if request.supplier_quote_ids:
        quotes = list(
            db.scalars(
                select(SupplierQuote).where(
                    SupplierQuote.owner_id == owner.id,
                    SupplierQuote.id.in_(request.supplier_quote_ids),
                )
            )
        )
        if len(quotes) != len(set(request.supplier_quote_ids)):
            raise LookupError("Supplier quote evidence not found.")
    evidence: list[dict[str, Any]] = []
    for product_row in products:
        evidence.append(
            {
                "type": "supplier_product",
                "id": str(product_row.id),
                "supplier_id": str(product_row.supplier_id),
                "unit_price": (
                    str(product_row.observed_price)
                    if product_row.observed_price is not None
                    else None
                ),
                "currency": product_row.currency,
                "moq": str(product_row.moq) if product_row.moq is not None else None,
                "lead_time_days": product_row.production_lead_days,
                "evidence_state": "OBSERVED_FACT",
                "freshness": _freshness(product_row.observed_at, now),
                "source_reference": product_row.source_reference,
            }
        )
    for quote_row in quotes:
        evidence.append(
            {
                "type": "supplier_quote",
                "id": str(quote_row.id),
                "supplier_id": str(quote_row.supplier_id),
                "unit_price": str(quote_row.unit_price),
                "currency": quote_row.currency,
                "moq": quote_row.moq,
                "quote_date": quote_row.quote_date.isoformat(),
                "status": quote_row.status,
                "evidence_state": "SUPPLIER_QUOTED",
                "freshness": _freshness(quote_row.quote_date, now),
                "quote_reference": quote_row.quote_reference,
            }
        )
    return evidence, [{"type": item["type"], "id": item["id"]} for item in evidence]


def _landed_reference(
    db: Session,
    owner: User,
    request: CommercialCalculateRequest,
) -> tuple[Decimal | None, str | None, dict[str, Any] | None, Decimal | None, int | None]:
    if request.landed_cost_estimate_id is not None:
        estimate = db.scalar(
            select(LandedCostEstimate).where(
                LandedCostEstimate.id == request.landed_cost_estimate_id,
                LandedCostEstimate.owner_id == owner.id,
            )
        )
        if estimate is None:
            raise LookupError("Landed-cost reference not found.")
        scenario = db.scalar(
            select(CostScenario).where(
                CostScenario.id == estimate.scenario_id,
                CostScenario.owner_id == owner.id,
            )
        )
        if scenario is None:
            raise LookupError("Landed-cost scenario reference not found.")
        return (
            _decimal(estimate.per_unit),
            scenario.currency.upper(),
            {
                "type": "landed_cost_estimate",
                "id": str(estimate.id),
                "scenario_id": str(scenario.id),
            },
            None,
            None,
        )
    if request.scenario_version_id is not None:
        scenario_version = db.scalar(
            select(SourcingScenarioVersion).where(
                SourcingScenarioVersion.id == request.scenario_version_id,
                SourcingScenarioVersion.owner_id == owner.id,
            )
        )
        if scenario_version is None:
            raise LookupError("Sourcing scenario reference not found.")
        result: dict[str, Any] = (
            scenario_version.result if isinstance(scenario_version.result, dict) else {}
        )
        cost = result.get("cost") if isinstance(result.get("cost"), dict) else None
        currency = str(result.get("currency") or "").upper() or None
        per_unit = _decimal(cost.get("landed_cost_per_unit")) if cost else None
        raw_allocations = result.get("allocations")
        allocations: list[Any] = raw_allocations if isinstance(raw_allocations, list) else []
        raw_moqs = [
            _decimal(item.get("required_purchase_units") or item.get("moq"))
            for item in allocations
            if isinstance(item, dict)
        ]
        moqs: list[Decimal] = [value for value in raw_moqs if value is not None]
        lead_time = None
        lead = result.get("lead_time")
        if isinstance(lead, dict):
            raw = lead.get("critical_path")
            if raw is not None:
                try:
                    lead_time = int(raw)
                except (TypeError, ValueError):
                    lead_time = None
        return (
            per_unit,
            currency,
            {
                "type": "sourcing_scenario_version",
                "id": str(scenario_version.id),
                "version": scenario_version.version,
            },
            max(moqs) if moqs else None,
            lead_time,
        )
    return None, None, None, None, None


def _select_currency(
    request: CommercialCalculateRequest,
    constraint: ProductOpportunityConstraintVersion,
    price_groups: dict[str, Any],
) -> str | None:
    if request.selling_price_currency:
        return request.selling_price_currency.upper()
    if constraint.currency:
        return constraint.currency.upper()
    if len(price_groups) == 1:
        return next(iter(price_groups))
    return None


def _freshness_for_prices(prices: list[MarketplacePrice], now: datetime) -> dict[str, Any]:
    states = [_freshness(row.effective_from, now) for row in prices]
    if not states:
        return {"state": "unknown", "observed_at": []}
    state = (
        "stale"
        if any(x["state"] == "stale" for x in states)
        else "aging" if any(x["state"] == "aging" for x in states) else "fresh"
    )
    return {"state": state, "observed_at": [x["observed_at"] for x in states]}


def _metric(
    selling: Decimal | None,
    landed: Decimal | None,
    fee: Decimal | None,
    *,
    fixed_costs: Decimal | None = None,
    quantity: Decimal = Decimal("1"),
) -> dict[str, Any]:
    if selling is None or landed is None or fee is None:
        return {
            "selling_price": selling,
            "landed_cost_per_unit": landed,
            "fee_per_unit": fee,
            "contribution_per_unit": None,
            "contribution_margin_percent": None,
            "gross_margin_percent": None,
            "known_fixed_costs": fixed_costs,
            "break_even_units": None,
        }
    contribution = selling - landed - fee
    margin = contribution / selling if selling != 0 else None
    gross = (selling - landed) / selling if selling != 0 else None
    break_even = None
    if fixed_costs is not None and contribution > 0:
        break_even = (fixed_costs / contribution).to_integral_value(rounding=ROUND_CEILING)
    return {
        "selling_price": selling,
        "landed_cost_per_unit": landed,
        "fee_per_unit": fee,
        "contribution_per_unit": contribution,
        "contribution_margin_percent": margin * 100 if margin is not None else None,
        "gross_margin_percent": gross * 100 if gross is not None else None,
        "known_fixed_costs": fixed_costs,
        "break_even_units": break_even,
        "break_even_definition": "Units to recover known fixed/setup costs only.",
        "quantity": quantity,
    }


def _sensitivity(
    selling: Decimal | None,
    landed: Decimal | None,
    fee: Decimal | None,
    fixed_costs: Decimal | None,
) -> dict[str, Any]:
    def evaluate(label: str, price_delta: Decimal, cost_delta: Decimal) -> dict[str, Any]:
        scenario_selling = selling * (Decimal("1") + price_delta) if selling is not None else None
        scenario_landed = landed * (Decimal("1") + cost_delta) if landed is not None else None
        result = _metric(scenario_selling, scenario_landed, fee, fixed_costs=fixed_costs)
        baseline = _metric(selling, landed, fee, fixed_costs=fixed_costs)
        contribution = result["contribution_per_unit"]
        baseline_contribution = baseline["contribution_per_unit"]
        result["delta"] = (
            contribution - baseline_contribution
            if contribution is not None and baseline_contribution is not None
            else None
        )
        result.update(
            {
                "label": label,
                "scenario": "BASELINE" if price_delta == 0 and cost_delta == 0 else "SCENARIO",
                "price_change": price_delta * 100,
                "cost_change": cost_delta * 100,
            }
        )
        return result

    price = [evaluate("price", change, Decimal("0")) for change in PRICE_DELTAS]
    cost = [evaluate("cost", Decimal("0"), change) for change in COST_DELTAS]
    combined = [
        evaluate("combined", price_change, cost_change)
        for price_change in (Decimal("-0.10"), Decimal("0"), Decimal("0.10"))
        for cost_change in (Decimal("0"), Decimal("0.10"), Decimal("0.20"))
    ]
    return {"price": price, "cost": cost, "combined": combined, "bounded": True}


def _constraint_fit(
    constraint: ProductOpportunityConstraintVersion,
    currency: str | None,
    selling: Decimal | None,
    landed: Decimal | None,
    margin: Decimal | None,
    moq: Decimal | None,
    lead_time: int | None,
    capital: Decimal | None,
) -> dict[str, Any]:
    comparable = currency is not None and (
        constraint.currency is None or currency == constraint.currency.upper()
    )
    margin_state = (
        "UNKNOWN"
        if margin is None or constraint.target_margin is None
        else "MEETS_TARGET" if margin >= Decimal(constraint.target_margin) * 100 else "BELOW_TARGET"
    )
    landed_state = (
        "UNKNOWN"
        if landed is None or constraint.maximum_landed_cost is None or not comparable
        else (
            "WITHIN_LIMIT" if landed <= Decimal(constraint.maximum_landed_cost) else "EXCEEDS_LIMIT"
        )
    )
    moq_state = (
        "UNKNOWN"
        if moq is None or constraint.maximum_moq is None
        else "WITHIN_LIMIT" if moq <= Decimal(constraint.maximum_moq) else "EXCEEDS_LIMIT"
    )
    lead_state = (
        "UNKNOWN"
        if lead_time is None or constraint.maximum_lead_time_days is None
        else "WITHIN_LIMIT" if lead_time <= constraint.maximum_lead_time_days else "EXCEEDS_LIMIT"
    )
    capital_state = (
        "UNKNOWN"
        if capital is None or constraint.available_capital is None or not comparable
        else (
            "WITHIN_CAPITAL"
            if capital <= Decimal(constraint.available_capital) * Decimal("0.90")
            else (
                "NEAR_CAPITAL_LIMIT"
                if capital <= Decimal(constraint.available_capital)
                else "EXCEEDS_CAPITAL"
            )
        )
    )
    return {
        "currency_comparable": comparable,
        "margin": margin_state,
        "maximum_landed_cost": landed_state,
        "maximum_moq": moq_state,
        "maximum_lead_time": lead_state,
        "available_capital": capital_state,
        "target_selling_price": (
            "UNKNOWN"
            if selling is None or not comparable
            else (
                "WITHIN_RANGE"
                if (
                    constraint.target_selling_price_min is None
                    or selling >= Decimal(constraint.target_selling_price_min)
                )
                and (
                    constraint.target_selling_price_max is None
                    or selling <= Decimal(constraint.target_selling_price_max)
                )
                else "OUTSIDE_RANGE"
            )
        ),
    }


def calculate_commercial(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: CommercialCalculateRequest,
) -> ProductOpportunityCommercialOutput:
    opportunity, assessment, constraint, listings = _context(
        db, owner, opportunity_id, assessment_id
    )
    now = commercial_now()
    prices = _prices(db, owner, listings)
    fees = _fees(db, owner, listings)
    price_groups, price_snapshot = _price_summary(prices, now)
    fee_groups, fee_refs = _fee_summary(fees, now)
    supplier_evidence, supplier_refs = _supplier_summary(db, owner, request, now)
    landed, landed_currency, landed_ref, scenario_moq, scenario_lead = _landed_reference(
        db, owner, request
    )
    currency = _select_currency(request, constraint, price_groups)
    if request.selling_price is not None and request.selling_price_currency != currency:
        raise ValueError("Selling price and commercial evidence currencies are not comparable.")
    if landed is not None and landed_currency != currency:
        landed = None
        landed_ref = {**(landed_ref or {}), "comparison": "UNKNOWN_CURRENCY_MISMATCH"}
    selling = request.selling_price
    fee = request.fee_per_unit
    moq = request.moq or scenario_moq
    lead_time = request.lead_time_days if request.lead_time_days is not None else scenario_lead
    if moq is None:
        raw_quote_moqs = [_decimal(item.get("moq")) for item in supplier_evidence]
        quote_moqs: list[Decimal] = [
            value for value in raw_quote_moqs if value is not None and value > 0
        ]
        moq = min(quote_moqs) if quote_moqs else None
    fixed_costs = request.fixed_costs
    economics = _metric(selling, landed, fee, fixed_costs=fixed_costs)
    inventory_capital = landed * moq if landed is not None and moq is not None else None
    known_total = (
        (inventory_capital or Decimal("0")) + (fixed_costs or Decimal("0"))
        if inventory_capital is not None or fixed_costs is not None
        else None
    )
    economics.update(
        {
            "currency": currency,
            "selling_price_provenance": (
                "USER_ASSUMPTION" if selling is not None else "MISSING_EVIDENCE"
            ),
            "landed_cost_provenance": (
                "VERIFIED_FACT" if landed_ref and landed is not None else "MISSING_EVIDENCE"
            ),
            "fee_provenance": "USER_ASSUMPTION" if fee is not None else "MISSING_EVIDENCE",
            "moq": moq,
            "lead_time_days": lead_time,
            "inventory_capital": inventory_capital,
            "known_fixed_setup_capital": fixed_costs,
            "known_total_initial_capital": known_total,
            "capital_currency": currency,
            "fee_evidence": fee_groups,
            "landed_cost_reference": landed_ref,
        }
    )
    freshness = _freshness_for_prices(prices, now)
    supporting = price_snapshot["references"] + fee_refs + supplier_refs
    gaps: list[dict[str, Any]] = []
    if not prices:
        gaps.append(
            {
                "code": "SELLING_PRICE_EVIDENCE_REQUIRED",
                "reason": "No marketplace price observations are linked.",
            }
        )
    if selling is None:
        gaps.append(
            {
                "code": "SELLING_PRICE_ASSUMPTION_REQUIRED",
                "reason": "Provide a bounded modeled selling price and currency.",
            }
        )
    if not supplier_evidence:
        gaps.append(
            {
                "code": "SUPPLIER_PRICE_REQUIRED",
                "reason": "No supplier commercial evidence was referenced.",
            }
        )
    if landed is None:
        gaps.append(
            {
                "code": "LANDED_COST_REQUIRED",
                "reason": "Reference a canonical landed-cost estimate or sourcing scenario version.",  # noqa: E501
            }
        )
    if fee is None:
        gaps.append(
            {
                "code": "MARKETPLACE_FEE_REQUIRED",
                "reason": "A per-unit fee assumption is required; observed fee totals are not silently treated as per-unit.",  # noqa: E501
            }
        )
    if moq is None:
        gaps.append({"code": "MOQ_REQUIRED", "reason": "No authoritative MOQ is available."})
    if lead_time is None:
        gaps.append(
            {
                "code": "LEAD_TIME_REQUIRED",
                "reason": "No authoritative lead-time evidence is available.",
            }
        )
    if currency is None:
        gaps.append(
            {
                "code": "FX_REQUIRED",
                "reason": "A single comparable commercial currency is not available.",
            }
        )
    if not landed_ref:
        gaps.append(
            {
                "code": "LOGISTICS_EVIDENCE_REQUIRED",
                "reason": "No canonical logistics/landed-cost lineage was supplied.",
            }
        )
    margin = economics.get("contribution_margin_percent")
    fit = _constraint_fit(
        constraint, currency, selling, landed, margin, moq, lead_time, known_total
    )
    dimensions = [
        _dimension(
            "PRICE_HEADROOM",
            value=(
                None
                if selling is None or currency is None or not price_groups.get(currency)
                else {
                    "market_median": price_groups[currency]["median"],
                    "modeled_selling_price": str(selling),
                    "delta": str(selling - Decimal(price_groups[currency]["median"])),
                }
            ),
            classification=(
                "DERIVED_VALUE"
                if selling is not None and currency is not None and currency in price_groups
                else "UNKNOWN"
            ),
            evidence_state="available" if prices else "unknown",
            explanation="Observed market prices remain separate from the explicit modeled selling-price assumption.",  # noqa: E501
            supporting=supporting,
            missing=(
                []
                if selling is not None and currency is not None and currency in price_groups
                else ["comparable market price", "selling price assumption"]
            ),
            freshness=freshness,
        ),
        _dimension(
            "UNIT_ECONOMICS",
            value=economics if margin is not None else None,
            classification="DERIVED_VALUE" if margin is not None else "UNKNOWN",
            evidence_state="available" if margin is not None else "insufficient_evidence",
            explanation="Contribution equals modeled selling price less landed cost and explicit per-unit fee; it is not net profit.",  # noqa: E501
            supporting=supporting,
            missing=[] if margin is not None else ["selling price", "landed cost", "per-unit fees"],
            freshness=freshness,
        ),
        _dimension(
            "MARGIN_VIABILITY",
            value=margin,
            classification="DERIVED_VALUE" if margin is not None else "UNKNOWN",
            evidence_state="available" if margin is not None else "insufficient_evidence",
            explanation="Contribution margin percentage is contribution divided by modeled selling price.",  # noqa: E501
            supporting=supporting,
            missing=[] if margin is not None else ["complete unit economics"],
            freshness=freshness,
        ),
        _dimension(
            "CAPITAL_EFFICIENCY",
            value=(known_total if known_total is not None else None),
            classification="DERIVED_VALUE" if known_total is not None else "UNKNOWN",
            evidence_state=(
                "partial"
                if known_total is not None and (inventory_capital is None or fixed_costs is None)
                else "available" if known_total is not None else "insufficient_evidence"
            ),
            explanation="Known initial capital includes only evidenced inventory-at-MOQ and explicit fixed/setup costs; advertising and overhead are excluded.",  # noqa: E501
            supporting=supporting,
            missing=[] if known_total is not None else ["MOQ", "landed cost", "fixed/setup costs"],
            freshness=freshness,
        ),
        _dimension(
            "MOQ_FIT",
            value=fit["maximum_moq"],
            classification="DERIVED_VALUE" if fit["maximum_moq"] != "UNKNOWN" else "UNKNOWN",
            evidence_state="available" if moq is not None else "unknown",
            explanation="Authoritative MOQ compared with the versioned opportunity maximum MOQ.",
            supporting=supporting,
            missing=[] if moq is not None else ["MOQ"],
            freshness=freshness,
        ),
        _dimension(
            "LANDED_COST_FIT",
            value=fit["maximum_landed_cost"],
            classification=(
                "DERIVED_VALUE" if fit["maximum_landed_cost"] != "UNKNOWN" else "UNKNOWN"
            ),
            evidence_state=(
                "available" if landed is not None and fit["currency_comparable"] else "unknown"
            ),
            explanation="Landed cost is compared only when currencies are directly comparable.",
            supporting=supporting,
            missing=(
                []
                if landed is not None and fit["currency_comparable"]
                else ["comparable landed cost"]
            ),
            freshness=freshness,
        ),
        _dimension(
            "CONSTRAINT_FIT",
            value=fit,
            classification=(
                "DERIVED_VALUE"
                if any(
                    value != "UNKNOWN" for key, value in fit.items() if key != "currency_comparable"
                )
                else "UNKNOWN"
            ),
            evidence_state=(
                "available"
                if any(
                    value != "UNKNOWN" for key, value in fit.items() if key != "currency_comparable"
                )
                else "unknown"
            ),
            explanation="Versioned opportunity constraints are evaluated independently; incomparable currencies remain UNKNOWN.",  # noqa: E501
            supporting=supporting,
            missing=(
                []
                if any(
                    value != "UNKNOWN" for key, value in fit.items() if key != "currency_comparable"
                )
                else ["comparable commercial evidence"]
            ),
            freshness=freshness,
        ),
        _dimension(
            "BREAK_EVEN_FEASIBILITY",
            value=economics.get("break_even_units"),
            classification=(
                "DERIVED_VALUE" if economics.get("break_even_units") is not None else "UNKNOWN"
            ),
            evidence_state=(
                "available"
                if economics.get("break_even_units") is not None
                else "insufficient_evidence"
            ),
            explanation="Break-even units recover known fixed/setup costs only; unknown fixed costs remain insufficient evidence.",  # noqa: E501
            supporting=supporting,
            missing=(
                []
                if economics.get("break_even_units") is not None
                else ["positive contribution", "known fixed/setup costs"]
            ),
            freshness=freshness,
        ),
        _dimension(
            "ECONOMIC_RESILIENCE",
            value=(
                None
                if margin is None
                else {
                    "scenarios": "bounded",
                    "worst_case_contribution": min(
                        (
                            item["contribution_per_unit"]
                            for item in _sensitivity(selling, landed, fee, fixed_costs)["combined"]
                            if item["contribution_per_unit"] is not None
                        ),
                        default=None,
                    ),
                }
            ),
            classification="SCENARIO_RESULT" if margin is not None else "UNKNOWN",
            evidence_state="available" if margin is not None else "insufficient_evidence",
            explanation="Describes bounded price/cost scenarios; it is not supplier portfolio resilience or a forecast.",  # noqa: E501
            supporting=supporting,
            missing=[] if margin is not None else ["complete unit economics"],
            freshness=freshness,
        ),
        _dimension(
            "COMMERCIAL_EVIDENCE_COVERAGE",
            value=len(supporting) or None,
            classification="DERIVED_VALUE" if supporting else "UNKNOWN",
            evidence_state="available" if supporting else "unknown",
            explanation="Count of bounded marketplace, fee, and supplier evidence references.",
            supporting=supporting,
            missing=[] if supporting else ["commercial evidence"],
            freshness=freshness,
        ),
        _dimension(
            "COMMERCIAL_EVIDENCE_FRESHNESS",
            value=freshness["state"],
            classification="OBSERVED_FACT" if prices else "UNKNOWN",
            evidence_state="available" if prices else "unknown",
            explanation="Freshness is derived from marketplace price observation timestamps; supplier and fee timestamps remain visible in lineage.",  # noqa: E501
            supporting=supporting,
            missing=[] if prices else ["commercial observation timestamps"],
            freshness=freshness,
        ),
    ]
    snapshot = {
        "constraint_version_id": str(constraint.id),
        "constraint_version": constraint.version,
        "price_snapshot": price_snapshot,
        "fee_ids": [str(row.id) for row in fees],
        "supplier_references": supplier_refs,
        "landed_cost_reference": landed_ref,
        "request": request.model_dump(mode="json"),
        "calculated_at": now.isoformat(),
        "calculation_version": CALCULATION_VERSION,
    }
    key = request.idempotency_key or f"opportunity-commercial:{assessment.id}"
    existing = db.scalar(
        select(ProductOpportunityCommercialOutput).where(
            ProductOpportunityCommercialOutput.owner_id == owner.id,
            ProductOpportunityCommercialOutput.assessment_id == assessment.id,
        )
    )
    if existing is not None:
        return existing
    output = ProductOpportunityCommercialOutput(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        calculation_version=CALCULATION_VERSION,
        constraint_snapshot={
            key: _json(getattr(constraint, key))
            for key in (
                "id",
                "version",
                "currency",
                "available_capital",
                "target_margin",
                "maximum_landed_cost",
                "maximum_moq",
                "maximum_lead_time_days",
                "target_selling_price_min",
                "target_selling_price_max",
            )
        },
        input_snapshot=_json(snapshot),
        dimensions=_json(dimensions),
        economics=_json(economics),
        sensitivity=_json(_sensitivity(selling, landed, fee, fixed_costs)),
        evidence_summary=_json(
            {
                "prices": price_groups,
                "fees": fee_groups,
                "supplier_evidence": supplier_evidence,
                "freshness": freshness,
            }
        ),
        research_gaps=gaps,
        idempotency_key=key,
        notes="Commercial viability intelligence only; no winner score, ranking, recommendation, procurement, or publishing action.",  # noqa: E501
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output
