"""Deterministic projections and gates for supplier shortlisting."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from vayujit_api.intelligence.sourcing_closure import capital_requirement, landed_cost, sensitivity


def evidence(supplier: Any) -> dict[str, Any]:
    view = dict(getattr(supplier, "view_json", None) or {})
    commercial = view.get("commercial", {})
    if isinstance(commercial, dict):
        view.update({key: value for key, value in commercial.items() if key not in view})
        price = commercial.get("price")
        if isinstance(price, Mapping):
            # Canonical supplier views retain price observations under the
            # commercial projection. Reuse those observations; never invent
            # a value when the projection is absent.
            if view.get("unit_supplier_price") is None:
                observed = price.get("median")
                if observed is None:
                    observed = price.get("minimum")
                if observed is not None:
                    view["unit_supplier_price"] = observed
            safety = commercial.get("currency_safety")
            if isinstance(safety, Mapping) and view.get("currency") is None:
                currencies = safety.get("currencies")
                if isinstance(currencies, list) and len(currencies) == 1:
                    view["currency"] = currencies[0]
    view.setdefault("freshness", getattr(supplier, "freshness_status", "unknown"))
    view.setdefault("confidence", float(getattr(supplier, "confidence_score", 0) or 0))
    return view


def landed_cost_projection(context: Any, supplier: Any) -> dict[str, Any]:
    ev = evidence(supplier)
    payload = cast(dict[str, Any], getattr(context, "payload", None) or {})
    inputs = dict(ev.get("landed_cost_inputs", {}))
    keys = {
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
        "quantity",
        "currency",
    }
    inputs.update({key: ev[key] for key in keys if key in ev})
    currency = str(inputs.get("currency") or payload.get("budget_currency") or "INR").upper()
    missing = [
        key for key in ("unit_supplier_price", "freight", "duty", "tax") if inputs.get(key) is None
    ]
    lineage = {"supplier_id": str(supplier.id), "context_id": str(context.id)}
    if missing:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "missing": missing,
            "currency": currency,
            "lineage": lineage,
        }
    try:
        result = landed_cost(inputs, currency=currency)
    except ValueError:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "missing": ["valid_landed_cost_inputs"],
            "currency": currency,
            "lineage": lineage,
        }
    return {
        "status": (
            "AVAILABLE" if result["confidence"] != "INSUFFICIENT" else "INSUFFICIENT_EVIDENCE"
        ),
        "landed_cost": result["landed_cost_per_unit"],
        "total_landed_cost": result["total_landed_cost"],
        "component_breakdown": result["components"],
        "assumption_references": [
            item["evidence"] for item in result["components"] if item.get("evidence")
        ],
        "confidence": result["confidence"],
        "currency": result["currency"],
        "calculation_version": "sourcing-closure-v1",
        "lineage": lineage,
    }


def economics_projection(context: Any, supplier: Any) -> dict[str, Any]:
    ev = evidence(supplier)
    inputs = dict(ev.get("economics_inputs", {}))
    keys = {
        "unit_supplier_price",
        "selling_price",
        "quantity",
        "freight",
        "insurance",
        "duty",
        "tax",
        "marketplace_fee",
        "payment_fee",
        "ads_cac",
        "returns_allowance",
        "sample_costs",
        "tooling_setup",
        "deposit",
        "balance",
        "working_capital_buffer",
    }
    inputs.update({key: ev[key] for key in keys if key in ev})
    if inputs.get("unit_supplier_price") is None or inputs.get("selling_price") is None:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "missing": ["unit_supplier_price", "selling_price"],
        }
    currency = str(
        (getattr(context, "payload", None) or {}).get("budget_currency") or "INR"
    ).upper()
    try:
        scenarios = sensitivity(inputs)
        capital = capital_requirement(inputs, currency=currency)
    except (TypeError, ValueError):
        return {"status": "INSUFFICIENT_EVIDENCE", "missing": ["valid_economics_inputs"]}
    base = next((item for item in scenarios if item.get("scenario") == "base"), scenarios[-1])
    return {
        "status": "AVAILABLE",
        "contribution": base.get("contribution"),
        "margin": base.get("margin"),
        "max_cac": base.get("maximum_cac"),
        "break_even_price": base.get("break_even_price"),
        "capital_requirement": capital["total_launch_capital"],
        "cash_timeline": capital["timed_cash_requirements"],
        "sensitivity": scenarios,
        "scenario_version": "sourcing-closure-v1",
        "currency": currency,
        "lineage": {"supplier_id": str(supplier.id), "context_id": str(context.id)},
    }


def contradiction_gate(value: Any) -> dict[str, Any]:
    if value in (None, [], {}, False):
        return {"outcome": "ALLOW", "contradictions": []}
    values = list(value) if isinstance(value, (list, tuple, set)) else [value]
    if all(isinstance(item, Mapping) and item.get("resolved") is True for item in values):
        return {"outcome": "ALLOW", "contradictions": values}
    material = [item for item in values if isinstance(item, Mapping) and item.get("material", True)]
    return {"outcome": "BLOCK" if material else "REVIEW_REQUIRED", "contradictions": values}


def risk_gate(value: Any) -> dict[str, str]:
    state = str(value or "UNKNOWN").upper()
    outcome = (
        "ALLOW"
        if state in {"LOW", "RESOLVED"}
        else "BLOCK" if state == "HIGH" else "REVIEW_REQUIRED"
    )
    return {"risk": state, "outcome": outcome}


def freshness_gate(value: Any) -> dict[str, str]:
    state = str(value or "UNKNOWN").upper()
    if state not in {"FRESH", "AGING", "STALE", "EXPIRED", "UNKNOWN"}:
        state = "UNKNOWN"
    return {"freshness": state, "outcome": "ALLOW" if state == "FRESH" else "REVIEW_REQUIRED"}


def currency_gate(context: Any, supplier: Any) -> dict[str, Any]:
    context_currency = str(
        (getattr(context, "payload", None) or {}).get("budget_currency") or ""
    ).upper()
    supplier_currency = str(evidence(supplier).get("currency") or "").upper()
    if not context_currency or not supplier_currency:
        return {
            "status": "UNKNOWN",
            "outcome": "REVIEW_REQUIRED",
            "context_currency": context_currency or None,
            "supplier_currency": supplier_currency or None,
        }
    comparable = context_currency == supplier_currency
    return {
        "status": "DIRECTLY_COMPARABLE" if comparable else "NOT_DIRECTLY_COMPARABLE",
        "outcome": "ALLOW" if comparable else "REVIEW_REQUIRED",
        "context_currency": context_currency,
        "supplier_currency": supplier_currency,
    }


def diversity_gate(suppliers: list[Any]) -> dict[str, Any]:
    sources: set[str] = set()
    domains: set[str] = set()
    for supplier in suppliers:
        ev = evidence(supplier)
        freshness = ev.get("freshness")
        freshness_sources = freshness.get("sources", []) if isinstance(freshness, Mapping) else []
        source_rows = ev.get("sources") or ev.get("source_types") or freshness_sources
        if isinstance(source_rows, list):
            sources.update(
                (
                    str(item.get("source_type", item)).casefold()
                    if isinstance(item, Mapping)
                    else str(item).casefold()
                )
                for item in source_rows
            )
        domain = ev.get("domain") or ev.get("website_domain")
        if domain:
            domains.add(str(domain).casefold())
    independent = len(sources) >= 2 or len(domains) >= 2
    return {
        "outcome": "ALLOW" if independent else "REVIEW_REQUIRED" if suppliers else "BLOCK",
        "supplier_count": len(suppliers),
        "independent_sources": len(sources),
        "independent_domains": len(domains),
        "confidence_not_inflated": True,
    }


def verification_readiness(supplier: Any) -> dict[str, Any]:
    ev = evidence(supplier)
    required = {
        "business_identity": "business_identity",
        "certification": "certifications",
        "facility": "facilities",
        "commercial_claims": "commercial",
        "sample": "sample",
        "inspection": "inspection",
    }
    outstanding = [label for label, key in required.items() if not ev.get(key)]
    return {"status": "READY" if not outstanding else "REVIEW_REQUIRED", "outstanding": outstanding}


def readiness(context: Any, supplier: Any, *, sample: bool = False) -> dict[str, Any]:
    ev = evidence(supplier)
    payload = cast(dict[str, Any], getattr(context, "payload", None) or {})
    capabilities = {
        str(item).casefold() for item in ev.get("capabilities", []) if isinstance(item, str)
    }
    certifications = {
        str(item).casefold() for item in ev.get("certifications", []) if isinstance(item, str)
    }
    missing = [
        f"required_capability:{item}"
        for item in payload.get("required_capabilities", [])
        if str(item).casefold() not in capabilities
    ]
    missing += [
        f"required_certification:{item}"
        for item in payload.get("required_certifications", [])
        if str(item).casefold() not in certifications
    ]
    verification = verification_readiness(supplier)
    contradiction = contradiction_gate(ev.get("contradictions"))
    risk = risk_gate(ev.get("risk"))
    freshness = freshness_gate(getattr(supplier, "freshness_status", "unknown"))
    currency = currency_gate(context, supplier)
    commercial = ev.get("commercial")
    commercial_complete = bool(ev.get("unit_supplier_price")) and bool(
        isinstance(commercial, Mapping)
        and isinstance(commercial.get("currency_safety"), Mapping)
        and commercial["currency_safety"].get("status") == "DIRECTLY_COMPARABLE"
    )
    if missing or risk["outcome"] == "BLOCK" or contradiction["outcome"] == "BLOCK":
        status = "BLOCKED"
    elif not commercial_complete:
        status = "INSUFFICIENT_EVIDENCE"
    elif (
        verification["status"] != "READY"
        or freshness["outcome"] != "ALLOW"
        or currency["outcome"] != "ALLOW"
        or contradiction["outcome"] != "ALLOW"
        or risk["outcome"] != "ALLOW"
    ):
        status = "REVIEW_REQUIRED"
    else:
        status = "READY_FOR_HUMAN_SAMPLE" if sample else "READY_FOR_HUMAN_RFQ"
    return {
        "status": status,
        "verification": verification,
        "risk": risk,
        "freshness": freshness,
        "contradiction": contradiction,
        "currency": currency,
        "commercial_complete": commercial_complete,
        "reasons": missing,
    }
