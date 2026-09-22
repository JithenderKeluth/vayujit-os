"""Deterministic, synchronous Trend 12B ingestion and normalization."""

from __future__ import annotations

import re
import uuid
from collections import Counter
from decimal import InvalidOperation
from typing import Protocol

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceSource
from vayujit_api.intelligence.trend_ingestion_models import (
    TrendIngestionBatch,
    TrendIngestionCandidate,
    TrendObservationRevision,
)
from vayujit_api.intelligence.trend_ingestion_schemas import (
    TrendIngestionRequest,
    TrendRawCandidate,
)
from vayujit_api.intelligence.trend_models import TrendContext, TrendObservation
from vayujit_api.intelligence.trend_schemas import TrendObservationCreate
from vayujit_api.intelligence.trend_service import (
    _fingerprint,
    _now,
    _owned,
    _redact,
    _safe_metadata,
    coverage,
    create_observation,
)

MAX_CANDIDATES = 500
REJECTION_CODES = {
    "INVALID_NUMERIC_VALUE",
    "INVALID_PERIOD",
    "INVALID_TIMESTAMP",
    "INVALID_SCALE",
    "UNSUPPORTED_SIGNAL",
    "UNSUPPORTED_MEASUREMENT",
    "MISSING_REQUIRED_SOURCE",
    "METADATA_TOO_LARGE",
    "INVALID_GEOGRAPHY",
    "INVALID_PROVIDER_IDENTITY",
}


class TrendIngestionAdapter(Protocol):
    provider: str
    mode: str

    def receive(self) -> list[TrendRawCandidate]: ...


class LocalFixtureAdapter:
    provider = "LOCAL_FIXTURE"
    mode = "LOCAL_FIXTURE"

    def __init__(self, candidates: list[TrendRawCandidate]) -> None:
        self.candidates = candidates

    def receive(self) -> list[TrendRawCandidate]:
        return self.candidates


def _normalize_text(value: str | None) -> str | None:
    return re.sub(r"\s+", " ", value.strip()) if value is not None else None


def _normalize_candidate(raw: TrendRawCandidate) -> TrendRawCandidate:
    payload = raw.model_dump()
    for key in (
        "signal_key",
        "measurement_type",
        "unit",
        "granularity",
        "geography_scope",
        "evidence_kind",
        "verification_state",
        "freshness_state",
    ):
        if isinstance(payload.get(key), str):
            normalized = _normalize_text(payload[key]) or ""
            payload[key] = normalized.upper() if key != "unit" else _normalize_text(payload[key])
    payload["signal_key"] = str(payload["signal_key"]).upper()
    payload["source_reference"] = _normalize_text(payload.get("source_reference")) or ""
    for key in ("country", "region", "city", "marketplace"):
        payload[key] = _normalize_text(payload.get(key))
    return TrendRawCandidate.model_validate(payload)


def _batch_fingerprint(context_id: uuid.UUID, data: TrendIngestionRequest) -> str:
    return _fingerprint(
        {
            "context": str(context_id),
            "source": str(data.source_id),
            "mode": data.mode,
            "provider": data.provider,
            "version": data.normalization_version,
            "candidates": [item.model_dump(mode="json") for item in data.candidates],
        }
    )


def _safe_raw(raw: TrendRawCandidate) -> dict[str, object]:
    value = _redact(raw.model_dump(mode="json"))
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="candidate payload is invalid")
    return value


def _observation_payload(context: TrendContext, raw: TrendRawCandidate) -> TrendObservationCreate:
    return TrendObservationCreate(
        source_id=uuid.UUID(int=0),
        signal_type=raw.signal_key,
        provider_observation_id=raw.provider_observation_id,
        observed_at=raw.observed_at,
        captured_at=raw.captured_at,
        period_start=raw.period_start,
        period_end=raw.period_end,
        granularity=raw.granularity,
        measurement_type=raw.measurement_type,
        value_numeric=raw.value_numeric,
        value_text=raw.value_text,
        value_boolean=raw.value_boolean,
        unit=raw.unit,
        scale=raw.scale,
        geography_scope=raw.geography_scope,
        country=raw.country,
        region=raw.region,
        city=raw.city,
        marketplace=raw.marketplace,
        source_reference=raw.source_reference,
        evidence_id=raw.evidence_id,
        evidence_kind=raw.evidence_kind,
        verification_state=raw.verification_state,
        freshness_state=raw.freshness_state,
        raw_metadata=raw.metadata,
        canonical_metadata=raw.canonical_metadata,
    )


