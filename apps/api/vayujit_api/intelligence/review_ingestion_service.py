from __future__ import annotations

import uuid
from collections import Counter
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.review_ingestion import (
    ADAPTER_VERSION,
    MAX_BATCH_SIZE,
    NORMALIZATION_VERSION,
    ReviewIngestionCandidate,
    adapter_for,
)
from vayujit_api.intelligence.review_models import (
    ReviewContext,
    ReviewIngestionBatch,
    ReviewObservation,
    ReviewRecord,
    ReviewSnapshot,
    ReviewSource,
)
from vayujit_api.intelligence.review_models import (
    ReviewIngestionCandidate as CandidateModel,
)
from vayujit_api.intelligence.review_schemas import (
    ReviewIngestionRequest,
    ReviewRecordCreate,
    ReviewSnapshotCreate,
    ReviewSourceCreate,
)
from vayujit_api.intelligence.review_service import (
    _context_or_404,
    _fingerprint,
    _safe_metadata,
    create_snapshot,
    create_source,
)

KNOWN_LOCAL_PROVIDERS = {"LOCAL_FIXTURE", "manual", "amazon", "flipkart", "meesho", "website"}


def _batch_or_404(db: Session, owner: User, batch_id: uuid.UUID) -> ReviewIngestionBatch:
    value = db.scalar(
        select(ReviewIngestionBatch).where(
            ReviewIngestionBatch.id == batch_id, ReviewIngestionBatch.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Review ingestion batch not found.")
    return value


def _safe_dict(value: object) -> dict[str, object]:
    safe = _safe_metadata(value)
    return dict(safe) if isinstance(safe, dict) else {}


def _batch_fingerprint(data: ReviewIngestionRequest) -> str:
    return data.input_fingerprint or _fingerprint(
        {
            "provider": data.provider,
            "mode": data.mode,
            "source_id": str(data.source_id) if data.source_id else None,
            "source": data.source.model_dump(mode="json") if data.source else None,
            "records": data.records,
            "normalization_version": NORMALIZATION_VERSION,
        }
    )


def _candidate_fingerprint(candidate: ReviewIngestionCandidate, source: ReviewSource | None) -> str:
    return _fingerprint(
        {
            "version": "review-fingerprint-v2",
            "provider": candidate.provider,
            "provider_review_id": candidate.provider_review_id,
            "external_product_id": candidate.external_product_id,
            "source": source.source_key if source else candidate.source_reference,
            "rating": str(candidate.rating) if candidate.rating is not None else None,
            "rating_scale": (
                str(candidate.rating_scale) if candidate.rating_scale is not None else None
            ),
            "title": candidate.title,
            "body": candidate.body,
            "review_date": candidate.review_date.isoformat() if candidate.review_date else None,
        }
    )


def _quality(candidate: ReviewIngestionCandidate, source: ReviewSource | None) -> str:
    identity = bool(
        candidate.provider_review_id
        or candidate.external_product_id
        or candidate.title
        or candidate.body
    )
    if not identity or source is None:
        return "MINIMAL" if identity else "INVALID"
    fields = [
        candidate.rating is not None,
        bool(candidate.title or candidate.body),
        candidate.review_date is not None,
        candidate.verified_purchase != "UNKNOWN",
        candidate.helpful_count is not None,
    ]
    return "COMPLETE" if all(fields) else "PARTIAL"


def _record_data(
    candidate: ReviewIngestionCandidate, source: ReviewSource, fingerprint: str
) -> ReviewRecordCreate:
    return ReviewRecordCreate(
        provider=candidate.provider,
        provider_review_id=candidate.provider_review_id,
        external_product_id=candidate.external_product_id,
        source_id=source.id,
        rating=candidate.rating,
        rating_scale=candidate.rating_scale,
        title=candidate.title,
        body=candidate.body,
        reviewer_display_id=candidate.reviewer_display_id,
        verified_purchase=cast(Literal["TRUE", "FALSE", "UNKNOWN"], candidate.verified_purchase),
        review_date=candidate.review_date,
        observed_at=candidate.observed_at,
        language=candidate.language,
        locale=candidate.locale,
        helpful_count=candidate.helpful_count,
        variant_info=candidate.variant_info,
        source_reference=candidate.source_reference or source.source_reference,
        verification_status=cast(
            Literal["UNVERIFIED", "VERIFIED", "REJECTED", "UNKNOWN"], source.verification_status
        ),
        freshness_status=cast(Literal["CURRENT", "STALE", "UNKNOWN"], source.freshness_status),
        evidence_state="AVAILABLE" if source.intelligence_source_id else "PARTIAL",
        raw_metadata=_safe_dict(
            {
                **candidate.raw_payload,
                "raw_title": candidate.raw_payload.get("title"),
                "raw_body": candidate.raw_payload.get("body"),
            }
        ),
        canonical_metadata={
            "normalization_version": NORMALIZATION_VERSION,
            "review_date_precision": candidate.review_date_precision,
            "derived_fields": [],
        },
        idempotency_key=fingerprint,
    )


def _observation_fingerprint(candidate: ReviewIngestionCandidate) -> str:
    return _fingerprint(
        {
            "provider_review_id": candidate.provider_review_id,
            "external_product_id": candidate.external_product_id,
            "rating": str(candidate.rating) if candidate.rating is not None else None,
            "rating_scale": (
                str(candidate.rating_scale) if candidate.rating_scale is not None else None
            ),
            "title": candidate.title,
            "body": candidate.body,
            "review_date": candidate.review_date.isoformat() if candidate.review_date else None,
            "verified_purchase": candidate.verified_purchase,
            "helpful_count": candidate.helpful_count,
            "variant": candidate.variant_info,
        }
    )


def _update_record(
    record: ReviewRecord, candidate: ReviewIngestionCandidate, source: ReviewSource
) -> None:
    record.source_id = source.id
    record.external_product_id = candidate.external_product_id
    record.rating = candidate.rating
    record.rating_scale = candidate.rating_scale
    record.title = candidate.title
    record.body = candidate.body
    record.reviewer_display_id = candidate.reviewer_display_id
    record.verified_purchase = candidate.verified_purchase
    record.review_date = candidate.review_date
    record.observed_at = candidate.observed_at or now()
    record.language = candidate.language
    record.locale = candidate.locale
    record.helpful_count = candidate.helpful_count
    record.variant_info = _safe_dict(candidate.variant_info)
    record.source_reference = candidate.source_reference or source.source_reference
    record.raw_metadata = _safe_dict(candidate.raw_payload)
    record.canonical_metadata = {
        **_safe_dict(record.canonical_metadata),
        "normalization_version": NORMALIZATION_VERSION,
        "review_date_precision": candidate.review_date_precision,
    }


def _observation(
    db: Session,
    owner: User,
    batch: ReviewIngestionBatch,
    record: ReviewRecord,
    source: ReviewSource,
    candidate: ReviewIngestionCandidate,
    source_fingerprint: str,
) -> bool:
    existing = db.scalar(
        select(ReviewObservation).where(
            ReviewObservation.owner_id == owner.id,
            ReviewObservation.review_record_id == record.id,
            ReviewObservation.source_fingerprint == source_fingerprint,
        )
    )
    if existing is not None:
        return False
    db.add(
        ReviewObservation(
            owner_id=owner.id,
            context_id=batch.context_id,
            review_record_id=record.id,
            batch_id=batch.id,
            source_id=source.id,
            provider=candidate.provider,
            provider_review_id=candidate.provider_review_id,
            observed_at=candidate.observed_at or now(),
            source_fingerprint=source_fingerprint,
            normalization_version=NORMALIZATION_VERSION,
            raw_snapshot=_safe_dict(candidate.raw_payload),
            created_at=now(),
        )
    )
    db.flush()
    return True


def _candidate_value(
    owner: User,
    batch: ReviewIngestionBatch,
    source: ReviewSource | None,
    ordinal: int,
    candidate: ReviewIngestionCandidate | None,
    raw_payload: dict[str, object],
    *,
    accepted: bool,
    duplicate_classification: str = "DISTINCT",
    quality_state: str = "INVALID",
    rejection_reason: str | None = None,
    fingerprint: str | None = None,
    review_record_id: uuid.UUID | None = None,
) -> CandidateModel:
    return CandidateModel(
        owner_id=owner.id,
        batch_id=batch.id,
        context_id=batch.context_id,
        source_id=source.id if source else None,
        ordinal=ordinal,
        provider_review_id=candidate.provider_review_id if candidate else None,
        fingerprint=fingerprint,
        duplicate_classification=duplicate_classification,
        quality_state=quality_state,
        accepted=accepted,
        rejection_reason=rejection_reason,
        raw_payload=_safe_dict(raw_payload),
        normalized_payload=candidate.normalized_payload if candidate else {},
        review_record_id=review_record_id,
        created_at=now(),
    )


def _summary(db: Session, owner: User, batch: ReviewIngestionBatch) -> dict[str, object]:
    values = list(
        db.scalars(
            select(CandidateModel).where(
                CandidateModel.owner_id == owner.id, CandidateModel.batch_id == batch.id
            )
        )
    )
    return {
        "quality_counts": dict(Counter(item.quality_state for item in values)),
        "duplicate_counts": dict(Counter(item.duplicate_classification for item in values)),
        "rejection_counts": dict(
            Counter(item.rejection_reason for item in values if item.rejection_reason)
        ),
        "accepted_with_source": sum(
            item.source_id is not None and item.accepted for item in values
        ),
    }


def execute_ingestion(
    db: Session, owner: User, context: ReviewContext, data: ReviewIngestionRequest
) -> tuple[ReviewIngestionBatch, list[CandidateModel], ReviewSnapshot | None]:
    if len(data.records) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=422, detail="Review ingestion batch is too large.")
    existing = db.scalar(
        select(ReviewIngestionBatch).where(
            ReviewIngestionBatch.owner_id == owner.id,
            ReviewIngestionBatch.context_id == context.id,
            ReviewIngestionBatch.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return (
            existing,
            list(
                db.scalars(
                    select(CandidateModel)
                    .where(
                        CandidateModel.owner_id == owner.id, CandidateModel.batch_id == existing.id
                    )
                    .order_by(CandidateModel.ordinal)
                )
            ),
            db.scalar(
                select(ReviewSnapshot)
                .where(
                    ReviewSnapshot.owner_id == owner.id,
                    ReviewSnapshot.context_id == context.id,
                )
                .order_by(ReviewSnapshot.snapshot_version.desc())
                .limit(1)
            ),
        )
    source: ReviewSource | None = None
    if data.source_id is not None:
        source = db.scalar(
            select(ReviewSource).where(
                ReviewSource.id == data.source_id,
                ReviewSource.owner_id == owner.id,
                ReviewSource.context_id == context.id,
            )
        )
        if source is None:
            raise HTTPException(status_code=404, detail="Review source not found.")
    elif data.source is not None:
        source = create_source(db, owner, context, data.source)
        db.commit()
    elif data.provider:
        source = create_source(
            db,
            owner,
            context,
            ReviewSourceCreate(
                provider=data.provider,
                source_type="local_fixture",
                source_reference=f"{data.provider}:context:{context.id}",
            ),
        )
        db.commit()
    batch = ReviewIngestionBatch(
        owner_id=owner.id,
        context_id=context.id,
        source_id=source.id if source else None,
        provider=data.provider,
        mode=data.mode,
        status="REQUESTED",
        input_count=len(data.records),
        input_fingerprint=_batch_fingerprint(data),
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        idempotency_key=data.idempotency_key,
        created_at=now(),
    )
    db.add(batch)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ReviewIngestionBatch).where(
                ReviewIngestionBatch.owner_id == owner.id,
                ReviewIngestionBatch.context_id == context.id,
                ReviewIngestionBatch.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return (
            existing,
            list(
                db.scalars(
                    select(CandidateModel)
                    .where(
                        CandidateModel.owner_id == owner.id,
                        CandidateModel.batch_id == existing.id,
                    )
                    .order_by(CandidateModel.ordinal)
                )
            ),
            db.scalar(
                select(ReviewSnapshot)
                .where(
                    ReviewSnapshot.owner_id == owner.id,
                    ReviewSnapshot.context_id == context.id,
                )
                .order_by(ReviewSnapshot.snapshot_version.desc())
                .limit(1)
            ),
        )
    record_event(
        db,
        actor_id=owner.id,
        action="review.ingestion_requested",
        entity_type="ReviewIngestionBatch",
        entity_id=batch.id,
        metadata={"mode": data.mode, "provider": data.provider, "input_count": len(data.records)},
        idempotency_key=f"review.ingestion_requested:{batch.id}",
    )
    db.commit()
    if data.mode in {"DISABLED", "LIVE_READ_ONLY"}:
        batch.status = "FAILED"
        batch.error_count = 1
        batch.error_message = (
            "Review ingestion provider is disabled."
            if data.mode == "DISABLED"
            else "Live read-only review ingestion is not configured."
        )
        batch.completed_at = now()
        record_event(
            db,
            actor_id=owner.id,
            action="review.ingestion_failed",
            entity_type="ReviewIngestionBatch",
            entity_id=batch.id,
            metadata={"reason": batch.error_message},
            idempotency_key=f"review.ingestion_failed:{batch.id}",
        )
        db.commit()
        return batch, [], None
    if data.provider not in KNOWN_LOCAL_PROVIDERS:
        batch.status = "FAILED"
        batch.error_count = 1
        batch.error_message = "UNSUPPORTED_PROVIDER"
        batch.completed_at = now()
        record_event(
            db,
            actor_id=owner.id,
            action="review.ingestion_failed",
            entity_type="ReviewIngestionBatch",
            entity_id=batch.id,
            metadata={"reason": batch.error_message},
            idempotency_key=f"review.ingestion_failed:{batch.id}",
        )
        db.commit()
        return batch, [], None
    adapter = adapter_for(data.provider, data.mode)
    batch.status = "RUNNING"
    batch.started_at = now()
    db.commit()
    for ordinal, payload in enumerate(data.records):
        candidate: ReviewIngestionCandidate | None = None
        try:
            if not isinstance(payload, dict):
                raise ValueError("MALFORMED_PAYLOAD")
            candidate = adapter.adapt(payload)
            fingerprint = _candidate_fingerprint(candidate, source)
            quality = _quality(candidate, source)
            if quality == "INVALID":
                raise ValueError("MISSING_IDENTITY")
            record = None
            classification = "DISTINCT"
            if candidate.provider_review_id:
                record = db.scalar(
                    select(ReviewRecord).where(
                        ReviewRecord.owner_id == owner.id,
                        ReviewRecord.context_id == context.id,
                        ReviewRecord.provider == data.provider,
                        ReviewRecord.provider_review_id == candidate.provider_review_id,
                    )
                )
                if record is not None:
                    classification = "AUTHORITATIVE_DUPLICATE"
            if record is None:
                record = db.scalar(
                    select(ReviewRecord).where(
                        ReviewRecord.owner_id == owner.id,
                        ReviewRecord.context_id == context.id,
                        ReviewRecord.fingerprint == fingerprint,
                    )
                )
                if record is not None:
                    classification = "FINGERPRINT_DUPLICATE"
            if record is None and candidate.body:
                possible = db.scalar(
                    select(ReviewRecord.id).where(
                        ReviewRecord.owner_id == owner.id,
                        ReviewRecord.context_id == context.id,
                        ReviewRecord.body == candidate.body,
                        ReviewRecord.provider != data.provider,
                    )
                )
                if possible is not None:
                    classification = "POSSIBLE_DUPLICATE"
            if record is not None:
                observation_fp = _observation_fingerprint(candidate)
                changed = (
                    _observation(db, owner, batch, record, source, candidate, observation_fp)
                    if source
                    else False
                )
                if changed:
                    _update_record(record, candidate, source) if source else None
                    batch.updated_observation_count += 1
                elif classification == "AUTHORITATIVE_DUPLICATE":
                    classification = "EXACT_REPLAY"
                batch.duplicate_count += 1
                db.add(
                    _candidate_value(
                        owner,
                        batch,
                        source,
                        ordinal,
                        candidate,
                        payload,
                        accepted=False,
                        duplicate_classification=classification,
                        quality_state=quality,
                        fingerprint=fingerprint,
                        review_record_id=record.id,
                    )
                )
                db.flush()
                continue
            if source is None:
                raise ValueError("MISSING_SOURCE")
            record_data = _record_data(candidate, source, fingerprint)
            from vayujit_api.intelligence.review_service import create_review

            record = create_review(db, owner, context, record_data)
            record.ingestion_batch_id = batch.id
            db.commit()
            changed = _observation(
                db, owner, batch, record, source, candidate, _observation_fingerprint(candidate)
            )
            db.add(
                _candidate_value(
                    owner,
                    batch,
                    source,
                    ordinal,
                    candidate,
                    payload,
                    accepted=True,
                    duplicate_classification=classification,
                    quality_state=quality,
                    fingerprint=fingerprint,
                    review_record_id=record.id,
                )
            )
            batch.accepted_count += 1
            db.flush()
        except (ValueError, HTTPException) as exc:
            reason = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            db.add(
                _candidate_value(
                    owner,
                    batch,
                    source,
                    ordinal,
                    candidate,
                    payload if isinstance(payload, dict) else {},
                    accepted=False,
                    quality_state="INVALID",
                    rejection_reason=reason[:80],
                )
            )
            batch.rejected_count += 1
            db.flush()
        except IntegrityError:
            db.rollback()
            batch.error_count += 1
            batch.error_message = "DATABASE_CONSTRAINT"
    batch.status = (
        "FAILED"
        if batch.error_count and batch.accepted_count == 0
        else "PARTIAL" if batch.rejected_count or batch.error_count else "COMPLETED"
    )
    batch.completed_at = now()
    db.commit()
    accepted_ids = sorted(
        str(item)
        for item in db.scalars(
            select(CandidateModel.review_record_id).where(
                CandidateModel.owner_id == owner.id,
                CandidateModel.batch_id == batch.id,
                CandidateModel.accepted.is_(True),
                CandidateModel.review_record_id.is_not(None),
            )
        )
        if item is not None
    )
    snapshot = create_snapshot(
        db,
        owner,
        context,
        ReviewSnapshotCreate(
            calculation_version=NORMALIZATION_VERSION,
            input_fingerprint=_fingerprint({"batch": str(batch.id), "records": accepted_ids}),
        ),
    )
    batch = _batch_or_404(db, owner, batch.id)
    record_event(
        db,
        actor_id=owner.id,
        action=(
            "review.ingestion_completed"
            if batch.status in {"COMPLETED", "PARTIAL"}
            else "review.ingestion_failed"
        ),
        entity_type="ReviewIngestionBatch",
        entity_id=batch.id,
        metadata={
            "status": batch.status,
            "accepted_count": batch.accepted_count,
            "rejected_count": batch.rejected_count,
            "duplicate_count": batch.duplicate_count,
        },
        idempotency_key=f"review.ingestion.completed:{batch.id}",
    )
    db.commit()
    return (
        batch,
        list(
            db.scalars(
                select(CandidateModel)
                .where(CandidateModel.owner_id == owner.id, CandidateModel.batch_id == batch.id)
                .order_by(CandidateModel.ordinal)
            )
        ),
        snapshot,
    )


def batch_list(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> list[ReviewIngestionBatch]:
    _context_or_404(db, owner, context_id)
    return list(
        db.scalars(
            select(ReviewIngestionBatch)
            .where(
                ReviewIngestionBatch.owner_id == owner.id,
                ReviewIngestionBatch.context_id == context_id,
            )
            .order_by(ReviewIngestionBatch.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


def batch_detail(
    db: Session, owner: User, context_id: uuid.UUID, batch_id: uuid.UUID
) -> tuple[ReviewIngestionBatch, list[CandidateModel]]:
    _context_or_404(db, owner, context_id)
    batch = _batch_or_404(db, owner, batch_id)
    if batch.context_id != context_id:
        raise HTTPException(status_code=404, detail="Review ingestion batch not found.")
    candidates = list(
        db.scalars(
            select(CandidateModel)
            .where(CandidateModel.owner_id == owner.id, CandidateModel.batch_id == batch.id)
            .order_by(CandidateModel.ordinal)
        )
    )
    return batch, candidates


def ingestion_summary(db: Session, owner: User, context_id: uuid.UUID) -> dict[str, object]:
    _context_or_404(db, owner, context_id)
    batches = list(
        db.scalars(
            select(ReviewIngestionBatch).where(
                ReviewIngestionBatch.owner_id == owner.id,
                ReviewIngestionBatch.context_id == context_id,
            )
        )
    )
    return {
        "batch_count": len(batches),
        "successful_batches": sum(item.status == "COMPLETED" for item in batches),
        "partial_batches": sum(item.status == "PARTIAL" for item in batches),
        "failed_batches": sum(item.status == "FAILED" for item in batches),
        "accepted_reviews": sum(item.accepted_count for item in batches),
        "rejected_candidates": sum(item.rejected_count for item in batches),
        "duplicate_candidates": sum(item.duplicate_count for item in batches),
        "latest_ingestion": max(
            (item.completed_at for item in batches if item.completed_at), default=None
        ),
        "provider_modes": dict(Counter(f"{item.provider}:{item.mode}" for item in batches)),
    }
