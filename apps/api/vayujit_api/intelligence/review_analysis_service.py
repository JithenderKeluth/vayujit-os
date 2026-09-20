"""Deterministic, evidence-backed Review Intelligence analysis (Slice 11C)."""

from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewAnalysisAnnotation,
    ReviewAnalysisItem,
    ReviewContext,
    ReviewRecord,
    ReviewSnapshot,
)
from vayujit_api.intelligence.review_schemas import ReviewAnalysisRequest
from vayujit_api.intelligence.review_service import _context_or_404, _fingerprint

ANALYSIS_VERSION = "review-analysis-v1"
CALCULATION_VERSION = "review-calculation-v1"
TAXONOMY_VERSION = "review-taxonomy-v1"
SEMANTIC_METHOD_VERSION = "local-rules-v1"
SUPPORTED_LANGUAGES = {"", "en", "eng", "en-us", "en-in"}

POSITIVE_WORDS = {
    "good",
    "great",
    "excellent",
    "love",
    "like",
    "helpful",
    "perfect",
    "easy",
    "fast",
    "beautiful",
    "durable",
    "sturdy",
}
NEGATIVE_WORDS = {
    "bad",
    "poor",
    "terrible",
    "hate",
    "disappoint",
    "disappointed",
    "broken",
    "leak",
    "fail",
    "missing",
    "slow",
    "small",
    "expensive",
    "fragile",
    "unusable",
}
TOPIC_RULES: dict[str, tuple[str, ...]] = {
    "QUALITY_DURABILITY": ("quality", "durable", "sturdy", "fragile", "broken", "break", "leak"),
    "BATTERY_LIFE": ("battery", "charge", "charging", "usb-c", "usb c"),
    "SIZE_FIT": ("size", "fit", "small", "large", "bigger", "smaller"),
    "PACKAGING": ("package", "packaging", "box", "wrapped"),
    "DELIVERY": ("delivery", "shipping", "arrived", "late", "dispatch"),
    "PRICE_VALUE": ("price", "value", "expensive", "cheap", "worth"),
    "EASE_OF_USE": ("easy", "simple", "use", "setup", "install"),
    "DESIGN": ("design", "beautiful", "color", "look", "appearance"),
    "PERFORMANCE": ("performance", "works", "fast", "slow", "power"),
    "CUSTOMER_SUPPORT": ("support", "service", "refund", "response"),
}
FEATURE_PHRASES = (
    "wish",
    "please add",
    "would like",
    "needs",
    "need a",
    "should have",
    "larger size",
    "travel case",
    "usb-c",
)
QUALITY_PHRASES = (
    "broken",
    "break",
    "leak",
    "battery failure",
    "missing component",
    "incorrect size",
    "fragile",
)


def _text(record: ReviewRecord) -> str:
    return " ".join(
        value.strip() for value in (record.title or "", record.body or "") if value
    ).strip()


def _words(text: str) -> set[str]:
    return {part.strip(".,!?;:()[]{}\"'").lower() for part in text.split() if part.strip()}


def _sentiment(text: str) -> str:
    if not text:
        return "UNKNOWN"
    words = _words(text)
    positive = bool(words & POSITIVE_WORDS)
    negative = bool(words & NEGATIVE_WORDS)
    if positive and negative:
        return "MIXED"
    if positive:
        return "POSITIVE"
    if negative:
        return "NEGATIVE"
    return "NEUTRAL"


def _topics(text: str) -> list[str]:
    lower = text.lower()
    return sorted(
        label
        for label, phrases in TOPIC_RULES.items()
        if any(phrase in lower for phrase in phrases)
    )


def _aspect_sentiment(text: str, phrases: tuple[str, ...]) -> str:
    lower = text.lower()
    if not any(phrase in lower for phrase in phrases):
        return "UNKNOWN"
    return _sentiment(text)


def _confidence(support: int) -> str:
    return "HIGH" if support >= 3 else "MEDIUM" if support >= 2 else "LOW"


def _severity(support: int, cohort: int) -> str:
    if support >= max(3, math.ceil(cohort * 0.2)):
        return "HIGH"
    if support >= 2:
        return "MODERATE"
    return "LOW"


def _json_decimal(value: Decimal | float | None) -> str | None:
    return str(value) if value is not None else None


