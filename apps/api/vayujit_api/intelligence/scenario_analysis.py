"""Deterministic scenario analysis over immutable snapshots, using the shared cost engine."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, cast

from vayujit_api.intelligence.scenario_schemas import ContextCreate, ScenarioCreate
from vayujit_api.intelligence.sourcing_closure import landed_cost

CALCULATION_VERSION = "scenario-decimal-v1"
LANDED_COST_VERSION = "sourcing-landed-cost-exact-v1"
SCORING_VERSION = "scenario-relative-v1"
COST_KEYS = (
    "tooling",
    "branding",
    "packaging",
    "inspection",
    "freight",
    "insurance",
    "duty",
    "tax",
    "brokerage",
    "local_transport",
    "warehouse_inbound",
    "payment_fx_fee",
    "other",
)
WEIGHTS = {
    "COST": 15,
    "MARGIN": 15,
    "CAPITAL": 10,
    "LEAD_TIME": 10,
    "RISK": 15,
    "RESILIENCE": 10,
    "EVIDENCE_QUALITY": 10,
    "SUPPLIER_CONFIDENCE": 5,
    "MOQ_FEASIBILITY": 5,
    "LOGISTICS": 5,
}


def decimal_json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))
    if isinstance(value, dict):
        return {k: decimal_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decimal_json(v) for v in value]
    return value


def calculate(
    settings: dict[str, Any],
    request: dict[str, Any],
    lineage: list[dict[str, Any]],
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    with localcontext() as ctx:
        ctx.prec = 40
        ctx.rounding = ROUND_HALF_EVEN
        return cast(
            dict[str, Any],
            decimal_json(_calculate(settings, request, lineage, at or datetime.now(UTC))),
        )


def _calculate(
    settings: dict[str, Any],
    request: dict[str, Any],
    lineage: list[dict[str, Any]],
    at: datetime,
) -> dict[str, Any]:
    config = ContextCreate.model_validate(settings)
    data = ScenarioCreate.model_validate(request)
    if sum(a.quantity for a in data.allocations) != config.target_quantity:
        raise ValueError("Allocation quantities must equal the target quantity.")
    if set(data.costs) - set(COST_KEYS):
        raise ValueError("Unsupported cost component.")
    if {str(a.supplier_id) for a in data.allocations} != {x["supplier_id"] for x in lineage}:
        raise ValueError("Allocation lineage is incomplete.")
    missing: list[str] = []
    warnings = ["ESTIMATED_NOT_REALIZED", "COMMERCIAL_INPUTS_ARE_ASSUMPTIONS"]
    allocations: list[dict[str, Any]] = []
    fx = {f.from_currency: f for f in data.fx}
    sources = {x["supplier_id"]: x for x in lineage}
    purchase = Decimal(0)
    excess_capital = Decimal(0)
    moq_purchase = Decimal(0)
    leads: list[tuple[int, int]] = []
    country_shares: dict[str, Decimal] = {}
    manufacturers: dict[str, Decimal] = {}
    risk_total = Decimal(0)
    confidence_total = Decimal(0)
    all_risk_known = True
    known_countries = True
    known_manufacturers = True
    for allocation in data.allocations:
        supplier_id = str(allocation.supplier_id)
        source = sources[supplier_id]
        share = Decimal(allocation.quantity) / config.target_quantity
        rate: Decimal | None = Decimal(1)
        if allocation.currency != config.base_currency:
            record = fx.get(allocation.currency)
            if record is None or record.valid_until <= at or record.observed_at > at:
                missing.append(f"FX:{allocation.currency}")
                rate = None
            else:
                rate = record.rate
        if allocation.unit_price is None:
            missing.append(f"PRICE:{supplier_id}")
        unit = allocation.unit_price * rate if allocation.unit_price is not None and rate else None
        required_units = max(allocation.quantity, allocation.moq) if allocation.moq else None
        excess = required_units - allocation.quantity if required_units is not None else None
        if unit is not None:
            purchase += unit * allocation.quantity
            if required_units is not None:
                moq_purchase += unit * required_units
                excess_capital += unit * (excess or 0)
        if allocation.moq is None:
            missing.append(f"MOQ:{supplier_id}")
        if allocation.lead_time_days is None:
            missing.append(f"LEAD_TIME:{supplier_id}")
        else:
            leads.append((allocation.lead_time_days, allocation.quantity))
        if allocation.availability != "AVAILABLE":
            missing.append(f"AVAILABILITY:{supplier_id}")
        if not allocation.incoterm:
            missing.append(f"INCOTERM:{supplier_id}")
        guard = source["due_diligence"]
        if guard["outcome"] != "ALLOWED" or not source["assessment_version"]:
            missing.append(f"DUE_DILIGENCE:{supplier_id}")
        if guard.get("human_waivers"):
            warnings.append(f"HUMAN_WAIVER_NOT_VERIFICATION:{supplier_id}")
        if source["freshness"] != "fresh":
            missing.append(f"FRESHNESS:{supplier_id}")
        if source["eligibility"] != "ELIGIBLE":
            warnings.append(f"SHORTLIST_REVIEW_REQUIRED:{supplier_id}")
        facts = source["facts"]
        country = facts.get("country_code") or facts.get("country")
        manufacturer = facts.get("manufacturer_id")
        if country:
            country_shares[str(country)] = country_shares.get(str(country), Decimal(0)) + share
        else:
            known_countries = False
        if manufacturer:
            manufacturers[str(manufacturer)] = (
                manufacturers.get(str(manufacturer), Decimal(0)) + share
            )
        else:
            known_manufacturers = False
        # Consume an authoritative supplier risk score only; do not manufacture one.
        raw_risk = facts.get("risk_score")
        try:
            risk = Decimal(str(raw_risk))
            if not risk.is_finite() or not 0 <= risk <= 100:
                raise ValueError("Invalid risk score.")
            risk_total += risk * share
        except (ValueError, ArithmeticError):
            all_risk_known = False
        confidence_total += Decimal(str(source["confidence"])) * share
        if Decimal(str(source["source_diversity"])) < 2:
            warnings.append(f"LOW_SOURCE_DIVERSITY:{supplier_id}")
        allocations.append(
            {
                "supplier_id": supplier_id,
                "quantity": allocation.quantity,
                "percentage": share * 100,
                "base_unit_cost": unit,
                "moq": allocation.moq,
                "required_purchase_units": required_units,
                "excess_units": excess,
                "excess_capital": (
                    unit * excess if unit is not None and excess is not None else None
                ),
                "moq_feasibility": (
                    "UNKNOWN" if excess is None else "INFEASIBLE" if excess else "FEASIBLE"
                ),
                "lead_time_days": allocation.lead_time_days,
                "due_diligence": guard,
            }
        )
    for key in COST_KEYS:
        if key not in data.costs:
            missing.append(f"LOGISTICS_COST:{key}")
    cost_missing = any(x.startswith(("PRICE:", "FX:", "LOGISTICS_COST:")) for x in missing)
    cost = None
    if not cost_missing:
        cost = landed_cost(
            {
                "unit_supplier_price": purchase,
                "quantity": config.target_quantity,
                **data.costs,
                **{
                    f"{key}_classification": "ASSUMED"
                    for key in ("unit_supplier_price", *COST_KEYS)
                },
            },
            currency=config.base_currency,
            exact=True,
        )
    moq_unknown = any(x.startswith("MOQ:") for x in missing)
    landed = cost["total_landed_cost"] if cost else None
    per_unit = cost["landed_cost_per_unit"] if cost else None
    buffer = data.working_capital_buffer
    if buffer is None:
        missing.append("CAPITAL_BUFFER")
    capital: dict[str, Any] = {
        "minimum_purchase_capital": None if cost_missing or moq_unknown else moq_purchase,
        "landed_inventory_capital": landed,
        "minimum_order_cash_requirement": (
            None if landed is None or moq_unknown else landed + excess_capital
        ),
        "working_capital_requirement": buffer,
        "estimated_total_initial_cash": (
            None
            if landed is None or buffer is None or moq_unknown
            else landed + excess_capital + buffer
        ),
        "assumption": (
            "Full prepayment; excludes unentered launch costs. "
            "Excess MOQ freight is not estimated."
        ),
    }
    fees = [
        data.channel_fee_per_unit,
        data.payment_fee_per_unit,
        data.returns_per_unit,
        data.advertising_per_unit,
    ]
    margin = None
    if any(f is None for f in fees):
        missing.append("CHANNEL_RETURN_ADVERTISING_ASSUMPTIONS")
    if config.target_sale_price is None or config.target_sale_price == 0:
        missing.append("SALE_PRICE")
    elif per_unit is not None and all(f is not None for f in fees):
        sale = config.target_sale_price
        fee = sum((f for f in fees if f is not None), Decimal(0))
        contribution = sale - per_unit - fee
        margin = {
            "classification": "ESTIMATED",
            "gross_revenue": sale * config.target_quantity,
            "per_unit_contribution": contribution,
            "contribution": contribution * config.target_quantity,
            "contribution_margin_percent": contribution / sale * 100,
            "gross_margin_percent": (sale - per_unit) / sale * 100,
            "minimum_sale_price": per_unit + fee,
            "maximum_acquisition_cost": sale
            - per_unit
            - fee
            + (data.advertising_per_unit or Decimal(0)),
            "break_even_units": None,
            "break_even_revenue": None,
            "break_even_limitation": "Fixed versus variable cost split is not evidenced.",
        }
    stage_values = [data.logistics_days, data.customs_days, data.domestic_days]
    lead = None
    if len(leads) != len(allocations) or any(x is None for x in stage_values):
        missing.append("REPLENISHMENT_STAGES")
    else:
        stage_days = sum(x for x in stage_values if x is not None)
        lead = {
            "fastest": min(x[0] for x in leads) + stage_days,
            "slowest": max(x[0] for x in leads) + stage_days,
            "critical_path": max(x[0] for x in leads) + stage_days,
            "weighted": Decimal(sum(days * quantity for days, quantity in leads))
            / config.target_quantity
            + stage_days,
            "best_case": None,
            "worst_case": None,
            "limitation": "Only point estimates supplied; no uncertainty bounds.",
        }
    shares = [Decimal(a.quantity) / config.target_quantity for a in data.allocations]
    largest = max(shares) * 100
    concentration: dict[str, Any] = {
        "largest_supplier_percent": largest,
        "supplier_hhi": sum((x * x for x in shares), Decimal(0)) * 100,
        "largest_country_percent": max(country_shares.values()) * 100 if known_countries else None,
        "largest_manufacturer_percent": (
            max(manufacturers.values()) * 100 if known_manufacturers else None
        ),
        "independent_manufacturers_verified": known_manufacturers,
    }
    if len(shares) == 1:
        warnings.append("SINGLE_SUPPLIER_DEPENDENCY")
    if known_countries and max(country_shares.values()) >= Decimal("0.8"):
        warnings.append("HIGH_COUNTRY_CONCENTRATION")
    if not known_manufacturers:
        warnings.append("UNVERIFIED_BACKUP_SUPPLIER")
    resilience = {
        "score": 100 - concentration["supplier_hhi"] if known_manufacturers else None,
        "explanation": (
            "100 minus supplier HHI; withheld unless manufacturer identity is evidenced. "
            "Not a supplier risk model."
        ),
    }
    if not all_risk_known:
        warnings.append("SUPPLIER_RISK_UNKNOWN")
    moq_states = {a["moq_feasibility"] for a in allocations}
    moq = (
        "UNKNOWN"
        if "UNKNOWN" in moq_states
        else "PARTIALLY_FEASIBLE" if len(moq_states) > 1 else next(iter(moq_states))
    )
    blocked = any(s["due_diligence"]["outcome"] == "BLOCKED" for s in lineage)
    if moq != "FEASIBLE":
        warnings.append("MOQ_REQUIRES_REVIEW")
    if (
        capital["estimated_total_initial_cash"] is not None
        and config.capital_limit is not None
        and capital["estimated_total_initial_cash"] > config.capital_limit
    ):
        warnings.append("CAPITAL_LIMIT_EXCEEDED")
    if (
        margin
        and config.margin_target is not None
        and margin["contribution_margin_percent"] < config.margin_target
    ):
        warnings.append("MARGIN_BELOW_TARGET")
    return {
        "classification": "INSUFFICIENT_EVIDENCE" if missing else "REVIEW_REQUIRED",
        "status": "BLOCKED" if blocked else "REVIEW_REQUIRED",
        "missing_dimensions": sorted(set(missing)),
        "warnings": sorted(set(warnings)),
        "currency": config.base_currency,
        "allocations": allocations,
        "cost": cost,
        "capital": capital,
        "margin": margin,
        "lead_time": lead,
        "moq_feasibility": moq,
        "concentration": concentration,
        "resilience": resilience,
        "supplier_risk": risk_total if all_risk_known else None,
        "supplier_confidence": confidence_total,
        "fx": [f.model_dump(mode="json") for f in data.fx],
        "logistics_mode": data.logistics_mode,
        "external_dispatch": False,
    }


def compare(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Relative scores always disclose the comparison set and unknown dimensions."""
    paths = {
        "COST": ("cost", "total_landed_cost"),
        "MARGIN": ("margin", "contribution_margin_percent"),
        "CAPITAL": ("capital", "estimated_total_initial_cash"),
        "LEAD_TIME": ("lead_time", "critical_path"),
        "RISK": ("supplier_risk",),
        "RESILIENCE": ("resilience", "score"),
        "EVIDENCE_QUALITY": (),
        "SUPPLIER_CONFIDENCE": ("supplier_confidence",),
        "MOQ_FEASIBILITY": (),
        "LOGISTICS": ("lead_time", "weighted"),
    }
    higher = {"MARGIN", "RESILIENCE", "EVIDENCE_QUALITY", "SUPPLIER_CONFIDENCE", "MOQ_FEASIBILITY"}
    measures: dict[str, dict[str, Decimal | None]] = {}
    for row in rows:
        values: dict[str, Decimal | None] = {}
        for dim, path in paths.items():
            raw: Any = row["result"]
            for key in path:
                raw = raw.get(key) if isinstance(raw, dict) else None
            if dim == "EVIDENCE_QUALITY":
                raw = 100 if not row["result"]["missing_dimensions"] else None
            elif dim == "MOQ_FEASIBILITY":
                raw = 100 if row["result"]["moq_feasibility"] == "FEASIBLE" else 0
            values[dim] = Decimal(str(raw)) if raw is not None else None
        measures[row["id"]] = values
    result = []
    for row in rows:
        parts: list[dict[str, Any]] = []
        for dim, weight in WEIGHTS.items():
            value = measures[row["id"]][dim]
            population = [v for m in measures.values() if (v := m[dim]) is not None]
            raw_score = None
            if value is not None and population:
                low, high = min(population), max(population)
                raw_score = Decimal(100) if low == high else (value - low) / (high - low) * 100
                if dim not in higher and low != high:
                    raw_score = 100 - raw_score
            parts.append(
                {
                    "dimension": dim,
                    "weight": weight,
                    "score": raw_score,
                    "explanation": (
                        "Relative min-max within these exact scenario versions; "
                        "unknowns not imputed."
                    ),
                }
            )
        score = (
            sum((p["score"] * p["weight"] / 100 for p in parts), Decimal(0))
            if all(p["score"] is not None for p in parts)
            else None
        )
        labels = [row["result"]["classification"]]
        result.append({**row, "score": score, "dimensions": parts, "labels": labels})
    label_map = {
        "COST": "LOWEST_COST",
        "CAPITAL": "LOWEST_CAPITAL",
        "MARGIN": "BEST_MARGIN",
        "LEAD_TIME": "FASTEST",
        "RISK": "LOWEST_RISK",
        "RESILIENCE": "BEST_RESILIENCE",
    }
    for dim, label in label_map.items():
        eligible = [
            r
            for r in result
            if not r["result"]["missing_dimensions"] and measures[r["id"]][dim] is not None
        ]
        if eligible:
            known = [v for r in eligible if (v := measures[r["id"]][dim]) is not None]
            best = (max if dim in higher else min)(known)
            for row in eligible:
                if measures[row["id"]][dim] == best:
                    row["labels"].append(label)
    ranked = sorted(
        [
            r
            for r in result
            if r["score"] is not None
            and not r["result"]["missing_dimensions"]
            and r["result"]["status"] != "BLOCKED"
        ],
        key=lambda r: (-r["score"], r["id"]),
    )
    if ranked:
        ranked[0]["labels"].append("BEST_BALANCED")
    return cast(
        dict[str, Any],
        decimal_json(
            {
                "scoring_version": SCORING_VERSION,
                "weights": WEIGHTS,
                "scenarios": result,
                "recommended_version_id": ranked[0]["id"] if ranked else None,
                "recommendation": (
                    "RECOMMENDED_FOR_HUMAN_REVIEW" if ranked else "INSUFFICIENT_EVIDENCE"
                ),
            }
        ),
    )


