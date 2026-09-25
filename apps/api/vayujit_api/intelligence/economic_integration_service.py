"""Read-only 13G projection over the existing sourcing economics authorities."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_calculation_models import (
    EconomicCalculation,
    EconomicCalculationBreakdown,
)
from vayujit_api.intelligence.economic_calculation_service import list_breakdown
from vayujit_api.intelligence.economic_models import EconomicContext
from vayujit_api.intelligence.economic_scenario_models import (
    EconomicScenario,
    EconomicScenarioResult,
    EconomicSensitivityRun,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity

ECONOMICS_CAPABILITIES = {"sourcing_economics.inspect"}


def _json(value: object) -> object:
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _gap(message: str) -> dict[str, object]:
    return {"code": "ECONOMICS_RESEARCH_GAP", "message": message}


def _readiness(status: str | None) -> str:
    return {
        "COMPLETE": "AVAILABLE",
        "PARTIAL": "PARTIAL",
        "INSUFFICIENT": "INSUFFICIENT",
    }.get(status or "", "NOT_EVALUATED")


def _breakdown_view(row: EconomicCalculationBreakdown) -> dict[str, object]:
    return {
        "id": str(row.id),
        "source_kind": row.source_kind,
        "source_id": str(row.source_id) if row.source_id else None,
        "category": row.category,
        "original_amount": _json(row.original_amount),
        "currency": row.currency,
        "basis": row.basis,
        "multiplier": _json(row.multiplier),
        "included_amount": _json(row.included_amount),
        "converted_amount": _json(row.converted_amount),
        "provenance": row.provenance,
        "freshness": row.freshness,
        "assumption_reason": row.assumption_reason,
        "inclusion_status": row.inclusion_status,
        "exclusion_reason": row.exclusion_reason,
        "lineage": _json(row.lineage),
        "line_order": row.line_order,
    }


def _calculation_view(db: Session, owner: User, row: EconomicCalculation) -> dict[str, object]:
    return {
        "id": str(row.id),
        "context_id": str(row.context_id),
        "status": row.status,
        "readiness": _readiness(row.status),
        "calculation_version": row.calculation_version,
        "policy_version": row.policy_version,
        "currency": row.currency,
        "reporting_currency": row.reporting_currency,
        "target_quantity": _json(row.target_quantity),
        "total_included_cost": _json(row.total_included_cost),
        "per_unit_cost": _json(row.per_unit_cost),
        "included_component_count": row.included_component_count,
        "excluded_component_count": row.excluded_component_count,
        "missing_inputs": _json(row.missing_inputs),
        "warnings": _json(row.warnings),
        "assumptions": _json(row.assumptions),
        "stale_inputs": _json(row.stale_inputs),
        "explanation": _json(row.explanation),
        "created_at": row.created_at.isoformat(),
        "breakdown": [_breakdown_view(item) for item in list_breakdown(db, owner, row.id)],
    }


def _scenario_view(result: EconomicScenarioResult, scenario: EconomicScenario) -> dict[str, object]:
    return {
        "id": str(result.id),
        "scenario_id": str(scenario.id),
        "scenario_name": scenario.name,
        "sourcing_scenario_id": (
            str(scenario.sourcing_scenario_id) if scenario.sourcing_scenario_id else None
        ),
        "comparability": result.comparability,
        "baseline": {
            "status": result.baseline_status,
            "currency": result.baseline_currency,
            "total": _json(result.baseline_total),
            "per_unit": _json(result.baseline_per_unit),
        },
        "scenario": {
            "status": result.scenario_status,
            "currency": result.scenario_currency,
            "total": _json(result.scenario_total),
            "per_unit": _json(result.scenario_per_unit),
        },
        "delta": {
            "absolute": _json(result.absolute_delta),
            "percentage": _json(result.percentage_delta),
            "per_unit": _json(result.per_unit_delta),
        },
        "changed_inputs": _json(result.changed_inputs),
        "component_deltas": _json(result.component_deltas),
        "assumptions": _json(result.assumptions),
        "missing_inputs": _json(result.missing_inputs),
        "stale_inputs": _json(result.stale_inputs),
        "warnings": _json(result.warnings),
        "calculation_version": result.calculation_version,
        "policy_version": result.policy_version,
        "created_at": result.created_at.isoformat(),
    }


def project_economics_for_opportunity(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    economic_context_id: uuid.UUID | None = None,
) -> dict[str, object]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id,
            ProductOpportunity.owner_id == owner.id,
        )
    )
    if opportunity is None:
        raise HTTPException(404, "Product opportunity not found.")

    if economic_context_id is not None:
        context = db.scalar(
            select(EconomicContext).where(
                EconomicContext.id == economic_context_id,
                EconomicContext.owner_id == owner.id,
            )
        )
        if context is None:
            raise HTTPException(404, "Economic context is not available in the owner scope.")
        if (
            opportunity.product_id is not None
            and context.product_id is not None
            and context.product_id != opportunity.product_id
        ):
            raise HTTPException(409, "Economic context does not match the product opportunity.")
    else:
        query = select(EconomicContext).where(EconomicContext.owner_id == owner.id)
        if opportunity.product_id is not None:
            query = query.where(EconomicContext.product_id == opportunity.product_id)
        else:
            query = query.where(EconomicContext.opportunity_id == opportunity.id)
        contexts = list(db.scalars(query.order_by(EconomicContext.updated_at.desc())))
        if not contexts:
            return {
                "opportunity_id": str(opportunity.id),
                "status": "NOT_EVALUATED",
                "readiness": "NOT_EVALUATED",
                "economic_context_id": None,
                "research_gaps": [
                    _gap(
                        "No owner-scoped sourcing economics context is linked to this opportunity."
                    )
                ],
                "external_writes": [],
            }
        if len(contexts) > 1:
            raise HTTPException(
                409, "Multiple economic contexts match; provide economic_context_id."
            )
        context = contexts[0]

    calculation = db.scalar(
        select(EconomicCalculation)
        .where(
            EconomicCalculation.owner_id == owner.id,
            EconomicCalculation.context_id == context.id,
        )
        .order_by(EconomicCalculation.created_at.desc())
    )
    lineage = {
        "economic_context_id": str(context.id),
        "product_id": str(context.product_id) if context.product_id else None,
        "supplier_id": str(context.supplier_id) if context.supplier_id else None,
        "sourcing_scenario_id": str(context.scenario_id) if context.scenario_id else None,
        "source_marketplace": context.source_marketplace,
        "target_channel": context.target_channel,
        "origin_country": context.origin_country,
        "destination_country": context.destination_country,
        "target_quantity": _json(context.target_quantity),
        "quantity_unit": context.quantity_unit,
        "base_currency": context.base_currency,
    }
    if calculation is None:
        return {
            "opportunity_id": str(opportunity.id),
            "status": "NOT_EVALUATED",
            "readiness": "NOT_EVALUATED",
            **lineage,
            "research_gaps": [_gap("No landed-cost calculation is available for this context.")],
            "external_writes": [],
        }

    scenario_rows = list(
        db.execute(
            select(EconomicScenarioResult, EconomicScenario)
            .join(EconomicScenario, EconomicScenario.id == EconomicScenarioResult.scenario_id)
            .where(
                EconomicScenarioResult.owner_id == owner.id,
                EconomicScenario.economic_context_id == context.id,
            )
            .order_by(EconomicScenarioResult.created_at.desc())
        ).all()
    )
    scenario_ids = [scenario.id for _, scenario in scenario_rows]
    sensitivity_rows = []
    if scenario_ids:
        sensitivity_rows = list(
            db.scalars(
                select(EconomicSensitivityRun)
                .where(
                    EconomicSensitivityRun.owner_id == owner.id,
                    EconomicSensitivityRun.scenario_id.in_(scenario_ids),
                )
                .order_by(EconomicSensitivityRun.created_at.desc())
            )
        )
    gaps: list[dict[str, object]] = []
    if calculation.status != "COMPLETE":
        gaps.append(
            _gap("Complete landed cost is not available; review missing, stale, or warning inputs.")
        )
    return {
        "opportunity_id": str(opportunity.id),
        "status": calculation.status,
        "readiness": _readiness(calculation.status),
        **lineage,
        "calculation": _calculation_view(db, owner, calculation),
        "scenario_comparisons": [
            _scenario_view(result, scenario) for result, scenario in scenario_rows
        ],
        "sensitivity_runs": [
            {
                "id": str(row.id),
                "scenario_id": str(row.scenario_id),
                "dimension": row.dimension,
                "points": _json(row.points),
                "created_at": row.created_at.isoformat(),
            }
            for row in sensitivity_rows
        ],
        "research_gaps": gaps,
        "semantic_boundary": (
            "Sourcing economics is factual cost evidence, not profitability, demand, "
            "forecast, supplier ranking, or product ranking."
        ),
        "external_writes": [],
    }
