"""Deterministic owner-scoped FX observation and snapshot services (13C)."""

from __future__ import annotations

import uuid
from decimal import Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_fx_models import FXObservation, FXRateSnapshot
from vayujit_api.intelligence.economic_schemas import (
    FXObservationCreate,
    FXSnapshotCreate,
    safe_metadata,
)
from vayujit_api.intelligence.economic_service import fingerprint, now


def _unique(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "pgcode", None) == "23505" or "duplicate key" in str(exc.orig).lower()


def create_observation(
    db: Session, owner: User, data: FXObservationCreate
) -> tuple[FXObservation, bool]:
    metadata = safe_metadata(data.metadata_json)
    canonical = {
        "base_currency": data.base_currency,
        "quote_currency": data.quote_currency,
        "rate": str(data.rate),
        "observed_at": data.observed_at.isoformat(),
        "provider": data.provider,
        "mode": data.mode,
        "provenance": data.provenance,
        "freshness": data.freshness,
        "evidence_ref": str(data.evidence_ref) if data.evidence_ref else None,
        "assumption_reason": data.assumption_reason,
        "metadata": metadata,
    }
    digest = fingerprint(canonical)
    existing = db.scalar(
        select(FXObservation).where(
            FXObservation.owner_id == owner.id,
            FXObservation.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing, True
    row = FXObservation(
        owner_id=owner.id,
        idempotency_key=data.idempotency_key,
        fingerprint=digest,
        metadata_json=metadata,
        **data.model_dump(exclude={"idempotency_key", "metadata_json"}),
    )
    db.add(row)
    try:
        db.flush()
        db.add(
            AuditEvent(
                actor_id=owner.id,
                action="intelligence.fx_observation_created",
                entity_type="fx_observation",
                entity_id=row.id,
                metadata_json={
                    "pair": f"{row.base_currency}/{row.quote_currency}",
                    "mode": row.mode,
                    "freshness": row.freshness,
                },
                occurred_at=now(),
                idempotency_key=f"intelligence.fx_observation_created:{row.id}",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _unique(exc):
            raise
        existing = db.scalar(
            select(FXObservation).where(
                FXObservation.owner_id == owner.id,
                FXObservation.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def create_snapshot(
    db: Session, owner: User, data: FXSnapshotCreate
) -> tuple[FXRateSnapshot, bool]:
    observation = db.scalar(
        select(FXObservation).where(
            FXObservation.id == data.observation_id, FXObservation.owner_id == owner.id
        )
    )
    if observation is None:
        raise HTTPException(404, "FX observation is not available in the owner scope.")
    direct = (
        data.base_currency == observation.base_currency
        and data.quote_currency == observation.quote_currency
    )
    inverse = (
        data.base_currency == observation.quote_currency
        and data.quote_currency == observation.base_currency
    )
    if not direct and not inverse:
        raise HTTPException(422, "Only direct or inverse FX pairs are supported.")
    rate = observation.rate
    if inverse:
        with localcontext() as context:
            context.prec = 40
            rate = Decimal(1) / Decimal(observation.rate)
    digest = fingerprint(
        {
            "observation": str(observation.fingerprint),
            "base": data.base_currency,
            "quote": data.quote_currency,
            "version": data.version,
        }
    )
    existing = db.scalar(
        select(FXRateSnapshot).where(
            FXRateSnapshot.owner_id == owner.id, FXRateSnapshot.fingerprint == digest
        )
    )
    if existing is not None:
        return existing, True
    row = FXRateSnapshot(
        owner_id=owner.id,
        observation_id=observation.id,
        base_currency=data.base_currency,
        quote_currency=data.quote_currency,
        rate=rate,
        effective_at=observation.observed_at,
        provider=observation.provider,
        provenance=observation.provenance,
        freshness=observation.freshness,
        evidence_ref=observation.evidence_ref,
        assumption_reason=observation.assumption_reason,
        source_mode=observation.mode,
        original_base_currency=observation.base_currency,
        original_quote_currency=observation.quote_currency,
        original_rate=observation.rate,
        inverted=inverse,
        fingerprint=digest,
        version=data.version,
    )
    db.add(row)
    try:
        db.flush()
        db.add(
            AuditEvent(
                actor_id=owner.id,
                action="intelligence.fx_snapshot_created",
                entity_type="fx_snapshot",
                entity_id=row.id,
                metadata_json={
                    "pair": f"{row.base_currency}/{row.quote_currency}",
                    "inverted": row.inverted,
                    "observation_id": str(observation.id),
                },
                occurred_at=now(),
                idempotency_key=f"intelligence.fx_snapshot_created:{row.id}",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _unique(exc):
            raise
        existing = db.scalar(
            select(FXRateSnapshot).where(
                FXRateSnapshot.owner_id == owner.id, FXRateSnapshot.fingerprint == digest
            )
        )
        if existing is None:
            raise
        return existing, True
    db.refresh(row)
    return row, False


def list_observations(db: Session, owner: User) -> list[FXObservation]:
    return list(
        db.scalars(
            select(FXObservation)
            .where(FXObservation.owner_id == owner.id)
            .order_by(FXObservation.observed_at.desc())
        )
    )


def list_snapshots(db: Session, owner: User) -> list[FXRateSnapshot]:
    return list(
        db.scalars(
            select(FXRateSnapshot)
            .where(FXRateSnapshot.owner_id == owner.id)
            .order_by(FXRateSnapshot.created_at.desc())
        )
    )


def get_snapshot(db: Session, owner: User, snapshot_id: uuid.UUID) -> FXRateSnapshot:
    row = db.scalar(
        select(FXRateSnapshot).where(
            FXRateSnapshot.id == snapshot_id, FXRateSnapshot.owner_id == owner.id
        )
    )
    if row is None:
        raise HTTPException(404, "FX snapshot is not available in the owner scope.")
    return row