def sensitivity(snapshot: dict[str, Any], dimension: str, change: Decimal) -> dict[str, Any]:
    limits = {
        "purchase": 10,
        "freight": 20,
        "fx": 5,
        "sale_price": 10,
        "returns": 20,
        "advertising": 20,
        "lead_time": 20,
    }
    if dimension not in limits or not change.is_finite() or abs(change) > limits[dimension]:
        raise ValueError("Sensitivity change exceeds the supported band.")
    copied = deepcopy(snapshot)
    data = copied["request"]
    factor = 1 + change / 100
    if dimension in {"purchase", "lead_time"}:
        field = "unit_price" if dimension == "purchase" else "lead_time_days"
        for a in data["allocations"]:
            if a[field] is not None:
                a[field] = (
                    str(Decimal(str(a[field])) * factor)
                    if field == "unit_price"
                    else int(
                        (Decimal(a[field]) * factor).to_integral_value(rounding="ROUND_CEILING")
                    )
                )
    elif dimension == "fx":
        for f in data["fx"]:
            f["rate"] = str(Decimal(f["rate"]) * factor)
    elif dimension == "freight":
        if data["costs"].get("freight") is not None:
            data["costs"]["freight"] = str(Decimal(data["costs"]["freight"]) * factor)
    elif dimension == "sale_price":
        if copied["settings"]["target_sale_price"] is not None:
            copied["settings"]["target_sale_price"] = str(
                Decimal(copied["settings"]["target_sale_price"]) * factor
            )
    else:
        field = "returns_per_unit" if dimension == "returns" else "advertising_per_unit"
        if data[field] is not None:
            data[field] = str(Decimal(data[field]) * factor)
    return calculate(
        copied["settings"],
        data,
        copied["lineage"],
        at=datetime.fromisoformat(snapshot["calculated_at"]),
    )