def _empty_failure(
    db: Session,
    owner: User,
    context: TrendContext,
    source: IntelligenceSource,
    data: TrendIngestionRequest,
    fingerprint: str,
    code: str,
    message: str,
) -> TrendIngestionBatch:
    now = _now()
    batch = TrendIngestionBatch(
        owner_id=owner.id,
        context_id=context.id,
        source_id=source.id,
        provider=data.provider,
        mode=data.mode,
        status="FAILED",
        started_at=now,
        completed_at=now,
        input_fingerprint=fingerprint,
        idempotency_key=data.idempotency_key or fingerprint,
        error_code=code,
        error_message=message,
        created_at=now,
        summary_json={},
    )
    db.add(batch)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.ingestion_failed",
        entity_type="TrendIngestionBatch",
        entity_id=batch.id,
        metadata={"error_code": code},
        idempotency_key=f"trend.ingestion_failed:{batch.id}",
    )
    db.commit()
    return batch


def ingest(
    db: Session, owner: User, context: TrendContext, data: TrendIngestionRequest
) -> TrendIngestionBatch:
    source = _owned(db, IntelligenceSource, data.source_id, owner, "Intelligence source")
    if len(data.candidates) > MAX_CANDIDATES:
        raise HTTPException(
            status_code=422, detail="candidate count exceeds the bounded ingestion limit"
        )
    fingerprint = _batch_fingerprint(context.id, data)
    key = data.idempotency_key or fingerprint
    existing = db.scalar(
        select(TrendIngestionBatch).where(
            TrendIngestionBatch.owner_id == owner.id,
            TrendIngestionBatch.context_id == context.id,
            TrendIngestionBatch.idempotency_key == key,
        )
    )
    if existing:
        return existing
    if data.mode == "DISABLED":
        return _empty_failure(
            db,
            owner,
            context,
            source,
            data,
            fingerprint,
            "PROVIDER_DISABLED",
            "Trend ingestion is disabled.",
        )
    if data.mode == "LIVE_READ_ONLY":
        return _empty_failure(
            db,
            owner,
            context,
            source,
            data,
            fingerprint,
            "PROVIDER_NOT_CONFIGURED",
            "No live Trend provider is configured.",
        )
    now = _now()
    batch = TrendIngestionBatch(
        owner_id=owner.id,
        context_id=context.id,
        source_id=source.id,
        provider=data.provider,
        mode=data.mode,
        status="RUNNING",
        started_at=now,
        requested_count=len(data.candidates),
        received_count=len(data.candidates),
        input_fingerprint=fingerprint,
        adapter_version=data.adapter_version,
        normalization_version=data.normalization_version,
        idempotency_key=key,
        created_at=now,
        summary_json={},
    )
    db.add(batch)
    db.flush()
    accepted = rejected = duplicates = updated = 0
    quality: Counter[str] = Counter()
    freshness: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for ordinal, original in enumerate(LocalFixtureAdapter(data.candidates).receive()):
        raw_payload = _safe_raw(original)
        candidate = TrendIngestionCandidate(
            owner_id=owner.id,
            batch_id=batch.id,
            context_id=context.id,
            source_id=source.id,
            ordinal=ordinal,
            provider_observation_id=original.provider_observation_id,
            signal_key=original.signal_key,
            raw_payload=raw_payload,
            created_at=now,
        )
        db.add(candidate)
        db.flush()
        try:
            raw = _normalize_candidate(original)
            payload = _observation_payload(context, raw)
            payload.source_id = source.id
            existing_observation = None
            if raw.provider_observation_id:
                existing_observation = db.scalar(
                    select(TrendObservation).where(
                        TrendObservation.owner_id == owner.id,
                        TrendObservation.context_id == context.id,
                        TrendObservation.source_id == source.id,
                        TrendObservation.provider_observation_id == raw.provider_observation_id,
                    )
                )
            if existing_observation:
                old: dict[str, object] = {
                    "value_numeric": str(existing_observation.value_numeric),
                    "value_text": existing_observation.value_text,
                    "value_boolean": existing_observation.value_boolean,
                    "observed_at": existing_observation.observed_at.isoformat(),
                }
                new: dict[str, object] = {
                    "value_numeric": str(raw.value_numeric),
                    "value_text": raw.value_text,
                    "value_boolean": raw.value_boolean,
                    "observed_at": raw.observed_at.isoformat(),
                }
                candidate.duplicate_classification = (
                    "EXACT_REPLAY" if old == new else "AUTHORITATIVE_DUPLICATE"
                )
                if old != new:
                    db.add(
                        TrendObservationRevision(
                            owner_id=owner.id,
                            observation_id=existing_observation.id,
                            batch_id=batch.id,
                            provider_observation_id=raw.provider_observation_id,
                            old_payload=old,
                            new_payload=new,
                            changed_at=now,
                        )
                    )
                    updated += 1
                duplicates += 1
                candidate.normalized_payload = new
                candidate.quality_state = existing_observation.quality_state
                candidate.rejection_code = candidate.duplicate_classification
                reasons[candidate.duplicate_classification] += 1
                continue
            observation = create_observation(db, owner, context, payload)
            candidate.accepted = True
            candidate.observation_id = observation.id
            candidate.quality_state = observation.quality_state
            candidate.fingerprint = observation.fingerprint
            candidate.normalized_payload = _safe_metadata(raw.model_dump(mode="json"))
            accepted += 1
            quality[observation.quality_state] += 1
            freshness[observation.freshness_state] += 1
        except HTTPException as exc:
            candidate.rejection_code = (
                "UNSUPPORTED_SIGNAL"
                if "signal" in str(exc.detail).lower()
                else (
                    "INVALID_PERIOD"
                    if "period" in str(exc.detail).lower()
                    else "INVALID_NUMERIC_VALUE"
                )
            )
            candidate.quality_state = "INVALID"
            candidate.normalized_payload = {}
            rejected += 1
            reasons[candidate.rejection_code] += 1
        except (ValueError, InvalidOperation, OverflowError):
            candidate.rejection_code = "INVALID_NUMERIC_VALUE"
            candidate.quality_state = "INVALID"
            rejected += 1
            reasons["INVALID_NUMERIC_VALUE"] += 1
    batch.accepted_count = accepted
    batch.rejected_count = rejected
    batch.duplicate_count = duplicates
    batch.updated_observation_count = updated
    batch.status = "COMPLETED" if rejected == 0 else "PARTIAL"
    batch.completed_at = _now()
    batch.summary_json = {
        "quality_distribution": dict(quality),
        "freshness_distribution": dict(freshness),
        "rejection_distribution": dict(reasons),
        "coverage": jsonable_encoder(coverage(db, owner, context)),
        "gaps": (["NO_OBSERVATIONS"] if accepted == 0 else []),
    }
    record_event(
        db,
        actor_id=owner.id,
        action="trend.ingestion_completed",
        entity_type="TrendIngestionBatch",
        entity_id=batch.id,
        metadata={"accepted": accepted, "rejected": rejected, "duplicates": duplicates},
        idempotency_key=f"trend.ingestion_completed:{batch.id}",
    )
    db.commit()
    db.refresh(batch)
    return batch


def batch_or_404(db: Session, owner: User, batch_id: uuid.UUID) -> TrendIngestionBatch:
    return _owned(db, TrendIngestionBatch, batch_id, owner, "Trend ingestion batch")


def candidates(
    db: Session,
    owner: User,
    batch: TrendIngestionBatch,
    rejected_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[TrendIngestionCandidate]:
    query = select(TrendIngestionCandidate).where(
        TrendIngestionCandidate.owner_id == owner.id, TrendIngestionCandidate.batch_id == batch.id
    )
    if rejected_only:
        query = query.where(TrendIngestionCandidate.accepted.is_(False))
    return list(
        db.scalars(query.order_by(TrendIngestionCandidate.ordinal).offset(offset).limit(limit))
    )
