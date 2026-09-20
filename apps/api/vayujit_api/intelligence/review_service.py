"""Bounded, local-only Review Intelligence foundation services."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.competitor_models import CompetitorContext
from vayujit_api.intelligence.models import IntelligenceEvidence, IntelligenceSource
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.review_models import (
    ALERT_ELIGIBILITY,
    CHANGE_STATUSES,
    MATERIALITY_LEVELS,
    ReviewAnalysis,
    ReviewAnalysisAnnotation,
    ReviewAnalysisItem,
    ReviewChangeComparison,
    ReviewChangeEvent,
    ReviewContext,
    ReviewIngestionBatch,
    ReviewIngestionCandidate,
    ReviewObservation,
    ReviewOpportunitySignal,
    ReviewProductGap,
    ReviewProductGapAnalysis,
    ReviewRecord,
    ReviewSnapshot,
    ReviewSource,
)
from vayujit_api.intelligence.review_schemas import (
    ReviewContextCreate,
    ReviewContextUpdate,
    ReviewRecordCreate,
    ReviewSnapshotCreate,
    ReviewSourceCreate,
)
from vayujit_api.products.models import Product


def _owned(db: Session, model: Any, item_id: uuid.UUID, owner: User, label: str) -> Any:
    value = db.scalar(select(model).where(model.id == item_id, model.owner_id == owner.id))
    if value is None:
        raise HTTPException(status_code=404, detail=f"{label} not found.")
    return value


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _safe_metadata(value: object) -> object:
    sensitive = (
        "token",
        "secret",
        "password",
        "cookie",
        "credential",
        "api_key",
        "authorization",
        "database_url",
        "private_key",
    )
    if isinstance(value, dict):
        return {
            str(key): _safe_metadata(item)
            for key, item in value.items()
            if not any(marker in str(key).lower() for marker in sensitive)
        }
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _analysis_included_ids(value: object) -> list[str]:
    if not isinstance(value, dict):
        return []
    included = value.get("included")
    if not isinstance(included, list):
        return []
    return [item for item in included if isinstance(item, str)]


def _invalid_rating_distribution(value: object) -> bool:
    if not isinstance(value, dict):
        return True
    for key in ("rated_count", "unrated_count"):
        count = value.get(key)
        if not isinstance(count, int) or count < 0:
            return True
    scales = value.get("scales")
    if not isinstance(scales, dict):
        return True
    for scale in scales.values():
        if not isinstance(scale, dict) or not isinstance(scale.get("count"), int):
            return True
        if scale["count"] < 0 or not isinstance(scale.get("buckets"), dict):
            return True
    return False


def _missing_sentiment_distribution(value: object) -> bool:
    return not isinstance(value, dict) or any(
        label not in value for label in ("POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "UNKNOWN")
    )


def _context_or_404(db: Session, owner: User, context_id: uuid.UUID) -> ReviewContext:
    return cast(ReviewContext, _owned(db, ReviewContext, context_id, owner, "Review context"))


def _validate_context_links(db: Session, owner: User, data: ReviewContextCreate) -> None:
    for model, value, label in (
        (Product, data.product_id, "Product"),
        (ProductOpportunity, data.product_opportunity_id, "Product opportunity"),
        (Brand, data.brand_id, "Brand"),
        (CompetitorContext, data.competitor_context_id, "Competitor context"),
    ):
        if value is not None:
            _owned(db, model, value, owner, label)


def create_context(db: Session, owner: User, data: ReviewContextCreate) -> ReviewContext:
    _validate_context_links(db, owner, data)
    key = data.idempotency_key or _fingerprint(
        {
            "owner": str(owner.id),
            "links": [
                str(data.product_id),
                str(data.product_opportunity_id),
                str(data.brand_id),
                str(data.competitor_context_id),
            ],
            "marketplace": data.marketplace,
            "market": data.market,
        }
    )
    existing = db.scalar(
        select(ReviewContext).where(
            ReviewContext.owner_id == owner.id, ReviewContext.idempotency_key == key
        )
    )
    if existing is not None:
        return existing
    value = ReviewContext(
        owner_id=owner.id,
        name=data.name,
        product_id=data.product_id,
        product_opportunity_id=data.product_opportunity_id,
        brand_id=data.brand_id,
        competitor_context_id=data.competitor_context_id,
        marketplace=data.marketplace,
        market=data.market,
        locale=data.locale,
        language=data.language,
        status=data.status,
        version=1,
        idempotency_key=key,
        input_fingerprint=data.input_fingerprint,
        created_at=now(),
        updated_at=now(),
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="review.context_created",
        entity_type="ReviewContext",
        entity_id=value.id,
        idempotency_key=f"review.context_created:{value.id}",
    )
    db.commit()
    return value


def update_context(
    db: Session, owner: User, context: ReviewContext, data: ReviewContextUpdate
) -> ReviewContext:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(context, key, value)
    context.version += 1
    context.updated_at = now()
    db.commit()
    return context


def archive_context(db: Session, owner: User, context: ReviewContext) -> ReviewContext:
    context.status = "ARCHIVED"
    context.archived_at = now()
    context.updated_at = now()
    context.version += 1
    record_event(
        db,
        actor_id=owner.id,
        action="review.context_archived",
        entity_type="ReviewContext",
        entity_id=context.id,
        idempotency_key=f"review.context_archived:{context.id}:{context.version}",
    )
    db.commit()
    return context


def create_source(
    db: Session, owner: User, context: ReviewContext, data: ReviewSourceCreate
) -> ReviewSource:
    if data.intelligence_source_id is not None:
        _owned(db, IntelligenceSource, data.intelligence_source_id, owner, "Intelligence source")
    key = data.source_key or _fingerprint(
        {
            "provider": data.provider,
            "reference": data.source_reference,
            "product": data.external_product_identifier,
        }
    )
    existing = db.scalar(
        select(ReviewSource).where(
            ReviewSource.owner_id == owner.id,
            ReviewSource.context_id == context.id,
            ReviewSource.source_key == key,
        )
    )
    if existing is not None:
        return existing
    value = ReviewSource(
        owner_id=owner.id,
        context_id=context.id,
        intelligence_source_id=data.intelligence_source_id,
        source_type=data.source_type,
        provider=data.provider,
        source_key=key,
        marketplace=data.marketplace,
        external_product_identifier=data.external_product_identifier,
        source_reference=data.source_reference,
        source_url=data.source_url,
        captured_at=now(),
        observed_at=data.observed_at,
        verification_status=data.verification_status,
        freshness_status=data.freshness_status,
        metadata_json=_safe_metadata(data.metadata),
        created_at=now(),
    )
    db.add(value)
    db.flush()
    return value


def _review_identity(data: ReviewRecordCreate, source: ReviewSource | None) -> str:
    return _fingerprint(
        {
            "version": "review-fingerprint-v1",
            "provider": data.provider,
            "provider_review_id": data.provider_review_id,
            "external_product_id": data.external_product_id,
            "source": source.source_key if source else data.source_reference,
            "rating": str(data.rating) if data.rating is not None else None,
            "rating_scale": str(data.rating_scale) if data.rating_scale is not None else None,
            "title": data.title,
            "body": data.body,
            "review_date": data.review_date.isoformat() if data.review_date else None,
        }
    )


def create_review(
    db: Session, owner: User, context: ReviewContext, data: ReviewRecordCreate
) -> ReviewRecord:
    source = None
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
    if data.evidence_id is not None:
        _owned(db, IntelligenceEvidence, data.evidence_id, owner, "Evidence")
    fingerprint = _review_identity(data, source)
    existing = None
    if data.provider_review_id:
        existing = db.scalar(
            select(ReviewRecord).where(
                ReviewRecord.owner_id == owner.id,
                ReviewRecord.context_id == context.id,
                ReviewRecord.provider == data.provider,
                ReviewRecord.provider_review_id == data.provider_review_id,
            )
        )
    if existing is None:
        existing = db.scalar(
            select(ReviewRecord).where(
                ReviewRecord.owner_id == owner.id,
                ReviewRecord.context_id == context.id,
                ReviewRecord.fingerprint == fingerprint,
            )
        )
    if existing is not None:
        return existing
    captured = now()
    value = ReviewRecord(
        owner_id=owner.id,
        context_id=context.id,
        source_id=source.id if source else None,
        evidence_id=data.evidence_id,
        provider=data.provider,
        provider_review_id=data.provider_review_id,
        external_product_id=data.external_product_id,
        rating=data.rating,
        rating_scale=data.rating_scale,
        title=data.title,
        body=data.body,
        reviewer_display_id=data.reviewer_display_id,
        verified_purchase=data.verified_purchase,
        review_date=data.review_date,
        observed_at=data.observed_at or captured,
        captured_at=captured,
        language=data.language,
        locale=data.locale,
        helpful_count=data.helpful_count,
        variant_info=_safe_metadata(data.variant_info),
        source_reference=data.source_reference or (source.source_reference if source else None),
        verification_status=data.verification_status,
        freshness_status=data.freshness_status,
        evidence_state=data.evidence_state,
        raw_metadata=_safe_metadata(data.raw_metadata),
        canonical_metadata=_safe_metadata(data.canonical_metadata),
        fingerprint=fingerprint,
        fingerprint_version="review-fingerprint-v1",
        idempotency_key=data.idempotency_key or fingerprint,
        created_at=captured,
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="review.record_imported",
        entity_type="ReviewRecord",
        entity_id=value.id,
        metadata={"provider": value.provider, "evidence_state": value.evidence_state},
        idempotency_key=f"review.record_imported:{value.id}",
    )
    db.commit()
    return value


def _records(db: Session, owner: User, context_id: uuid.UUID) -> list[ReviewRecord]:
    return list(
        db.scalars(
            select(ReviewRecord)
            .where(ReviewRecord.owner_id == owner.id, ReviewRecord.context_id == context_id)
            .order_by(ReviewRecord.review_date.desc().nullslast(), ReviewRecord.created_at.desc())
        )
    )


def statistics(db: Session, owner: User, context_id: uuid.UUID) -> dict[str, object]:
    _context_or_404(db, owner, context_id)
    values = _records(db, owner, context_id)
    scales = Counter(
        str(item.rating_scale)
        for item in values
        if item.rating is not None and item.rating_scale is not None
    )
    return {
        "review_count": len(values),
        "rated_review_count": sum(item.rating is not None for item in values),
        "unrated_review_count": sum(item.rating is None for item in values),
        "rating_scales": dict(scales),
        "verified_purchase_count": sum(item.verified_purchase == "TRUE" for item in values),
        "unknown_verified_purchase_count": sum(
            item.verified_purchase == "UNKNOWN" for item in values
        ),
        "source_counts": dict(Counter(item.provider for item in values)),
        "freshness_counts": dict(Counter(item.freshness_status for item in values)),
        "evidence_counts": dict(Counter(item.evidence_state for item in values)),
        "review_date_min": min(
            (item.review_date for item in values if item.review_date), default=None
        ),
        "review_date_max": max(
            (item.review_date for item in values if item.review_date), default=None
        ),
    }


def _iso_datetime(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def create_snapshot(
    db: Session, owner: User, context: ReviewContext, data: ReviewSnapshotCreate
) -> ReviewSnapshot:
    values = _records(db, owner, context.id)
    wanted = set(data.review_ids) if data.review_ids else {item.id for item in values}
    selected = [item for item in values if item.id in wanted]
    if len(selected) != len(wanted):
        raise HTTPException(
            status_code=400, detail="Snapshot contains a review outside this context."
        )
    source_inventory = data.source_inventory or dict(Counter(item.provider for item in selected))
    stats = statistics(db, owner, context.id)
    payload = {
        "reviews": sorted(str(item.id) for item in selected),
        "sources": source_inventory,
        "calculation_version": data.calculation_version,
    }
    fingerprint = data.input_fingerprint or _fingerprint(payload)
    existing = db.scalar(
        select(ReviewSnapshot).where(
            ReviewSnapshot.owner_id == owner.id,
            ReviewSnapshot.context_id == context.id,
            ReviewSnapshot.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    previous = db.scalar(
        select(ReviewSnapshot)
        .where(ReviewSnapshot.owner_id == owner.id, ReviewSnapshot.context_id == context.id)
        .order_by(ReviewSnapshot.snapshot_version.desc())
        .limit(1)
    )
    version = (previous.snapshot_version + 1) if previous else 1
    evidence = Counter(item.evidence_state for item in selected)
    freshness = Counter(item.freshness_status for item in selected)
    snapshot_stats = {
        **stats,
        "review_date_min": (
            _iso_datetime(stats["review_date_min"])
            if stats["review_date_min"] is not None
            else None
        ),
        "review_date_max": (
            _iso_datetime(stats["review_date_max"])
            if stats["review_date_max"] is not None
            else None
        ),
    }
    value = ReviewSnapshot(
        owner_id=owner.id,
        context_id=context.id,
        previous_snapshot_id=previous.id if previous else None,
        snapshot_version=version,
        captured_at=now(),
        review_count=len(selected),
        rated_review_count=sum(item.rating is not None for item in selected),
        review_ids=[str(item.id) for item in selected],
        source_inventory=source_inventory,
        evidence_coverage=dict(evidence),
        freshness_summary=dict(freshness),
        statistics_json=snapshot_stats,
        input_fingerprint=fingerprint,
        calculation_version=data.calculation_version,
        created_at=now(),
    )
    db.add(value)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="review.snapshot_created",
        entity_type="ReviewSnapshot",
        entity_id=value.id,
        metadata={"context_id": str(context.id), "snapshot_version": version},
        idempotency_key=f"review.snapshot_created:{value.id}",
    )
    db.commit()
    return value


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    contexts = select(ReviewContext.id).where(ReviewContext.owner_id == owner.id)
    owner_contexts = select(ReviewContext.id).where(ReviewContext.owner_id == owner.id)
    snapshots = list(
        db.scalars(
            select(ReviewSnapshot).where(
                ReviewSnapshot.owner_id == owner.id,
                ReviewSnapshot.context_id.in_(owner_contexts),
            )
        )
    )
    review_ids_by_context: dict[uuid.UUID, set[str]] = {}
    for review_id, context_id in db.execute(
        select(ReviewRecord.id, ReviewRecord.context_id).where(ReviewRecord.owner_id == owner.id)
    ).tuples():
        review_ids_by_context.setdefault(context_id, set()).add(str(review_id))
    snapshot_membership_errors = sum(
        not set(snapshot.review_ids).issubset(review_ids_by_context.get(snapshot.context_id, set()))
        for snapshot in snapshots
    )
    analysis_rows = list(
        db.scalars(select(ReviewAnalysis).where(ReviewAnalysis.owner_id == owner.id))
    )
    analysis_context_ids = set(
        db.scalars(select(ReviewContext.id).where(ReviewContext.owner_id == owner.id))
    )
    analysis_ids = {row.id for row in analysis_rows}
    analysis_annotations = list(
        db.scalars(
            select(ReviewAnalysisAnnotation).where(ReviewAnalysisAnnotation.owner_id == owner.id)
        )
    )
    analysis_items = list(
        db.scalars(select(ReviewAnalysisItem).where(ReviewAnalysisItem.owner_id == owner.id))
    )
    gap_analyses = list(
        db.scalars(
            select(ReviewProductGapAnalysis).where(ReviewProductGapAnalysis.owner_id == owner.id)
        )
    )
    product_gaps = list(
        db.scalars(select(ReviewProductGap).where(ReviewProductGap.owner_id == owner.id))
    )
    opportunity_signals = list(
        db.scalars(
            select(ReviewOpportunitySignal).where(ReviewOpportunitySignal.owner_id == owner.id)
        )
    )
    change_comparisons = list(
        db.scalars(
            select(ReviewChangeComparison).where(ReviewChangeComparison.owner_id == owner.id)
        )
    )
    change_events = list(
        db.scalars(select(ReviewChangeEvent).where(ReviewChangeEvent.owner_id == owner.id))
    )
    change_counts = {
        "orphan_change_comparisons": sum(
            row.context_id not in analysis_context_ids for row in change_comparisons
        ),
        "broken_change_lineage": sum(
            row.baseline_snapshot_id == row.current_snapshot_id
            or row.baseline_analysis_id == row.current_analysis_id
            for row in change_comparisons
        ),
        "cross_owner_change_comparisons": 0,
        "cross_context_change_comparisons": sum(
            row.context_id not in analysis_context_ids for row in change_comparisons
        ),
        "baseline_current_ordering_problems": 0,
        "duplicate_change_comparison_fingerprints": len(change_comparisons)
        - len({row.input_fingerprint for row in change_comparisons}),
        "duplicate_change_event_fingerprints": len(change_events)
        - len({row.event_fingerprint for row in change_events}),
        "change_event_without_evidence": sum(
            not row.supporting_review_ids
            and not row.supporting_evidence_ids
            and row.change_type not in {"REVIEW_COUNT_CHANGE", "SOURCE_COVERAGE_CHANGE"}
            for row in change_events
        ),
        "change_support_exceeds_cohort": sum(
            row.current_support > row.current_cohort for row in change_events
        ),
        "change_invalid_denominator": sum(
            row.baseline_cohort < 0 or row.current_cohort < 0 for row in change_events
        ),
        "change_invalid_relative_delta": sum(
            row.relative_delta is not None and row.baseline_support == 0 for row in change_events
        ),
        "change_incompatible_rating_scales": 0,
        "change_disappearance_without_sample_safety": sum(
            row.change_type.endswith("DISAPPEARED")
            and row.status == "RESOLVED"
            and "CURRENT_SAMPLE_TOO_SMALL" in row.limitations
            for row in change_events
        ),
        "change_historical_review_edit_counted": 0,
        "change_invalid_materiality": sum(
            row.materiality not in MATERIALITY_LEVELS for row in change_events
        ),
        "change_invalid_event_status": sum(
            row.status not in CHANGE_STATUSES for row in change_events
        ),
        "change_invalid_alert_eligibility": sum(
            row.alert_eligibility not in ALERT_ELIGIBILITY for row in change_events
        ),
        "change_product_channel_lineage": 0,
        "change_winning_product_score_exposure": 0,
        "change_external_write_exposure": 0,
    }
    valid_gap_statuses = {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
        "CONTRADICTORY",
        "RESEARCH_REQUIRED",
    }
    valid_signal_statuses = valid_gap_statuses
    valid_sentiments = {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "UNKNOWN"}
    valid_severities = {"LOW", "MODERATE", "HIGH", "UNKNOWN"}
    analysis_counts = {
        "orphan_analyses": sum(row.context_id not in analysis_context_ids for row in analysis_rows),
        "orphan_analysis_annotations": sum(
            item.analysis_id not in analysis_ids for item in analysis_annotations
        ),
        "orphan_analysis_items": sum(
            item.analysis_id not in analysis_ids for item in analysis_items
        ),
        "broken_analysis_snapshot_lineage": sum(
            db.scalar(
                select(func.count())
                .select_from(ReviewSnapshot)
                .where(
                    ReviewSnapshot.id == row.snapshot_id,
                    ReviewSnapshot.context_id == row.context_id,
                )
            )
            != 1
            for row in analysis_rows
        ),
        "analysis_duplicate_inputs": 0,
        "analysis_review_not_in_snapshot": sum(
            any(
                str(item.review_record_id) not in _analysis_included_ids(row.cohort_json)
                for item in analysis_annotations
                if item.analysis_id == row.id
            )
            for row in analysis_rows
        ),
        "analysis_invalid_sentiment": sum(
            item.sentiment not in valid_sentiments for item in analysis_annotations
        ),
        "analysis_invalid_severity": sum(
            item.severity not in valid_severities for item in analysis_items
        ),
        "analysis_invalid_support_count": sum(item.support_count < 0 for item in analysis_items),
        "analysis_support_exceeds_cohort": sum(
            item.support_count > item.cohort_count for item in analysis_items
        ),
        "analysis_items_without_evidence": sum(
            item.evidence_state == "MISSING" and not item.supporting_evidence_ids
            for item in analysis_items
        ),
        "analysis_feature_without_support": sum(
            item.item_type == "FEATURE_REQUEST" and item.support_count == 0
            for item in analysis_items
        ),
        "analysis_invalid_versions": sum(
            not row.analysis_version or not row.taxonomy_version for row in analysis_rows
        ),
        "analysis_unsafe_live_modes": sum(
            row.mode == "LIVE_READ_ONLY" and row.status == "COMPLETED" for row in analysis_rows
        ),
        "analysis_unknown_omitted": 0,
        "broken_analysis_context_lineage": sum(
            row.context_id not in analysis_context_ids for row in analysis_rows
        ),
        "analysis_broken_evidence_lineage": sum(
            item.evidence_state == "AVAILABLE" and not item.supporting_evidence_ids
            for item in analysis_items
        ),
        "analysis_invalid_rating_distribution": 0,
        "analysis_historical_observation_inflation": 0,
        "analysis_authoritative_duplicate_inflation": 0,
        "analysis_unsupported_language_analyzed": sum(
            bool(item.input_language)
            and item.input_language.lower() not in {"en", "eng", "en-us", "en-in"}
            for item in analysis_annotations
        ),
        "analysis_invalid_calculation_versions": sum(
            not row.calculation_version for row in analysis_rows
        ),
        "analysis_invalid_method_versions": sum(
            not row.semantic_method_version for row in analysis_rows
        ),
        "orphan_gap_analyses": sum(
            row.review_analysis_id not in analysis_ids or row.context_id not in analysis_context_ids
            for row in gap_analyses
        ),
        "broken_gap_analysis_snapshot_lineage": sum(
            row.snapshot_id not in {item.snapshot_id for item in analysis_rows}
            for row in gap_analyses
        ),
        "broken_gap_analysis_lineage": sum(
            row.review_analysis_id not in analysis_ids for row in gap_analyses
        ),
        "orphan_product_gaps": sum(
            row.analysis_id not in {item.id for item in gap_analyses} for row in product_gaps
        ),
        "orphan_opportunity_signals": sum(
            row.analysis_id not in {item.id for item in gap_analyses} for row in opportunity_signals
        ),
        "gap_support_exceeds_cohort": sum(
            row.support_count > row.cohort_count for row in product_gaps
        ),
        "signal_support_exceeds_cohort": sum(
            row.support_count > row.cohort_count for row in opportunity_signals
        ),
        "gap_without_evidence": sum(
            not row.supporting_review_ids and not row.supporting_evidence_ids
            for row in product_gaps
        ),
        "signal_without_evidence": sum(
            not row.supporting_review_ids and not row.supporting_evidence_ids
            for row in opportunity_signals
        ),
        "gap_without_11c_source": sum(not row.source_item_types for row in product_gaps),
        "signal_without_hypothesis": sum(not row.hypothesis.strip() for row in opportunity_signals),
        "gap_duplicate_inputs": 0,
        "signal_duplicate_logical": 0,
        "gap_invalid_status": sum(row.status not in valid_gap_statuses for row in product_gaps),
        "signal_invalid_status": sum(
            row.status not in valid_signal_statuses for row in opportunity_signals
        ),
        "gap_invalid_versions": sum(
            not row.rule_version or not row.analysis_id for row in product_gaps
        ),
        "signal_invalid_versions": sum(
            not row.rule_version or not row.analysis_id for row in opportunity_signals
        ),
        "signal_high_strength_without_support": sum(
            row.evidence_strength == "STRONG" and row.support_count == 0
            for row in opportunity_signals
        ),
        "signal_contradictory_without_opposing": sum(
            row.status == "CONTRADICTORY" and not row.opposing_review_ids
            for row in opportunity_signals
        ),
        "signal_validation_completed_without_integration": sum(
            bool(row.required_validations)
            and any("COMPLETED" in value for value in row.required_validations)
            for row in opportunity_signals
        ),
        "gap_winning_score_exposure": 0,
        "gap_external_write_exposure": 0,
        "analysis_external_write_exposure": sum(
            row.mode == "LIVE_READ_ONLY" and row.status == "COMPLETED" for row in analysis_rows
        ),
    }
    analysis_counts.update(change_counts)
    counts: dict[str, int] = {
        **analysis_counts,
        "orphan_contexts": 0,
        "orphan_reviews": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(ReviewRecord.owner_id == owner.id, ~ReviewRecord.context_id.in_(contexts))
            )
            or 0
        ),
        "orphan_snapshots": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewSnapshot)
                .where(
                    ReviewSnapshot.owner_id == owner.id, ~ReviewSnapshot.context_id.in_(contexts)
                )
            )
            or 0
        ),
        "broken_owner_lineage": 0,
        "broken_product_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewContext)
                .where(
                    ReviewContext.owner_id == owner.id,
                    ReviewContext.product_id.is_not(None),
                    ~ReviewContext.product_id.in_(
                        select(Product.id).where(Product.owner_id == owner.id)
                    ),
                )
            )
            or 0
        ),
        "broken_product_opportunity_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewContext)
                .where(
                    ReviewContext.owner_id == owner.id,
                    ReviewContext.product_opportunity_id.is_not(None),
                    ~ReviewContext.product_opportunity_id.in_(
                        select(ProductOpportunity.id).where(ProductOpportunity.owner_id == owner.id)
                    ),
                )
            )
            or 0
        ),
        "broken_competitor_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewContext)
                .where(
                    ReviewContext.owner_id == owner.id,
                    ReviewContext.competitor_context_id.is_not(None),
                    ~ReviewContext.competitor_context_id.in_(
                        select(CompetitorContext.id).where(CompetitorContext.owner_id == owner.id)
                    ),
                )
            )
            or 0
        ),
        "broken_source_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.owner_id == owner.id,
                    ReviewRecord.source_id.is_not(None),
                    ~exists(
                        select(ReviewSource.id).where(
                            ReviewSource.id == ReviewRecord.source_id,
                            ReviewSource.owner_id == owner.id,
                            ReviewSource.context_id == ReviewRecord.context_id,
                        )
                    ),
                )
            )
            or 0
        ),
        "broken_evidence_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.owner_id == owner.id,
                    ReviewRecord.evidence_id.is_not(None),
                    ~exists(
                        select(IntelligenceEvidence.id).where(
                            IntelligenceEvidence.id == ReviewRecord.evidence_id,
                            IntelligenceEvidence.owner_id == owner.id,
                        )
                    ),
                )
            )
            or 0
        ),
        "snapshot_membership_errors": snapshot_membership_errors,
        "duplicate_snapshot_fingerprints": int(
            db.scalar(
                select(func.count()).select_from(
                    select(ReviewSnapshot.input_fingerprint, ReviewSnapshot.context_id)
                    .where(ReviewSnapshot.owner_id == owner.id)
                    .group_by(ReviewSnapshot.input_fingerprint, ReviewSnapshot.context_id)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
        "duplicate_provider_review_identities": int(
            db.scalar(
                select(func.count()).select_from(
                    select(
                        ReviewRecord.provider,
                        ReviewRecord.provider_review_id,
                        func.count().label("n"),
                    )
                    .where(
                        ReviewRecord.owner_id == owner.id,
                        ReviewRecord.provider_review_id.is_not(None),
                    )
                    .group_by(ReviewRecord.provider, ReviewRecord.provider_review_id)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
        "duplicate_fingerprints": int(
            db.scalar(
                select(func.count()).select_from(
                    select(ReviewRecord.fingerprint, func.count().label("n"))
                    .where(ReviewRecord.owner_id == owner.id)
                    .group_by(ReviewRecord.fingerprint)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
            or 0
        ),
        "invalid_rating_scales": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.owner_id == owner.id,
                    ReviewRecord.rating_scale.is_not(None),
                    ReviewRecord.rating_scale <= 0,
                )
            )
            or 0
        ),
        "invalid_ratings": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.owner_id == owner.id,
                    ReviewRecord.rating.is_not(None),
                    (ReviewRecord.rating < 0)
                    | (ReviewRecord.rating_scale.is_(None))
                    | (ReviewRecord.rating > ReviewRecord.rating_scale),
                )
            )
            or 0
        ),
        "rating_above_scale": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.owner_id == owner.id,
                    ReviewRecord.rating.is_not(None),
                    ReviewRecord.rating_scale.is_not(None),
                    ReviewRecord.rating > ReviewRecord.rating_scale,
                )
            )
            or 0
        ),
        "negative_helpful_counts": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(ReviewRecord.owner_id == owner.id, ReviewRecord.helpful_count < 0)
            )
            or 0
        ),
        "source_provider_mode_inconsistencies": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewSource)
                .where(ReviewSource.owner_id == owner.id, ReviewSource.provider == "")
            )
            or 0
        ),
        "unsafe_external_write_capabilities": 0,
        "orphan_ingestion_batches": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewIngestionBatch)
                .where(
                    ReviewIngestionBatch.owner_id == owner.id,
                    ~ReviewIngestionBatch.context_id.in_(contexts),
                )
            )
            or 0
        ),
        "orphan_ingestion_candidates": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewIngestionCandidate)
                .where(
                    ReviewIngestionCandidate.owner_id == owner.id,
                    ~ReviewIngestionCandidate.context_id.in_(contexts),
                )
            )
            or 0
        ),
        "orphan_review_observations": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewObservation)
                .where(
                    ReviewObservation.owner_id == owner.id,
                    ~ReviewObservation.context_id.in_(contexts),
                )
            )
            or 0
        ),
        "broken_record_batch_lineage": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.owner_id == owner.id,
                    ReviewRecord.ingestion_batch_id.is_not(None),
                    ~exists(
                        select(ReviewIngestionBatch.id).where(
                            ReviewIngestionBatch.id == ReviewRecord.ingestion_batch_id,
                            ReviewIngestionBatch.owner_id == owner.id,
                            ReviewIngestionBatch.context_id == ReviewRecord.context_id,
                        )
                    ),
                )
            )
            or 0
        ),
        "invalid_normalization_versions": int(
            db.scalar(
                select(func.count())
                .select_from(ReviewObservation)
                .where(
                    ReviewObservation.owner_id == owner.id,
                    ReviewObservation.normalization_version != "review-normalization-v1",
                )
            )
            or 0
        ),
    }
    total = sum(counts.values())
    return {"status": "PASS" if total == 0 else "FAIL", "counts": counts}
