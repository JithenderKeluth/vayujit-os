"""Bounded, deterministic and read-only supplier portfolio simulations (8E.4)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.portfolio_analysis import (
    _assessment,
    _dedupe_members,
    _members,
    calculate_concentration,
    calculate_dependencies,
    calculate_readiness,
)
from vayujit_api.intelligence.portfolio_models import SupplierPortfolioContext
from vayujit_api.intelligence.resilience_analysis import calculate_resilience
from vayujit_api.intelligence.simulation_models import (
    PortfolioSimulation,
    PortfolioSimulationResult,
)
from vayujit_api.intelligence.simulation_schemas import SimulationRequest

SIMULATION_POLICY_VERSION = "8E.4-simulation-v1"
SIMULATION_TYPES = (
    "SUPPLIER_UNAVAILABLE",
    "SUPPLIER_CAPACITY_REDUCTION",
    "COUNTRY_DISRUPTION",
    "REGION_DISRUPTION",
    "LEAD_TIME_INCREASE",
    "LANDED_COST_INCREASE",
    "FX_SHOCK",
    "MOQ_INCREASE",
    "AVAILABILITY_REDUCTION",
    "MULTI_SUPPLIER_DISRUPTION",
    "CUSTOM",
)
MAX_AFFECTED_SUPPLIERS = 3
MAX_AFFECTED_PRODUCTS = 100
MAX_PERCENT = Decimal("100")
MAX_DAYS = Decimal("365")
_CURRENCY_PAIR = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _number(value: Decimal | None) -> float | None:
    return float(value.quantize(Decimal("0.0001"))) if value is not None else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    parsed = _decimal(value)
    if parsed is not None and not isinstance(value, (str, bool)):
        return format(parsed.normalize(), "f")
    return value


def normalize_assumptions(assumptions: dict[str, object]) -> dict[str, Any]:
    normalized = _jsonable(assumptions)
    if not isinstance(normalized, dict):
        raise HTTPException(422, "Simulation assumptions must be an object.")
    return normalized


def assumption_hash(assumptions: dict[str, object]) -> str:
    payload = json.dumps(normalize_assumptions(assumptions), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _percent(value: Any, name: str) -> Decimal | None:
    if value is None:
        return None
    parsed = _decimal(value)
    if parsed is None or parsed < 0 or parsed > MAX_PERCENT:
        raise HTTPException(422, f"{name} must be a finite percentage from 0 to 100.")
    return parsed


def _days(value: Any) -> Decimal | None:
    if value is None:
        return None
    parsed = _decimal(value)
    if parsed is None or parsed < 0 or parsed > MAX_DAYS:
        raise HTTPException(422, "increase_days must be finite, non-negative, and at most 365.")
    return parsed


def _products(member: dict[str, Any]) -> set[str]:
    return {str(value) for value in member.get("associated_products") or []}


def _geo(member: dict[str, Any]) -> tuple[str, str]:
    value = str(member.get("country_region") or "UNKNOWN").strip().upper()
    return value or "UNKNOWN", value or "UNKNOWN"


def _shares(
    members: list[dict[str, Any]], affected: set[str], reduction_percent: Decimal = Decimal("100")
) -> dict[str, Any]:
    suppliers: dict[str, Decimal] = {}
    countries: dict[str, Decimal] = {}
    regions: dict[str, Decimal] = {}
    total = Decimal("0")
    exposed = Decimal("0")
    products: set[str] = set()
    for member in members:
        supplier = str(member.get("supplier_id"))
        allocation = _decimal(member.get("allocation_percent")) or Decimal("0")
        total += allocation
        reduction = reduction_percent if supplier in affected else Decimal("0")
        simulated = allocation * (Decimal("100") - reduction) / Decimal("100")
        if supplier in affected and simulated < allocation:
            exposed += allocation - simulated
            products.update(_products(member))
        if simulated <= 0:
            continue
        suppliers[supplier] = suppliers.get(supplier, Decimal("0")) + simulated
        country, region = _geo(member)
        countries[country] = countries.get(country, Decimal("0")) + simulated
        regions[region] = regions.get(region, Decimal("0")) + simulated
    remaining = sum(suppliers.values(), Decimal("0"))

    def metrics(values: dict[str, Decimal]) -> dict[str, Any]:
        denominator = remaining or Decimal("1")
        fractions = [value / denominator for value in values.values()]
        ordered = sorted(values.values(), reverse=True)
        return {
            "largest_share": _number((ordered[0] / denominator) * 100 if ordered else None),
            "top_three_share": _number(sum(ordered[:3], Decimal("0")) / denominator * 100),
            "hhi": _number(sum((fraction * fraction for fraction in fractions), Decimal("0"))),
            "group_count": len(values),
        }

    return {
        "total_allocation": _number(total),
        "remaining_allocation": _number(remaining),
        "allocation_exposed": _number(exposed),
        "uncovered_exposure": _number(exposed),
        "allocation_by_supplier": {key: _number(value) for key, value in sorted(suppliers.items())},
        "allocation_by_country": {key: _number(value) for key, value in sorted(countries.items())},
        "allocation_by_region": {key: _number(value) for key, value in sorted(regions.items())},
        "supplier_concentration": metrics(suppliers),
        "country_concentration": metrics(countries),
        "region_concentration": metrics(regions),
        "affected_product_ids": sorted(products),
    }


def _affected(kind: str, assumptions: dict[str, Any], members: list[dict[str, Any]]) -> set[str]:
    if kind in {"SUPPLIER_UNAVAILABLE", "SUPPLIER_CAPACITY_REDUCTION", "AVAILABILITY_REDUCTION"}:
        value = assumptions.get("supplier_ids", assumptions.get("supplier_id"))
        values: list[Any] = value if isinstance(value, list) else [value]
        return {str(item) for item in values if item}
    if kind == "MULTI_SUPPLIER_DISRUPTION":
        raw_values = assumptions.get("supplier_ids")
        if not isinstance(raw_values, list) or not raw_values:
            raise HTTPException(422, "supplier_ids is required for multi-supplier disruption.")
        multi_values: list[Any] = raw_values
        return {str(item) for item in multi_values}
    if kind == "COUNTRY_DISRUPTION":
        country = str(assumptions.get("country") or "").strip().upper()
        if not country:
            raise HTTPException(422, "country is required for country disruption.")
        return {str(member.get("supplier_id")) for member in members if _geo(member)[0] == country}
    if kind == "REGION_DISRUPTION":
        region = str(assumptions.get("region") or "").strip().upper()
        if not region:
            raise HTTPException(422, "region is required for region disruption.")
        return {str(member.get("supplier_id")) for member in members if _geo(member)[1] == region}
    return set()


def _validate(
    request: SimulationRequest, members: list[dict[str, Any]]
) -> tuple[dict[str, Any], set[str], list[str]]:
    assumptions = normalize_assumptions(request.assumptions)
    affected = _affected(request.simulation_type, assumptions, members)
    known = {str(member.get("supplier_id")) for member in members}
    if affected - known:
        raise HTTPException(404, "Simulation supplier reference was not found in this portfolio.")
    if len(affected) > MAX_AFFECTED_SUPPLIERS:
        raise HTTPException(422, "Simulation exceeds the maximum affected supplier budget of 3.")
    for key in (
        "capacity_reduction_percent",
        "availability_reduction_percent",
        "increase_percent",
        "moq_increase_percent",
    ):
        _percent(assumptions.get(key), key)
    _days(assumptions.get("increase_days"))
    if request.simulation_type == "FX_SHOCK" and not _CURRENCY_PAIR.fullmatch(
        str(assumptions.get("currency_pair") or "").upper()
    ):
        raise HTTPException(422, "currency_pair must use the ISO format XXX/XXX.")
    if request.simulation_type == "CUSTOM":
        primitives = assumptions.get("primitives")
        allowed = {
            "supplier_unavailable",
            "lead_time_increase",
            "landed_cost_increase",
            "moq_increase",
        }
        if (
            not isinstance(primitives, list)
            or len(primitives) > 8
            or any(
                not isinstance(item, dict) or item.get("type") not in allowed for item in primitives
            )
        ):
            raise HTTPException(422, "CUSTOM contains an unsupported simulation primitive.")
    products = sorted(
        {
            product
            for member in members
            if str(member.get("supplier_id")) in affected
            for product in _products(member)
        }
    )
    if len(products) > MAX_AFFECTED_PRODUCTS:
        raise HTTPException(422, "Simulation exceeds the maximum affected product budget of 100.")
    return assumptions, affected, products


def _payload(
    simulation: PortfolioSimulation,
    result: PortfolioSimulationResult,
    current_assessment_version_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    return {
        "id": str(simulation.id),
        "owner_id": str(simulation.owner_id),
        "portfolio_id": str(simulation.portfolio_id),
        "assessment_version_id": str(simulation.assessment_version_id),
        "simulation_type": simulation.simulation_type,
        "policy_version": simulation.policy_version,
        "idempotency_key": simulation.idempotency_key,
        "assumption_hash": simulation.assumption_hash,
        "assumptions": simulation.assumptions,
        "status": simulation.status,
        "staleness": (
            "BASELINE_CURRENT"
            if current_assessment_version_id == simulation.assessment_version_id
            else "BASELINE_STALE" if current_assessment_version_id is not None else "UNKNOWN"
        ),
        "created_at": simulation.created_at.isoformat(),
        "result": {
            "id": str(result.id),
            "status": result.status,
            "baseline": result.baseline,
            "simulated": result.simulated,
            "delta": result.delta,
            "affected_supplier_ids": result.affected_supplier_ids,
            "affected_product_ids": result.affected_product_ids,
            "allocation_exposed": _number(_decimal(result.allocation_exposed)),
            "uncovered_exposure": _number(_decimal(result.uncovered_exposure)),
            "missing_evidence": result.missing_evidence,
            "limitations": result.limitations,
            "recommendations": result.recommendations,
            "explanation": result.explanation,
            "calculation_versions": result.calculation_versions,
            "created_at": result.created_at.isoformat(),
        },
    }


def _find(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, simulation_id: uuid.UUID
) -> tuple[PortfolioSimulation, PortfolioSimulationResult]:
    simulation = db.scalar(
        select(PortfolioSimulation).where(
            PortfolioSimulation.id == simulation_id,
            PortfolioSimulation.owner_id == owner.id,
            PortfolioSimulation.portfolio_id == portfolio.id,
        )
    )
    if simulation is None:
        raise HTTPException(404, "Portfolio simulation not found.")
    result = db.scalar(
        select(PortfolioSimulationResult).where(
            PortfolioSimulationResult.simulation_id == simulation.id,
            PortfolioSimulationResult.owner_id == owner.id,
        )
    )
    if result is None:
        raise HTTPException(409, "Portfolio simulation result is not available.")
    return simulation, result


def create_simulation(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, request: SimulationRequest
) -> tuple[dict[str, Any], bool]:
    assessment = _assessment(db, owner, portfolio, request.assessment_version_id)
    members = _dedupe_members(_members(assessment))
    assumptions, affected, products = _validate(request, members)
    digest = assumption_hash(assumptions)
    query = select(PortfolioSimulation).where(
        PortfolioSimulation.owner_id == owner.id,
        PortfolioSimulation.portfolio_id == portfolio.id,
        PortfolioSimulation.assessment_version_id == assessment.id,
        PortfolioSimulation.simulation_type == request.simulation_type,
        PortfolioSimulation.assumption_hash == digest,
        PortfolioSimulation.idempotency_key == request.idempotency_key,
    )
    existing = db.scalar(query)
    if existing:
        saved = db.scalar(
            select(PortfolioSimulationResult).where(
                PortfolioSimulationResult.simulation_id == existing.id
            )
        )
        if saved:
            return _payload(existing, saved, portfolio.current_assessment_version_id), True
    baseline = _shares(members, set())
    reduction = Decimal("100")
    if request.simulation_type in {"SUPPLIER_CAPACITY_REDUCTION", "AVAILABILITY_REDUCTION"}:
        key = (
            "capacity_reduction_percent"
            if request.simulation_type == "SUPPLIER_CAPACITY_REDUCTION"
            else "availability_reduction_percent"
        )
        reduction = _decimal(assumptions.get(key)) or Decimal("100")
    simulated = _shares(members, affected, reduction)
    missing: list[str] = []
    limitations: list[str] = []
    if (
        request.simulation_type in {"SUPPLIER_CAPACITY_REDUCTION", "AVAILABILITY_REDUCTION"}
        and assumptions.get(
            "capacity_reduction_percent"
            if request.simulation_type == "SUPPLIER_CAPACITY_REDUCTION"
            else "availability_reduction_percent"
        )
        is None
    ):
        missing.append("authoritative capacity/availability baseline")
        limitations.append("No authoritative capacity/availability baseline was supplied.")
    if request.simulation_type == "LEAD_TIME_INCREASE":
        if assumptions.get("increase_days") is None:
            raise HTTPException(422, "increase_days is required for lead-time simulation.")
        missing.append("baseline lead-time evidence")
    if request.simulation_type in {"LANDED_COST_INCREASE", "FX_SHOCK"}:
        if assumptions.get("increase_percent") is None:
            raise HTTPException(422, "increase_percent is required for cost/FX simulation.")
        missing.append("normalized comparable landed-cost evidence")
    if request.simulation_type == "MOQ_INCREASE":
        if assumptions.get("increase_percent") is None:
            raise HTTPException(422, "increase_percent is required for MOQ simulation.")
        missing.append("authoritative MOQ evidence")
    concentration = calculate_concentration(db, owner, portfolio, assessment.id)
    dependencies = calculate_dependencies(db, owner, portfolio, assessment.id)
    readiness = calculate_readiness(db, owner, portfolio, assessment.id)
    resilience = calculate_resilience(db, owner, portfolio, assessment.id)
    base_score = _decimal(resilience["score"].get("score"))
    baseline_score = _number(base_score)
    exposure = _decimal(simulated["uncovered_exposure"]) or Decimal("0")
    simulated_score = (
        _number(max(Decimal("0"), base_score - exposure)) if base_score is not None else None
    )
    baseline["resilience"] = {
        "score": baseline_score,
        "score_version": resilience["score"].get("score_version"),
        "classification": resilience["score"].get("classification"),
    }
    baseline["concentration"] = concentration
    baseline["dependencies"] = dependencies
    baseline["alternate_readiness"] = readiness
    baseline["risk"] = resilience["risk"]
    baseline["confidence"] = resilience["confidence"]
    baseline["dimensions"] = resilience["dimensions"]
    simulated["resilience"] = {
        "score": simulated_score,
        "score_version": resilience["score"].get("score_version"),
        "classification": resilience["score"].get("classification"),
    }
    simulated["dependencies"] = dependencies
    simulated["alternate_readiness"] = readiness
    simulated["risk"] = resilience["risk"]
    simulated["confidence"] = resilience["confidence"]
    delta = {
        "allocation_exposed": simulated["allocation_exposed"],
        "uncovered_exposure": simulated["uncovered_exposure"],
        "resilience_score": _number(
            (Decimal(str(simulated_score)) - Decimal(str(baseline_score)))
            if simulated_score is not None and baseline_score is not None
            else None
        ),
    }
    recommendations: list[dict[str, Any]] = []
    if affected:
        recommendations.append(
            {
                "type": "QUALIFY_SECOND_SUPPLIER",
                "priority": "HIGH",
                "reason": (
                    "Consider qualifying an alternate without automatically "
                    "reallocating exposure."
                ),
            }
        )
    if "baseline lead-time evidence" in missing:
        recommendations.append(
            {
                "type": "REFRESH_COMMERCIAL_EVIDENCE",
                "priority": "MEDIUM",
                "reason": "Refresh lead-time evidence before relying on simulated recovery.",
            }
        )
    if "normalized comparable landed-cost evidence" in missing:
        recommendations.append(
            {
                "type": "REFRESH_LANDED_COST",
                "priority": "MEDIUM",
                "reason": "Refresh normalized landed-cost evidence before using the cost result.",
            }
        )
    lifecycle = "INSUFFICIENT_EVIDENCE" if missing else "CALCULATED"
    simulation = PortfolioSimulation(
        owner_id=owner.id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id,
        simulation_type=request.simulation_type,
        policy_version=SIMULATION_POLICY_VERSION,
        idempotency_key=request.idempotency_key,
        assumption_hash=digest,
        assumptions={
            **assumptions,
            "provenance": {key: "SIMULATION_ASSUMPTION" for key in assumptions},
        },
        status=lifecycle,
    )
    result = PortfolioSimulationResult(
        simulation=simulation,
        owner_id=owner.id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id,
        status=lifecycle,
        baseline=baseline,
        simulated=simulated,
        delta=delta,
        affected_supplier_ids=sorted(affected),
        affected_product_ids=products,
        allocation_exposed=simulated["allocation_exposed"],
        uncovered_exposure=simulated["uncovered_exposure"],
        missing_evidence=sorted(set(missing)),
        limitations=limitations,
        recommendations=recommendations,
        explanation=(
            "Simulation compares an immutable assessment baseline with bounded "
            "assumptions; no allocation is automatically reassigned."
        ),
        calculation_versions={
            "simulation": SIMULATION_POLICY_VERSION,
            "resilience": resilience["score"].get("score_version"),
        },
    )
    try:
        db.add(result)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(query)
        if existing:
            saved = db.scalar(
                select(PortfolioSimulationResult).where(
                    PortfolioSimulationResult.simulation_id == existing.id
                )
            )
            if saved:
                return _payload(existing, saved, portfolio.current_assessment_version_id), True
        raise HTTPException(409, "Portfolio simulation could not be created safely.") from None
    return _payload(simulation, result, portfolio.current_assessment_version_id), False


def list_simulations(
    db: Session, owner: User, portfolio: SupplierPortfolioContext
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(PortfolioSimulation)
        .where(
            PortfolioSimulation.owner_id == owner.id,
            PortfolioSimulation.portfolio_id == portfolio.id,
        )
        .order_by(PortfolioSimulation.created_at.desc())
    )
    return [
        _payload(row, result, portfolio.current_assessment_version_id)
        for row in rows
        if (
            result := db.scalar(
                select(PortfolioSimulationResult).where(
                    PortfolioSimulationResult.simulation_id == row.id
                )
            )
        )
    ]


def get_simulation(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, simulation_id: uuid.UUID
) -> dict[str, Any]:
    simulation, result = _find(db, owner, portfolio, simulation_id)
    return _payload(simulation, result, portfolio.current_assessment_version_id)