def _rating_distribution(records: list[ReviewRecord]) -> dict[str, object]:
    groups: dict[str, list[Decimal]] = defaultdict(list)
    for record in records:
        if record.rating is not None and record.rating_scale is not None:
            groups[str(record.rating_scale)].append(Decimal(record.rating))
    result: dict[str, object] = {
        "rated_count": sum(len(values) for values in groups.values()),
        "unrated_count": sum(record.rating is None for record in records),
        "scales": {},
    }
    scales = result["scales"]
    if not isinstance(scales, dict):
        return result
    for scale, values in sorted(groups.items()):
        buckets = Counter(str(value) for value in values)
        scales[scale] = {
            "count": len(values),
            "min": _json_decimal(min(values)),
            "max": _json_decimal(max(values)),
            "mean": _json_decimal(sum(values) / len(values)),
            "median": _json_decimal(Decimal(str(median(values)))),
            "buckets": dict(buckets),
        }
    return result


def _rating_sentiment_disagreement(records: list[ReviewRecord]) -> dict[str, object]:
    disagreements: list[dict[str, object]] = []
    comparable = 0
    for record in records:
        if record.rating is None or record.rating_scale is None:
            continue
        text_sentiment = _sentiment(_text(record))
        if text_sentiment in {"UNKNOWN", "MIXED"}:
            continue
        comparable += 1
        midpoint = float(record.rating_scale) / 2
        rating_sentiment = (
            "POSITIVE"
            if float(record.rating) > midpoint + 0.5
            else "NEGATIVE" if float(record.rating) < midpoint - 0.5 else "NEUTRAL"
        )
        if rating_sentiment != text_sentiment:
            disagreements.append(
                {
                    "review_id": str(record.id),
                    "rating_sentiment": rating_sentiment,
                    "text_sentiment": text_sentiment,
                }
            )
    return {
        "comparable_count": comparable,
        "disagreement_count": len(disagreements),
        "disagreement_rate": round(len(disagreements) / comparable, 6) if comparable else 0.0,
        "review_ids": disagreements,
    }


def _snapshot(
    db: Session, owner: User, context_id: uuid.UUID, snapshot_id: uuid.UUID | None
) -> ReviewSnapshot:
    query = select(ReviewSnapshot).where(
        ReviewSnapshot.owner_id == owner.id, ReviewSnapshot.context_id == context_id
    )
    if snapshot_id is not None:
        query = query.where(ReviewSnapshot.id == snapshot_id)
    else:
        query = query.order_by(ReviewSnapshot.snapshot_version.desc()).limit(1)
    value = db.scalar(query)
    if value is None:
        raise HTTPException(status_code=404, detail="Review snapshot not found.")
    return value


def _detail_records(db: Session, owner: User, snapshot: ReviewSnapshot) -> list[ReviewRecord]:
    ids = [uuid.UUID(value) for value in snapshot.review_ids]
    if not ids:
        return []
    values = list(
        db.scalars(
            select(ReviewRecord).where(
                ReviewRecord.owner_id == owner.id,
                ReviewRecord.context_id == snapshot.context_id,
                ReviewRecord.id.in_(ids),
            )
        )
    )
    by_id = {value.id: value for value in values}
    return [by_id[item] for item in ids if item in by_id]


def _fingerprint_for(
    owner: User, context: ReviewContext, snapshot: ReviewSnapshot, data: ReviewAnalysisRequest
) -> str:
    return _fingerprint(
        {
            "owner": str(owner.id),
            "context": str(context.id),
            "snapshot": str(snapshot.id),
            "snapshot_version": snapshot.snapshot_version,
            "mode": data.mode,
            "analysis": data.analysis_version,
            "calculation": data.calculation_version,
            "taxonomy": data.taxonomy_version,
        }
    )


def _item_payload(
    analysis_id: uuid.UUID,
    context_id: uuid.UUID,
    owner_id: uuid.UUID,
    item_type: str,
    label: str,
    values: list[tuple[ReviewRecord, str]],
    cohort: int,
) -> ReviewAnalysisItem:
    support_ids = [str(record.id) for record, _ in values]
    sentiments = Counter(sentiment for _, sentiment in values)
    source_counts = Counter(record.provider for record, _ in values)
    freshness = Counter(record.freshness_status for record, _ in values)
    evidence_ids = sorted({str(record.evidence_id) for record, _ in values if record.evidence_id})
    dominant = sentiments.most_common(1)[0][0] if sentiments else "UNKNOWN"
    severity = (
        _severity(len(values), cohort)
        if item_type in {"PAIN_POINT", "QUALITY_ISSUE"}
        else "UNKNOWN"
    )
    return ReviewAnalysisItem(
        owner_id=owner_id,
        analysis_id=analysis_id,
        context_id=context_id,
        item_type=item_type,
        canonical_label=label,
        raw_labels=[label],
        sentiment=dominant,
        sentiment_distribution=dict(sentiments),
        severity=severity,
        support_count=len(values),
        cohort_count=cohort,
        coverage={
            "support_count": len(values),
            "cohort_count": cohort,
            "proportion": round(len(values) / cohort, 6) if cohort else 0.0,
        },
        source_distribution=dict(source_counts),
        supporting_review_ids=support_ids,
        supporting_evidence_ids=evidence_ids,
        freshness=dict(freshness),
        confidence=_confidence(len(values)),
        evidence_state="AVAILABLE" if evidence_ids else "PARTIAL",
        classification_type="DERIVED_SEMANTIC",
        method_version=SEMANTIC_METHOD_VERSION,
        limitation=None if evidence_ids else "review evidence identifiers were not available",
        created_at=now(),
    )


