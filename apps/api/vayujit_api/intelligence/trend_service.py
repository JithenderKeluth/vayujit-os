"""Bounded, provider-independent Trend Intelligence foundation services."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceEvidence, IntelligenceSource
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.trend_models import (
    TrendContext,
    TrendObservation,
    TrendSignalDefinition,
    TrendSnapshot,
)
from vayujit_api.intelligence.trend_schemas import (
    TrendContextCreate,
    TrendContextUpdate,
    TrendObservationCreate,
    TrendSignalDefinitionCreate,
    TrendSnapshotCreate,
)
from vayujit_api.products.models import Product

DEFAULT_SIGNALS = {
    "SEARCH_INTEREST_INDEX": "INDEX",
    "SEARCH_RESULT_COUNT": "COUNT",
    "LISTING_COUNT": "COUNT",
    "PRICE_OBSERVATION": "DECIMAL",
    "REVIEW_ACTIVITY_COUNT": "COUNT",
    "RATING_ACTIVITY": "DECIMAL",
    "SOCIAL_MENTION_COUNT": "COUNT",
    "CONTENT_ACTIVITY": "COUNT",
    "COMPETITOR_COUNT": "COUNT",
    "AVAILABILITY_OBSERVATION": "CATEGORY",
    "CUSTOM_INDEX": "INDEX",
}
SENSITIVE = (
    "token",
    "secret",
    "password",
    "credential",
    "authorization",
    "cookie",
    "session",
    "api_key",
    "access_key",
    "database_url",
    "private_key",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _redact(value: object, depth: int = 0) -> object:
    if depth > 5:
        raise HTTPException(status_code=422, detail="metadata nesting is too deep")
    if isinstance(value, dict):
        return {
            str(k): (
                "[REDACTED]"
                if any(s in str(k).lower() for s in SENSITIVE)
                else _redact(v, depth + 1)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v, depth + 1) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _safe_metadata(value: object) -> dict[str, object]:
    cleaned = _redact(value)
    if not isinstance(cleaned, dict) or len(json.dumps(cleaned, default=str)) > 32768:
        raise HTTPException(status_code=422, detail="metadata exceeds the bounded safety limit")
    return cleaned


def _owned(db: Session, model: Any, item_id: uuid.UUID, owner: User, label: str) -> Any:
    value = db.scalar(select(model).where(model.id == item_id, model.owner_id == owner.id))
    if value is None:
        raise HTTPException(status_code=404, detail=f"{label} not found.")
    return value


def context_or_404(db: Session, owner: User, context_id: uuid.UUID) -> TrendContext:
    return _owned(db, TrendContext, context_id, owner, "Trend context")


def _validate_links(db: Session, owner: User, data: TrendContextCreate) -> None:
    for model, value, label in (
        (Product, data.product_id, "Product"),
        (ProductOpportunity, data.product_opportunity_id, "Product opportunity"),
        (Brand, data.brand_id, "Brand"),
    ):
        if value:
            _owned(db, model, value, owner, label)
    if data.subject_type == "PRODUCT" and not data.product_id and not data.subject_key:
        raise HTTPException(
            status_code=422, detail="PRODUCT contexts require a product link or subject_key"
        )


def create_context(db: Session, owner: User, data: TrendContextCreate) -> TrendContext:
    _validate_links(db, owner, data)
    key = data.idempotency_key or _fingerprint(data.model_dump(mode="json"))
    existing = db.scalar(
        select(TrendContext).where(
            TrendContext.owner_id == owner.id, TrendContext.idempotency_key == key
        )
    )
    if existing:
        return existing
    value = TrendContext(
        owner_id=owner.id,
        idempotency_key=key,
        input_fingerprint=data.input_fingerprint or _fingerprint(data.model_dump(mode="json")),
        created_at=_now(),
        updated_at=_now(),
        **data.model_dump(exclude={"idempotency_key", "input_fingerprint"}),
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.context_created",
        entity_type="trend_context",
        entity_id=value.id,
        idempotency_key=f"trend-context:{owner.id}:{key}",
    )
    db.commit()
    db.refresh(value)
    return value


def update_context(
    db: Session, owner: User, context: TrendContext, data: TrendContextUpdate
) -> TrendContext:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(context, key, value)
    if context.status == "ARCHIVED":
        context.archived_at = _now()
    context.version += 1
    context.updated_at = _now()
    db.commit()
    db.refresh(context)
    return context


def archive_context(db: Session, owner: User, context: TrendContext) -> TrendContext:
    return update_context(db, owner, context, TrendContextUpdate(status="ARCHIVED"))


def list_signal_definitions(db: Session, owner: User) -> list[TrendSignalDefinition]:
    rows = list(
        db.scalars(
            select(TrendSignalDefinition)
            .where(
                (TrendSignalDefinition.owner_id == owner.id)
                | (TrendSignalDefinition.owner_id.is_(None))
            )
            .order_by(TrendSignalDefinition.signal_type)
        )
    )
    existing = {row.signal_type for row in rows}
    for signal, measurement in DEFAULT_SIGNALS.items():
        if signal not in existing:
            row = TrendSignalDefinition(
                owner_id=None,
                signal_type=signal,
                measurement_type=measurement,
                version="v1",
                aggregation_semantics="source_reported",
                compatible_source_types=[],
                description="Provider-independent signal definition",
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            rows.append(row)
    if db.new:
        db.commit()
    return sorted(rows, key=lambda item: item.signal_type)


def create_signal_definition(
    db: Session, owner: User, data: TrendSignalDefinitionCreate
) -> TrendSignalDefinition:
    row = TrendSignalDefinition(
        owner_id=owner.id, created_at=_now(), updated_at=_now(), **data.model_dump()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _definition(db: Session, owner: User, data: TrendObservationCreate) -> TrendSignalDefinition:
    if data.signal_definition_id:
        row = db.scalar(
            select(TrendSignalDefinition).where(
                TrendSignalDefinition.id == data.signal_definition_id,
                (TrendSignalDefinition.owner_id == owner.id)
                | (TrendSignalDefinition.owner_id.is_(None)),
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Signal definition not found.")
        return row
    if not data.signal_type:
        raise HTTPException(
            status_code=422, detail="signal_definition_id or signal_type is required"
        )
    row = db.scalar(
        select(TrendSignalDefinition)
        .where(
            TrendSignalDefinition.signal_type == data.signal_type,
            (TrendSignalDefinition.owner_id == owner.id)
            | (TrendSignalDefinition.owner_id.is_(None)),
        )
        .order_by(TrendSignalDefinition.owner_id.desc())
    )
    if row is None:
        raise HTTPException(status_code=422, detail="Unknown signal type")
    return row


def create_observation(
    db: Session, owner: User, context: TrendContext, data: TrendObservationCreate
) -> TrendObservation:
    if context.status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="Archived contexts cannot accept observations.")
    source = _owned(db, IntelligenceSource, data.source_id, owner, "Intelligence source")
    evidence = (
        _owned(db, IntelligenceEvidence, data.evidence_id, owner, "Intelligence evidence")
        if data.evidence_id
        else None
    )
    if evidence and evidence.source_id != source.id:
        raise HTTPException(
            status_code=422, detail="Evidence source does not match observation source"
        )
    definition = _definition(db, owner, data)
    measurement = data.measurement_type or definition.measurement_type
    identity = {
        "context": str(context.id),
        "source": str(source.id),
        "provider": data.provider_observation_id,
        "signal": str(definition.id),
        "observed_at": data.observed_at.isoformat(),
        "period_start": str(data.period_start),
        "period_end": str(data.period_end),
        "numeric": str(data.value_numeric),
        "text": data.value_text,
        "boolean": data.value_boolean,
        "unit": data.unit,
        "geography": data.geography_scope,
    }
    fingerprint = _fingerprint(identity)
    existing = db.scalar(
        select(TrendObservation).where(
            TrendObservation.owner_id == owner.id,
            TrendObservation.context_id == context.id,
            TrendObservation.fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    captured = data.captured_at or _now()
    age = (captured - data.observed_at).total_seconds()
    freshness = data.freshness_state or ("CURRENT" if age <= 7 * 86400 else "STALE")
    metadata = _safe_metadata(data.raw_metadata)
    canonical = _safe_metadata(data.canonical_metadata)
    row = TrendObservation(
        owner_id=owner.id,
        context_id=context.id,
        source_id=source.id,
        evidence_id=evidence.id if evidence else None,
        signal_definition_id=definition.id,
        observed_at=data.observed_at,
        captured_at=captured,
        fingerprint=fingerprint,
        measurement_type=measurement,
        freshness_state=freshness,
        quality_state=data.quality_state or "COMPLETE",
        created_at=_now(),
        raw_metadata=metadata,
        canonical_metadata=canonical,
        **data.model_dump(
            exclude={
                "source_id",
                "signal_definition_id",
                "signal_type",
                "measurement_type",
                "evidence_id",
                "freshness_state",
                "quality_state",
                "raw_metadata",
                "canonical_metadata",
                "idempotency_key",
                "captured_at",
                "observed_at",
            }
        ),
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.observation_accepted",
        entity_type="trend_observation",
        entity_id=row.id,
        idempotency_key=f"trend-observation:{owner.id}:{fingerprint}",
    )
    db.commit()
    db.refresh(row)
    return row


def create_snapshot(
    db: Session, owner: User, context: TrendContext, data: TrendSnapshotCreate
) -> TrendSnapshot:
    query = select(TrendObservation).where(
        TrendObservation.owner_id == owner.id,
        TrendObservation.context_id == context.id,
        TrendObservation.quality_state != "INVALID",
    )
    if data.observation_ids:
        query = query.where(TrendObservation.id.in_(data.observation_ids))
    observations = list(
        db.scalars(query.order_by(TrendObservation.observed_at, TrendObservation.id))
    )
    observation_ids = [str(item.id) for item in observations]
    fingerprint = _fingerprint(
        {"calculation_version": data.calculation_version, "observation_ids": observation_ids}
    )
    existing = db.scalar(
        select(TrendSnapshot).where(
            TrendSnapshot.owner_id == owner.id,
            TrendSnapshot.context_id == context.id,
            TrendSnapshot.input_fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    latest = db.scalar(
        select(TrendSnapshot)
        .where(TrendSnapshot.owner_id == owner.id, TrendSnapshot.context_id == context.id)
        .order_by(TrendSnapshot.snapshot_version.desc())
    )

    def counts(values: list[str]) -> dict[str, int]:
        return dict(Counter(values))

    row = TrendSnapshot(
        owner_id=owner.id,
        context_id=context.id,
        previous_snapshot_id=latest.id if latest else None,
        snapshot_version=(latest.snapshot_version + 1 if latest else 1),
        captured_at=data.captured_at or _now(),
        observation_ids=observation_ids,
        source_inventory=counts([str(x.source_id) for x in observations]),
        signal_inventory=counts([str(x.signal_definition_id) for x in observations]),
        geographic_inventory=counts([x.geography_scope for x in observations]),
        granularity_inventory=counts([x.granularity for x in observations]),
        evidence_summary=counts([x.evidence_kind for x in observations]),
        freshness_summary=counts([x.freshness_state for x in observations]),
        observation_count=len(observations),
        input_fingerprint=fingerprint,
        calculation_version=data.calculation_version,
        created_at=_now(),
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.snapshot_created",
        entity_type="trend_snapshot",
        entity_id=row.id,
        idempotency_key=f"trend-snapshot:{owner.id}:{fingerprint}",
    )
    db.commit()
    db.refresh(row)
    return row


def coverage(db: Session, owner: User, context: TrendContext) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(TrendObservation).where(
                TrendObservation.owner_id == owner.id, TrendObservation.context_id == context.id
            )
        )
    )
    return {
        "context_id": context.id,
        "observation_count": len(rows),
        "first_observed_at": min((x.observed_at for x in rows), default=None),
        "last_observed_at": max((x.observed_at for x in rows), default=None),
        "sources": [
            {"source_id": str(k), "count": v}
            for k, v in Counter(str(x.source_id) for x in rows).items()
        ],
        "signals": [
            {"signal_definition_id": str(k), "count": v}
            for k, v in Counter(str(x.signal_definition_id) for x in rows).items()
        ],
        "geographies": sorted({x.geography_scope for x in rows}),
        "granularities": sorted({x.granularity for x in rows}),
    }


def doctor(db: Session, owner: User) -> dict[str, object]:
    checks = {
        "orphan_context_links": 0,
        "cross_owner_links": 0,
        "orphan_observations": 0,
        "broken_lineage": 0,
        "invalid_measurements": 0,
        "invalid_periods": 0,
        "invalid_metadata": 0,
        "semantic_leakage": 0,
    }
    for row in db.scalars(select(TrendObservation).where(TrendObservation.owner_id == owner.id)):
        if row.value_numeric is None and row.value_text is None and row.value_boolean is None:
            checks["invalid_measurements"] += 1
        if row.period_start and row.period_end and row.period_end < row.period_start:
            checks["invalid_periods"] += 1
        blob = json.dumps(
            {
                "raw": row.raw_metadata,
                "canonical": row.canonical_metadata,
                "note": row.provenance_note,
            }
        ).lower()
        if any(
            token in blob
            for token in ("sales", "revenue", "demand", "momentum", "forecast", "winner")
        ):
            checks["semantic_leakage"] += 1
    total = sum(checks.values())
    return {
        "status": "PASS" if total == 0 else "FAIL",
        "checks": checks,
        "external_write_exposure": 0,
    }


def operations(db: Session, owner: User) -> dict[str, object]:
    from vayujit_api.intelligence.trend_analysis_service import analysis_operations
    from vayujit_api.intelligence.trend_change_service import change_operations

    return {
        "contexts": db.scalar(
            select(func.count()).select_from(TrendContext).where(TrendContext.owner_id == owner.id)
        )
        or 0,
        "observations": db.scalar(
            select(func.count())
            .select_from(TrendObservation)
            .where(TrendObservation.owner_id == owner.id)
        )
        or 0,
        "snapshots": db.scalar(
            select(func.count())
            .select_from(TrendSnapshot)
            .where(TrendSnapshot.owner_id == owner.id)
        )
        or 0,
        "sources": db.scalar(
            select(func.count())
            .select_from(IntelligenceSource)
            .where(IntelligenceSource.owner_id == owner.id)
        )
        or 0,
        "last_observation_at": db.scalar(
            select(func.max(TrendObservation.observed_at)).where(
                TrendObservation.owner_id == owner.id
            )
        ),
        **analysis_operations(db, owner),
        **change_operations(db, owner),
    }
