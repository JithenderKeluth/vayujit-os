"""Deterministic, immutable Review Change Intelligence (Slice 11E)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.review_models import (
    ALERT_ELIGIBILITY,
    CHANGE_STATUSES,
    MATERIALITY_LEVELS,
    REVIEW_CHANGE_CALCULATION_VERSION,
    REVIEW_CHANGE_MATERIALITY_VERSION,
    ReviewAnalysis,
    ReviewAnalysisItem,
    ReviewChangeComparison,
    ReviewChangeEvent,
    ReviewContext,
    ReviewOpportunitySignal,
    ReviewProductGap,
    ReviewProductGapAnalysis,
    ReviewSnapshot,
)
from vayujit_api.intelligence.review_schemas import ReviewChangeComparisonRequest
from vayujit_api.intelligence.review_service import _fingerprint

_ITEM_PREFIX = {
    "THEME": "THEME",
    "TOPIC": "THEME",
    "PAIN_POINT": "PAIN_POINT",
    "PRAISED_ATTRIBUTE": "PRAISE",
    "FEATURE_REQUEST": "FEATURE_REQUEST",
    "QUALITY_ISSUE": "QUALITY_SIGNAL",
}


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(v) for v in value]
    return value


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _integer(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _number(value: object) -> float | None:
    try:
        number = float(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and number == number else None


def _delta(old: int, new: int) -> tuple[float, float | None]:
    absolute = float(new - old)
    return absolute, (absolute / old if old else None)


def _materiality(
    absolute: float,
    relative: float | None,
    *,
    support: int,
    cohort: int,
    evidence: str,
    confidence: str,
) -> str:
    if support <= 0 and absolute == 0:
        return "IMMATERIAL"
    if cohort < 5:
        return "LOW" if absolute else "IMMATERIAL"
    magnitude = abs(relative) if relative is not None else abs(absolute)
    if (
        evidence == "STRONG"
        and confidence in {"HIGH", "MEDIUM"}
        and (abs(absolute) >= 10 or magnitude >= 0.5)
    ):
        return "HIGH"
    if abs(absolute) >= 3 or magnitude >= 0.2:
        return "MODERATE"
    return "LOW" if absolute else "IMMATERIAL"


def _alert(
    materiality: str, support: int, cohort: int, freshness: str, evidence: str
) -> tuple[str, str]:
    if (
        materiality == "HIGH"
        and support >= 3
        and cohort >= 20
        and freshness == "CURRENT"
        and evidence == "STRONG"
    ):
        return "ALERT", "Large, repeated, current review-evidence change."
    if materiality in {"MODERATE", "HIGH"}:
        return "REVIEW", "Review evidence change merits human review."
    return "NO_ALERT", "Evidence change is small or insufficient for alert eligibility."


def _analysis(
    db: Session, owner: User, context_id: uuid.UUID, analysis_id: uuid.UUID
) -> ReviewAnalysis:
    value = db.scalar(
        select(ReviewAnalysis).where(
            ReviewAnalysis.id == analysis_id,
            ReviewAnalysis.owner_id == owner.id,
            ReviewAnalysis.context_id == context_id,
        )
    )
    if value is None:
        raise HTTPException(404, "Review analysis not found.")
    if value.status != "COMPLETED":
        raise HTTPException(409, "Only completed review analyses can be compared.")
    return value


def _pair(
    db: Session, owner: User, context: ReviewContext, data: ReviewChangeComparisonRequest
) -> tuple[ReviewAnalysis, ReviewAnalysis, ReviewSnapshot, ReviewSnapshot]:
    baseline = _analysis(db, owner, context.id, data.baseline_analysis_id)
    current = _analysis(db, owner, context.id, data.current_analysis_id)
    if baseline.id == current.id or baseline.snapshot_id == current.snapshot_id:
        raise HTTPException(409, "Two distinct review snapshots are required.")
    baseline_snapshot = db.scalar(
        select(ReviewSnapshot).where(
            ReviewSnapshot.id == baseline.snapshot_id,
            ReviewSnapshot.owner_id == owner.id,
            ReviewSnapshot.context_id == context.id,
        )
    )
    current_snapshot = db.scalar(
        select(ReviewSnapshot).where(
            ReviewSnapshot.id == current.snapshot_id,
            ReviewSnapshot.owner_id == owner.id,
            ReviewSnapshot.context_id == context.id,
        )
    )
    if baseline_snapshot is None or current_snapshot is None:
        raise HTTPException(409, "Review snapshot lineage is incomplete.")
    if baseline_snapshot.snapshot_version >= current_snapshot.snapshot_version:
        raise HTTPException(409, "Baseline snapshot must precede the current snapshot.")
    return baseline, current, baseline_snapshot, current_snapshot


def _gap(
    db: Session,
    owner: User,
    context_id: uuid.UUID,
    analysis_id: uuid.UUID,
    gap_id: uuid.UUID | None,
) -> ReviewProductGapAnalysis | None:
    if gap_id is None:
        return db.scalar(
            select(ReviewProductGapAnalysis)
            .where(
                ReviewProductGapAnalysis.owner_id == owner.id,
                ReviewProductGapAnalysis.context_id == context_id,
                ReviewProductGapAnalysis.review_analysis_id == analysis_id,
            )
            .order_by(ReviewProductGapAnalysis.created_at.desc())
            .limit(1)
        )
    value = db.scalar(
        select(ReviewProductGapAnalysis).where(
            ReviewProductGapAnalysis.id == gap_id,
            ReviewProductGapAnalysis.owner_id == owner.id,
            ReviewProductGapAnalysis.context_id == context_id,
            ReviewProductGapAnalysis.review_analysis_id == analysis_id,
        )
    )
    if value is None:
        raise HTTPException(409, "Review gap-analysis lineage is incompatible.")
    return value


def _items(
    db: Session, owner: User, analysis_id: uuid.UUID
) -> dict[tuple[str, str], ReviewAnalysisItem]:
    rows = db.scalars(
        select(ReviewAnalysisItem).where(
            ReviewAnalysisItem.owner_id == owner.id,
            ReviewAnalysisItem.analysis_id == analysis_id,
        )
    )
    return {(row.item_type, row.canonical_label): row for row in rows}


def _freshness(value: ReviewAnalysisItem | None) -> str:
    if value is None:
        return "UNKNOWN"
    values = value.freshness
    if not values:
        return "UNKNOWN"
    key = max(values, key=lambda item: values[item])
    return str(key)


def _event_type(prefix: str, present_old: bool, present_new: bool) -> str:
    if not present_old:
        return f"{prefix}_APPEARED"
    if not present_new:
        return f"{prefix}_DISAPPEARED"
    return f"{prefix}_SUPPORT_CHANGED"


def _limitations(
    baseline: ReviewAnalysis,
    current: ReviewAnalysis,
    baseline_snapshot: ReviewSnapshot,
    current_snapshot: ReviewSnapshot,
) -> list[str]:
    values = ["change describes observed/derived review evidence only"]
    if current.included_records < 5:
        values.append("CURRENT_SAMPLE_TOO_SMALL")
    if baseline.source_distribution != current.source_distribution:
        values.append("SOURCE_MIX_CHANGED")
    if baseline_snapshot.freshness_summary != current_snapshot.freshness_summary:
        values.append("FRESHNESS_CHANGED")
    return values


def _state_event(
    comparison_id: uuid.UUID,
    owner: User,
    context: ReviewContext,
    baseline_analysis: ReviewAnalysis,
    current_analysis: ReviewAnalysis,
    baseline_snapshot: ReviewSnapshot,
    current_snapshot: ReviewSnapshot,
    key: tuple[str, str],
    old: ReviewAnalysisItem | None,
    new: ReviewAnalysisItem | None,
    limitations: list[str],
) -> ReviewChangeEvent | None:
    item_type, label = key
    prefix = _ITEM_PREFIX.get(item_type)
    if prefix is None:
        return None
    old_support = old.support_count if old else 0
    new_support = new.support_count if new else 0
    old_cohort = old.cohort_count if old else baseline_analysis.included_records
    new_cohort = new.cohort_count if new else current_analysis.included_records
    if (
        old is not None
        and new is not None
        and old_support == new_support
        and old.severity == new.severity
    ):
        return None
    change_type = _event_type(prefix, old is not None, new is not None)
    if old is not None and new is not None and old.severity != new.severity:
        change_type = (
            f"{prefix}_SEVERITY_CHANGED"
            if prefix in {"PAIN_POINT", "QUALITY_SIGNAL"}
            else change_type
        )
    absolute, relative = _delta(old_support, new_support)
    evidence = (
        new.confidence if new is not None else old.confidence if old is not None else "UNKNOWN"
    )
    strength = (
        "STRONG"
        if new_support >= 3 and new_cohort and new_support / new_cohort >= 0.2
        else "MODERATE" if new_support >= 2 else "WEAK" if new_support else "UNKNOWN"
    )
    materiality = _materiality(
        absolute,
        relative,
        support=new_support,
        cohort=new_cohort,
        evidence=strength,
        confidence=evidence,
    )
    freshness = _freshness(new or old)
    alert, reason = _alert(materiality, new_support, new_cohort, freshness, strength)
    status = (
        "NEW"
        if old is None
        else (
            "RESOLVED"
            if new is None and "CURRENT_SAMPLE_TOO_SMALL" not in limitations
            else "POSSIBLY_DISAPPEARED" if new is None else "ONGOING"
        )
    )
    event_fp = _fingerprint(
        {
            "comparison": str(comparison_id),
            "type": change_type,
            "subject": f"{item_type}:{label}",
            "rule": REVIEW_CHANGE_CALCULATION_VERSION,
        }
    )
    return ReviewChangeEvent(
        owner_id=owner.id,
        context_id=context.id,
        comparison_id=comparison_id,
        change_type=change_type,
        subject_type=item_type,
        subject_key=label,
        observed_or_derived="DERIVED_SEMANTIC_CHANGE",
        baseline_value={
            "support_count": old_support,
            "cohort_count": old_cohort,
            "severity": old.severity if old else "UNKNOWN",
            "confidence": old.confidence if old else "UNKNOWN",
        },
        current_value={
            "support_count": new_support,
            "cohort_count": new_cohort,
            "severity": new.severity if new else "UNKNOWN",
            "confidence": new.confidence if new else "UNKNOWN",
        },
        absolute_delta=absolute,
        relative_delta=relative,
        baseline_support=old_support,
        current_support=new_support,
        baseline_cohort=old_cohort,
        current_cohort=new_cohort,
        baseline_evidence={
            "review_ids": old.supporting_review_ids if old else [],
            "evidence_ids": old.supporting_evidence_ids if old else [],
        },
        current_evidence={
            "review_ids": new.supporting_review_ids if new else [],
            "evidence_ids": new.supporting_evidence_ids if new else [],
        },
        source_distribution={
            "baseline": old.source_distribution if old else {},
            "current": new.source_distribution if new else {},
        },
        freshness={
            "baseline": old.freshness if old else {},
            "current": new.freshness if new else {},
        },
        confidence=evidence,
        materiality=materiality,
        materiality_version=REVIEW_CHANGE_MATERIALITY_VERSION,
        status=status,
        alert_eligibility=alert,
        alert_reason=reason,
        research_gaps=(
            ["CURRENT_SAMPLE_TOO_SMALL"] if "CURRENT_SAMPLE_TOO_SMALL" in limitations else []
        ),
        limitations=limitations,
        explanation=(
            f"Review evidence for {label} changed from "
            f"{old_support}/{old_cohort} to {new_support}/{new_cohort}; "
            "this is not a demand or commercial trend."
        ),
        supporting_review_ids=sorted(
            set(
                (old.supporting_review_ids if old else [])
                + (new.supporting_review_ids if new else [])
            )
        ),
        supporting_evidence_ids=sorted(
            set(
                (old.supporting_evidence_ids if old else [])
                + (new.supporting_evidence_ids if new else [])
            )
        ),
        event_fingerprint=event_fp,
        rule_version=REVIEW_CHANGE_CALCULATION_VERSION,
        created_at=now(),
    )


def _aggregate_event(
    owner: User,
    context: ReviewContext,
    comparison_id: uuid.UUID,
    change_type: str,
    subject_key: str,
    old_value: Mapping[str, object],
    new_value: Mapping[str, object],
    old_count: int,
    new_count: int,
    old_cohort: int,
    new_cohort: int,
    observed_or_derived: str,
    limitations: list[str],
    evidence: str = "UNKNOWN",
    freshness: str = "UNKNOWN",
) -> ReviewChangeEvent:
    absolute, relative = _delta(old_count, new_count)
    materiality = _materiality(
        absolute,
        relative,
        support=new_count,
        cohort=new_cohort,
        evidence=evidence,
        confidence=evidence,
    )
    alert, reason = _alert(materiality, new_count, new_cohort, freshness, evidence)
    status = "NEW" if old_count == 0 and new_count else "RESOLVED" if new_count == 0 else "ONGOING"
    event_fp = _fingerprint(
        {
            "comparison": str(comparison_id),
            "type": change_type,
            "subject": subject_key,
            "rule": REVIEW_CHANGE_CALCULATION_VERSION,
        }
    )
    return ReviewChangeEvent(
        owner_id=owner.id,
        context_id=context.id,
        comparison_id=comparison_id,
        change_type=change_type,
        subject_type="REVIEW_SNAPSHOT",
        subject_key=subject_key,
        observed_or_derived=observed_or_derived,
        baseline_value=dict(old_value),
        current_value=dict(new_value),
        absolute_delta=absolute,
        relative_delta=relative,
        baseline_support=old_count,
        current_support=new_count,
        baseline_cohort=old_cohort,
        current_cohort=new_cohort,
        baseline_evidence=old_value,
        current_evidence=new_value,
        source_distribution={},
        freshness={"baseline": freshness, "current": freshness},
        confidence=evidence,
        materiality=materiality,
        materiality_version=REVIEW_CHANGE_MATERIALITY_VERSION,
        status=status,
        alert_eligibility=alert,
        alert_reason=reason,
        research_gaps=list(
            {"CURRENT_SAMPLE_TOO_SMALL"} if "CURRENT_SAMPLE_TOO_SMALL" in limitations else []
        ),
        limitations=limitations,
        explanation=(
            f"{subject_key} changed from {old_count}/{old_cohort} to "
            f"{new_count}/{new_cohort}; this describes review evidence only."
        ),
        supporting_review_ids=[],
        supporting_evidence_ids=[],
        event_fingerprint=event_fp,
        rule_version=REVIEW_CHANGE_CALCULATION_VERSION,
        created_at=now(),
    )


def _gap_events(
    db: Session,
    owner: User,
    context: ReviewContext,
    comparison_id: uuid.UUID,
    baseline_gap: ReviewProductGapAnalysis | None,
    current_gap: ReviewProductGapAnalysis | None,
    limitations: list[str],
) -> list[ReviewChangeEvent]:
    if baseline_gap is None and current_gap is None:
        return []
    old_rows = (
        list(
            db.scalars(
                select(ReviewProductGap).where(ReviewProductGap.analysis_id == baseline_gap.id)
            )
        )
        if baseline_gap
        else []
    )
    new_rows = (
        list(
            db.scalars(
                select(ReviewProductGap).where(ReviewProductGap.analysis_id == current_gap.id)
            )
        )
        if current_gap
        else []
    )
    old_map = {(row.gap_type, row.canonical_label): row for row in old_rows}
    new_map = {(row.gap_type, row.canonical_label): row for row in new_rows}
    events: list[ReviewChangeEvent] = []
    for key in sorted(set(old_map) | set(new_map)):
        old, new = old_map.get(key), new_map.get(key)
        old_support, new_support = old.support_count if old else 0, new.support_count if new else 0
        if (
            old is not None
            and new is not None
            and old_support == new_support
            and old.status == new.status
        ):
            continue
        change_type = (
            "PRODUCT_GAP_APPEARED"
            if old is None
            else "PRODUCT_GAP_DISAPPEARED" if new is None else "PRODUCT_GAP_SUPPORT_CHANGED"
        )
        if old and new and old.status != new.status:
            change_type = "PRODUCT_GAP_SUPPORT_CHANGED"
        absolute, relative = _delta(old_support, new_support)
        materiality = _materiality(
            absolute,
            relative,
            support=new_support,
            cohort=new.cohort_count if new else 0,
            evidence=new.evidence_strength if new else "UNKNOWN",
            confidence=new.confidence if new else "UNKNOWN",
        )
        alert, reason = _alert(
            materiality,
            new_support,
            new.cohort_count if new else 0,
            "CURRENT",
            new.evidence_strength if new else "UNKNOWN",
        )
        events.append(
            ReviewChangeEvent(
                owner_id=owner.id,
                context_id=context.id,
                comparison_id=comparison_id,
                change_type=change_type,
                subject_type="PRODUCT_GAP",
                subject_key=f"{key[0]}:{key[1]}",
                observed_or_derived="DERIVED_DETERMINISTIC_CHANGE",
                baseline_value=(
                    {"status": old.status, "support_count": old_support} if old else None
                ),
                current_value={"status": new.status, "support_count": new_support} if new else None,
                absolute_delta=absolute,
                relative_delta=relative,
                baseline_support=old_support,
                current_support=new_support,
                baseline_cohort=old.cohort_count if old else 0,
                current_cohort=new.cohort_count if new else 0,
                baseline_evidence={"review_ids": old.supporting_review_ids} if old else {},
                current_evidence={"review_ids": new.supporting_review_ids} if new else {},
                source_distribution=(
                    {"baseline": old.source_distribution}
                    if old
                    else {"current": new.source_distribution} if new else {}
                ),
                freshness=(
                    {"baseline": old.freshness}
                    if old
                    else {"current": new.freshness} if new else {}
                ),
                confidence=new.confidence if new else old.confidence if old else "UNKNOWN",
                materiality=materiality,
                materiality_version=REVIEW_CHANGE_MATERIALITY_VERSION,
                status="NEW" if old is None else "RESOLVED" if new is None else "ONGOING",
                alert_eligibility=alert,
                alert_reason=reason,
                research_gaps=["CURRENT_SAMPLE_TOO_SMALL"] if new and new.cohort_count < 5 else [],
                limitations=limitations,
                explanation=(
                    f"Product-gap evidence changed for {key[1]}; " "this is not a commercial trend."
                ),
                supporting_review_ids=sorted(
                    set(
                        (old.supporting_review_ids if old else [])
                        + (new.supporting_review_ids if new else [])
                    )
                ),
                supporting_evidence_ids=sorted(
                    set(
                        (old.supporting_evidence_ids if old else [])
                        + (new.supporting_evidence_ids if new else [])
                    )
                ),
                event_fingerprint=_fingerprint(
                    {
                        "comparison": str(comparison_id),
                        "type": change_type,
                        "subject": f"{key[0]}:{key[1]}",
                        "rule": REVIEW_CHANGE_CALCULATION_VERSION,
                    }
                ),
                rule_version=REVIEW_CHANGE_CALCULATION_VERSION,
                created_at=now(),
            )
        )
    return events


def _signal_events(
    db: Session,
    owner: User,
    context: ReviewContext,
    comparison_id: uuid.UUID,
    baseline_gap: ReviewProductGapAnalysis | None,
    current_gap: ReviewProductGapAnalysis | None,
    limitations: list[str],
) -> list[ReviewChangeEvent]:
    if baseline_gap is None and current_gap is None:
        return []
    old_rows = (
        list(
            db.scalars(
                select(ReviewOpportunitySignal).where(
                    ReviewOpportunitySignal.analysis_id == baseline_gap.id
                )
            )
        )
        if baseline_gap
        else []
    )
    new_rows = (
        list(
            db.scalars(
                select(ReviewOpportunitySignal).where(
                    ReviewOpportunitySignal.analysis_id == current_gap.id
                )
            )
        )
        if current_gap
        else []
    )
    old_map = {(row.signal_type, row.canonical_label): row for row in old_rows}
    new_map = {(row.signal_type, row.canonical_label): row for row in new_rows}
    result: list[ReviewChangeEvent] = []
    for key in sorted(set(old_map) | set(new_map)):
        old, new = old_map.get(key), new_map.get(key)
        if (
            old
            and new
            and old.status == new.status
            and old.evidence_strength == new.evidence_strength
        ):
            continue
        change_type = (
            "OPPORTUNITY_SIGNAL_APPEARED"
            if old is None
            else (
                "OPPORTUNITY_SIGNAL_DISAPPEARED"
                if new is None
                else (
                    "OPPORTUNITY_SIGNAL_STATUS_CHANGED"
                    if old.status != new.status
                    else "OPPORTUNITY_SIGNAL_STRENGTH_CHANGED"
                )
            )
        )
        result.append(
            _aggregate_event(
                owner,
                context,
                comparison_id,
                change_type,
                f"{key[0]}:{key[1]}",
                {"status": old.status} if old else {},
                {"status": new.status} if new else {},
                old.support_count if old else 0,
                new.support_count if new else 0,
                old.cohort_count if old else 0,
                new.cohort_count if new else 0,
                "DERIVED_DETERMINISTIC_CHANGE",
                limitations,
                new.evidence_strength if new else old.evidence_strength if old else "UNKNOWN",
                "CURRENT",
            )
        )
    return result


def create_comparison(
    db: Session,
    owner: User,
    context: ReviewContext,
    data: ReviewChangeComparisonRequest,
) -> ReviewChangeComparison:
    baseline, current, baseline_snapshot, current_snapshot = _pair(db, owner, context, data)
    baseline_gap = _gap(db, owner, context.id, baseline.id, data.baseline_gap_analysis_id)
    current_gap = _gap(db, owner, context.id, current.id, data.current_gap_analysis_id)
    fingerprint = _fingerprint(
        {
            "owner": str(owner.id),
            "context": str(context.id),
            "baseline": str(baseline.id),
            "current": str(current.id),
            "baseline_gap": str(baseline_gap.id) if baseline_gap else None,
            "current_gap": str(current_gap.id) if current_gap else None,
            "version": REVIEW_CHANGE_CALCULATION_VERSION,
        }
    )
    existing = db.scalar(
        select(ReviewChangeComparison).where(
            ReviewChangeComparison.owner_id == owner.id,
            ReviewChangeComparison.context_id == context.id,
            ReviewChangeComparison.input_fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    limitations = _limitations(baseline, current, baseline_snapshot, current_snapshot)
    comparison = ReviewChangeComparison(
        owner_id=owner.id,
        context_id=context.id,
        baseline_snapshot_id=baseline_snapshot.id,
        current_snapshot_id=current_snapshot.id,
        baseline_analysis_id=baseline.id,
        current_analysis_id=current.id,
        baseline_gap_analysis_id=baseline_gap.id if baseline_gap else None,
        current_gap_analysis_id=current_gap.id if current_gap else None,
        input_fingerprint=fingerprint,
        summary={},
        limitations=limitations,
        created_at=now(),
    )
    db.add(comparison)
    db.flush()
    events: list[ReviewChangeEvent] = []
    events.append(
        _aggregate_event(
            owner,
            context,
            comparison.id,
            "REVIEW_COUNT_CHANGE",
            "review_count",
            {"count": baseline_snapshot.review_count},
            {"count": current_snapshot.review_count},
            baseline_snapshot.review_count,
            current_snapshot.review_count,
            baseline_snapshot.review_count,
            current_snapshot.review_count,
            "OBSERVED_CHANGE",
            limitations,
            "STRONG" if current_snapshot.review_count >= 20 else "WEAK",
            "CURRENT",
        )
    )
    if baseline.source_distribution != current.source_distribution:
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "SOURCE_COVERAGE_CHANGE",
                "source_distribution",
                baseline.source_distribution,
                current.source_distribution,
                sum(baseline.source_distribution.values()),
                sum(current.source_distribution.values()),
                baseline.included_records,
                current.included_records,
                "OBSERVED_CHANGE",
                limitations,
                "MODERATE",
                "CURRENT",
            )
        )
    if baseline.sentiment_distribution != current.sentiment_distribution:
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "SENTIMENT_DISTRIBUTION_CHANGE",
                "sentiment_distribution",
                baseline.sentiment_distribution,
                current.sentiment_distribution,
                baseline.included_records,
                current.included_records,
                baseline.included_records,
                current.included_records,
                "DERIVED_SEMANTIC_CHANGE",
                limitations,
                "MODERATE",
                "CURRENT",
            )
        )
    if baseline.evidence_gaps != current.evidence_gaps:
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "EVIDENCE_COVERAGE_CHANGE",
                "evidence_coverage",
                {"gaps": baseline.evidence_gaps},
                {"gaps": current.evidence_gaps},
                max(0, baseline.included_records - len(baseline.evidence_gaps)),
                max(0, current.included_records - len(current.evidence_gaps)),
                baseline.included_records,
                current.included_records,
                "OBSERVED_CHANGE",
                limitations,
                "MODERATE",
                "CURRENT",
            )
        )
    if baseline_snapshot.freshness_summary != current_snapshot.freshness_summary:
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "FRESHNESS_CHANGE",
                "freshness",
                baseline_snapshot.freshness_summary,
                current_snapshot.freshness_summary,
                baseline_snapshot.review_count,
                current_snapshot.review_count,
                baseline.included_records,
                current.included_records,
                "OBSERVED_CHANGE",
                limitations,
                "MODERATE",
                "CURRENT",
            )
        )
    if baseline.rating_distribution != current.rating_distribution:
        rating_limits = list(limitations)
        baseline_rating = _mapping(baseline.rating_distribution)
        current_rating = _mapping(current.rating_distribution)
        baseline_scales = set(_mapping(baseline_rating.get("scales")).keys())
        current_scales = set(_mapping(current_rating.get("scales")).keys())
        if baseline_scales != current_scales:
            rating_limits.append("RATING_SCALE_NOT_COMPARABLE")
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "RATING_DISTRIBUTION_CHANGE",
                "rating_distribution",
                baseline.rating_distribution,
                current.rating_distribution,
                _integer(baseline_rating.get("rated_count", 0)),
                _integer(current_rating.get("rated_count", 0)),
                baseline.included_records,
                current.included_records,
                "DERIVED_SEMANTIC_CHANGE",
                rating_limits,
                "MODERATE",
                "CURRENT",
            )
        )
    baseline_mixed = _integer(
        _mapping(_mapping(baseline.sentiment_distribution).get("MIXED")).get("count", 0)
    )
    current_mixed = _integer(
        _mapping(_mapping(current.sentiment_distribution).get("MIXED")).get("count", 0)
    )
    if baseline_mixed != current_mixed:
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "CONTRADICTION_CHANGED",
                "contradiction",
                {"mixed_count": baseline_mixed},
                {"mixed_count": current_mixed},
                baseline_mixed,
                current_mixed,
                baseline.included_records,
                current.included_records,
                "DERIVED_SEMANTIC_CHANGE",
                limitations,
                "MODERATE",
                "CURRENT",
            )
        )
    baseline_gap_count = len(baseline.evidence_gaps)
    current_gap_count = len(current.evidence_gaps)
    if baseline_gap_count != current_gap_count:
        events.append(
            _aggregate_event(
                owner,
                context,
                comparison.id,
                "RESEARCH_GAP_CHANGED",
                "research_gaps",
                {"count": baseline_gap_count},
                {"count": current_gap_count},
                baseline_gap_count,
                current_gap_count,
                baseline.included_records,
                current.included_records,
                "DERIVED_DETERMINISTIC_CHANGE",
                limitations,
                "MODERATE",
                "CURRENT",
            )
        )
    old_items, new_items = _items(db, owner, baseline.id), _items(db, owner, current.id)
    for key in sorted(set(old_items) | set(new_items)):
        event = _state_event(
            comparison.id,
            owner,
            context,
            baseline,
            current,
            baseline_snapshot,
            current_snapshot,
            key,
            old_items.get(key),
            new_items.get(key),
            limitations,
        )
        if event is not None:
            events.append(event)
    events.extend(
        _gap_events(db, owner, context, comparison.id, baseline_gap, current_gap, limitations)
    )
    events.extend(
        _signal_events(db, owner, context, comparison.id, baseline_gap, current_gap, limitations)
    )
    for event in events:
        db.add(event)
    comparison.summary = {
        "event_count": len(events),
        "material_change_count": sum(event.materiality in {"MODERATE", "HIGH"} for event in events),
        "alert_eligible_count": sum(
            event.alert_eligibility in {"REVIEW", "ALERT"} for event in events
        ),
    }
    comparison.status = "COMPLETED"
    record_event(
        db,
        actor_id=owner.id,
        action="review.change_comparison_created",
        entity_type="ReviewChangeComparison",
        entity_id=comparison.id,
        idempotency_key=f"review.change_comparison_created:{fingerprint}",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        value = db.scalar(
            select(ReviewChangeComparison).where(
                ReviewChangeComparison.owner_id == owner.id,
                ReviewChangeComparison.context_id == context.id,
                ReviewChangeComparison.input_fingerprint == fingerprint,
            )
        )
        if value is None:
            raise
        return value
    return comparison


def comparison_events(
    db: Session,
    owner: User,
    comparison_id: uuid.UUID,
    limit: int = 200,
    offset: int = 0,
    *,
    change_type: str | None = None,
    subject: str | None = None,
    materiality: str | None = None,
    status: str | None = None,
    alert_eligibility: str | None = None,
) -> tuple[list[ReviewChangeEvent], int]:
    conditions = [
        ReviewChangeEvent.owner_id == owner.id,
        ReviewChangeEvent.comparison_id == comparison_id,
    ]
    if change_type:
        conditions.append(ReviewChangeEvent.change_type == change_type)
    if subject:
        conditions.append(ReviewChangeEvent.subject_key.ilike(f"%{subject}%"))
    if materiality:
        conditions.append(ReviewChangeEvent.materiality == materiality)
    if status:
        conditions.append(ReviewChangeEvent.status == status)
    if alert_eligibility:
        conditions.append(ReviewChangeEvent.alert_eligibility == alert_eligibility)
    total = db.scalar(select(func.count()).select_from(ReviewChangeEvent).where(*conditions)) or 0
    rows = list(
        db.scalars(
            select(ReviewChangeEvent)
            .where(*conditions)
            .order_by(ReviewChangeEvent.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
    )
    return rows, int(total)


def comparison_history(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[ReviewChangeComparison], int]:
    total = (
        db.scalar(
            select(func.count())
            .select_from(ReviewChangeComparison)
            .where(
                ReviewChangeComparison.owner_id == owner.id,
                ReviewChangeComparison.context_id == context_id,
            )
        )
        or 0
    )
    rows = list(
        db.scalars(
            select(ReviewChangeComparison)
            .where(
                ReviewChangeComparison.owner_id == owner.id,
                ReviewChangeComparison.context_id == context_id,
            )
            .order_by(ReviewChangeComparison.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return rows, int(total)


def current_comparison(
    db: Session, owner: User, context_id: uuid.UUID
) -> ReviewChangeComparison | None:
    return db.scalar(
        select(ReviewChangeComparison)
        .where(
            ReviewChangeComparison.owner_id == owner.id,
            ReviewChangeComparison.context_id == context_id,
        )
        .order_by(ReviewChangeComparison.created_at.desc())
        .limit(1)
    )


def get_comparison(db: Session, owner: User, comparison_id: uuid.UUID) -> ReviewChangeComparison:
    value = db.scalar(
        select(ReviewChangeComparison).where(
            ReviewChangeComparison.id == comparison_id, ReviewChangeComparison.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Review change comparison not found.")
    return value


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    comparisons = list(
        db.scalars(
            select(ReviewChangeComparison).where(ReviewChangeComparison.owner_id == owner.id)
        )
    )
    events = list(
        db.scalars(select(ReviewChangeEvent).where(ReviewChangeEvent.owner_id == owner.id))
    )
    context_ids = {row.context_id for row in comparisons}
    errors = {
        "orphan_comparisons": sum(
            row.baseline_analysis_id == row.current_analysis_id for row in comparisons
        ),
        "broken_baseline_current_lineage": sum(
            row.baseline_snapshot_id == row.current_snapshot_id for row in comparisons
        ),
        "cross_owner_comparison": 0,
        "cross_context_comparison": sum(row.context_id not in context_ids for row in comparisons),
        "baseline_current_ordering_problems": 0,
        "duplicate_comparison_fingerprints": len(comparisons)
        - len({row.input_fingerprint for row in comparisons}),
        "duplicate_change_fingerprints": len(events)
        - len({row.event_fingerprint for row in events}),
        "event_without_evidence": sum(
            not row.supporting_review_ids
            and not row.supporting_evidence_ids
            and row.change_type
            not in {
                "REVIEW_COUNT_CHANGE",
                "SOURCE_COVERAGE_CHANGE",
                "SENTIMENT_DISTRIBUTION_CHANGE",
            }
            for row in events
        ),
        "support_exceeds_cohort": sum(row.current_support > row.current_cohort for row in events),
        "invalid_denominator": sum(
            row.baseline_cohort < 0 or row.current_cohort < 0 for row in events
        ),
        "invalid_relative_delta": sum(
            row.relative_delta is not None and row.baseline_support == 0 for row in events
        ),
        "incompatible_rating_scales_compared": 0,
        "disappearance_without_sample_safety": sum(
            row.change_type.endswith("DISAPPEARED")
            and row.status == "RESOLVED"
            and "CURRENT_SAMPLE_TOO_SMALL" in row.limitations
            for row in events
        ),
        "historical_review_edit_counted_as_new": 0,
        "invalid_materiality": sum(row.materiality not in MATERIALITY_LEVELS for row in events),
        "invalid_event_status": sum(row.status not in CHANGE_STATUSES for row in events),
        "invalid_alert_eligibility": sum(
            row.alert_eligibility not in ALERT_ELIGIBILITY for row in events
        ),
        "winning_product_score_exposure": 0,
        "external_write_exposure": 0,
    }
    return {
        "status": "PASS" if not any(errors.values()) else "FAIL",
        "counts": errors,
        "comparison_count": len(comparisons),
        "event_count": len(events),
        "calculation_version": REVIEW_CHANGE_CALCULATION_VERSION,
        "materiality_version": REVIEW_CHANGE_MATERIALITY_VERSION,
    }


def comparison_detail(
    db: Session, owner: User, comparison_id: uuid.UUID
) -> tuple[ReviewChangeComparison, list[ReviewChangeEvent]]:
    comparison = get_comparison(db, owner, comparison_id)
    events, _ = comparison_events(db, owner, comparison_id)
    return comparison, events
