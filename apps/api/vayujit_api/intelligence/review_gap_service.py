"""Deterministic Review Product Gap and Opportunity Signal derivation (Slice 11D)."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewAnalysisItem,
    ReviewContext,
    ReviewOpportunitySignal,
    ReviewProductGap,
    ReviewProductGapAnalysis,
)
from vayujit_api.intelligence.review_service import _context_or_404, _fingerprint

ANALYSIS_VERSION = "review-gap-analysis-v1"
CALCULATION_VERSION = "review-gap-calculation-v1"
RULE_VERSION = "review-gap-rules-v1"


def _support_classification(count: int) -> str:
    return (
        "SINGLE_OBSERVATION"
        if count == 1
        else "LIMITED" if count == 2 else "REPEATED" if count < 5 else "STRONG"
    )


def _strength(count: int, cohort: int) -> str:
    if count <= 0:
        return "UNKNOWN"
    if count >= 3 and (not cohort or count / cohort >= 0.2):
        return "STRONG"
    return "MODERATE" if count >= 2 else "WEAK"


def _gap_type(item: ReviewAnalysisItem) -> str:
    if item.item_type == "FEATURE_REQUEST":
        return "MISSING_FEATURE"
    if item.item_type == "PRAISED_ATTRIBUTE":
        return "PRESERVE_ATTRIBUTE"
    label = item.canonical_label
    if label == "SIZE_FIT":
        return "SIZE_OR_FIT_GAP"
    if label == "PACKAGING":
        return "PACKAGING_GAP"
    if label == "EASE_OF_USE":
        return "USABILITY_GAP"
    if label == "PERFORMANCE":
        return "PERFORMANCE_GAP"
    if label == "PRICE_VALUE":
        return "VALUE_CONCERN"
    if label in {"QUALITY_DURABILITY", "BATTERY_LIFE"}:
        return "QUALITY_IMPROVEMENT"
    if item.item_type == "PAIN_POINT":
        return "FEATURE_IMPROVEMENT"
    if item.item_type == "QUALITY_ISSUE":
        return "QUALITY_IMPROVEMENT"
    return "UNKNOWN"


def _validations(gap_type: str) -> list[str]:
    if gap_type == "PRESERVE_ATTRIBUTE":
        return []
    values = ["DEMAND_VALIDATION_REQUIRED"]
    if gap_type == "MISSING_FEATURE":
        values += [
            "COMPETITOR_VALIDATION_REQUIRED",
            "COMMERCIAL_VALIDATION_REQUIRED",
            "SUPPLIER_FEASIBILITY_REQUIRED",
        ]
    elif gap_type in {"QUALITY_IMPROVEMENT", "DURABILITY_IMPROVEMENT", "VARIANT_GAP"}:
        values += ["COMMERCIAL_VALIDATION_REQUIRED", "SUPPLIER_FEASIBILITY_REQUIRED"]
    return values


def _hypothesis(gap_type: str, label: str) -> str:
    wording = {
        "MISSING_FEATURE": "Reviewers repeatedly requested",
        "PRESERVE_ATTRIBUTE": "Reviewers repeatedly praised",
        "QUALITY_IMPROVEMENT": "Review evidence indicates a quality improvement hypothesis for",
        "FEATURE_IMPROVEMENT": "Review evidence indicates an improvement hypothesis for",
        "USABILITY_GAP": "Review evidence indicates a usability gap around",
        "SIZE_OR_FIT_GAP": "Review evidence indicates a size or fit gap around",
        "PACKAGING_GAP": "Review evidence indicates a packaging gap around",
        "PERFORMANCE_GAP": "Review evidence indicates a performance gap around",
        "VALUE_CONCERN": "Review evidence indicates a value concern around",
    }
    prefix = wording.get(gap_type, "Review evidence indicates a research hypothesis around")
    return f"{prefix} {label.replace('_', ' ').lower()}."


def _merge_items(items: list[ReviewAnalysisItem]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[ReviewAnalysisItem]] = {}
    for item in items:
        key = (_gap_type(item), item.canonical_label)
        grouped.setdefault(key, []).append(item)
    result: list[dict[str, Any]] = []
    for (gap_type, label), values in sorted(grouped.items()):
        reviews = sorted(
            {review_id for value in values for review_id in value.supporting_review_ids}
        )
        evidence = sorted(
            {evidence_id for value in values for evidence_id in value.supporting_evidence_ids}
        )
        sources: Counter[str] = Counter()
        freshness: Counter[str] = Counter()
        for value in values:
            sources.update(value.source_distribution)
            freshness.update(value.freshness)
        support = len(reviews) or sum(value.support_count for value in values)
        cohort = max((value.cohort_count for value in values), default=0)
        opposing: list[str] = []
        for value in values:
            distribution = value.sentiment_distribution
            if distribution.get("POSITIVE", 0) and distribution.get("NEGATIVE", 0):
                opposing.extend(value.supporting_review_ids)
        status = (
            "CONTRADICTORY"
            if opposing
            else (
                "SUPPORTED"
                if support >= 2
                else "PARTIALLY_SUPPORTED" if support == 1 else "INSUFFICIENT_EVIDENCE"
            )
        )
        if support == 0:
            status = "RESEARCH_REQUIRED"
        limitations = ["review evidence is limited to the analyzed cohort"]
        if cohort < 5:
            limitations.append(
                "small sample: support is reported as a count of the eligible cohort"
            )
        if not evidence:
            limitations.append("source evidence identifiers were unavailable")
        result.append(
            {
                "gap_type": gap_type,
                "label": label,
                "items": values,
                "reviews": reviews,
                "evidence": evidence,
                "opposing": sorted(set(opposing)),
                "sources": dict(sources),
                "freshness": dict(freshness),
                "support": support,
                "cohort": cohort,
                "coverage": {
                    "support_count": support,
                    "cohort_count": cohort,
                    "proportion": round(support / cohort, 6) if cohort else 0.0,
                },
                "status": status,
                "strength": _strength(support, cohort),
                "support_classification": (
                    _support_classification(support) if support else "UNKNOWN"
                ),
                "severity": max(
                    (value.severity for value in values),
                    key=lambda value: {"HIGH": 3, "MODERATE": 2, "LOW": 1, "UNKNOWN": 0}.get(
                        value, 0
                    ),
                    default="UNKNOWN",
                ),
                "confidence": max(
                    (value.confidence for value in values),
                    key=lambda value: {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}.get(
                        value, 0
                    ),
                    default="UNKNOWN",
                ),
                "validations": _validations(gap_type),
                "limitations": limitations,
            }
        )
    return result


def _signal_type(gap_type: str, status: str) -> str:
    if status in {"CONTRADICTORY", "RESEARCH_REQUIRED"}:
        return "TRADE_OFF" if status == "CONTRADICTORY" else "RESEARCH_REQUIRED"
    return {
        "MISSING_FEATURE": "FEATURE_ADDITION",
        "PRESERVE_ATTRIBUTE": "PRESERVE_STRENGTH",
        "QUALITY_IMPROVEMENT": "QUALITY_IMPROVEMENT",
        "VARIANT_GAP": "VARIANT_EXPANSION",
        "USABILITY_GAP": "USABILITY_IMPROVEMENT",
        "ACCESSORY_GAP": "ACCESSORY_OPPORTUNITY",
    }.get(gap_type, "PRODUCT_IMPROVEMENT")


def create_gap_analysis(
    db: Session, owner: User, context: ReviewContext, review_analysis_id: uuid.UUID
) -> ReviewProductGapAnalysis:
    analysis = db.scalar(
        select(ReviewAnalysis).where(
            ReviewAnalysis.id == review_analysis_id,
            ReviewAnalysis.owner_id == owner.id,
            ReviewAnalysis.context_id == context.id,
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Review analysis not found.")
    if analysis.status != "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail="Only completed review analyses can produce product gap signals.",
        )
    fingerprint = _fingerprint(
        {
            "owner": str(owner.id),
            "context": str(context.id),
            "snapshot": str(analysis.snapshot_id),
            "analysis": str(analysis.id),
            "analysis_version": ANALYSIS_VERSION,
            "calculation_version": CALCULATION_VERSION,
            "rule_version": RULE_VERSION,
        }
    )
    existing = db.scalar(
        select(ReviewProductGapAnalysis).where(
            ReviewProductGapAnalysis.owner_id == owner.id,
            ReviewProductGapAnalysis.context_id == context.id,
            ReviewProductGapAnalysis.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    items = list(
        db.scalars(
            select(ReviewAnalysisItem)
            .where(
                ReviewAnalysisItem.owner_id == owner.id,
                ReviewAnalysisItem.analysis_id == analysis.id,
            )
            .order_by(ReviewAnalysisItem.canonical_label)
        )
    )
    groups = _merge_items(items)
    value = ReviewProductGapAnalysis(
        owner_id=owner.id,
        context_id=context.id,
        snapshot_id=analysis.snapshot_id,
        review_analysis_id=analysis.id,
        product_id=context.product_id,
        product_opportunity_id=context.product_opportunity_id,
        analysis_version=ANALYSIS_VERSION,
        calculation_version=CALCULATION_VERSION,
        rule_version=RULE_VERSION,
        input_fingerprint=fingerprint,
        status="COMPLETED",
        gap_count=len(groups),
        signal_count=len(groups),
        limitations=[
            "signals are review-derived hypotheses and require validation outside "
            "Review Intelligence"
        ],
        created_at=now(),
    )
    db.add(value)
    db.flush()
    for group in groups:
        gap = ReviewProductGap(
            owner_id=owner.id,
            analysis_id=value.id,
            context_id=context.id,
            gap_type=group["gap_type"],
            canonical_label=group["label"],
            hypothesis=_hypothesis(group["gap_type"], group["label"]),
            source_item_types=sorted({item.item_type for item in group["items"]}),
            support_classification=group["support_classification"],
            support_count=group["support"],
            cohort_count=group["cohort"],
            coverage=group["coverage"],
            source_distribution=group["sources"],
            supporting_review_ids=group["reviews"],
            supporting_evidence_ids=group["evidence"],
            opposing_review_ids=group["opposing"],
            severity=group["severity"],
            evidence_strength=group["strength"],
            confidence=group["confidence"],
            freshness=group["freshness"],
            status=group["status"],
            required_validations=group["validations"],
            limitations=group["limitations"],
            rule_version=RULE_VERSION,
            created_at=now(),
        )
        db.add(gap)
        db.flush()
        signal_type = _signal_type(group["gap_type"], group["status"])
        item_types = ", ".join(sorted({item.item_type for item in group["items"]}))
        support_count = group["support"]
        cohort_count = group["cohort"]
        signal = ReviewOpportunitySignal(
            owner_id=owner.id,
            analysis_id=value.id,
            gap_id=gap.id,
            context_id=context.id,
            signal_type=signal_type,
            canonical_label=group["label"],
            hypothesis=gap.hypothesis,
            explanation=(
                f"Derived from 11C {item_types} "
                f"evidence; {support_count} of {cohort_count} eligible reviews "
                "support this signal."
            ),
            status=(
                group["status"]
                if group["status"] != "PARTIALLY_SUPPORTED"
                else "PARTIALLY_SUPPORTED"
            ),
            evidence_strength=group["strength"],
            support_count=group["support"],
            cohort_count=group["cohort"],
            coverage=group["coverage"],
            source_distribution=group["sources"],
            supporting_review_ids=group["reviews"],
            supporting_evidence_ids=group["evidence"],
            opposing_review_ids=group["opposing"],
            confidence=group["confidence"],
            freshness=group["freshness"],
            required_validations=group["validations"],
            limitations=group["limitations"],
            rule_version=RULE_VERSION,
            created_at=now(),
        )
        db.add(signal)
    record_event(
        db,
        actor_id=owner.id,
        action="review.gap_analysis_created",
        entity_type="ReviewProductGapAnalysis",
        entity_id=value.id,
        metadata={
            "context_id": str(context.id),
            "review_analysis_id": str(analysis.id),
            "gap_count": len(groups),
            "signal_count": len(groups),
        },
        idempotency_key=f"review.gap_analysis_created:{value.id}",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ReviewProductGapAnalysis).where(
                ReviewProductGapAnalysis.owner_id == owner.id,
                ReviewProductGapAnalysis.context_id == context.id,
                ReviewProductGapAnalysis.input_fingerprint == fingerprint,
            )
        )
        if existing is None:
            raise
        return existing
    return value


def gap_analysis_detail(
    db: Session, owner: User, context_id: uuid.UUID, analysis_id: uuid.UUID
) -> tuple[ReviewProductGapAnalysis, list[ReviewProductGap], list[ReviewOpportunitySignal]]:
    value = db.scalar(
        select(ReviewProductGapAnalysis).where(
            ReviewProductGapAnalysis.id == analysis_id,
            ReviewProductGapAnalysis.owner_id == owner.id,
            ReviewProductGapAnalysis.context_id == context_id,
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Product gap analysis not found.")
    gaps = list(
        db.scalars(
            select(ReviewProductGap)
            .where(ReviewProductGap.owner_id == owner.id, ReviewProductGap.analysis_id == value.id)
            .order_by(ReviewProductGap.gap_type, ReviewProductGap.canonical_label)
        )
    )
    signals = list(
        db.scalars(
            select(ReviewOpportunitySignal)
            .where(
                ReviewOpportunitySignal.owner_id == owner.id,
                ReviewOpportunitySignal.analysis_id == value.id,
            )
            .order_by(ReviewOpportunitySignal.signal_type, ReviewOpportunitySignal.canonical_label)
        )
    )
    return value, gaps, signals


def current_gap_analysis(
    db: Session, owner: User, context_id: uuid.UUID
) -> ReviewProductGapAnalysis | None:
    _context_or_404(db, owner, context_id)
    return db.scalar(
        select(ReviewProductGapAnalysis)
        .where(
            ReviewProductGapAnalysis.owner_id == owner.id,
            ReviewProductGapAnalysis.context_id == context_id,
        )
        .order_by(ReviewProductGapAnalysis.created_at.desc())
        .limit(1)
    )
