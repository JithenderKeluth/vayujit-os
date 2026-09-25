"""13F orchestration over the existing 13A-13E immutable economics authorities."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_calculation_models import EconomicCalculation
from vayujit_api.intelligence.economic_calculation_service import (
    CUSTOMS_CALCULATION_VERSION,
    CUSTOMS_POLICY_VERSION,
    FREIGHT_CALCULATION_VERSION,
    FREIGHT_POLICY_VERSION,
    FX_CALCULATION_VERSION,
    FX_POLICY_VERSION,
    calculate_from_snapshot,
    list_breakdown,
)
from vayujit_api.intelligence.economic_customs_models import CustomsTaxSnapshot
from vayujit_api.intelligence.economic_freight_models import FreightSnapshot
from vayujit_api.intelligence.economic_fx_models import FXRateSnapshot
from vayujit_api.intelligence.economic_models import EconomicContext, EconomicInputSnapshot
from vayujit_api.intelligence.economic_scenario_models import (
    EconomicScenario,
    EconomicScenarioResult,
    EconomicSensitivityRun,
)
from vayujit_api.intelligence.economic_scenario_schemas import (
    EconomicScenarioCreate,
    EconomicScenarioRun,
    EconomicSensitivityCreate,
    ScenarioOverrides,
    SensitivityPoint,
)
from vayujit_api.intelligence.economic_schemas import EconomicCalculationRequest
from vayujit_api.intelligence.economic_service import fingerprint, now
from vayujit_api.intelligence.scenario_models import SourcingScenario

SUPPORTED_OVERRIDE_FIELDS = (
    "target_quantity",
    "product_unit_cost",
    "component_category",
    "component_amount",
    "fx_snapshot_id",
    "fx_rate",
    "freight_snapshot_id",
    "freight_amount",
    "customs_tax_snapshot_id",
    "duty_rate",
    "tax_rate",
)


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_json(value), sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _owned(db: Session, model: type[Any], owner: User, identity: uuid.UUID, label: str) -> Any:
    row = db.scalar(select(model).where(model.id == identity, model.owner_id == owner.id))
    if row is None:
        raise HTTPException(404, f"{label} is not available in the owner scope.")
    return row


def _lock(db: Session, owner: User) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"economic-scenario:{owner.id}"},
    )


def _override_payload(data: ScenarioOverrides) -> dict[str, object]:
    raw = data.model_dump(mode="json", exclude_none=True)
    raw["provenance"] = "SCENARIO_OVERRIDE"
    return raw


def _result_view(row: EconomicScenarioResult, reused: bool) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "scenario_id": str(row.scenario_id),
        "baseline_calculation_id": str(row.baseline_calculation_id),
        "scenario_calculation_id": str(row.scenario_calculation_id),
        "scenario_snapshot_id": str(row.scenario_snapshot_id),
        "calculation_version": row.calculation_version,
        "policy_version": row.policy_version,
        "comparability": row.comparability,
        "baseline": {
            "status": row.baseline_status,
            "currency": row.baseline_currency,
            "total": str(row.baseline_total) if row.baseline_total is not None else None,
            "per_unit": str(row.baseline_per_unit) if row.baseline_per_unit is not None else None,
        },
        "scenario": {
            "status": row.scenario_status,
            "currency": row.scenario_currency,
            "total": str(row.scenario_total) if row.scenario_total is not None else None,
            "per_unit": str(row.scenario_per_unit) if row.scenario_per_unit is not None else None,
        },
        "delta": {
            "absolute": str(row.absolute_delta) if row.absolute_delta is not None else None,
            "percentage": str(row.percentage_delta) if row.percentage_delta is not None else None,
            "per_unit": str(row.per_unit_delta) if row.per_unit_delta is not None else None,
        },
        "changed_inputs": row.changed_inputs,
        "component_deltas": row.component_deltas,
        "assumptions": row.assumptions,
        "missing_inputs": row.missing_inputs,
        "stale_inputs": row.stale_inputs,
        "warnings": row.warnings,
        "idempotent_reuse": reused,
    }


def _copy_columns(row: Any, excluded: set[str]) -> dict[str, object]:
    return {
        column.key: getattr(row, column.key)
        for column in row.__table__.columns
        if column.key not in excluded
    }


def _scenario_snapshot(
    db: Session,
    owner: User,
    baseline: EconomicCalculation,
    overrides: ScenarioOverrides,
) -> EconomicInputSnapshot:
    source = _owned(db, EconomicInputSnapshot, owner, baseline.snapshot_id, "Economic snapshot")
    payload = copy.deepcopy(source.payload if isinstance(source.payload, dict) else {})
    context_value = payload.get("context")
    components_value = payload.get("components")
    quotes_value = payload.get("quotes")
    context: dict[str, object] = cast(
        dict[str, object], copy.deepcopy(context_value if isinstance(context_value, dict) else {})
    )
    components: list[object] = cast(
        list[object], copy.deepcopy(components_value if isinstance(components_value, list) else [])
    )
    quotes: list[object] = cast(
        list[object], copy.deepcopy(quotes_value if isinstance(quotes_value, list) else [])
    )
    if overrides.target_quantity is not None:
        context["target_quantity"] = str(overrides.target_quantity)
    changed_reason = overrides.reason
    if overrides.product_unit_cost is not None:
        updated = False
        for row in components:
            if isinstance(row, dict) and str(row.get("category", "")).upper() == "PRODUCT_COST":
                row["amount"] = str(overrides.product_unit_cost)
                row["provenance"] = "CONFIGURED"
                row["assumption_reason"] = changed_reason
                updated = True
                break
        if not updated:
            for row in quotes:
                if isinstance(row, dict) and row.get("unit_price") is not None:
                    row["unit_price"] = str(overrides.product_unit_cost)
                    row["provenance"] = "CONFIGURED"
                    row["assumption_reason"] = changed_reason
                    updated = True
                    break
        if not updated:
            raise HTTPException(
                422, "Product unit cost cannot be overridden without a product input."
            )
    if overrides.component_category is not None and overrides.component_amount is not None:
        updated = False
        for row in components:
            if (
                isinstance(row, dict)
                and str(row.get("category", "")).upper() == overrides.component_category
            ):
                row["amount"] = str(overrides.component_amount)
                row["provenance"] = "CONFIGURED"
                row["assumption_reason"] = changed_reason
                updated = True
                break
        if not updated:
            raise HTTPException(
                422, "The selected cost component is not present in the immutable baseline."
            )
    payload["context"] = context
    payload["components"] = components
    payload["quotes"] = quotes
    payload["scenario_override"] = _json(_override_payload(overrides))
    scenario_fingerprint = fingerprint(
        {"source": source.fingerprint, "overrides": _override_payload(overrides)}
    )
    existing = db.scalar(
        select(EconomicInputSnapshot).where(
            EconomicInputSnapshot.owner_id == owner.id,
            EconomicInputSnapshot.context_id == source.context_id,
            EconomicInputSnapshot.fingerprint == scenario_fingerprint,
        )
    )
    if existing is not None:
        return existing
    current = (
        db.scalar(
            select(func.max(EconomicInputSnapshot.version)).where(
                EconomicInputSnapshot.owner_id == owner.id,
                EconomicInputSnapshot.context_id == source.context_id,
            )
        )
        or 0
    )
    missing = payload.get("missing_inputs", source.missing_inputs)
    row = EconomicInputSnapshot(
        owner_id=owner.id,
        context_id=source.context_id,
        version=int(current) + 1,
        fingerprint=scenario_fingerprint,
        completeness=str(payload.get("completeness", source.completeness)),
        missing_inputs=copy.deepcopy(missing) if isinstance(missing, list) else [],
        payload=_json(payload),
    )
    db.add(row)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=owner.id,
            action="intelligence.economic_scenario_snapshot_created",
            entity_type="economic_input_snapshot",
            entity_id=row.id,
            metadata_json={"source_snapshot_id": str(source.id), "provenance": "SCENARIO_OVERRIDE"},
            occurred_at=now(),
            idempotency_key=f"intelligence.economic_scenario_snapshot_created:{row.id}",
        )
    )
    return row


def _scenario_fx(
    db: Session,
    owner: User,
    source_id: uuid.UUID | None,
    rate: Decimal | None,
    reason: str,
) -> FXRateSnapshot | None:
    if source_id is None:
        return None
    source = cast(FXRateSnapshot, _owned(db, FXRateSnapshot, owner, source_id, "FX snapshot"))
    if rate is None:
        return source
    digest = fingerprint({"source": source.fingerprint, "rate": str(rate), "reason": reason})
    existing = db.scalar(
        select(FXRateSnapshot).where(
            FXRateSnapshot.owner_id == owner.id, FXRateSnapshot.fingerprint == digest
        )
    )
    if existing is not None:
        return existing
    values = _copy_columns(source, {"id", "created_at", "fingerprint"})
    values.update(
        {
            "rate": rate,
            "provenance": "CONFIGURED",
            "freshness": source.freshness,
            "provider": "SCENARIO_OVERRIDE",
            "source_mode": "MANUAL",
            "assumption_reason": reason,
            "version": "fx-scenario-v1",
            "fingerprint": digest,
        }
    )
    row = FXRateSnapshot(owner_id=owner.id, **values)
    db.add(row)
    db.flush()
    return row


def _scenario_freight(
    db: Session,
    owner: User,
    source_id: uuid.UUID | None,
    amount: Decimal | None,
    reason: str,
) -> FreightSnapshot | None:
    if source_id is None:
        return None
    source = cast(
        FreightSnapshot, _owned(db, FreightSnapshot, owner, source_id, "Freight snapshot")
    )
    if amount is None:
        return source
    digest = fingerprint({"source": source.fingerprint, "amount": str(amount), "reason": reason})
    existing = db.scalar(
        select(FreightSnapshot).where(
            FreightSnapshot.owner_id == owner.id, FreightSnapshot.fingerprint == digest
        )
    )
    if existing is not None:
        return existing
    values = _copy_columns(source, {"id", "created_at", "fingerprint"})
    values.update(
        {
            "amount": amount,
            "provenance": "CONFIGURED",
            "provider": "SCENARIO_OVERRIDE",
            "source_mode": "MANUAL",
            "assumption_reason": reason,
            "version": "freight-scenario-v1",
            "fingerprint": digest,
        }
    )
    row = FreightSnapshot(owner_id=owner.id, **values)
    db.add(row)
    db.flush()
    return row


def _scenario_customs(
    db: Session,
    owner: User,
    source_id: uuid.UUID | None,
    duty_rate: Decimal | None,
    tax_rate: Decimal | None,
    reason: str,
) -> CustomsTaxSnapshot | None:
    if source_id is None:
        return None
    source = cast(
        CustomsTaxSnapshot, _owned(db, CustomsTaxSnapshot, owner, source_id, "Customs/tax snapshot")
    )
    if duty_rate is None and tax_rate is None:
        return source
    payload = copy.deepcopy(source.payload if isinstance(source.payload, dict) else {})
    rates = (
        cast(list[object], payload.get("rates")) if isinstance(payload.get("rates"), list) else []
    )
    changed = False
    for raw in rates:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("rate_kind", "")).upper()
        if duty_rate is not None and kind == "DUTY":
            raw["rate"] = str(duty_rate)
            raw["provenance"] = "CONFIGURED"
            raw["assumption_reason"] = reason
            changed = True
        if tax_rate is not None and kind == "IMPORT_TAX":
            raw["rate"] = str(tax_rate)
            raw["provenance"] = "CONFIGURED"
            raw["assumption_reason"] = reason
            changed = True
    if not changed:
        raise HTTPException(
            422, "The requested duty/tax category is not present in the immutable baseline."
        )
    payload["rates"] = rates
    payload["scenario_override"] = {"provenance": "SCENARIO_OVERRIDE", "reason": reason}
    digest = fingerprint({"source": source.fingerprint, "payload": payload})
    existing = db.scalar(
        select(CustomsTaxSnapshot).where(
            CustomsTaxSnapshot.owner_id == owner.id, CustomsTaxSnapshot.fingerprint == digest
        )
    )
    if existing is not None:
        return existing
    warnings = list(source.warnings or [])
    warnings.append(
        "Duty/tax rates are hypothetical scenario inputs; legal applicability is not determined."
    )
    values = _copy_columns(source, {"id", "created_at", "fingerprint", "payload", "warnings"})
    row = CustomsTaxSnapshot(
        owner_id=owner.id,
        fingerprint=digest,
        payload=payload,
        warnings=list(dict.fromkeys(warnings)),
        **values,
    )
    db.add(row)
    db.flush()
    return row


def _versions(
    fx: FXRateSnapshot | None,
    freight: FreightSnapshot | None,
    customs: CustomsTaxSnapshot | None,
) -> tuple[str, str]:
    if customs is not None:
        return CUSTOMS_CALCULATION_VERSION, CUSTOMS_POLICY_VERSION
    if freight is not None:
        return FREIGHT_CALCULATION_VERSION, FREIGHT_POLICY_VERSION
    if fx is not None:
        return FX_CALCULATION_VERSION, FX_POLICY_VERSION
    return "landed-cost-v1", "known-cost-v1"


def _numeric(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _amount(line: Any) -> Decimal | None:
    value = line.converted_amount if line.converted_amount is not None else line.included_amount
    return _numeric(value)


def _component_deltas(
    db: Session, owner: User, baseline_id: uuid.UUID, scenario_id: uuid.UUID
) -> list[dict[str, object]]:
    base = {str(row.category): _amount(row) for row in list_breakdown(db, owner, baseline_id)}
    scenario = {str(row.category): _amount(row) for row in list_breakdown(db, owner, scenario_id)}
    output: list[dict[str, object]] = []
    for category in sorted(set(base) | set(scenario)):
        old, new = base.get(category), scenario.get(category)
        if old is None or new is None:
            continue
        output.append(
            {
                "category": category,
                "baseline": str(old),
                "scenario": str(new),
                "delta": str(new - old),
            }
        )
    return output


def _execute_calculation(db: Session, owner: User, scenario: EconomicScenario) -> tuple[
    EconomicCalculation,
    EconomicCalculation,
    EconomicInputSnapshot,
    str,
    str,
    list[dict[str, object]],
]:
    baseline = _owned(
        db, EconomicCalculation, owner, scenario.baseline_calculation_id, "Baseline calculation"
    )
    context = _owned(db, EconomicContext, owner, baseline.context_id, "Economic context")
    if context.id != scenario.economic_context_id:
        raise HTTPException(
            422, "Baseline calculation must belong to the scenario economic context."
        )
    overrides = ScenarioOverrides.model_validate(
        {
            k: v
            for k, v in scenario.overrides.items()
            if k in SUPPORTED_OVERRIDE_FIELDS or k == "reason"
        }
    )
    scenario_snapshot = _scenario_snapshot(db, owner, baseline, overrides)
    fx_id = overrides.fx_snapshot_id or baseline.fx_snapshot_id
    freight_id = overrides.freight_snapshot_id or baseline.freight_snapshot_id
    customs_id = overrides.customs_tax_snapshot_id or baseline.customs_tax_snapshot_id
    fx = _scenario_fx(db, owner, fx_id, overrides.fx_rate, overrides.reason)
    freight = _scenario_freight(db, owner, freight_id, overrides.freight_amount, overrides.reason)
    customs = _scenario_customs(
        db, owner, customs_id, overrides.duty_rate, overrides.tax_rate, overrides.reason
    )
    version, policy = _versions(fx, freight, customs)
    request = EconomicCalculationRequest(
        fx_snapshot_id=fx.id if fx else None,
        freight_snapshot_id=freight.id if freight else None,
        customs_tax_snapshot_id=customs.id if customs else None,
        calculation_version=version,
        policy_version=policy,
        options={"economic_scenario_id": str(scenario.id), "provenance": "SCENARIO_OVERRIDE"},
    )
    scenario_calc, _ = calculate_from_snapshot(db, owner, scenario_snapshot.id, request)
    return (
        baseline,
        scenario_calc,
        scenario_snapshot,
        version,
        policy,
        _component_deltas(db, owner, baseline.id, scenario_calc.id),
    )


def _comparability(baseline: EconomicCalculation, scenario: EconomicCalculation) -> str:
    if (
        baseline.currency != scenario.currency
        or baseline.reporting_currency != scenario.reporting_currency
    ):
        return "NOT_COMPARABLE"
    if baseline.status == "INSUFFICIENT" or scenario.status == "INSUFFICIENT":
        return "NOT_COMPARABLE"
    if baseline.status != "COMPLETE" or scenario.status != "COMPLETE":
        return "PARTIALLY_COMPARABLE"
    return "COMPARABLE"


def _make_result(
    db: Session,
    owner: User,
    scenario: EconomicScenario,
    run_key: str,
) -> tuple[EconomicScenarioResult, bool]:
    existing_key = db.scalar(
        select(EconomicScenarioResult).where(
            EconomicScenarioResult.owner_id == owner.id,
            EconomicScenarioResult.scenario_id == scenario.id,
            EconomicScenarioResult.idempotency_key == run_key,
        )
    )
    if existing_key is not None:
        return existing_key, True
    baseline, scenario_calc, snapshot, version, policy, component_deltas = _execute_calculation(
        db, owner, scenario
    )
    comparability = _comparability(baseline, scenario_calc)
    base_total, scenario_total = _numeric(baseline.total_included_cost), _numeric(
        scenario_calc.total_included_cost
    )
    base_unit, scenario_unit = _numeric(baseline.per_unit_cost), _numeric(
        scenario_calc.per_unit_cost
    )
    absolute = (
        scenario_total - base_total
        if base_total is not None
        and scenario_total is not None
        and comparability != "NOT_COMPARABLE"
        else None
    )
    percentage = (
        (absolute / base_total * Decimal("100"))
        if absolute is not None and base_total is not None and base_total != Decimal("0")
        else None
    )
    per_unit_delta = (
        scenario_unit - base_unit
        if scenario_unit is not None and base_unit is not None and comparability != "NOT_COMPARABLE"
        else None
    )
    changed = [
        {
            "field": key,
            "value": value,
            "provenance": "SCENARIO_OVERRIDE",
            "reason": scenario.overrides.get("reason"),
        }
        for key, value in scenario.overrides.items()
        if key not in {"reason", "provenance"}
    ]
    warnings = list(dict.fromkeys([*(baseline.warnings or []), *(scenario_calc.warnings or [])]))
    missing = list(
        dict.fromkeys([*(baseline.missing_inputs or []), *(scenario_calc.missing_inputs or [])])
    )
    stale = list(
        dict.fromkeys([*(baseline.stale_inputs or []), *(scenario_calc.stale_inputs or [])])
    )
    result_fingerprint = fingerprint(
        {
            "scenario": str(scenario.id),
            "baseline": baseline.calculation_fingerprint,
            "scenario_calculation": scenario_calc.calculation_fingerprint,
            "overrides": scenario.overrides,
            "version": version,
            "policy": policy,
        }
    )
    existing = db.scalar(
        select(EconomicScenarioResult).where(
            EconomicScenarioResult.owner_id == owner.id,
            EconomicScenarioResult.fingerprint == result_fingerprint,
        )
    )
    if existing is not None:
        return existing, True
    row = EconomicScenarioResult(
        owner_id=owner.id,
        scenario_id=scenario.id,
        idempotency_key=run_key,
        baseline_calculation_id=baseline.id,
        scenario_calculation_id=scenario_calc.id,
        scenario_snapshot_id=snapshot.id,
        calculation_version=version,
        policy_version=policy,
        comparability=comparability,
        baseline_status=baseline.status,
        scenario_status=scenario_calc.status,
        baseline_currency=baseline.currency,
        scenario_currency=scenario_calc.currency,
        baseline_total=base_total,
        scenario_total=scenario_total,
        absolute_delta=absolute,
        percentage_delta=percentage,
        baseline_per_unit=base_unit,
        scenario_per_unit=scenario_unit,
        per_unit_delta=per_unit_delta,
        changed_inputs=_json(changed),
        component_deltas=_json(component_deltas),
        assumptions=_json([*(baseline.assumptions or []), *(scenario_calc.assumptions or [])]),
        missing_inputs=_json(missing),
        stale_inputs=_json(stale),
        warnings=_json(warnings),
        fingerprint=result_fingerprint,
    )
    db.add(row)
    scenario.status = "EXECUTED"
    db.add(
        AuditEvent(
            actor_id=owner.id,
            action="intelligence.economic_scenario_executed",
            entity_type="economic_scenario",
            entity_id=scenario.id,
            metadata_json={"result_id": str(row.id), "comparability": comparability},
            occurred_at=now(),
            idempotency_key=f"intelligence.economic_scenario_executed:{scenario.id}:{run_key}",
        )
    )
    db.commit()
    db.refresh(row)
    return row, False


def create_scenario(
    db: Session, owner: User, context_id: uuid.UUID, data: EconomicScenarioCreate
) -> dict[str, Any]:
    _lock(db, owner)
    context = _owned(db, EconomicContext, owner, context_id, "Economic context")
    baseline = _owned(
        db, EconomicCalculation, owner, data.baseline_calculation_id, "Baseline calculation"
    )
    if baseline.context_id != context.id:
        raise HTTPException(422, "Baseline calculation must belong to the economic context.")
    if data.sourcing_scenario_id is not None:
        _owned(db, SourcingScenario, owner, data.sourcing_scenario_id, "Sourcing scenario")
    existing = db.scalar(
        select(EconomicScenario).where(
            EconomicScenario.owner_id == owner.id,
            EconomicScenario.idempotency_key == data.idempotency_key,
        )
    )
    payload = data.model_dump(mode="json")
    if existing is not None:
        if existing.fingerprint != fingerprint(payload):
            raise HTTPException(409, "Idempotency key was used for a different economic scenario.")
        return scenario_detail(db, owner, existing.id, True)
    row = EconomicScenario(
        owner_id=owner.id,
        economic_context_id=context.id,
        sourcing_scenario_id=data.sourcing_scenario_id,
        baseline_calculation_id=baseline.id,
        name=data.name,
        description=data.description,
        overrides=_json(_override_payload(data.overrides)),
        version=1,
        status="READY",
        fingerprint=fingerprint(payload),
        idempotency_key=data.idempotency_key,
    )
    db.add(row)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=owner.id,
            action="intelligence.economic_scenario_created",
            entity_type="economic_scenario",
            entity_id=row.id,
            metadata_json={
                "economic_context_id": str(context.id),
                "provenance": "SCENARIO_OVERRIDE",
            },
            occurred_at=now(),
            idempotency_key=f"intelligence.economic_scenario_created:{data.idempotency_key}",
        )
    )
    db.commit()
    db.refresh(row)
    return scenario_detail(db, owner, row.id, False)


def scenario_detail(
    db: Session, owner: User, scenario_id: uuid.UUID, reused: bool = False
) -> dict[str, Any]:
    row = _owned(db, EconomicScenario, owner, scenario_id, "Economic scenario")
    return {
        "id": str(row.id),
        "economic_context_id": str(row.economic_context_id),
        "sourcing_scenario_id": str(row.sourcing_scenario_id) if row.sourcing_scenario_id else None,
        "baseline_calculation_id": str(row.baseline_calculation_id),
        "name": row.name,
        "description": row.description,
        "overrides": row.overrides,
        "version": row.version,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "idempotent_reuse": reused,
    }


def list_scenarios(
    db: Session, owner: User, context_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    query = select(EconomicScenario).where(EconomicScenario.owner_id == owner.id)
    if context_id is not None:
        query = query.where(EconomicScenario.economic_context_id == context_id)
    return [
        scenario_detail(db, owner, row.id)
        for row in db.scalars(query.order_by(EconomicScenario.created_at.desc()).limit(200))
    ]


def run_scenario(
    db: Session, owner: User, scenario_id: uuid.UUID, data: EconomicScenarioRun
) -> dict[str, Any]:
    _lock(db, owner)
    scenario = _owned(db, EconomicScenario, owner, scenario_id, "Economic scenario")
    if scenario.status == "ARCHIVED":
        raise HTTPException(409, "Archived economic scenarios cannot be executed.")
    row, reused = _make_result(db, owner, scenario, data.idempotency_key)
    return _result_view(row, reused)


def _point_overrides(
    db: Session, owner: User, scenario: EconomicScenario, point: SensitivityPoint
) -> ScenarioOverrides:
    baseline = _owned(
        db, EconomicCalculation, owner, scenario.baseline_calculation_id, "Baseline calculation"
    )
    base: dict[str, object] = {
        "reason": f"Explicit sensitivity point {point.dimension}={point.value}"
    }
    if point.dimension == "product_unit_cost":
        base["product_unit_cost"] = point.value
    elif point.dimension == "target_quantity":
        base["target_quantity"] = int(point.value)
    elif point.dimension == "fx_rate":
        base.update(
            {
                "fx_rate": point.value,
                "fx_snapshot_id": scenario.overrides.get("fx_snapshot_id")
                or (str(baseline.fx_snapshot_id) if baseline.fx_snapshot_id else None),
            }
        )
    elif point.dimension == "freight_amount":
        base.update(
            {
                "freight_amount": point.value,
                "freight_snapshot_id": scenario.overrides.get("freight_snapshot_id")
                or (str(baseline.freight_snapshot_id) if baseline.freight_snapshot_id else None),
            }
        )
    elif point.dimension == "duty_rate":
        base.update(
            {
                "duty_rate": point.value,
                "customs_tax_snapshot_id": scenario.overrides.get("customs_tax_snapshot_id")
                or (
                    str(baseline.customs_tax_snapshot_id)
                    if baseline.customs_tax_snapshot_id
                    else None
                ),
            }
        )
    elif point.dimension == "tax_rate":
        base.update(
            {
                "tax_rate": point.value,
                "customs_tax_snapshot_id": scenario.overrides.get("customs_tax_snapshot_id")
                or (
                    str(baseline.customs_tax_snapshot_id)
                    if baseline.customs_tax_snapshot_id
                    else None
                ),
            }
        )
    try:
        return ScenarioOverrides.model_validate(base)
    except ValueError as exc:
        raise HTTPException(
            422, "Sensitivity point requires the matching immutable baseline snapshot."
        ) from exc


def sensitivity(
    db: Session, owner: User, scenario_id: uuid.UUID, data: EconomicSensitivityCreate
) -> dict[str, Any]:
    _lock(db, owner)
    scenario = _owned(db, EconomicScenario, owner, scenario_id, "Economic scenario")
    fingerprint_value = fingerprint(
        {"scenario": str(scenario.id), "points": data.model_dump(mode="json")}
    )
    existing_key = db.scalar(
        select(EconomicSensitivityRun).where(
            EconomicSensitivityRun.owner_id == owner.id,
            EconomicSensitivityRun.scenario_id == scenario.id,
            EconomicSensitivityRun.idempotency_key == data.idempotency_key,
        )
    )
    if existing_key is not None:
        if existing_key.fingerprint != fingerprint_value:
            raise HTTPException(409, "Idempotency key was used for a different sensitivity run.")
        return {
            "id": str(existing_key.id),
            "dimension": existing_key.dimension,
            "points": existing_key.points,
            "idempotent_reuse": True,
        }
    existing = db.scalar(
        select(EconomicSensitivityRun).where(
            EconomicSensitivityRun.owner_id == owner.id,
            EconomicSensitivityRun.fingerprint == fingerprint_value,
        )
    )
    if existing is not None:
        return {
            "id": str(existing.id),
            "dimension": existing.dimension,
            "points": existing.points,
            "idempotent_reuse": True,
        }
    points: list[dict[str, object]] = []
    for index, point in enumerate(data.points):
        overrides = _point_overrides(db, owner, scenario, point)
        temp = EconomicScenario(
            owner_id=owner.id,
            economic_context_id=scenario.economic_context_id,
            sourcing_scenario_id=scenario.sourcing_scenario_id,
            baseline_calculation_id=scenario.baseline_calculation_id,
            name=f"{scenario.name} sensitivity {index + 1}",
            description="Explicit one-variable sensitivity point; not a forecast.",
            overrides=_json(_override_payload(overrides)),
            version=1,
            status="READY",
            fingerprint=fingerprint(
                {"parent": str(scenario.id), "point": point.model_dump(mode="json")}
            ),
            idempotency_key=f"sensitivity:{scenario.id}:{fingerprint_value}:{index}",
        )
        db.add(temp)
        db.flush()
        result, _ = _make_result(db, owner, temp, f"sensitivity-run:{fingerprint_value}:{index}")
        points.append(
            {
                "value": str(point.value),
                "dimension": point.dimension,
                "result_id": str(result.id),
                "comparability": result.comparability,
                "baseline_total": (
                    str(result.baseline_total) if result.baseline_total is not None else None
                ),
                "scenario_total": (
                    str(result.scenario_total) if result.scenario_total is not None else None
                ),
                "per_unit_cost": (
                    str(result.scenario_per_unit) if result.scenario_per_unit is not None else None
                ),
                "status": result.scenario_status,
                "provenance": "SCENARIO_OVERRIDE",
            }
        )
    row = EconomicSensitivityRun(
        owner_id=owner.id,
        scenario_id=scenario.id,
        idempotency_key=data.idempotency_key,
        dimension=data.points[0].dimension,
        points=_json(points),
        fingerprint=fingerprint_value,
    )
    db.add(row)
    db.add(
        AuditEvent(
            actor_id=owner.id,
            action="intelligence.economic_sensitivity_executed",
            entity_type="economic_scenario",
            entity_id=scenario.id,
            metadata_json={
                "dimension": row.dimension,
                "point_count": len(points),
                "forecast": False,
            },
            occurred_at=now(),
            idempotency_key=f"intelligence.economic_sensitivity_executed:{fingerprint_value}",
        )
    )
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "dimension": row.dimension,
        "points": row.points,
        "idempotent_reuse": False,
    }


def list_results(
    db: Session, owner: User, scenario_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    query = select(EconomicScenarioResult).where(EconomicScenarioResult.owner_id == owner.id)
    if scenario_id is not None:
        query = query.where(EconomicScenarioResult.scenario_id == scenario_id)
    rows = db.scalars(query.order_by(EconomicScenarioResult.created_at.desc()).limit(200))
    return [_result_view(row, False) for row in rows]
