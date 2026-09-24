"""Deterministic owner-scoped logistics and freight evidence service (13D)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_freight_models import (
    FreightObservation,
    FreightSnapshot,
    LogisticsContext,
)
from vayujit_api.intelligence.economic_models import EconomicContext
from vayujit_api.intelligence.economic_schemas import (
    FreightObservationCreate,
    FreightSnapshotCreate,
    LogisticsContextCreate,
    safe_metadata,
)
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


def create_logistics_context(
    db: Session, owner: User, data: LogisticsContextCreate
) -> tuple[LogisticsContext, bool]:
    economic_context = _owned(
        db, EconomicContext, owner.id, data.economic_context_id, "Economic context"
    )
    existing = db.scalar(
        select(LogisticsContext).where(
            LogisticsContext.owner_id == owner.id,
            LogisticsContext.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    values = data.model_dump(exclude={"economic_context_id"})
    row = LogisticsContext(owner_id=owner.id, economic_context_id=economic_context.id, **values)
    db.add(row)
    try:
        db.flush()
        _audit(
            db,
            owner,
            "intelligence.logistics_context_created",
            "logistics_context",
            row.id,
            {"economic_context_id": str(economic_context.id), "transport_mode": row.transport_mode},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _unique(exc):
            raise
        existing = db.scalar(
            select(LogisticsContext).where(
                LogisticsContext.owner_id == owner.id,
                LogisticsContext.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def create_observation(
    db: Session, owner: User, data: FreightObservationCreate
) -> tuple[FreightObservation, bool]:
    context = _owned(db, LogisticsContext, owner.id, data.logistics_context_id, "Logistics context")
    if data.evidence_ref is not None:
        _owned(db, SupplierEvidence, owner.id, data.evidence_ref, "Evidence")
    existing = db.scalar(
        select(FreightObservation).where(
            FreightObservation.owner_id == owner.id,
            FreightObservation.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    quoted_at = data.quoted_at or now()
    freshness = data.freshness
    if freshness == "CURRENT" and data.valid_until is not None and data.valid_until < now():
        freshness = "STALE"
    metadata = safe_metadata(data.metadata_json)
    values = data.model_dump(
        exclude={
            "logistics_context_id",
            "quoted_at",
            "freshness",
            "transport_mode",
            "origin_country",
            "origin_location",
            "destination_country",
            "destination_location",
            "quoted_quantity",
            "quoted_quantity_unit",
            "quoted_weight",
            "quoted_weight_unit",
            "quoted_volume",
            "quoted_volume_unit",
            "quoted_package_count",
            "quoted_container_count",
            "incoterm",
            "metadata_json",
        }
    )
    copied = {
        "transport_mode": data.transport_mode or context.transport_mode,
        "origin_country": (
            data.origin_country if data.origin_country is not None else context.origin_country
        ),
        "origin_location": (
            data.origin_location if data.origin_location is not None else context.origin_location
        ),
        "destination_country": (
            data.destination_country
            if data.destination_country is not None
            else context.destination_country
        ),
        "destination_location": (
            data.destination_location
            if data.destination_location is not None
            else context.destination_location
        ),
        "quoted_quantity": (
            data.quoted_quantity if data.quoted_quantity is not None else context.target_quantity
        ),
        "quoted_quantity_unit": (
            data.quoted_quantity_unit
            if data.quoted_quantity_unit is not None
            else context.quantity_unit
        ),
        "quoted_weight": (
            data.quoted_weight if data.quoted_weight is not None else context.total_weight
        ),
        "quoted_weight_unit": (
            data.quoted_weight_unit if data.quoted_weight_unit is not None else context.weight_unit
        ),
        "quoted_volume": (
            data.quoted_volume if data.quoted_volume is not None else context.total_volume
        ),
        "quoted_volume_unit": (
            data.quoted_volume_unit if data.quoted_volume_unit is not None else context.volume_unit
        ),
        "quoted_package_count": (
            data.quoted_package_count
            if data.quoted_package_count is not None
            else context.package_count
        ),
        "quoted_container_count": (
            data.quoted_container_count
            if data.quoted_container_count is not None
            else context.container_count
        ),
        "incoterm": data.incoterm if data.incoterm is not None else context.incoterm,
        "quoted_at": quoted_at,
        "freshness": freshness,
        "metadata_json": metadata,
    }
    canonical = {
        "logistics_context_id": str(context.id),
        **{key: value for key, value in values.items() if key != "version"},
        **copied,
        "version": data.version,
    }
    digest = fingerprint(canonical)
    row = FreightObservation(
        owner_id=owner.id,
        logistics_context_id=context.id,
        fingerprint=digest,
        **values,
        **copied,
    )
    db.add(row)
    try:
        db.flush()
        _audit(
            db,
            owner,
            "intelligence.freight_observation_recorded",
            "freight_observation",
            row.id,
            {
                "logistics_context_id": str(context.id),
                "provider": row.provider,
                "mode": row.mode,
                "provenance": row.provenance,
                "freshness": row.freshness,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _unique(exc):
            raise
        existing = db.scalar(
            select(FreightObservation).where(
                FreightObservation.owner_id == owner.id,
                FreightObservation.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def create_snapshot(
    db: Session, owner: User, data: FreightSnapshotCreate
) -> tuple[FreightSnapshot, bool]:
    observation = _owned(
        db, FreightObservation, owner.id, data.observation_id, "Freight observation"
    )
    digest = fingerprint(
        {
            "observation_fingerprint": observation.fingerprint,
            "observation_version": observation.version,
            "snapshot_version": data.version,
        }
    )
    existing = db.scalar(
        select(FreightSnapshot).where(
            FreightSnapshot.owner_id == owner.id,
            FreightSnapshot.fingerprint == digest,
        )
    )
    if existing is not None:
        return existing, True
    fields = {
        key: getattr(observation, key)
        for key in (
            "logistics_context_id",
            "amount",
            "currency",
            "basis",
            "transport_mode",
            "origin_country",
            "origin_location",
            "destination_country",
            "destination_location",
            "quoted_quantity",
            "quoted_quantity_unit",
            "quoted_weight",
            "quoted_weight_unit",
            "quoted_volume",
            "quoted_volume_unit",
            "quoted_package_count",
            "quoted_container_count",
            "incoterm",
            "quoted_at",
            "valid_until",
            "provider",
            "mode",
            "provenance",
            "freshness",
            "evidence_ref",
            "assumption_reason",
            "metadata_json",
        )
    }
    row = FreightSnapshot(
        owner_id=owner.id,
        observation_id=observation.id,
        source_mode=observation.mode,
        version=data.version,
        fingerprint=digest,
        **fields,
    )
    db.add(row)
    try:
        db.flush()
        _audit(
            db,
            owner,
            "intelligence.freight_snapshot_created",
            "freight_snapshot",
            row.id,
            {
                "observation_id": str(observation.id),
                "logistics_context_id": str(observation.logistics_context_id),
                "source_mode": row.source_mode,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _unique(exc):
            raise
        existing = db.scalar(
            select(FreightSnapshot).where(
                FreightSnapshot.owner_id == owner.id,
                FreightSnapshot.fingerprint == digest,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def list_logistics_contexts(db: Session, owner: User) -> list[LogisticsContext]:
    return list(
        db.scalars(
            select(LogisticsContext)
            .where(LogisticsContext.owner_id == owner.id)
            .order_by(LogisticsContext.updated_at.desc())
        )
    )


def get_logistics_context(db: Session, owner: User, context_id: uuid.UUID) -> LogisticsContext:
    return _owned(db, LogisticsContext, owner.id, context_id, "Logistics context")


def list_observations(db: Session, owner: User) -> list[FreightObservation]:
    return list(
        db.scalars(
            select(FreightObservation)
            .where(FreightObservation.owner_id == owner.id)
            .order_by(FreightObservation.created_at.desc())
        )
    )


def get_observation(db: Session, owner: User, observation_id: uuid.UUID) -> FreightObservation:
    return _owned(db, FreightObservation, owner.id, observation_id, "Freight observation")


def list_snapshots(db: Session, owner: User) -> list[FreightSnapshot]:
    return list(
        db.scalars(
            select(FreightSnapshot)
            .where(FreightSnapshot.owner_id == owner.id)
            .order_by(FreightSnapshot.created_at.desc())
        )
    )


def get_snapshot(db: Session, owner: User, snapshot_id: uuid.UUID) -> FreightSnapshot:
    return _owned(db, FreightSnapshot, owner.id, snapshot_id, "Freight snapshot")
