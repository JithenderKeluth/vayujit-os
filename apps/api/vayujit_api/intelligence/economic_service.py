"""Owner-scoped service boundary for 13A economic inputs."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_models import (
    EconomicAssumption,
    EconomicContext,
    EconomicCostComponent,
    EconomicInputSnapshot,
    EconomicQuoteInput,
    EconomicSnapshotComponent,
)
from vayujit_api.intelligence.economic_schemas import (
    EconomicAssumptionCreate,
    EconomicContextCreate,
    EconomicContextUpdate,
    EconomicCostComponentCreate,
    EconomicQuoteInputCreate,
    safe_metadata,
)
from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.scenario_models import SourcingScenario
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence
from vayujit_api.products.models import Product


def now() -> datetime:
    return datetime.now(UTC)


def _safe_metadata(value: dict[str, object]) -> dict[str, object]:
    try:
        return safe_metadata(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _json(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_json(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _owned(db: Session, model: Any, owner_id: uuid.UUID, value: uuid.UUID, label: str) -> Any:
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


def _validate_context_refs(
    db: Session, owner: User, data: EconomicContextCreate | EconomicContextUpdate
) -> None:
    for value, model, label in (
        (data.product_id, Product, "Product"),
        (data.opportunity_id, IntelligenceOpportunity, "Product opportunity"),
        (data.supplier_id, Supplier, "Supplier"),
        (data.scenario_id, SourcingScenario, "Sourcing scenario"),
    ):
        if value is not None:
            _owned(db, model, owner.id, value, label)


def create_context(
    db: Session, owner: User, data: EconomicContextCreate
) -> tuple[EconomicContext, bool]:
    existing = db.scalar(
        select(EconomicContext).where(
            EconomicContext.owner_id == owner.id,
            EconomicContext.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    _validate_context_refs(db, owner, data)
    row = EconomicContext(owner_id=owner.id, **data.model_dump())
    db.add(row)
    db.flush()
    _audit(
        db,
        owner,
        "intelligence.economic_context_created",
        "economic_context",
        row.id,
        {"status": row.status},
    )
    db.commit()
    db.refresh(row)
    return row, False


def update_context(
    db: Session, owner: User, row: EconomicContext, data: EconomicContextUpdate
) -> EconomicContext:
    _validate_context_refs(db, owner, data)
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(row, key, value)
    row.version += 1
    row.updated_at = now()
    _audit(
        db,
        owner,
        "intelligence.economic_context_updated",
        "economic_context",
        row.id,
        {"version": row.version},
    )
    db.commit()
    db.refresh(row)
    return row


def create_quote(
    db: Session, owner: User, data: EconomicQuoteInputCreate
) -> tuple[EconomicQuoteInput, bool]:
    context = _owned(db, EconomicContext, owner.id, data.context_id, "Economic context")
    existing = db.scalar(
        select(EconomicQuoteInput).where(
            EconomicQuoteInput.owner_id == owner.id,
            EconomicQuoteInput.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    for value, model, label in (
        (data.supplier_id, Supplier, "Supplier"),
        (data.product_id, Product, "Product"),
        (data.evidence_ref, SupplierEvidence, "Evidence"),
    ):
        if value is not None:
            _owned(db, model, owner.id, value, label)
    if data.supplier_quote_id is not None:
        from vayujit_api.intelligence.sourcing_models import SupplierQuote

        _owned(db, SupplierQuote, owner.id, data.supplier_quote_id, "Supplier quote")
    if (
        data.provenance in {"QUOTED", "OBSERVED"}
        and data.unit_price is not None
        and data.evidence_ref is None
        and data.supplier_quote_id is None
    ):
        raise HTTPException(
            422, "Quoted or observed monetary input requires quote or evidence lineage."
        )
    values = data.model_dump()
    values["metadata_json"] = _safe_metadata(values["metadata_json"])
    row = EconomicQuoteInput(owner_id=owner.id, **values)
    db.add(row)
    db.flush()
    _audit(
        db,
        owner,
        "intelligence.economic_quote_recorded",
        "economic_quote_input",
        row.id,
        {"context_id": str(context.id), "provenance": row.provenance},
    )
    db.commit()
    db.refresh(row)
    return row, False


def create_component(
    db: Session, owner: User, data: EconomicCostComponentCreate
) -> tuple[EconomicCostComponent, bool]:
    _owned(db, EconomicContext, owner.id, data.context_id, "Economic context")
    if data.quote_input_id is not None:
        quote = _owned(
            db, EconomicQuoteInput, owner.id, data.quote_input_id, "Economic quote input"
        )
        if quote.context_id != data.context_id:
            raise HTTPException(422, "Quote input must belong to the economic context.")
    if data.evidence_ref is not None:
        _owned(db, SupplierEvidence, owner.id, data.evidence_ref, "Evidence")
    values = data.model_dump()
    values["metadata_json"] = _safe_metadata(values["metadata_json"])
    material = {key: value for key, value in values.items() if key not in {"context_id"}}
    component_fingerprint = fingerprint(material)
    existing = db.scalar(
        select(EconomicCostComponent).where(
            EconomicCostComponent.owner_id == owner.id,
            EconomicCostComponent.context_id == data.context_id,
            EconomicCostComponent.fingerprint == component_fingerprint,
        )
    )
    if existing:
        return existing, True
    row = EconomicCostComponent(owner_id=owner.id, fingerprint=component_fingerprint, **values)
    db.add(row)
    db.flush()
    _audit(
        db,
        owner,
        "intelligence.economic_component_added",
        "economic_cost_component",
        row.id,
        {"context_id": str(row.context_id), "category": row.category, "provenance": row.provenance},
    )
    db.commit()
    db.refresh(row)
    return row, False


def create_assumption(
    db: Session, owner: User, data: EconomicAssumptionCreate
) -> EconomicAssumption:
    _owned(db, EconomicContext, owner.id, data.context_id, "Economic context")
    current = db.scalar(
        select(EconomicAssumption)
        .where(
            EconomicAssumption.owner_id == owner.id,
            EconomicAssumption.context_id == data.context_id,
            EconomicAssumption.key == data.key,
        )
        .order_by(EconomicAssumption.version.desc())
    )
    row = EconomicAssumption(
        owner_id=owner.id, version=(current.version + 1 if current else 1), **data.model_dump()
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        owner,
        "intelligence.economic_assumption_added",
        "economic_assumption",
        row.id,
        {"context_id": str(row.context_id), "key": row.key},
    )
    db.commit()
    db.refresh(row)
    return row


def _snapshot_payload(
    db: Session, context: EconomicContext, owner_id: uuid.UUID
) -> tuple[dict[str, object], list[EconomicCostComponent], str]:
    quotes = list(
        db.scalars(
            select(EconomicQuoteInput)
            .where(
                EconomicQuoteInput.owner_id == owner_id, EconomicQuoteInput.context_id == context.id
            )
            .order_by(EconomicQuoteInput.id)
        )
    )
    components = list(
        db.scalars(
            select(EconomicCostComponent)
            .where(
                EconomicCostComponent.owner_id == owner_id,
                EconomicCostComponent.context_id == context.id,
            )
            .order_by(EconomicCostComponent.fingerprint)
        )
    )
    assumptions = list(
        db.scalars(
            select(EconomicAssumption)
            .where(
                EconomicAssumption.owner_id == owner_id, EconomicAssumption.context_id == context.id
            )
            .order_by(EconomicAssumption.key, EconomicAssumption.version)
        )
    )
    payload: dict[str, object] = {
        "context": {key: value for key, value in vars(context).items() if not key.startswith("_")},
        "quotes": [
            {key: value for key, value in vars(row).items() if not key.startswith("_")}
            for row in quotes
        ],
        "components": [
            {key: value for key, value in vars(row).items() if not key.startswith("_")}
            for row in components
        ],
        "assumptions": [
            {key: value for key, value in vars(row).items() if not key.startswith("_")}
            for row in assumptions
        ],
    }
    missing: list[str] = []
    if not quotes:
        missing.append("supplier_quote")
    if not context.base_currency:
        missing.append("base_currency")
    if not context.target_quantity or not context.quantity_unit:
        missing.append("target_quantity_unit")
    status = "COMPLETE" if not missing else "PARTIAL" if components or quotes else "UNKNOWN"
    payload["missing_inputs"] = missing
    payload["completeness"] = status
    return payload, components, fingerprint(payload)


def create_snapshot(
    db: Session, owner: User, context_id: uuid.UUID
) -> tuple[EconomicInputSnapshot, bool]:
    context = _owned(db, EconomicContext, owner.id, context_id, "Economic context")
    payload, components, input_fingerprint = _snapshot_payload(db, context, owner.id)
    existing = db.scalar(
        select(EconomicInputSnapshot).where(
            EconomicInputSnapshot.owner_id == owner.id,
            EconomicInputSnapshot.context_id == context.id,
            EconomicInputSnapshot.fingerprint == input_fingerprint,
        )
    )
    if existing:
        return existing, True
    current = (
        db.scalar(
            select(EconomicInputSnapshot.version)
            .where(
                EconomicInputSnapshot.owner_id == owner.id,
                EconomicInputSnapshot.context_id == context.id,
            )
            .order_by(EconomicInputSnapshot.version.desc())
        )
        or 0
    )
    row = EconomicInputSnapshot(
        owner_id=owner.id,
        context_id=context.id,
        version=current + 1,
        fingerprint=input_fingerprint,
        completeness=str(payload["completeness"]),
        missing_inputs=payload["missing_inputs"],
        payload=_json(payload),
    )
    db.add(row)
    db.flush()
    for component in components:
        db.add(
            EconomicSnapshotComponent(
                owner_id=owner.id, snapshot_id=row.id, component_id=component.id
            )
        )
    _audit(
        db,
        owner,
        "intelligence.economic_snapshot_created",
        "economic_input_snapshot",
        row.id,
        {"context_id": str(context.id), "fingerprint": input_fingerprint},
    )
    db.commit()
    db.refresh(row)
    return row, False
