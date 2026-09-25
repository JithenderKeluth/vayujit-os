"""Deterministic landed-cost calculation from immutable 13A snapshots."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_calculation_models import (
    EconomicCalculation,
    EconomicCalculationBreakdown,
)
from vayujit_api.intelligence.economic_customs_models import CustomsTaxSnapshot
from vayujit_api.intelligence.economic_customs_service import build_customs_lines
from vayujit_api.intelligence.economic_freight_models import FreightSnapshot, LogisticsContext
from vayujit_api.intelligence.economic_fx_models import FXRateSnapshot
from vayujit_api.intelligence.economic_models import EconomicInputSnapshot
from vayujit_api.intelligence.economic_schemas import EconomicCalculationRequest
from vayujit_api.intelligence.economic_service import fingerprint, now

CALCULATION_VERSION = "landed-cost-v1"
POLICY_VERSION = "known-cost-v1"
FX_CALCULATION_VERSION = "landed-cost-v2"
FX_POLICY_VERSION = "known-cost-fx-v1"
FREIGHT_CALCULATION_VERSION = "landed-cost-v3"
FREIGHT_POLICY_VERSION = "known-cost-freight-v1"
CUSTOMS_CALCULATION_VERSION = "landed-cost-v4"
CUSTOMS_POLICY_VERSION = "known-cost-customs-tax-v1"
SUPPORTED_BASES = {"PER_UNIT", "PER_SHIPMENT", "ONE_TIME"}
STORAGE_QUANTUM = Decimal("0.00000001")


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _money(value: Decimal | None) -> Decimal | None:
    return value.quantize(STORAGE_QUANTUM, rounding=ROUND_HALF_UP) if value is not None else None


def _upper(value: object, default: str = "") -> str:
    return str(value or default).strip().upper()


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _lineage(source_kind: str, source: Mapping[str, object]) -> dict[str, object]:
    return {
        "source_kind": source_kind,
        "source_id": source.get("id"),
        "snapshot_component_id": source.get("id") if source_kind == "component" else None,
        "quote_input_id": (
            source.get("quote_input_id") if source_kind == "component" else source.get("id")
        ),
        "evidence_ref": source.get("evidence_ref"),
    }


def _line(
    *,
    source_kind: str,
    source: Mapping[str, object],
    category: str,
    reason: str | None = None,
    inclusion_status: str = "EXCLUDED",
    multiplier: Decimal | None = None,
    included_amount: Decimal | None = None,
    basis: str | None = None,
) -> dict[str, object]:
    return {
        "source_kind": source_kind,
        "source_id": source.get("id"),
        "category": category,
        "original_amount": _decimal(source.get("amount", source.get("unit_price"))),
        "currency": source.get("currency"),
        "basis": basis or source.get("unit_basis"),
        "multiplier": multiplier,
        "included_amount": included_amount,
        "converted_amount": None,
        "fx_snapshot_id": None,
        "fx_pair": None,
        "fx_rate": None,
        "fx_effective_at": None,
        "fx_provider": None,
        "fx_freshness": None,
        "fx_inverted": None,
        "freight_snapshot_id": None,
        "provenance": _upper(source.get("provenance"), "UNKNOWN"),
        "freshness": _upper(source.get("freshness"), "UNKNOWN"),
        "assumption_reason": source.get("assumption_reason"),
        "evidence_ref": source.get("evidence_ref"),
        "inclusion_status": inclusion_status,
        "exclusion_reason": reason,
        "lineage": _lineage(source_kind, source),
    }


def _evaluate_source(
    *,
    source_kind: str,
    source: Mapping[str, object],
    category: str,
    currency: str | None,
    target_quantity: Decimal | None,
) -> tuple[dict[str, object], Decimal | None]:
    amount = _decimal(source.get("amount", source.get("unit_price")))
    provenance = _upper(source.get("provenance"), "UNKNOWN")
    basis = _upper(source.get("unit_basis"))
    if amount is None or provenance == "UNKNOWN":
        return (
            _line(
                source_kind=source_kind,
                source=source,
                category=category,
                reason="UNKNOWN_AMOUNT",
                basis=basis,
            ),
            None,
        )
    source_currency = _upper(source.get("currency"))
    if currency is None or not source_currency:
        return (
            _line(
                source_kind=source_kind,
                source=source,
                category=category,
                reason="MISSING_CURRENCY",
                basis=basis,
            ),
            None,
        )
    if source_currency != currency:
        return (
            _line(
                source_kind=source_kind,
                source=source,
                category=category,
                reason="CURRENCY_MISMATCH",
                basis=basis,
            ),
            None,
        )
    if basis not in SUPPORTED_BASES:
        return (
            _line(
                source_kind=source_kind,
                source=source,
                category=category,
                reason="UNSUPPORTED_BASIS",
                basis=basis or None,
            ),
            None,
        )
    if basis == "PER_UNIT":
        if target_quantity is None or target_quantity <= 0:
            return (
                _line(
                    source_kind=source_kind,
                    source=source,
                    category=category,
                    reason="MISSING_TARGET_QUANTITY",
                    basis=basis,
                ),
                None,
            )
        multiplier = target_quantity
    else:
        multiplier = Decimal("1")
    included = amount * multiplier
    return (
        _line(
            source_kind=source_kind,
            source=source,
            category=category,
            inclusion_status="INCLUDED",
            multiplier=multiplier,
            included_amount=included,
            basis=basis,
        ),
        included,
    )


def _apply_fx(
    line: dict[str, object],
    value: Decimal | None,
    reporting: str | None,
    fx_snapshots: list[FXRateSnapshot],
) -> tuple[Decimal | None, str | None]:
    source = _upper(line.get("currency"))
    if (
        value is None
        or line.get("inclusion_status") != "INCLUDED"
        or not source
        or not reporting
        or source == reporting
    ):
        if value is not None and line.get("inclusion_status") == "INCLUDED":
            line["converted_amount"] = _money(value)
        return value, None
    fx = next(
        (
            item
            for item in fx_snapshots
            if item.base_currency == source and item.quote_currency == reporting
        ),
        None,
    )
    if fx is None:
        line["inclusion_status"] = "EXCLUDED"
        line["exclusion_reason"] = "NO_COMPATIBLE_FX_SNAPSHOT"
        line["included_amount"] = None
        return None, f"{line.get('category')}:NO_COMPATIBLE_FX_SNAPSHOT"
    converted = _money(value * Decimal(fx.rate))
    line["converted_amount"] = converted
    line["fx_snapshot_id"] = fx.id
    line["fx_pair"] = f"{fx.base_currency}/{fx.quote_currency}"
    line["fx_rate"] = fx.rate
    line["fx_effective_at"] = fx.effective_at
    line["fx_provider"] = fx.provider
    line["fx_freshness"] = fx.freshness
    line["fx_inverted"] = fx.inverted
    return converted, ("STALE_FX_RATE" if fx.freshness == "STALE" else None)


def _freight_line(
    freight: FreightSnapshot,
) -> tuple[dict[str, object], Decimal | None]:
    source = {
        "id": freight.id,
        "amount": freight.amount,
        "currency": freight.currency,
        "unit_basis": freight.basis,
        "provenance": freight.provenance,
        "freshness": freight.freshness,
        "assumption_reason": freight.assumption_reason,
        "evidence_ref": freight.evidence_ref,
    }
    line = _line(
        source_kind="freight_snapshot",
        source=source,
        category="FREIGHT",
        basis=freight.basis,
    )
    line["freight_snapshot_id"] = freight.id
    amount = _decimal(freight.amount)
    if amount is None or freight.provenance == "UNKNOWN":
        line["exclusion_reason"] = "UNKNOWN_AMOUNT"
        return line, None
    multiplier = Decimal("1")
    basis = _upper(freight.basis)
    if basis == "PER_KG":
        if freight.quoted_weight is None or freight.quoted_weight_unit != "KG":
            line["exclusion_reason"] = "UNSUPPORTED_BASIS"
            return line, None
        multiplier = Decimal(str(freight.quoted_weight))
    elif basis == "PER_CBM":
        if freight.quoted_volume is None or freight.quoted_volume_unit != "CBM":
            line["exclusion_reason"] = "UNSUPPORTED_BASIS"
            return line, None
        multiplier = Decimal(str(freight.quoted_volume))
    elif basis == "PER_CARTON":
        if freight.quoted_package_count is None:
            line["exclusion_reason"] = "UNSUPPORTED_BASIS"
            return line, None
        multiplier = Decimal(freight.quoted_package_count)
    elif basis == "PER_CONTAINER":
        if freight.quoted_container_count is None:
            line["exclusion_reason"] = "UNSUPPORTED_BASIS"
            return line, None
        multiplier = Decimal(freight.quoted_container_count)
    elif basis not in {"PER_SHIPMENT", "FIXED_QUOTE"}:
        line["exclusion_reason"] = "UNSUPPORTED_BASIS"
        return line, None
    if multiplier <= 0:
        line["exclusion_reason"] = "UNSUPPORTED_BASIS"
        return line, None
    line["multiplier"] = multiplier
    line["included_amount"] = amount * multiplier
    line["inclusion_status"] = "INCLUDED"
    line["exclusion_reason"] = None
    line["lineage"] = {
        "source_kind": "freight_snapshot",
        "source_id": freight.id,
        "freight_snapshot_id": freight.id,
        "observation_id": freight.observation_id,
        "logistics_context_id": freight.logistics_context_id,
        "evidence_ref": freight.evidence_ref,
    }
    return line, amount * multiplier


def _calculate(
    snapshot: EconomicInputSnapshot,
    request: EconomicCalculationRequest,
    fx_snapshots: list[FXRateSnapshot],
    freight_snapshot: FreightSnapshot | None = None,
    customs_snapshot: CustomsTaxSnapshot | None = None,
) -> dict[str, Any]:
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
    context_value = payload.get("context")
    context: dict[str, object] = context_value if isinstance(context_value, dict) else {}
    component_rows = payload.get("components", [])
    components: list[dict[str, object]] = (
        [row for row in component_rows if isinstance(row, dict)]
        if isinstance(component_rows, list)
        else []
    )
    quote_rows = payload.get("quotes", [])
    quotes: list[dict[str, object]] = (
        [row for row in quote_rows if isinstance(row, dict)] if isinstance(quote_rows, list) else []
    )
    target_quantity = _decimal(context.get("target_quantity"))
    currency = _upper(context.get("base_currency")) or None
    lines: list[dict[str, object]] = []
    included_total = Decimal("0")
    included_categories: set[str] = set()
    missing: list[str] = []
    warnings: list[str] = []
    assumptions: list[dict[str, object]] = []
    stale: list[dict[str, object]] = []
    explicit_product = any(_upper(row.get("category")) == "PRODUCT_COST" for row in components)
    explicit_freight = any(_upper(row.get("category")) == "FREIGHT" for row in components)

    def add_line(line: dict[str, object], value: Decimal | None) -> None:
        nonlocal included_total
        converted, fx_issue = _apply_fx(line, value, currency, fx_snapshots)
        if fx_issue == "STALE_FX_RATE":
            warnings.append("Calculation includes stale FX rates.")
        elif fx_issue:
            missing.append(fx_issue)
        if converted is not None and line["inclusion_status"] == "INCLUDED":
            included_total += converted
            included_categories.add(str(line["category"]))
        if line["provenance"] == "ASSUMED" and line["inclusion_status"] == "INCLUDED":
            assumptions.append(
                {"source_id": line["source_id"], "reason": line["assumption_reason"]}
            )
        if line["freshness"] == "STALE" and line["inclusion_status"] == "INCLUDED":
            stale.append({"source_id": line["source_id"], "category": line["category"]})
        if line["inclusion_status"] == "EXCLUDED" and line["exclusion_reason"] in {
            "UNKNOWN_AMOUNT",
            "CURRENCY_MISMATCH",
            "UNSUPPORTED_BASIS",
            "NO_COMPATIBLE_FX_SNAPSHOT",
        }:
            missing.append(f"{line['category']}:{line['exclusion_reason']}")
        lines.append(line)

    for row in components:
        category = _upper(row.get("category"), "OTHER")
        line, value = _evaluate_source(
            source_kind="component",
            source=row,
            category=category,
            currency=_upper(row.get("currency")) if fx_snapshots else currency,
            target_quantity=target_quantity,
        )
        add_line(line, value)

    if customs_snapshot is not None:
        customs_lines, customs_missing, customs_warnings = build_customs_lines(
            None, None, customs_snapshot, currency, freight_snapshot
        )
        explicit_custom_categories = {_upper(row.get("category")) for row in components}
        for customs_line in customs_lines:
            if str(customs_line["category"]) in explicit_custom_categories:
                customs_line["inclusion_status"] = "EXCLUDED"
                customs_line["exclusion_reason"] = "EXPLICIT_COMPONENT_PRECEDENCE"
                warnings.append(
                    "An explicit 13A component takes precedence over customs/tax evidence."
                )
                lines.append(customs_line)
            else:
                customs_amount = customs_line.get("included_amount")
                add_line(
                    customs_line,
                    customs_amount if isinstance(customs_amount, Decimal) else None,
                )
        missing.extend(customs_missing)
        warnings.extend(customs_warnings)
    if freight_snapshot is not None and not explicit_freight:
        freight_line, freight_value = _freight_line(freight_snapshot)
        add_line(freight_line, freight_value)
    elif freight_snapshot is not None:
        warnings.append("Explicit FREIGHT component takes precedence over the freight snapshot.")

    if not explicit_product:
        for row in quotes:
            if _decimal(row.get("unit_price")) is None:
                continue
            source_currency = _upper(row.get("currency"))
            line, value = _evaluate_source(
                source_kind="quote",
                source=row,
                category="PRODUCT_COST",
                currency=(
                    source_currency if fx_snapshots and source_currency != currency else currency
                ),
                target_quantity=target_quantity,
            )
            if value is not None and "PRODUCT_COST" in included_categories:
                line["inclusion_status"] = "EXCLUDED"
                line["exclusion_reason"] = "DUPLICATE_PRODUCT_COST"
                lines.append(line)
            else:
                add_line(line, value)
            if "PRODUCT_COST" in included_categories:
                break
    else:
        for row in quotes:
            if _decimal(row.get("unit_price")) is not None:
                lines.append(
                    _line(
                        source_kind="quote",
                        source=row,
                        category="PRODUCT_COST",
                        reason="DUPLICATE_PRODUCT_COST",
                        basis=_upper(row.get("unit_basis")) or None,
                    )
                )

    if "PRODUCT_COST" not in included_categories:
        missing.append("PRODUCT_COST")
    if "FREIGHT" not in included_categories:
        missing.append("FREIGHT")
    if target_quantity is not None:
        for row in quotes:
            moq = _decimal(row.get("moq"))
            if moq is not None and target_quantity < moq:
                warnings.append(
                    "Target quantity is below the known MOQ; requested quantity was not changed."
                )
                break
    if currency is None:
        missing.append("base_currency")
        warnings.append("No calculation currency is present in the immutable snapshot.")
    if target_quantity is None or target_quantity <= 0:
        missing.append("target_quantity")
    if snapshot.completeness == "UNKNOWN":
        warnings.append("The immutable snapshot is marked UNKNOWN.")
    if assumptions:
        warnings.append("Calculation includes assumed inputs.")
    if stale:
        warnings.append("Calculation includes stale inputs.")
    missing = list(dict.fromkeys(missing))
    warnings = list(dict.fromkeys(warnings))
    status = (
        "INSUFFICIENT"
        if "PRODUCT_COST" not in included_categories
        else (
            "PARTIAL"
            if missing or warnings or any(line["inclusion_status"] == "EXCLUDED" for line in lines)
            else "COMPLETE"
        )
    )
    per_unit = (
        included_total / target_quantity if status != "INSUFFICIENT" and target_quantity else None
    )
    explanation = {
        "target_quantity": str(target_quantity) if target_quantity is not None else None,
        "currency": currency,
        "reporting_currency": currency,
        "included_total_label": (
            "Known-cost subtotal" if status != "COMPLETE" else "Calculated landed cost"
        ),
        "included_categories": sorted(included_categories),
        "missing_inputs": missing,
        "assumption_count": len(assumptions),
        "stale_input_count": len(stale),
        "fx_snapshot_ids": [str(item.id) for item in fx_snapshots],
        "freight_snapshot_id": str(freight_snapshot.id) if freight_snapshot else None,
        "rounding": (
            "Decimal arithmetic; values stored to 8 fractional places with " "HALF_UP rounding."
        ),
    }
    return {
        "status": status,
        "currency": currency,
        "reporting_currency": currency,
        "target_quantity": target_quantity,
        "total_included_cost": _money(included_total) or Decimal("0"),
        "per_unit_cost": _money(per_unit),
        "lines": lines,
        "missing_inputs": missing,
        "warnings": warnings,
        "assumptions": assumptions,
        "stale_inputs": stale,
        "explanation": explanation,
    }


def _is_unique_violation(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "pgcode", None) == "23505" or "duplicate key" in str(exc.orig).lower()


def calculate_from_snapshot(
    db: Session,
    owner: User,
    snapshot_id: uuid.UUID,
    request: EconomicCalculationRequest,
) -> tuple[EconomicCalculation, bool]:
    snapshot = db.scalar(
        select(EconomicInputSnapshot).where(
            EconomicInputSnapshot.id == snapshot_id, EconomicInputSnapshot.owner_id == owner.id
        )
    )
    if snapshot is None:
        raise HTTPException(404, "Economic snapshot is not available in the owner scope.")

    customs_snapshot: CustomsTaxSnapshot | None = None
    if request.customs_tax_snapshot_id is not None:
        customs_snapshot = db.scalar(
            select(CustomsTaxSnapshot).where(
                CustomsTaxSnapshot.id == request.customs_tax_snapshot_id,
                CustomsTaxSnapshot.owner_id == owner.id,
            )
        )
        if customs_snapshot is None:
            raise HTTPException(404, "Customs/tax snapshot is not available in the owner scope.")
        from vayujit_api.intelligence.economic_customs_models import CustomsTaxContext

        customs_context = db.scalar(
            select(CustomsTaxContext).where(
                CustomsTaxContext.id == customs_snapshot.context_id,
                CustomsTaxContext.owner_id == owner.id,
            )
        )
        if customs_context is None or customs_context.economic_context_id != snapshot.context_id:
            raise HTTPException(422, "Customs/tax snapshot must belong to the economic context.")
        if (
            request.calculation_version != CUSTOMS_CALCULATION_VERSION
            or request.policy_version != CUSTOMS_POLICY_VERSION
        ):
            raise HTTPException(
                422,
                "Customs/tax calculations require landed-cost-v4 and known-cost-customs-tax-v1.",
            )

    freight_snapshot: FreightSnapshot | None = None
    if request.freight_snapshot_id is not None:
        freight_snapshot = db.scalar(
            select(FreightSnapshot).where(
                FreightSnapshot.id == request.freight_snapshot_id,
                FreightSnapshot.owner_id == owner.id,
            )
        )
        if freight_snapshot is None:
            raise HTTPException(404, "Freight snapshot is not available in the owner scope.")
        logistics_context = db.scalar(
            select(LogisticsContext).where(
                LogisticsContext.id == freight_snapshot.logistics_context_id,
                LogisticsContext.owner_id == owner.id,
            )
        )
        if (
            logistics_context is None
            or logistics_context.economic_context_id != snapshot.context_id
        ):
            raise HTTPException(422, "Freight snapshot must belong to the economic context.")
        if request.customs_tax_snapshot_id is None and (
            request.calculation_version != FREIGHT_CALCULATION_VERSION
            or request.policy_version != FREIGHT_POLICY_VERSION
        ):
            raise HTTPException(
                422, "Freight calculations require landed-cost-v3 and known-cost-freight-v1."
            )

    fx_snapshots: list[FXRateSnapshot] = []
    if request.fx_snapshot_id is not None:
        fx = db.scalar(
            select(FXRateSnapshot).where(
                FXRateSnapshot.id == request.fx_snapshot_id, FXRateSnapshot.owner_id == owner.id
            )
        )
        if fx is None:
            raise HTTPException(404, "FX snapshot is not available in the owner scope.")
        fx_snapshots = [fx]
        if freight_snapshot is None and (
            request.calculation_version != FX_CALCULATION_VERSION
            or request.policy_version != FX_POLICY_VERSION
        ):
            raise HTTPException(422, "FX calculations require landed-cost-v2 and known-cost-fx-v1.")
    elif (
        freight_snapshot is None
        and customs_snapshot is None
        and (
            request.calculation_version != CALCULATION_VERSION
            or request.policy_version != POLICY_VERSION
        )
    ):
        raise HTTPException(422, "Unsupported calculation version or policy.")

    calc_fingerprint = fingerprint(
        {
            "snapshot_fingerprint": snapshot.fingerprint,
            "calculation_version": request.calculation_version,
            "policy_version": request.policy_version,
            "fx_snapshot_ids": [str(item.id) for item in fx_snapshots],
            "freight_snapshot_id": str(freight_snapshot.id) if freight_snapshot else None,
            "customs_tax_snapshot_id": str(customs_snapshot.id) if customs_snapshot else None,
            "options": request.options,
        }
    )
    existing = db.scalar(
        select(EconomicCalculation).where(
            EconomicCalculation.owner_id == owner.id,
            EconomicCalculation.calculation_fingerprint == calc_fingerprint,
        )
    )
    if existing is not None:
        return existing, True

    evaluated = _calculate(snapshot, request, fx_snapshots, freight_snapshot, customs_snapshot)
    row = EconomicCalculation(
        owner_id=owner.id,
        context_id=snapshot.context_id,
        snapshot_id=snapshot.id,
        fx_snapshot_id=fx_snapshots[0].id if fx_snapshots else None,
        freight_snapshot_id=freight_snapshot.id if freight_snapshot else None,
        customs_tax_snapshot_id=customs_snapshot.id if customs_snapshot else None,
        calculation_version=request.calculation_version,
        policy_version=request.policy_version,
        calculation_fingerprint=calc_fingerprint,
        status=evaluated["status"],
        currency=evaluated["currency"],
        reporting_currency=evaluated["reporting_currency"],
        target_quantity=(
            evaluated["target_quantity"]
            if evaluated["target_quantity"] is not None and evaluated["target_quantity"] > 0
            else None
        ),
        total_included_cost=evaluated["total_included_cost"],
        per_unit_cost=evaluated["per_unit_cost"],
        included_component_count=sum(
            1 for line in evaluated["lines"] if line["inclusion_status"] == "INCLUDED"
        ),
        excluded_component_count=sum(
            1 for line in evaluated["lines"] if line["inclusion_status"] == "EXCLUDED"
        ),
        missing_inputs=_json(evaluated["missing_inputs"]),
        warnings=_json(evaluated["warnings"]),
        assumptions=_json(evaluated["assumptions"]),
        stale_inputs=_json(evaluated["stale_inputs"]),
        explanation=_json(evaluated["explanation"]),
    )
    db.add(row)
    try:
        db.flush()
        for order, line in enumerate(evaluated["lines"]):
            db.add(
                EconomicCalculationBreakdown(
                    owner_id=owner.id,
                    calculation_id=row.id,
                    line_order=order,
                    source_kind=line["source_kind"],
                    source_id=line["source_id"],
                    category=line["category"],
                    original_amount=line["original_amount"],
                    currency=line["currency"],
                    basis=line["basis"],
                    multiplier=line["multiplier"],
                    included_amount=line["included_amount"],
                    converted_amount=line["converted_amount"],
                    fx_snapshot_id=line["fx_snapshot_id"],
                    fx_pair=line["fx_pair"],
                    fx_rate=line["fx_rate"],
                    fx_effective_at=line["fx_effective_at"],
                    fx_provider=line["fx_provider"],
                    fx_freshness=line["fx_freshness"],
                    fx_inverted=line["fx_inverted"],
                    freight_snapshot_id=line["freight_snapshot_id"],
                    customs_tax_snapshot_id=customs_snapshot.id if customs_snapshot else None,
                    provenance=line["provenance"],
                    freshness=line["freshness"],
                    assumption_reason=line["assumption_reason"],
                    evidence_ref=line["evidence_ref"],
                    inclusion_status=line["inclusion_status"],
                    exclusion_reason=line["exclusion_reason"],
                    lineage=_json(line["lineage"]),
                )
            )
        db.add(
            AuditEvent(
                actor_id=owner.id,
                action="intelligence.economic_calculation_created",
                entity_type="economic_calculation",
                entity_id=row.id,
                metadata_json={
                    "snapshot_id": str(snapshot.id),
                    "fx_snapshot_id": str(fx_snapshots[0].id) if fx_snapshots else None,
                    "freight_snapshot_id": str(freight_snapshot.id) if freight_snapshot else None,
                    "customs_tax_snapshot_id": (
                        str(customs_snapshot.id) if customs_snapshot else None
                    ),
                    "status": row.status,
                    "calculation_version": row.calculation_version,
                },
                occurred_at=now(),
                idempotency_key=f"intelligence.economic_calculation_created:{row.id}",
            )
        )
        if freight_snapshot is not None:
            db.add(
                AuditEvent(
                    actor_id=owner.id,
                    action="intelligence.economic_freight_linked",
                    entity_type="economic_calculation",
                    entity_id=row.id,
                    metadata_json={
                        "freight_snapshot_id": str(freight_snapshot.id),
                        "observation_id": str(freight_snapshot.observation_id),
                    },
                    occurred_at=now(),
                    idempotency_key=f"intelligence.economic_freight_linked:{row.id}",
                )
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _is_unique_violation(exc):
            raise
        existing = db.scalar(
            select(EconomicCalculation).where(
                EconomicCalculation.owner_id == owner.id,
                EconomicCalculation.calculation_fingerprint == calc_fingerprint,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def list_breakdown(
    db: Session, owner: User, calculation_id: uuid.UUID
) -> list[EconomicCalculationBreakdown]:
    return list(
        db.scalars(
            select(EconomicCalculationBreakdown)
            .where(
                EconomicCalculationBreakdown.owner_id == owner.id,
                EconomicCalculationBreakdown.calculation_id == calculation_id,
            )
            .order_by(EconomicCalculationBreakdown.line_order)
        )
    )
