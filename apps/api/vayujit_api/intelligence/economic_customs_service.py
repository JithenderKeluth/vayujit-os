"""Owner-scoped customs/tax evidence and deterministic snapshot service (13E)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_customs_models import (
    ClassificationEvidence,
    CustomsRateEvidence,
    CustomsTaxContext,
    CustomsTaxSnapshot,
    RegulatoryCostEvidence,
)
from vayujit_api.intelligence.economic_customs_schemas import (
    ClassificationEvidenceCreate,
    CustomsRateEvidenceCreate,
    CustomsTaxContextCreate,
    CustomsTaxSnapshotCreate,
    RegulatoryCostEvidenceCreate,
)
from vayujit_api.intelligence.economic_freight_models import FreightSnapshot
from vayujit_api.intelligence.economic_models import EconomicContext
from vayujit_api.intelligence.economic_schemas import safe_metadata
from vayujit_api.intelligence.economic_service import fingerprint, now
from vayujit_api.intelligence.supplier_models import SupplierEvidence


def _unique(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "pgcode", None) == "23505" or "duplicate key" in str(exc.orig).lower()


def _owned(db: Session, model: Any, owner_id: uuid.UUID, value: uuid.UUID, label: str):
    row = db.scalar(select(model).where(model.id == value, model.owner_id == owner_id))
    if row is None:
        raise HTTPException(404, f"{label} is not available in the owner scope.")
    return row


def _audit(
    db: Session,
    owner: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, object],
) -> None:
    db.add(
        AuditEvent(
            actor_id=owner.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            occurred_at=now(),
            idempotency_key=f"{action}:{entity_id}",
        )
    )


def _commit_create(
    db: Session,
    row: Any,
    owner: User,
    action: str,
    entity_type: str,
    metadata: dict[str, object],
    query: Any,
    key: str,
):
    db.add(row)
    try:
        db.flush()
        _audit(db, owner, action, entity_type, row.id, metadata)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _unique(exc):
            raise
        existing = db.scalar(query)
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def create_context(db: Session, owner: User, data: CustomsTaxContextCreate):
    economic = _owned(db, EconomicContext, owner.id, data.economic_context_id, "Economic context")
    if data.evidence_ref is not None:
        _owned(db, SupplierEvidence, owner.id, data.evidence_ref, "Evidence")
    existing = db.scalar(
        select(CustomsTaxContext).where(
            CustomsTaxContext.owner_id == owner.id,
            CustomsTaxContext.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    values = data.model_dump(exclude={"economic_context_id"})
    row = CustomsTaxContext(owner_id=owner.id, economic_context_id=economic.id, **values)
    return _commit_create(
        db,
        row,
        owner,
        "intelligence.customs_tax_context_created",
        "customs_tax_context",
        {"economic_context_id": str(economic.id)},
        select(CustomsTaxContext).where(
            CustomsTaxContext.owner_id == owner.id,
            CustomsTaxContext.idempotency_key == data.idempotency_key,
        ),
        data.idempotency_key,
    )


def _context(db: Session, owner: User, context_id: uuid.UUID) -> CustomsTaxContext:
    return _owned(db, CustomsTaxContext, owner.id, context_id, "Customs/tax context")


def create_classification(db: Session, owner: User, data: ClassificationEvidenceCreate):
    context = _context(db, owner, data.context_id)
    safe_metadata(data.metadata_json)
    existing = db.scalar(
        select(ClassificationEvidence).where(
            ClassificationEvidence.owner_id == owner.id,
            ClassificationEvidence.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    values = data.model_dump(exclude={"context_id", "idempotency_key", "metadata_json"})
    digest = fingerprint(
        {
            "context_id": str(context.id),
            "code": data.classification_code,
            "scheme": data.classification_scheme,
            "jurisdiction": data.jurisdiction,
            "source": data.source,
            "source_reference": data.source_reference,
            "version": data.version,
        }
    )
    row = ClassificationEvidence(
        owner_id=owner.id,
        context_id=context.id,
        idempotency_key=data.idempotency_key,
        metadata_json=data.metadata_json,
        fingerprint=digest,
        **values,
    )
    return _commit_create(
        db,
        row,
        owner,
        "intelligence.classification_evidence_recorded",
        "classification_evidence",
        {
            "context_id": str(context.id),
            "classification_code": data.classification_code,
            "provenance": data.provenance,
        },
        select(ClassificationEvidence).where(
            ClassificationEvidence.owner_id == owner.id,
            ClassificationEvidence.idempotency_key == data.idempotency_key,
        ),
        data.idempotency_key,
    )


def create_rate(db: Session, owner: User, data: CustomsRateEvidenceCreate):
    context = _context(db, owner, data.context_id)
    if data.classification_evidence_id is not None:
        evidence = _owned(
            db,
            ClassificationEvidence,
            owner.id,
            data.classification_evidence_id,
            "Classification evidence",
        )
        if evidence.context_id != context.id:
            raise HTTPException(
                422, "Classification evidence must belong to the customs/tax context."
            )
    if data.evidence_ref is not None:
        _owned(db, SupplierEvidence, owner.id, data.evidence_ref, "Evidence")
    existing = db.scalar(
        select(CustomsRateEvidence).where(
            CustomsRateEvidence.owner_id == owner.id,
            CustomsRateEvidence.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    values = data.model_dump(exclude={"context_id", "idempotency_key", "metadata_json"})
    digest = fingerprint(
        {
            "context_id": str(context.id),
            "classification_evidence_id": (
                str(data.classification_evidence_id) if data.classification_evidence_id else None
            ),
            "rate_kind": data.rate_kind,
            "category": data.category,
            "rate": str(data.rate),
            "basis": data.basis,
            "jurisdiction": data.jurisdiction,
            "effective_at": data.effective_at.isoformat() if data.effective_at else None,
            "version": data.version,
        }
    )
    row = CustomsRateEvidence(
        owner_id=owner.id,
        context_id=context.id,
        idempotency_key=data.idempotency_key,
        metadata_json=data.metadata_json,
        fingerprint=digest,
        **values,
    )
    return _commit_create(
        db,
        row,
        owner,
        "intelligence.customs_rate_evidence_recorded",
        "customs_rate_evidence",
        {
            "context_id": str(context.id),
            "rate_kind": data.rate_kind,
            "basis": data.basis,
            "provenance": data.provenance,
        },
        select(CustomsRateEvidence).where(
            CustomsRateEvidence.owner_id == owner.id,
            CustomsRateEvidence.idempotency_key == data.idempotency_key,
        ),
        data.idempotency_key,
    )


def create_regulatory_cost(db: Session, owner: User, data: RegulatoryCostEvidenceCreate):
    context = _context(db, owner, data.context_id)
    if data.evidence_ref is not None:
        _owned(db, SupplierEvidence, owner.id, data.evidence_ref, "Evidence")
    existing = db.scalar(
        select(RegulatoryCostEvidence).where(
            RegulatoryCostEvidence.owner_id == owner.id,
            RegulatoryCostEvidence.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    values = data.model_dump(exclude={"context_id", "idempotency_key", "metadata_json"})
    digest = fingerprint(
        {
            "context_id": str(context.id),
            "category": data.cost_category,
            "amount": str(data.amount) if data.amount is not None else None,
            "currency": data.currency,
            "requirement_type": data.requirement_type,
            "source": data.source,
            "version": data.version,
        }
    )
    row = RegulatoryCostEvidence(
        owner_id=owner.id,
        context_id=context.id,
        idempotency_key=data.idempotency_key,
        metadata_json=data.metadata_json,
        fingerprint=digest,
        **values,
    )
    return _commit_create(
        db,
        row,
        owner,
        "intelligence.regulatory_cost_evidence_recorded",
        "regulatory_cost_evidence",
        {
            "context_id": str(context.id),
            "requirement_state": data.requirement_state,
            "cost_category": data.cost_category,
        },
        select(RegulatoryCostEvidence).where(
            RegulatoryCostEvidence.owner_id == owner.id,
            RegulatoryCostEvidence.idempotency_key == data.idempotency_key,
        ),
        data.idempotency_key,
    )


def _dump(row: Any) -> dict[str, object]:
    result: dict[str, object] = {}
    for column in row.__table__.columns:
        key = column.key
        value = getattr(row, key)
        if isinstance(value, (uuid.UUID, Decimal)):
            value = str(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        result[key] = value
    return result


def create_snapshot(db: Session, owner: User, data: CustomsTaxSnapshotCreate):
    context = _context(db, owner, data.context_id)

    def selected(model: Any, ids: list[uuid.UUID] | None, label: str):
        query = select(model).where(model.owner_id == owner.id, model.context_id == context.id)
        rows = list(db.scalars(query.order_by(model.created_at, model.id))) if ids is None else []
        if ids is not None:
            for value in ids:
                row = _owned(db, model, owner.id, value, label)
                if row.context_id != context.id:
                    raise HTTPException(422, f"{label} must belong to the customs/tax context.")
                rows.append(row)
        return rows

    classifications = selected(
        ClassificationEvidence, data.classification_evidence_ids, "Classification evidence"
    )
    rates = selected(CustomsRateEvidence, data.rate_evidence_ids, "Customs rate evidence")
    costs = selected(
        RegulatoryCostEvidence, data.regulatory_cost_evidence_ids, "Regulatory cost evidence"
    )
    basis = {key: value.model_dump(mode="json") for key, value in data.basis_inputs.items()}
    classification_keys = {
        (r.classification_code, r.classification_scheme, r.jurisdiction) for r in classifications
    }
    rate_keys: dict[tuple[str, str, str], set[str]] = {}
    for r in rates:
        rate_keys.setdefault((r.rate_kind, r.basis, r.jurisdiction), set()).add(str(r.rate))
    conflicts = {
        "classifications": len(classification_keys) > 1,
        "rates": any(len(values) > 1 for values in rate_keys.values()),
    }
    missing: list[str] = []
    if not classifications:
        missing.append("classification_evidence")
    if not rates:
        missing.append("rate_evidence")
    unknown_rates = [r for r in rates if r.basis == "UNKNOWN"]
    if unknown_rates:
        missing.append("UNKNOWN_RATE_BASIS")
    payload = {
        "context": {
            "id": str(context.id),
            "economic_context_id": str(context.economic_context_id),
            "origin_country": context.origin_country,
            "destination_country": context.destination_country,
            "reporting_currency": context.reporting_currency,
            "classification_code": context.classification_code,
            "classification_scheme": context.classification_scheme,
            "classification_provenance": context.classification_provenance,
        },
        "basis_inputs": basis,
        "classifications": [_dump(r) for r in classifications],
        "rates": [_dump(r) for r in rates],
        "regulatory_costs": [_dump(r) for r in costs],
        "conflicts": conflicts,
    }
    completeness = (
        "UNKNOWN"
        if not rates
        else (
            "PARTIAL"
            if missing or any(conflicts.values()) or any(r.freshness != "CURRENT" for r in rates)
            else "COMPLETE"
        )
    )
    digest = fingerprint(
        {
            "context_id": str(context.id),
            "version": data.version,
            "basis_inputs": basis,
            "classifications": [r.fingerprint for r in classifications],
            "rates": [r.fingerprint for r in rates],
            "regulatory_costs": [r.fingerprint for r in costs],
        }
    )
    existing = db.scalar(
        select(CustomsTaxSnapshot).where(
            CustomsTaxSnapshot.owner_id == owner.id, CustomsTaxSnapshot.fingerprint == digest
        )
    )
    if existing is not None:
        return existing, True
    row = CustomsTaxSnapshot(
        owner_id=owner.id,
        context_id=context.id,
        version=data.version,
        fingerprint=digest,
        completeness=completeness,
        payload=payload,
        missing_inputs=missing,
        warnings=(
            ["Conflicting evidence is preserved; no winner was selected."]
            if any(conflicts.values())
            else []
        ),
    )
    return _commit_create(
        db,
        row,
        owner,
        "intelligence.customs_tax_snapshot_created",
        "customs_tax_snapshot",
        {"context_id": str(context.id), "completeness": completeness, "conflicts": conflicts},
        select(CustomsTaxSnapshot).where(
            CustomsTaxSnapshot.owner_id == owner.id, CustomsTaxSnapshot.fingerprint == digest
        ),
        digest,
    )


def list_rows(db: Session, owner: User, model: Any, context_id: uuid.UUID | None = None):
    query = select(model).where(model.owner_id == owner.id)
    if context_id is not None:
        query = query.where(model.context_id == context_id)
    return list(db.scalars(query.order_by(model.created_at.desc())))


def get_row(db: Session, owner: User, model: Any, value: uuid.UUID, label: str):
    return _owned(db, model, owner.id, value, label)


def build_customs_lines(
    db: Session | None,
    owner: User | None,
    snapshot: CustomsTaxSnapshot,
    target_currency: str | None,
    freight_snapshot: FreightSnapshot | None = None,
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
    bases_value = payload.get("basis_inputs", {})
    bases: dict[str, object] = (
        cast(dict[str, object], bases_value) if isinstance(bases_value, dict) else {}
    )
    lines: list[dict[str, object]] = []
    missing: list[str] = []
    warnings: list[str] = []

    def base_value(rate: dict[str, object]):
        basis = str(rate.get("basis") or "UNKNOWN")
        raw = bases.get(basis)
        if not isinstance(raw, dict) or raw.get("amount") is None or not raw.get("currency"):
            return None, None, "UNKNOWN_BASIS"
        amount = Decimal(str(raw["amount"]))
        currency = str(raw["currency"]).upper()
        if basis == "PRODUCT_PLUS_FREIGHT":
            ref = raw.get("freight_snapshot_id")
            if freight_snapshot is None or str(freight_snapshot.id) != str(ref):
                return None, currency, "MISSING_REFERENCED_FREIGHT"
            if freight_snapshot.amount is None or not freight_snapshot.currency:
                return None, currency, "UNKNOWN_FREIGHT"
            if freight_snapshot.currency != currency:
                return None, currency, "FREIGHT_CURRENCY_MISMATCH"
            amount += Decimal(str(freight_snapshot.amount))
        return amount, currency, None

    rates_value = payload.get("rates", [])
    rates = rates_value if isinstance(rates_value, list) else []
    for rate in rates:
        if not isinstance(rate, dict):
            continue
        category = str(rate.get("category") or "OTHER")
        amount, currency, reason = base_value(rate)
        line = {
            "source_kind": "customs_rate_evidence",
            "source_id": rate.get("id"),
            "category": category,
            "original_amount": (
                amount * Decimal(str(rate.get("rate"))) if amount is not None else None
            ),
            "currency": currency,
            "basis": rate.get("basis"),
            "multiplier": Decimal(str(rate.get("rate"))) if rate.get("rate") is not None else None,
            "included_amount": None,
            "converted_amount": None,
            "fx_snapshot_id": None,
            "fx_pair": None,
            "fx_rate": None,
            "fx_effective_at": None,
            "fx_provider": None,
            "fx_freshness": None,
            "fx_inverted": None,
            "freight_snapshot_id": (
                freight_snapshot.id
                if rate.get("basis") == "PRODUCT_PLUS_FREIGHT" and freight_snapshot
                else None
            ),
            "provenance": str(rate.get("provenance") or "UNKNOWN"),
            "freshness": str(rate.get("freshness") or "UNKNOWN"),
            "assumption_reason": rate.get("assumption_reason"),
            "evidence_ref": rate.get("evidence_ref"),
            "inclusion_status": "EXCLUDED",
            "exclusion_reason": reason,
            "lineage": {
                "source_kind": "customs_rate_evidence",
                "source_id": rate.get("id"),
                "customs_tax_snapshot_id": str(snapshot.id),
                "classification_evidence_id": rate.get("classification_evidence_id"),
                "rate_scale": rate.get("rate_scale"),
                "basis": rate.get("basis"),
            },
        }
        if reason is None and amount is not None:
            line["included_amount"] = amount * Decimal(str(rate.get("rate")))
            line["inclusion_status"] = "INCLUDED"
            line["exclusion_reason"] = None
        else:
            missing.append(f"{category}:{reason}")
        lines.append(line)
    costs_value = payload.get("regulatory_costs", [])
    costs = costs_value if isinstance(costs_value, list) else []
    for cost in costs:
        if not isinstance(cost, dict):
            continue
        amount = cost.get("amount")
        currency = cost.get("currency")
        reason = None if amount is not None and currency else "UNKNOWN_AMOUNT"
        line = {
            "source_kind": "regulatory_cost_evidence",
            "source_id": cost.get("id"),
            "category": cost.get("cost_category", "OTHER"),
            "original_amount": Decimal(str(amount)) if amount is not None else None,
            "currency": currency,
            "basis": "REGULATORY_COST",
            "multiplier": Decimal("1") if amount is not None else None,
            "included_amount": Decimal(str(amount)) if amount is not None and currency else None,
            "converted_amount": None,
            "fx_snapshot_id": None,
            "fx_pair": None,
            "fx_rate": None,
            "fx_effective_at": None,
            "fx_provider": None,
            "fx_freshness": None,
            "fx_inverted": None,
            "freight_snapshot_id": None,
            "provenance": cost.get("provenance", "UNKNOWN"),
            "freshness": cost.get("freshness", "UNKNOWN"),
            "assumption_reason": cost.get("assumption_reason"),
            "evidence_ref": cost.get("evidence_ref"),
            "inclusion_status": "INCLUDED" if reason is None else "EXCLUDED",
            "exclusion_reason": reason,
            "lineage": {
                "source_kind": "regulatory_cost_evidence",
                "source_id": cost.get("id"),
                "customs_tax_snapshot_id": str(snapshot.id),
                "requirement_type": cost.get("requirement_type"),
                "requirement_state": cost.get("requirement_state"),
                "compliance_status": "NOT_DETERMINED",
            },
        }
        lines.append(line)
        if reason:
            missing.append(f"{line['category']}:{reason}")
    if snapshot.completeness != "COMPLETE":
        warnings.append(
            "Customs/tax inputs are partial or unknown; no legal or customs determination "
            "is implied."
        )
    conflicts_value = payload.get("conflicts", {})
    conflicts = conflicts_value if isinstance(conflicts_value, dict) else {}
    if conflicts.get("classifications") or conflicts.get("rates"):
        warnings.append("Conflicting customs/tax evidence is preserved without selecting a winner.")
    return lines, list(dict.fromkeys(missing)), list(dict.fromkeys(warnings))