def create_analysis(
    db: Session, owner: User, context: ReviewContext, data: ReviewAnalysisRequest
) -> ReviewAnalysis:
    snapshot = _snapshot(db, owner, context.id, data.snapshot_id)
    fingerprint = _fingerprint_for(owner, context, snapshot, data)
    existing = db.scalar(
        select(ReviewAnalysis).where(
            ReviewAnalysis.owner_id == owner.id,
            ReviewAnalysis.context_id == context.id,
            ReviewAnalysis.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    records = _detail_records(db, owner, snapshot)
    included: list[ReviewRecord] = []
    exclusions: list[dict[str, object]] = []
    for record in records:
        text = _text(record)
        language = (record.language or context.language or "").lower()
        if language not in SUPPORTED_LANGUAGES:
            exclusions.append({"review_id": str(record.id), "reason": "UNSUPPORTED_LANGUAGE"})
        elif not text:
            exclusions.append({"review_id": str(record.id), "reason": "INSUFFICIENT_TEXT"})
        else:
            included.append(record)
    gaps: list[dict[str, object]] = []
    limitations: list[str] = [
        "semantic classifications are deterministic local rules; "
        "external model execution is unavailable"
    ]
    if len(included) < 2:
        gaps.append({"code": "INSUFFICIENT_REVIEW_SAMPLE", "count": len(included)})
    if any(item["reason"] == "INSUFFICIENT_TEXT" for item in exclusions):
        gaps.append({"code": "INSUFFICIENT_TEXT_COVERAGE"})
    if any(item["reason"] == "UNSUPPORTED_LANGUAGE" for item in exclusions):
        gaps.append({"code": "UNSUPPORTED_LANGUAGE"})
    source_distribution = dict(Counter(record.provider for record in included))
    if len(source_distribution) < 2:
        gaps.append({"code": "INSUFFICIENT_SOURCE_COVERAGE"})
    if any(record.rating is None for record in included):
        gaps.append({"code": "MISSING_RATING_EVIDENCE"})
    sentiment_counts = Counter(_sentiment(_text(record)) for record in included)
    sentiment_distribution = {
        label: {
            "count": sentiment_counts.get(label, 0),
            "proportion": (
                round(sentiment_counts.get(label, 0) / len(included), 6) if included else 0.0
            ),
        }
        for label in ("POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "UNKNOWN")
    }
    if sentiment_counts.get("UNKNOWN", 0) > len(included) / 2 if included else False:
        gaps.append({"code": "HIGH_UNKNOWN_SENTIMENT"})
    analysis = ReviewAnalysis(
        owner_id=owner.id,
        context_id=context.id,
        snapshot_id=snapshot.id,
        snapshot_version=snapshot.snapshot_version,
        analysis_version=data.analysis_version,
        calculation_version=data.calculation_version,
        normalization_version="review-normalization-v1",
        taxonomy_version=data.taxonomy_version,
        semantic_method_version=SEMANTIC_METHOD_VERSION,
        input_fingerprint=fingerprint,
        mode=data.mode,
        status="COMPLETED" if data.mode == "LOCAL_FIXTURE" else "FAILED",
        total_records=len(records),
        included_records=len(included),
        excluded_records=len(exclusions),
        cohort_json={
            "total": len(records),
            "included": [str(item.id) for item in included],
            "excluded": exclusions,
        },
        rating_distribution={
            **_rating_distribution(included),
            "text_disagreement": _rating_sentiment_disagreement(included),
        },
        sentiment_distribution=sentiment_distribution,
        source_distribution=source_distribution,
        evidence_gaps=gaps,
        limitations=limitations,
        error_message=(
            None
            if data.mode == "LOCAL_FIXTURE"
            else "Analysis mode is disabled for this environment."
        ),
        created_at=now(),
    )
    db.add(analysis)
    db.flush()
    if data.mode == "LOCAL_FIXTURE":
        topic_values: dict[str, list[tuple[ReviewRecord, str]]] = defaultdict(list)
        for record in included:
            text = _text(record)
            sentiment = _sentiment(text)
            topics = _topics(text)
            aspect = {topic: _aspect_sentiment(text, TOPIC_RULES[topic]) for topic in topics}
            confidence = _confidence(1)
            db.add(
                ReviewAnalysisAnnotation(
                    owner_id=owner.id,
                    analysis_id=analysis.id,
                    context_id=context.id,
                    input_language=record.language or context.language or "",
                    analysis_language=record.language or context.language or "",
                    translation_lineage={},
                    review_record_id=record.id,
                    sentiment=sentiment,
                    aspect_sentiments=aspect,
                    topics=topics,
                    quality_state=record.evidence_state,
                    classification_type="DERIVED_SEMANTIC",
                    method_version=SEMANTIC_METHOD_VERSION,
                    confidence=confidence,
                    limitation=None,
                    created_at=now(),
                )
            )
            for topic in topics:
                topic_values[topic].append((record, aspect[topic]))
            lower = text.lower()
            if any(phrase in lower for phrase in FEATURE_PHRASES):
                topic_values["FEATURE_REQUEST"].append((record, sentiment))
            if any(phrase in lower for phrase in QUALITY_PHRASES):
                topic_values["QUALITY_ISSUE"].append((record, sentiment))
        for label, values in topic_values.items():
            if label == "FEATURE_REQUEST":
                item_type = "FEATURE_REQUEST"
            elif label == "QUALITY_ISSUE":
                item_type = "QUALITY_ISSUE"
            else:
                sentiments = [sentiment for _, sentiment in values]
                item_type = (
                    "PAIN_POINT"
                    if any(sentiment in {"NEGATIVE", "MIXED"} for sentiment in sentiments)
                    else (
                        "PRAISED_ATTRIBUTE"
                        if any(sentiment == "POSITIVE" for sentiment in sentiments)
                        else "TOPIC"
                    )
                )
            db.add(
                _item_payload(
                    analysis.id, context.id, owner.id, item_type, label, values, len(included)
                )
            )
        theme_values = {
            label: values
            for label, values in topic_values.items()
            if len(values) >= 2 and label not in {"FEATURE_REQUEST", "QUALITY_ISSUE"}
        }
        for label, values in theme_values.items():
            db.add(
                _item_payload(
                    analysis.id, context.id, owner.id, "THEME", label, values, len(included)
                )
            )
    action = (
        "review.analysis_created"
        if snapshot.snapshot_version == 1
        else "review.analysis_recalculated"
    )
    record_event(
        db,
        actor_id=owner.id,
        action=action,
        entity_type="ReviewAnalysis",
        entity_id=analysis.id,
        metadata={
            "context_id": str(context.id),
            "snapshot_version": snapshot.snapshot_version,
            "mode": data.mode,
        },
        idempotency_key=f"{action}:{analysis.id}",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ReviewAnalysis).where(
                ReviewAnalysis.owner_id == owner.id,
                ReviewAnalysis.context_id == context.id,
                ReviewAnalysis.input_fingerprint == fingerprint,
            )
        )
        if existing is None:
            raise
        return existing
    return analysis


def analysis_detail(
    db: Session, owner: User, context_id: uuid.UUID, analysis_id: uuid.UUID
) -> tuple[ReviewAnalysis, list[ReviewAnalysisItem], list[ReviewAnalysisAnnotation]]:
    analysis = db.scalar(
        select(ReviewAnalysis).where(
            ReviewAnalysis.id == analysis_id,
            ReviewAnalysis.owner_id == owner.id,
            ReviewAnalysis.context_id == context_id,
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Review analysis not found.")
    items = list(
        db.scalars(
            select(ReviewAnalysisItem)
            .where(
                ReviewAnalysisItem.owner_id == owner.id,
                ReviewAnalysisItem.analysis_id == analysis.id,
            )
            .order_by(ReviewAnalysisItem.item_type, ReviewAnalysisItem.canonical_label)
        )
    )
    annotations = list(
        db.scalars(
            select(ReviewAnalysisAnnotation)
            .where(
                ReviewAnalysisAnnotation.owner_id == owner.id,
                ReviewAnalysisAnnotation.analysis_id == analysis.id,
            )
            .order_by(ReviewAnalysisAnnotation.created_at)
        )
    )
    return analysis, items, annotations


def current_analysis(db: Session, owner: User, context_id: uuid.UUID) -> ReviewAnalysis | None:
    _context_or_404(db, owner, context_id)
    return db.scalar(
        select(ReviewAnalysis)
        .where(ReviewAnalysis.owner_id == owner.id, ReviewAnalysis.context_id == context_id)
        .order_by(ReviewAnalysis.snapshot_version.desc(), ReviewAnalysis.created_at.desc())
        .limit(1)
    )
