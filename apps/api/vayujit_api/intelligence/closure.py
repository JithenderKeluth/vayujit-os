# ruff: noqa: E501
"""Pure deterministic closure contracts for Winning Product Research.

This module intentionally has no network/provider dependencies.  It is safe to use
from API handlers, workers, and tests without importing ORM internals.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

RESTRICTION_ATTRIBUTES = (
    "glass",
    "fragile",
    "battery",
    "lithium_battery",
    "liquid",
    "powder",
    "electronics",
    "electrical",
    "wireless",
    "childrens_product",
    "food_contact",
    "cosmetics",
    "medical",
    "sharp_item",
    "magnetic",
    "hazardous",
    "oversized",
    "restricted_category",
    "brand_restricted",
)
RESTRICTION_ACTIONS = ("ALLOW", "WARN", "REVIEW_REQUIRED", "BLOCK")
POLICY_LEVELS = ("GLOBAL", "MARKET", "MARKETPLACE", "CATEGORY", "PROFILE", "MISSION")
ECONOMIC_CLASSIFICATIONS = ("OBSERVED", "ASSUMED", "ESTIMATED", "UNKNOWN")
RECOVERY_MATRIX: dict[str, tuple[str, ...]] = {
    "provider_unavailable": ("retry", "reconcile"),
    "provider_rate_limited": ("retry", "wait"),
    "unsafe_source": ("review_source", "cancel"),
    "invalid_fixture": ("review_source", "cancel"),
    "invalid_evidence": ("refresh_evidence", "cancel"),
    "stale_evidence": ("refresh_evidence", "review_source"),
    "scoring_failure": ("retry", "review_rules"),
    "rule_evaluation_failure": ("review_rules", "retry"),
    "checkpoint_invalid": ("reconcile", "cancel"),
}


@dataclass(frozen=True)
class NormalizedPhysical:
    weight_kg: float | None = None
    length_cm: float | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    volume_cm3: float | None = None
    volumetric_weight_kg: float | None = None


def normalize_physical(value: Mapping[str, Any]) -> NormalizedPhysical:
    """Normalize common mass/length units and derive volume and volumetric weight."""

    def mass_kg(key: str) -> float | None:
        raw = value.get(key)
        if raw is None:
            return None
        if isinstance(raw, Mapping):
            unit = str(raw.get("unit", "kg")).lower()
            amount = float(raw.get("value", 0))
        else:
            unit = "kg"
            amount = float(raw)
        factors = {"kg": 1.0, "g": 0.001, "gram": 0.001, "grams": 0.001, "lb": 0.45359237}
        if unit not in factors:
            raise ValueError(f"Unsupported mass unit: {unit}")
        return amount * factors[unit]

    def length_cm(key: str) -> float | None:
        raw = value.get(key)
        if raw is None:
            return None
        if isinstance(raw, Mapping):
            unit = str(raw.get("unit", "cm")).lower()
            amount = float(raw.get("value", 0))
        else:
            unit = "cm"
            amount = float(raw)
        factors = {"cm": 1.0, "m": 100.0, "mm": 0.1, "in": 2.54}
        if unit not in factors:
            raise ValueError(f"Unsupported length unit: {unit}")
        return amount * factors[unit]

    weight = mass_kg("weight") if "weight" in value else mass_kg("weight_kg")
    length = length_cm("length") if "length" in value else length_cm("length_cm")
    width = length_cm("width") if "width" in value else length_cm("width_cm")
    height = length_cm("height") if "height" in value else length_cm("height_cm")
    volume = None
    if length is not None and width is not None and height is not None:
        volume = length * width * height
    raw_volume = value.get("volume_cm3")
    if raw_volume is not None:
        volume = float(raw_volume)
    volumetric = volume / 5000 if volume is not None else None
    return NormalizedPhysical(weight, length, width, height, volume, volumetric)


def evaluate_physical_rules(
    actual: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> dict[str, Any]:
    normalized = normalize_physical(actual)
    values = {
        "weight_kg": normalized.weight_kg,
        "length_cm": normalized.length_cm,
        "width_cm": normalized.width_cm,
        "height_cm": normalized.height_cm,
        "volume_cm3": normalized.volume_cm3,
        "volumetric_weight_kg": normalized.volumetric_weight_kg,
    }
    checks: list[dict[str, Any]] = []
    for key, threshold in thresholds.items():
        if threshold is None or key not in values:
            continue
        if isinstance(threshold, Mapping):
            limit = normalize_physical({key: threshold}).__dict__.get(key)
            if limit is None:
                limit = float(threshold.get("value", 0))
        else:
            limit = float(threshold)
        value = values[key]
        if value is None:
            checks.append(
                {"dimension": key, "status": "REVIEW_REQUIRED", "reason": "value_missing"}
            )
        else:
            checks.append(
                {
                    "dimension": key,
                    "actual": value,
                    "threshold": limit,
                    "status": "PASS" if value <= limit else "BLOCK",
                }
            )
    status = (
        "BLOCK"
        if any(row["status"] == "BLOCK" for row in checks)
        else (
            "REVIEW_REQUIRED"
            if any(row["status"] == "REVIEW_REQUIRED" for row in checks)
            else "PASS"
        )
    )
    return {"status": status, "normalized": values, "checks": checks}


def evaluate_policy_hierarchy(
    rules: Mapping[str, Iterable[str]], *, authorized_override: bool = False
) -> dict[str, Any]:
    """Resolve policy actions with hard BLOCK precedence across scope levels."""
    normalized: dict[str, list[str]] = {
        level.upper(): [str(v).upper() for v in values] for level, values in rules.items()
    }
    blocks = [
        (level, action)
        for level in POLICY_LEVELS
        for action in normalized.get(level, [])
        if action == "BLOCK"
    ]
    if blocks and not authorized_override:
        return {
            "action": "BLOCK",
            "blocked": True,
            "winning_level": blocks[0][0],
            "evaluated": normalized,
        }
    order = {"BLOCK": 4, "REVIEW_REQUIRED": 3, "WARN": 2, "ALLOW": 1}
    candidates = [
        (action, level)
        for level in POLICY_LEVELS
        for action in normalized.get(level, [])
        if action in order and (action != "BLOCK" or not authorized_override)
    ]
    action, level = (
        max(candidates, key=lambda item: (order[item[0]], -POLICY_LEVELS.index(item[1])))
        if candidates
        else ("ALLOW", "GLOBAL")
    )
    return {
        "action": action,
        "blocked": action == "BLOCK",
        "winning_level": level,
        "evaluated": normalized,
    }


def validate_restriction_matrix(matrix: Mapping[str, str]) -> dict[str, str]:
    unknown = set(matrix) - set(RESTRICTION_ATTRIBUTES)
    invalid = {
        key: value for key, value in matrix.items() if str(value).upper() not in RESTRICTION_ACTIONS
    }
    if unknown:
        raise ValueError(f"Unknown restriction attributes: {sorted(unknown)}")
    if invalid:
        raise ValueError(f"Invalid restriction actions: {invalid}")
    return {key: str(value).upper() for key, value in matrix.items()}


def economic_input(
    value: Any,
    classification: str,
    *,
    currency: str = "INR",
    evidence_id: str | None = None,
    reason: str = "",
    confidence: float = 0.0,
) -> dict[str, Any]:
    classification = classification.upper()
    if classification not in ECONOMIC_CLASSIFICATIONS:
        raise ValueError("Invalid economic input classification")
    if len(currency) != 3:
        raise ValueError("Currency must be a three-letter code")
    if classification == "OBSERVED" and not evidence_id:
        raise ValueError("Observed economic inputs require source evidence")
    return {
        "classification": classification,
        "value": value,
        "currency": currency.upper(),
        "source_evidence_id": evidence_id,
        "assumption_reason": reason,
        "confidence": max(0.0, min(1.0, float(confidence))),
    }


def estimate_economics(inputs: Mapping[str, Any], *, currency: str = "INR") -> dict[str, Any]:
    """Return bounded estimate economics with explicit assumptions and capital."""
    keys = (
        "selling_price",
        "sourcing_cost",
        "marketplace_fee",
        "payment_fee",
        "fulfilment",
        "shipping",
        "advertising_allowance",
        "return_allowance",
        "tax_assumption",
    )
    values: dict[str, dict[str, Any]] = {}
    for key in keys:
        raw = inputs.get(key)
        if isinstance(raw, Mapping) and "classification" in raw:
            values[key] = economic_input(
                raw.get("value"),
                str(raw["classification"]),
                currency=str(raw.get("currency", currency)),
                evidence_id=raw.get("source_evidence_id"),
                reason=str(raw.get("assumption_reason", "")),
                confidence=float(raw.get("confidence", 0)),
            )
        elif raw is None:
            values[key] = economic_input(None, "UNKNOWN", currency=currency, reason="not provided")
        else:
            values[key] = economic_input(
                raw,
                "ESTIMATED",
                currency=currency,
                reason="deterministic local estimate",
                confidence=0.5,
            )

    def number(key: str) -> float:
        value = values[key]["value"]
        return float(value or 0)

    price = number("selling_price")
    landed = sum(number(key) for key in ("sourcing_cost", "fulfilment", "shipping"))
    variable = landed + sum(
        number(key)
        for key in (
            "marketplace_fee",
            "payment_fee",
            "advertising_allowance",
            "return_allowance",
            "tax_assumption",
        )
    )
    contribution = price - variable
    margin = contribution / price if price else 0.0
    break_even = variable
    max_cac = max(0.0, contribution)
    roas = price / max_cac if max_cac else None
    moq = int(inputs.get("moq", 1) or 1)
    launch = float(inputs.get("launch_allowance", 0) or 0)
    inbound = float(inputs.get("inbound_logistics_allowance", number("shipping")) or 0)
    buffer = float(inputs.get("working_capital_buffer", 0) or 0)
    capital = moq * number("sourcing_cost") + inbound + launch + buffer
    confidence = sum(item["confidence"] for item in values.values()) / len(values)
    return {
        "inputs": values,
        "outputs": {
            "estimated_landed_like_acquisition_basis": landed,
            "estimated_gross_contribution": contribution,
            "estimated_contribution_margin": margin,
            "estimated_break_even_selling_price": break_even,
            "estimated_maximum_cac": max_cac,
            "estimated_break_even_roas": roas,
            "estimated_initial_inventory_investment": moq * number("sourcing_cost"),
            "estimated_initial_capital": capital,
        },
        "confidence": confidence,
        "supplier_confirmed": False,
        "assumptions": [
            "All values are bounded estimates; supplier confirmation is not implemented."
        ],
    }


def legal_risk_flags(
    *, title: str, brand: str | None = None, attributes: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    text = f"{title} {brand or ''}".lower()
    attrs = attributes or {}
    flags = {
        "brand_dominated": bool(brand),
        "trademark_sensitive_keyword": any(
            word in text for word in ("nike", "apple", "disney", "lego")
        ),
        "restricted_brand_reference": bool(attrs.get("brand_restricted")),
        "possible_patent_review": bool(attrs.get("patent_risk")),
        "marketplace_brand_restriction": bool(attrs.get("brand_restricted")),
    }
    return {
        "flags": flags,
        "label": (
            "LEGAL REVIEW MAY BE REQUIRED"
            if any(flags.values())
            else "LEGAL REVIEW MAY BE REQUIRED"
        ),
        "legal_clearance": False,
    }


def source_diversity(
    source_classes: Iterable[str], critical_signal_sources: Iterable[str] | None = None
) -> dict[str, Any]:
    classes = {str(item) for item in source_classes}
    critical = {str(item) for item in (critical_signal_sources or ())}
    return {
        "independent_source_count": len(classes),
        "critical_signal_source_count": len(critical),
        "source_diversity_score": min(1.0, len(classes) / 5.0),
        "source_classes": sorted(classes),
    }


def evidence_quality(
    *,
    freshness: Iterable[str],
    source_diversity_score: float,
    verification_states: Iterable[str],
    observation_count: int,
    critical_signal_completeness: float,
    stale_evidence_ratio: float,
) -> dict[str, Any]:
    fresh = list(freshness)
    fresh_score = sum(1 for item in fresh if item == "fresh") / max(1, len(fresh))
    verified = list(verification_states)
    verification_score = sum(1 for item in verified if item == "verified") / max(1, len(verified))
    observation_score = min(1.0, observation_count / 5.0)
    stale_penalty = max(0.0, min(1.0, stale_evidence_ratio))
    score = round(
        max(
            0.0,
            min(
                1.0,
                0.25 * fresh_score
                + 0.2 * source_diversity_score
                + 0.2 * verification_score
                + 0.15 * observation_score
                + 0.2 * critical_signal_completeness
                - 0.2 * stale_penalty,
            ),
        ),
        4,
    )
    missing = []
    if not fresh:
        missing.append("freshness")
    if source_diversity_score < 0.4:
        missing.append("source_diversity")
    if critical_signal_completeness < 1:
        missing.append("critical_signals")
    return {
        "quality_score": score,
        "confidence": score,
        "missing_evidence": missing,
        "reasons": [
            "deterministic evidence-quality model",
            f"stale evidence ratio={stale_penalty:.2f}",
        ],
    }


def validate_score_weights(
    weights: Mapping[str, Any], known_dimensions: Iterable[str]
) -> dict[str, float]:
    known = set(known_dimensions)
    if set(weights) != known:
        raise ValueError("Scoring weights must contain known dimensions only")
    result = {str(key): float(value) for key, value in weights.items()}
    if any(value < 0 for value in result.values()):
        raise ValueError("Scoring weights cannot be negative")
    if abs(sum(result.values()) - 100.0) > 1e-6:
        raise ValueError("Scoring weights must sum to 100")
    return result


def rank_opportunities(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(item) for item in items),
        key=lambda item: (
            bool(item.get("hard_blocked")),
            -float(item.get("score", 0)),
            -float(item.get("confidence", 0)),
            float(item.get("risk", 100)),
            str(item.get("id", "")),
        ),
    )
