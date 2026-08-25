"""Pure, deterministic closure contracts for sourcing and economics."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from html import escape
from math import isfinite
from typing import Any

SHIPPING_MODES = ("AIR", "SEA", "ROAD", "RAIL", "COURIER", "LOCAL", "UNKNOWN")
INCOTERMS = ("EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP")
CLASSIFICATIONS = ("OBSERVED", "CONFIGURED", "ASSUMED", "UNKNOWN")
FX_CLASSIFICATIONS = ("CONFIGURED", "OBSERVED", "ASSUMED")
SCORE_DIMENSIONS = (
    "commercial_competitiveness",
    "moq",
    "lead_time",
    "payment_terms",
    "supplier_verification",
    "supplier_risk",
    "sample_result",
    "inspection_result",
    "landed_cost",
    "margin_potential",
    "capital_efficiency",
    "evidence_confidence",
)
DEFAULT_SCORE_WEIGHTS = {
    "commercial_competitiveness": 14.0,
    "moq": 8.0,
    "lead_time": 8.0,
    "payment_terms": 7.0,
    "supplier_verification": 12.0,
    "supplier_risk": 10.0,
    "sample_result": 8.0,
    "inspection_result": 7.0,
    "landed_cost": 10.0,
    "margin_potential": 7.0,
    "capital_efficiency": 4.0,
    "evidence_confidence": 5.0,
}


def validate_shipping_mode(value: str) -> str:
    mode = str(value).upper()
    if mode not in SHIPPING_MODES:
        raise ValueError("Unsupported shipping mode.")
    return mode


def validate_incoterm(value: str) -> str:
    term = str(value).upper()
    if term not in INCOTERMS:
        raise ValueError("Unsupported Incoterm.")
    return term


def validate_classification(value: str, *, fx: bool = False) -> str:
    value = str(value).upper()
    allowed = FX_CLASSIFICATIONS if fx else CLASSIFICATIONS
    if value not in allowed:
        raise ValueError("Unsupported assumption classification.")
    return value


def finite_nonnegative(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or float(value) < 0
    ):
        raise ValueError(f"{label} must be a finite non-negative number.")
    return float(value)


def validate_logistics(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["shipping_mode"] = validate_shipping_mode(result.get("shipping_mode", "UNKNOWN"))
    for key in (
        "unit_weight",
        "length",
        "width",
        "height",
        "volumetric_weight",
        "carton_quantity",
        "carton_length",
        "carton_width",
        "carton_height",
        "freight_estimate",
        "insurance",
        "handling",
        "brokerage",
        "local_transport",
    ):
        if key in result and result[key] is not None:
            result[key] = finite_nonnegative(result[key], key)
    for key in ("origin", "destination"):
        result[key] = str(result.get(key, "UNKNOWN"))[:240]
    result["classification"] = validate_classification(result.get("classification", "ASSUMED"))
    result["incoterm"] = validate_incoterm(result.get("incoterm", "EXW"))
    result["responsibility_notice"] = "VERIFY INCOTERM RESPONSIBILITIES BEFORE ORDER"
    if all(result.get(k) is not None for k in ("carton_length", "carton_width", "carton_height")):
        volume = (
            float(result["carton_length"])
            * float(result["carton_width"])
            * float(result["carton_height"])
        )
        result["volumetric_weight"] = round(volume / 5000.0, 6)
    return result


def validate_duty_tax(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    for key in (
        "customs_value",
        "duty_percent",
        "cess_percent",
        "gst_vat_percent",
        "import_tax_percent",
        "brokerage",
        "other_import_charges",
    ):
        if key in result and result[key] is not None:
            result[key] = finite_nonnegative(result[key], key)
    result["classification"] = validate_classification(result.get("classification", "UNKNOWN"))
    result["reason"] = str(result.get("reason", ""))[:1000]
    result["source_reference"] = str(result.get("source_reference", ""))[:500]
    return result


def validate_fx(payload: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    result = dict(payload)
    result["from_currency"] = str(result.get("from_currency", "")).upper()
    result["to_currency"] = str(result.get("to_currency", "")).upper()
    if len(result["from_currency"]) != 3 or len(result["to_currency"]) != 3:
        raise ValueError("Currencies must be three-letter codes.")
    rate = finite_nonnegative(result.get("rate"), "rate")
    if rate <= 0:
        raise ValueError("FX rate must be greater than zero.")
    result["rate"] = rate
    result["classification"] = validate_classification(
        result.get("classification", "ASSUMED"), fx=True
    )
    result["source_reference"] = str(result.get("source_reference", result.get("reference", "")))[
        :500
    ]
    check = now or datetime.now(UTC)
    valid_until = result.get("valid_until")
    if valid_until is not None and isinstance(valid_until, datetime) and valid_until <= check:
        result["expired"] = True
    else:
        result["expired"] = False
    return result


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    fx: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    amount = finite_nonnegative(amount, "amount")
    source, target = str(from_currency).upper(), str(to_currency).upper()
    if source == target:
        return {"amount": amount, "currency": target, "comparable": True, "label": "DIRECT"}
    if fx is None:
        return {
            "amount": None,
            "currency": target,
            "comparable": False,
            "label": "NOT DIRECTLY COMPARABLE",
        }
    checked = validate_fx(fx, now=now)
    if checked["expired"] or checked["from_currency"] != source or checked["to_currency"] != target:
        return {
            "amount": None,
            "currency": target,
            "comparable": False,
            "label": "NOT DIRECTLY COMPARABLE",
        }
    return {
        "amount": round(amount * checked["rate"], 6),
        "currency": target,
        "comparable": True,
        "label": "ESTIMATED_CONVERSION",
    }


def landed_cost(inputs: Mapping[str, Any], *, currency: str = "INR") -> dict[str, Any]:
    keys = (
        "unit_supplier_price",
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
    components: list[dict[str, Any]] = []
    for key in keys:
        raw = inputs.get(key, 0)
        value = finite_nonnegative(raw, key) if raw is not None else 0.0
        classification = str(
            inputs.get(f"{key}_classification", "ASSUMED" if value else "UNKNOWN")
        ).upper()
        if classification not in CLASSIFICATIONS and classification not in (
            "ESTIMATED",
            "SUPPLIER_QUOTED",
            "MANUAL",
            "VERIFIED",
            "DERIVED",
        ):
            raise ValueError("Unsupported cost classification.")
        components.append(
            {
                "component": key,
                "value": value,
                "currency": currency.upper(),
                "classification": classification,
                "evidence": inputs.get(f"{key}_evidence"),
                "confidence": inputs.get(
                    f"{key}_confidence", "MEDIUM" if value else "INSUFFICIENT"
                ),
            }
        )
    total = round(sum(item["value"] for item in components), 6)
    quantity = max(int(finite_nonnegative(inputs.get("quantity", 1), "quantity")), 1)
    unknown_critical = any(
        item["classification"] == "UNKNOWN"
        for item in components
        if item["component"] in {"unit_supplier_price", "freight", "duty", "tax"}
    )
    confidence = (
        "INSUFFICIENT"
        if unknown_critical
        else (
            "HIGH"
            if all(
                item["classification"] in {"OBSERVED", "SUPPLIER_QUOTED", "VERIFIED", "CONFIGURED"}
                for item in components
                if item["value"] > 0
            )
            else "MEDIUM"
        )
    )
    return {
        "components": components,
        "landed_cost_per_unit": round(total / quantity, 6),
        "total_landed_cost": total,
        "currency": currency.upper(),
        "confidence": confidence,
    }


def capital_requirement(inputs: Mapping[str, Any], *, currency: str = "INR") -> dict[str, Any]:
    fields = (
        "sample_costs",
        "tooling_setup",
        "inventory_purchase",
        "deposit",
        "balance",
        "freight",
        "insurance",
        "duties_tax",
        "inspection",
        "warehouse_inbound",
        "marketplace_launch_allowance",
        "ads_launch_allowance",
        "working_capital_buffer",
    )
    values = {key: finite_nonnegative(inputs.get(key, 0), key) for key in fields}
    initial = sum(
        values[key]
        for key in fields
        if key
        in {
            "sample_costs",
            "tooling_setup",
            "deposit",
            "freight",
            "insurance",
            "duties_tax",
            "inspection",
        }
    )
    total = sum(values.values())
    return {
        "currency": currency.upper(),
        "components": values,
        "initial_cash_required": round(initial, 6),
        "total_launch_capital": round(total, 6),
        "timed_cash_requirements": cash_timeline(values, currency=currency),
    }


def cash_timeline(values: Mapping[str, Any], *, currency: str = "INR") -> list[dict[str, Any]]:
    order = (
        ("sample", "sample_costs", "relative:before_rfq"),
        ("tooling", "tooling_setup", "relative:before_production"),
        ("deposit", "deposit", "relative:production_start"),
        ("balance", "balance", "relative:pre_shipment"),
        ("freight", "freight", "relative:shipment"),
        ("insurance", "insurance", "relative:shipment"),
        ("duty/tax", "duties_tax", "relative:import"),
        ("inspection", "inspection", "relative:pre_shipment"),
        ("warehouse", "warehouse_inbound", "relative:receiving"),
        ("launch", "marketplace_launch_allowance", "relative:launch"),
        ("Ads launch", "ads_launch_allowance", "relative:launch"),
    )
    return [
        {
            "event": label,
            "expected_timing": timing,
            "amount": float(values.get(key, 0) or 0),
            "currency": currency.upper(),
            "classification": "ASSUMED",
            "assumption_reference": "local deterministic projection",
        }
        for label, key, timing in order
    ]


def sensitivity(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    base_selling = float(inputs.get("selling_price", 0) or 0)

    def evaluate(label: str, patch: dict[str, Any]) -> dict[str, Any]:
        changed = dict(inputs)
        changed.update(patch)
        cost = landed_cost(changed)
        selling = float(changed.get("selling_price", base_selling) or 0)
        contribution = (
            selling
            - cost["landed_cost_per_unit"]
            - float(changed.get("marketplace_fee", 0) or 0)
            - float(changed.get("payment_fee", 0) or 0)
            - float(changed.get("ads_cac", 0) or 0)
            - float(changed.get("returns_allowance", 0) or 0)
        )
        capital = capital_requirement(changed)
        break_even = (
            cost["landed_cost_per_unit"]
            + float(changed.get("marketplace_fee", 0) or 0)
            + float(changed.get("payment_fee", 0) or 0)
            + float(changed.get("returns_allowance", 0) or 0)
        )
        return {
            "scenario": label,
            "landed_cost": cost["landed_cost_per_unit"],
            "contribution": round(contribution, 6),
            "margin": round(contribution / selling, 6) if selling else None,
            "break_even_price": round(break_even, 6),
            "break_even_roas": (
                round(selling / break_even, 6) if break_even > 0 and selling else None
            ),
            "capital": capital["total_launch_capital"],
            "maximum_cac": round(max(0.0, contribution + float(changed.get("ads_cac", 0) or 0)), 6),
        }

    unit = float(inputs.get("unit_supplier_price", 0) or 0)
    freight = float(inputs.get("freight", 0) or 0)
    fx_base = float(inputs.get("fx_rate", 1) or 1)
    quantity = float(inputs.get("quantity", 1) or 1)
    returns = float(inputs.get("returns_allowance", 0) or 0)
    return [
        evaluate("supplier_price_+10%", {"unit_supplier_price": unit * 1.1}),
        evaluate("supplier_price_-10%", {"unit_supplier_price": unit * 0.9}),
        evaluate("freight_+20%", {"freight": freight * 1.2}),
        evaluate("freight_-10%", {"freight": freight * 0.9}),
        evaluate("selling_price_-10%", {"selling_price": base_selling * 0.9}),
        evaluate("selling_price_+10%", {"selling_price": base_selling * 1.1}),
        evaluate("ads_cac_+25%", {"ads_cac": float(inputs.get("ads_cac", 0) or 0) * 1.25}),
        evaluate("returns_allowance_increase", {"returns_allowance": returns * 1.25}),
        evaluate(
            "fx_adverse_movement", {"fx_rate": fx_base * 1.1, "unit_supplier_price": unit * 1.1}
        ),
        evaluate("moq_+20%", {"quantity": max(1.0, quantity * 1.2)}),
        evaluate("base", {}),
    ]


def score_candidate(
    data: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
    *,
    model_version: str = "v1",
) -> dict[str, Any]:
    weights = dict(weights or DEFAULT_SCORE_WEIGHTS)
    if (
        set(weights) != set(SCORE_DIMENSIONS)
        or abs(sum(float(v) for v in weights.values()) - 100) > 1e-6
        or any(float(v) < 0 for v in weights.values())
    ):
        raise ValueError("Sourcing score weights must cover all dimensions and sum to 100.")
    dimensions: list[dict[str, Any]] = []
    total = 0.0
    for key in SCORE_DIMENSIONS:
        raw = data.get(key)
        known = raw is not None
        score = max(0.0, min(100.0, float(raw or 0))) if known else 0.0
        contribution = score * float(weights[key]) / 100.0
        total += contribution
        dimensions.append(
            {
                "dimension": key,
                "raw_score": score if known else None,
                "weight": float(weights[key]),
                "weighted_contribution": round(contribution, 6),
                "reason": (
                    "provided bounded evidence" if known else "missing information is not favorable"
                ),
                "confidence": "MEDIUM" if known else "INSUFFICIENT",
                "supporting_evidence": data.get(f"{key}_evidence"),
            }
        )
    confidence = (
        "INSUFFICIENT"
        if any(item["raw_score"] is None for item in dimensions)
        else ("HIGH" if total >= 75 else "MEDIUM" if total >= 50 else "LOW")
    )
    return {
        "model_version": model_version,
        "score": round(total, 6),
        "confidence": confidence,
        "dimensions": dimensions,
        "weights": weights,
    }


def critic(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    def number(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    checks: tuple[tuple[str, Any, Any], ...] = (
        (
            "supplier_verification",
            lambda v: number(v) is not None and (number(v) or 0) < 50,
            "Supplier verification is weak",
        ),
        (
            "supplier_risk",
            lambda v: number(v) is not None and (number(v) or 0) > 60,
            "Supplier risk is high",
        ),
        (
            "deposit_percent",
            lambda v: number(v) is not None and (number(v) or 0) > 50,
            "Deposit is high",
        ),
        (
            "moq",
            lambda v: number(v) is not None
            and (number(v) or 0) > (number(data.get("max_moq", 10**18)) or 10**18),
            "MOQ exceeds configured limit",
        ),
        (
            "lead_time",
            lambda v: number(v) is not None
            and (number(v) or 0) > (number(data.get("max_lead_time", 10**18)) or 10**18),
            "Lead time exceeds configured limit",
        ),
        (
            "contribution_margin",
            lambda v: number(v) is not None and (number(v) or 0) < 0.2,
            "Contribution margin is low",
        ),
        (
            "landed_cost_confidence",
            lambda v: str(v).upper() in {"LOW", "INSUFFICIENT"},
            "Landed-cost confidence is weak",
        ),
        ("sample_result", lambda v: str(v).upper() in {"FAIL", "REJECTED"}, "Sample failed"),
        (
            "inspection_result",
            lambda v: str(v).upper() in {"FAIL", "REJECTED"},
            "Inspection failed",
        ),
        ("single_source", lambda v: bool(v), "Supplier concentration is single-source"),
    )
    findings = [
        {
            "finding": key,
            "severity": (
                "BLOCK"
                if key in {"supplier_risk", "sample_result", "inspection_result"}
                else "REVIEW_REQUIRED"
            ),
            "reason": reason,
            "evidence": data.get(f"{key}_evidence"),
            "required_review_action": "Review evidence before sourcing",
        }
        for key, test, reason in checks
        if test(data.get(key))
    ]
    extras: tuple[tuple[str, bool, str], ...] = (
        (
            "payment_terms",
            data.get("payment_terms") in {"prepaid", "100%_advance", "UNFAVORABLE"},
            "Payment terms are unfavorable",
        ),
        ("quote_freshness", bool(data.get("quote_stale")), "Quote is stale"),
        (
            "certification",
            str(data.get("certification_confidence", "")).upper() in {"LOW", "UNKNOWN"},
            "Certification evidence is uncertain",
        ),
        (
            "logistics_complexity",
            number(data.get("logistics_complexity")) is not None
            and (number(data.get("logistics_complexity")) or 0) > 70,
            "Logistics complexity is high",
        ),
        (
            "fx_sensitivity",
            number(data.get("fx_sensitivity")) is not None
            and (number(data.get("fx_sensitivity")) or 0) > 20,
            "FX sensitivity is high",
        ),
        (
            "evidence_confidence",
            number(data.get("evidence_confidence")) is not None
            and (number(data.get("evidence_confidence")) or 0) < 50,
            "Evidence confidence is weak",
        ),
    )
    for key, triggered, reason in extras:
        if triggered:
            findings.append(
                {
                    "finding": key,
                    "severity": "REVIEW_REQUIRED",
                    "reason": reason,
                    "evidence": data.get(f"{key}_evidence"),
                    "required_review_action": "Review evidence before sourcing",
                }
            )
    return findings


def concentration(supplier_count: int | None, evidence_sufficient: bool = True) -> str:
    if not evidence_sufficient or not supplier_count or supplier_count < 1:
        return "INSUFFICIENT_EVIDENCE"
    return (
        "SINGLE_SOURCE"
        if supplier_count == 1
        else "DUAL_SOURCE" if supplier_count == 2 else "MULTI_SOURCE"
    )


def sourcing_decision(
    score: float | None,
    *,
    hard_block: bool = False,
    critic_findings: list[Mapping[str, Any]] | None = None,
    confidence: str = "INSUFFICIENT",
) -> str:
    if hard_block:
        return "BLOCKED"
    if score is None or confidence == "INSUFFICIENT":
        return "INSUFFICIENT_EVIDENCE"
    if any(str(item.get("severity", "")).upper() == "BLOCK" for item in (critic_findings or [])):
        return "REJECTED"
    if score >= 80:
        return "STRONG_CANDIDATE"
    if score >= 65:
        return "PROMISING"
    if score >= 45:
        return "REVIEW_REQUIRED"
    return "WEAK"


def evaluate_rules(
    data: Mapping[str, Any], rules: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    rules = dict(rules or {})
    checks: list[dict[str, object]] = []
    pairs = (
        ("max_moq", "moq", "MOQ"),
        ("max_deposit_percent", "deposit_percent", "deposit"),
        ("max_landed_cost", "landed_cost", "landed cost"),
        ("minimum_contribution_margin", "contribution_margin", "contribution margin"),
        ("maximum_lead_time", "lead_time", "lead time"),
        ("minimum_supplier_verification", "supplier_verification", "supplier verification"),
        ("maximum_supplier_risk", "supplier_risk", "supplier risk"),
        ("maximum_capital_requirement", "capital_requirement", "capital requirement"),
    )
    for rule_key, data_key, label in pairs:
        if rule_key not in rules or data.get(data_key) is None:
            checks.append(
                {
                    "rule": rule_key,
                    "action": "REVIEW_REQUIRED",
                    "reason": f"{label} evidence is missing",
                }
            )
            continue
        actual, limit = float(data[data_key]), float(rules[rule_key])
        passing = (
            actual <= limit
            if rule_key not in {"minimum_contribution_margin", "minimum_supplier_verification"}
            else actual >= limit
        )
        checks.append(
            {
                "rule": rule_key,
                "action": "ALLOW" if passing else "BLOCK",
                "actual": actual,
                "limit": limit,
                "reason": (
                    "within configured boundary"
                    if passing
                    else f"{label} violates configured boundary"
                ),
            }
        )
    for rule_key, data_key, label in (
        ("sample_required", "sample_result", "sample"),
        ("inspection_required", "inspection_result", "inspection"),
        ("required_certification", "certification", "certification"),
    ):
        if rules.get(rule_key) and not data.get(data_key):
            checks.append(
                {
                    "rule": rule_key,
                    "action": "REVIEW_REQUIRED",
                    "reason": f"{label} evidence is required",
                }
            )
    if "minimum_landed_cost_confidence" in rules:
        rank = {"INSUFFICIENT": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
        actual = rank.get(str(data.get("landed_cost_confidence", "INSUFFICIENT")).upper(), 0)
        limit = rank.get(str(rules["minimum_landed_cost_confidence"]).upper(), 3)
        checks.append(
            {
                "rule": "minimum_landed_cost_confidence",
                "action": "ALLOW" if actual >= limit else "BLOCK",
                "actual": actual,
                "limit": limit,
                "reason": (
                    "confidence meets configured boundary"
                    if actual >= limit
                    else "landed-cost confidence is below configured boundary"
                ),
            }
        )
    action = (
        "BLOCK"
        if any(c["action"] == "BLOCK" for c in checks)
        else "REVIEW_REQUIRED" if any(c["action"] == "REVIEW_REQUIRED" for c in checks) else "ALLOW"
    )
    return {"action": action, "checks": checks}


def negotiation_delta(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "unit_price",
        "moq",
        "sample_price",
        "deposit",
        "balance",
        "lead_time",
        "tooling",
        "packaging",
    )
    changes = {}
    for key in keys:
        if key in previous and key in current:
            old, new = float(previous[key]), float(current[key])
            changes[key] = {
                "previous": old,
                "current": new,
                "delta": round(new - old, 6),
                "direction": "IMPROVED" if new < old else "WORSENED" if new > old else "UNCHANGED",
            }
        else:
            changes[key] = {"direction": "NOT_COMPARABLE"}
    directions = {v["direction"] for v in changes.values()}
    comparable = directions - {"NOT_COMPARABLE"}
    overall = (
        "NOT_COMPARABLE"
        if not comparable
        else (
            "IMPROVED"
            if comparable <= {"IMPROVED", "UNCHANGED"}
            else (
                "WORSENED"
                if comparable <= {"WORSENED", "UNCHANGED"}
                else "UNCHANGED" if comparable == {"UNCHANGED"} else "NOT_COMPARABLE"
            )
        )
    )
    return {"overall": overall, "changes": changes}


def _safe_report_text(value: Any) -> str:
    text = str(value)
    text = re.sub(
        r"(?:postgres(?:ql)?|mysql|sqlite)://[^\s<]+",
        "[redacted database reference]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:bearer\s+|api[_-]?key[=:]?)\S+", "[redacted credential]", text, flags=re.IGNORECASE
    )
    return text


def safe_report(payload: Mapping[str, Any], format: str = "json") -> dict[str, Any] | str:
    format = format.lower()
    if format == "json":
        return dict(payload)
    if format == "markdown":
        return "# Sourcing report\n\n" + "\n".join(
            f"- **{escape(str(k))}**: {escape(_safe_report_text(v))}" for k, v in payload.items()
        )
    if format == "html":
        return (
            "<article><h1>Sourcing report</h1>"
            + "".join(
                f"<p><strong>{escape(str(k))}</strong>: {escape(_safe_report_text(v))}</p>"
                for k, v in payload.items()
            )
            + "</article>"
        )
    raise ValueError("Unsupported report format.")
