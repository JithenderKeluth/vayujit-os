"""Deterministic Trend 12E validation, confidence, and contradiction services."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from itertools import combinations
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.models import IntelligenceEvidence, IntelligenceSource
from vayujit_api.intelligence.trend_analysis_models import TrendAnalysis, TrendAnalysisSeries
from vayujit_api.intelligence.trend_change_models import TrendChangeComparison, TrendChangeEvent
from vayujit_api.intelligence.trend_models import TrendContext, TrendObservation, TrendSnapshot
from vayujit_api.intelligence.trend_service import _now
from vayujit_api.intelligence.trend_validation_models import (
    AGREEMENT_STATES,
    CONFIDENCE_STATES,
    CONTRADICTION_TYPES,
    READINESS_STATES,
    TrendValidation,
    TrendValidationContradiction,
    TrendValidationGap,
    TrendValidationHypothesis,
)
from vayujit_api.intelligence.trend_validation_schemas import TrendValidationCreate

CALCULATION_VERSION = "trend-validation-v1"
NO_COMMERCIAL_SYNTHESIS = (
    "Evidence confidence describes support and completeness of observed Trend evidence; "
    "it is not a probability of product success, demand, sales, revenue, market size, or "
    "commercial attractiveness."
)
SEVERE_CONTRADICTION = {"HIGH", "BLOCKING"}


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _source_identity(source: Any) -> str:
    metadata = source.metadata_json if isinstance(source.metadata_json, dict) else {}
    for key in ("canonical_provider_id", "provider_identity", "parent_source_id"):
        if metadata.get(key):
            return str(metadata[key])
    if source.provider:
        return str(source.provider).strip().lower()
    return str(source.id)


def _comparable(left: TrendAnalysisSeries, right: TrendAnalysisSeries) -> bool:
    return all(
        getattr(left, field) == getattr(right, field)
        for field in (
            "signal_definition_id",
            "measurement_type",
            "unit",
            "scale",
            "geography_scope",
            "country",
            "region",
            "city",
            "marketplace",
            "granularity",
        )
    )


def _direction_hypothesis(series: TrendAnalysisSeries) -> str:
    if series.variability_state == "HIGH_VARIABILITY":
        return "HIGH_VARIABILITY"
    if series.persistence == "PERSISTENT_INCREASE":
        return "SUSTAINED_INCREASE"
    if series.persistence == "PERSISTENT_DECREASE":
        return "SUSTAINED_DECREASE"
    if series.persistence == "REVERSING":
        return "REVERSING"
    if series.direction == "INCREASING":
        return "OBSERVED_SIGNAL_INCREASING"
    if series.direction == "DECREASING":
        return "OBSERVED_SIGNAL_DECREASING"
    if series.direction == "STABLE":
        return "OBSERVED_SIGNAL_STABLE"
    return "EVIDENCE_WEAKENING" if series.sample_size else "OBSERVED_SIGNAL_STABLE"


def _freshness(
    rows: list[TrendObservation], series: list[TrendAnalysisSeries]
) -> tuple[str, dict[str, int]]:
    values = [row.freshness_state for row in rows] or [item.freshness_state for item in series]
    counts = Counter(values)
    if not values or set(values) == {"UNKNOWN"}:
        state = "UNKNOWN"
    elif set(values) == {"CURRENT"}:
        state = "CURRENT"
    elif set(values) == {"STALE"}:
        state = "STALE"
    else:
        state = "MIXED"
    return state, {key.lower(): int(counts.get(key, 0)) for key in ("CURRENT", "STALE", "UNKNOWN")}


def _agreement(
    series: list[TrendAnalysisSeries], source_identity: dict[uuid.UUID, str]
) -> tuple[str, dict[str, object], list[tuple[TrendAnalysisSeries, TrendAnalysisSeries]]]:
    if not series:
        return "INSUFFICIENT_EVIDENCE", {"comparable": False, "known_direction_count": 0}, []
    pairs = list(combinations(series, 2))
    comparable_pairs = [(left, right) for left, right in pairs if _comparable(left, right)]
    if (
        len(series) < 2
        or len({source_identity.get(item.source_id, str(item.source_id)) for item in series}) < 2
    ):
        return (
            "INSUFFICIENT_EVIDENCE",
            {"comparable": True, "known_direction_count": 1},
            comparable_pairs,
        )
    if not comparable_pairs:
        return "NOT_COMPARABLE", {"comparable": False, "known_direction_count": 0}, []
    directions = [
        item.direction
        for item in series
        if item.direction in {"INCREASING", "DECREASING", "STABLE"}
    ]
    if len(directions) < 2:
        return (
            "UNKNOWN",
            {"comparable": True, "known_direction_count": len(directions)},
            comparable_pairs,
        )
    counts = Counter(directions)
    if len(counts) == 1:
        state = "AGREE"
    elif (
        len(counts) == 2
        and sum(counts.values()) >= 2
        and max(counts.values()) / len(directions) >= 0.66
    ):
        state = "MOSTLY_AGREE"
    elif {"INCREASING", "DECREASING"} <= set(counts):
        state = "DISAGREE"
    else:
        state = "MIXED"
    return (
        state,
        {
            "comparable": True,
            "known_direction_count": len(directions),
            "direction_counts": dict(counts),
            "comparable_pair_count": len(comparable_pairs),
        },
        comparable_pairs,
    )


def _coverage(
    rows: list[TrendObservation],
    series: list[TrendAnalysisSeries],
    sources: list[IntelligenceSource],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    source_ids = {str(item.source_id) for item in series}
    providers = {_source_identity(item) for item in sources}
    source_types = {item.source_type for item in sources}
    freshness_state, freshness_counts = _freshness(rows, series)
    periods = {(row.period_start or row.period_end or row.observed_at).isoformat() for row in rows}
    missing: list[str] = sorted(
        str(value)
        for item in series
        for value in cast(list[Any], item.missing_periods or [])
        if value is not None
    )
    quality_counts = Counter(row.quality_state for row in rows)
    complete_lineage = sum(
        bool(row.source_id and row.signal_definition_id and row.evidence_id) for row in rows
    )
    total = len(rows)
    evidence_coverage = {
        "observation_count": total,
        "period_count": len(periods),
        "source_count": len(source_ids),
        "independent_source_count": len(providers),
        "quality_counts": dict(quality_counts),
        "lineage_complete_count": complete_lineage,
        "lineage_completeness": (complete_lineage / total if total else 0),
        "denominator": "accepted observations in the authoritative snapshot",
    }
    source_coverage = {
        "source_count": len(source_ids),
        "independent_source_count": len(providers),
        "source_type_count": len(source_types),
        "diversity": (
            "single provider"
            if len(providers) <= 1
            else "multiple providers" if len(source_types) <= 1 else "multiple source types"
        ),
        "source_ids": sorted(source_ids),
    }
    all_missing = sorted(set(missing))
    ratios = [float(item.coverage_ratio) for item in series if item.coverage_ratio is not None]
    time_coverage = {
        "history_length": len(periods),
        "covered_periods": len(periods),
        "missing_period_count": len(all_missing),
        "missing_periods": all_missing,
        "coverage_ratio": min(ratios) if ratios else (1.0 if periods else 0.0),
        "baseline_current_coverage": bool(len(periods) >= 2),
        "time_window_start": (
            cast(
                Any, min((item.time_start for item in series if item.time_start), default=None)
            ).isoformat()
            if any(item.time_start for item in series)
            else None
        ),
        "time_window_end": (
            cast(
                Any, max((item.time_end for item in series if item.time_end), default=None)
            ).isoformat()
            if any(item.time_end for item in series)
            else None
        ),
    }
    freshness = {"state": freshness_state, **freshness_counts}
    gaps: list[str] = []
    if not rows:
        gaps.append("NO_OBSERVATIONS")
    if len(periods) < 2:
        gaps.append("INSUFFICIENT_HISTORY")
    if len(providers) <= 1:
        gaps.append("SINGLE_SOURCE_ONLY")
    if len(providers) < 2:
        gaps.append("INSUFFICIENT_INDEPENDENT_SOURCES")
    if all_missing:
        gaps.append("MISSING_PERIODS")
    if freshness_state == "STALE":
        gaps.append("STALE_EVIDENCE")
    if freshness_state == "UNKNOWN":
        gaps.append("UNKNOWN_FRESHNESS")
    if total and quality_counts.get("INVALID", 0):
        gaps.append("INSUFFICIENT_QUALITY")
    if total and complete_lineage < total:
        gaps.append("BROKEN_LINEAGE")
    return evidence_coverage, source_coverage, time_coverage, freshness, gaps


def _confidence(
    evidence: dict[str, Any],
    source: dict[str, Any],
    time: dict[str, Any],
    freshness: dict[str, Any],
    agreement: str,
    contradiction_count: int,
    blocking_contradiction: bool = False,
) -> str:
    score = 0
    observation_count = int(evidence.get("observation_count", 0))
    periods = int(time.get("covered_periods", 0))
    independent = int(source.get("independent_source_count", 0))
    coverage = float(time.get("coverage_ratio", 0) or 0)
    lineage = float(evidence.get("lineage_completeness", 0) or 0)
    if observation_count >= 2:
        score += 2
    if periods >= 3:
        score += 2
    elif periods >= 2:
        score += 1
    if independent >= 2:
        score += 2
    if coverage >= 0.8:
        score += 2
    elif coverage >= 0.5:
        score += 1
    if lineage >= 1:
        score += 1
    if agreement == "AGREE":
        score += 1
    elif agreement == "MOSTLY_AGREE":
        score += 0
    elif agreement in {"DISAGREE", "MIXED"}:
        score -= 2
    elif agreement == "NOT_COMPARABLE":
        score -= 1
    if freshness.get("state") == "CURRENT":
        score += 1
    elif freshness.get("state") == "MIXED":
        score -= 1
    elif freshness.get("state") in {"STALE", "UNKNOWN"}:
        score -= 2
    if evidence.get("quality_counts", {}).get("INVALID", 0):
        score -= 2
    if contradiction_count:
        score -= 3 if blocking_contradiction else 1
    if score >= 8:
        return "HIGH"
    if score >= 4:
        return "MODERATE"
    if score >= 1:
        return "LOW"
    return "UNKNOWN"


def _readiness(status: str, confidence: str, gaps: list[str], blocking_contradiction: bool) -> str:
    if status == "CONTRADICTORY" or blocking_contradiction:
        return "CONTRADICTORY"
    if status == "STALE":
        return "STALE"
    if status == "NOT_COMPARABLE":
        return "NOT_COMPARABLE"
    if status == "INSUFFICIENT_EVIDENCE":
        return "INSUFFICIENT_EVIDENCE"
    if confidence in {"HIGH", "MODERATE"} and not (
        {"BROKEN_LINEAGE", "NO_OBSERVATIONS"} & set(gaps)
    ):
        return "READY_FOR_DOWNSTREAM"
    if "STALE_EVIDENCE" in gaps:
        return "STALE"
    if gaps:
        return "RESEARCH_REQUIRED" if confidence in {"UNKNOWN", "LOW"} else "PARTIALLY_READY"
    return "PARTIALLY_READY"


def _status(
    evidence: dict[str, Any],
    freshness: dict[str, Any],
    agreement: str,
    contradictions: int,
    gaps: list[str],
) -> str:
    if not evidence.get("observation_count"):
        return "INSUFFICIENT_EVIDENCE"
    if contradictions:
        return "CONTRADICTORY"
    if agreement == "NOT_COMPARABLE":
        return "NOT_COMPARABLE"
    if freshness.get("state") == "STALE":
        return "STALE"
    if len(gaps) >= 3 or evidence.get("lineage_completeness", 0) < 1:
        return "RESEARCH_REQUIRED"
    if gaps:
        return "PARTIALLY_VALIDATED"
    return "VALIDATED"


def _owned_analysis(
    db: Session, owner: User, context: TrendContext, analysis_id: uuid.UUID
) -> TrendAnalysis:
    value = db.scalar(
        select(TrendAnalysis).where(
            TrendAnalysis.id == analysis_id,
            TrendAnalysis.owner_id == owner.id,
            TrendAnalysis.context_id == context.id,
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Trend analysis not found.")
    return value


def validation_or_404(
    db: Session, owner: User, context_id: uuid.UUID, validation_id: uuid.UUID
) -> TrendValidation:
    value = db.scalar(
        select(TrendValidation).where(
            TrendValidation.id == validation_id,
            TrendValidation.owner_id == owner.id,
            TrendValidation.context_id == context_id,
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Trend validation not found.")
    return value


def create_validation(
    db: Session, owner: User, context: TrendContext, data: TrendValidationCreate
) -> TrendValidation:
    analysis = _owned_analysis(db, owner, context, data.analysis_id)
    snapshot = db.scalar(
        select(TrendSnapshot).where(
            TrendSnapshot.id == analysis.snapshot_id,
            TrendSnapshot.owner_id == owner.id,
            TrendSnapshot.context_id == context.id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Trend snapshot not found.")
    comparison = None
    if data.comparison_id:
        comparison = db.scalar(
            select(TrendChangeComparison).where(
                TrendChangeComparison.id == data.comparison_id,
                TrendChangeComparison.owner_id == owner.id,
                TrendChangeComparison.context_id == context.id,
            )
        )
        if comparison is None:
            raise HTTPException(status_code=404, detail="Trend change comparison not found.")
    fingerprint = _fingerprint(
        {
            "context_id": str(context.id),
            "analysis_id": str(analysis.id),
            "snapshot_id": str(snapshot.id),
            "comparison_id": str(comparison.id) if comparison else None,
            "calculation_version": data.calculation_version,
        }
    )
    existing = db.scalar(
        select(TrendValidation).where(
            TrendValidation.owner_id == owner.id,
            TrendValidation.context_id == context.id,
            TrendValidation.input_fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    series = list(
        db.scalars(
            select(TrendAnalysisSeries)
            .where(
                TrendAnalysisSeries.owner_id == owner.id,
                TrendAnalysisSeries.analysis_id == analysis.id,
            )
            .order_by(TrendAnalysisSeries.id)
        )
    )
    observation_ids = sorted({value for item in series for value in item.observation_ids})
    observations = list(
        db.scalars(
            select(TrendObservation).where(
                TrendObservation.owner_id == owner.id,
                TrendObservation.context_id == context.id,
                TrendObservation.id.in_([uuid.UUID(value) for value in observation_ids]),
            )
        )
    )
    source_ids = {item.source_id for item in series}
    sources = list(
        db.scalars(
            select(IntelligenceSource).where(
                IntelligenceSource.owner_id == owner.id,
                IntelligenceSource.id.in_(source_ids),
            )
        )
    )
    source_identity = {item.id: _source_identity(item) for item in sources}
    evidence, source_coverage, time, freshness, gaps = _coverage(observations, series, sources)
    agreement, agreement_summary, comparable_pairs = _agreement(series, source_identity)
    contradictions: list[dict[str, Any]] = []
    for left, right in comparable_pairs:
        if (
            left.direction in {"INCREASING", "DECREASING"}
            and right.direction in {"INCREASING", "DECREASING"}
            and left.direction != right.direction
        ):
            contradictions.append(
                {
                    "type": "DIRECTION_CONTRADICTION",
                    "left": left,
                    "right": right,
                    "reason": "Comparable sources report opposing observed directions.",
                }
            )
        elif (
            left.persistence.startswith("PERSISTENT_")
            and right.persistence.startswith("PERSISTENT_")
            and left.persistence != right.persistence
        ):
            contradictions.append(
                {
                    "type": "PERSISTENCE_CONTRADICTION",
                    "left": left,
                    "right": right,
                    "reason": "Comparable sources report opposing persistent movement.",
                }
            )
    contradiction_count = len(contradictions)
    if contradiction_count:
        gaps.append("CONTRADICTORY_SOURCES")
    blocking = contradiction_count > 0
    confidence = _confidence(
        evidence, source_coverage, time, freshness, agreement, contradiction_count, blocking
    )
    status = _status(evidence, freshness, agreement, contradiction_count, gaps)
    readiness = _readiness(status, confidence, gaps, blocking)
    if comparison is not None:
        change_events = list(
            db.scalars(
                select(TrendChangeEvent).where(
                    TrendChangeEvent.owner_id == owner.id,
                    TrendChangeEvent.comparison_id == comparison.id,
                )
            )
        )
    else:
        change_events = []
    materialities = Counter(item.materiality for item in change_events)
    alerts = Counter(item.alert_eligibility for item in change_events)
    validation_version = (
        db.scalar(
            select(func.max(TrendValidation.validation_version)).where(
                TrendValidation.owner_id == owner.id, TrendValidation.context_id == context.id
            )
        )
        or 0
    ) + 1
    limitations = [
        NO_COMMERCIAL_SYNTHESIS,
        "Agreement increases evidence support but does not establish absolute truth.",
    ]
    if int(cast(Any, source_coverage["independent_source_count"])) <= 1:
        limitations.append("Single-source evidence is not cross-source validated.")
    if freshness["state"] in {"STALE", "MIXED", "UNKNOWN"}:
        limitations.append("Current evidence freshness limits current confidence.")
    validation = TrendValidation(
        owner_id=owner.id,
        context_id=context.id,
        analysis_id=analysis.id,
        snapshot_id=snapshot.id,
        comparison_id=comparison.id if comparison else None,
        validation_version=validation_version,
        calculation_version=data.calculation_version,
        input_fingerprint=fingerprint,
        status=status,
        evidence_coverage=evidence,
        source_coverage=source_coverage,
        time_coverage=time,
        freshness_summary=freshness,
        agreement_summary={"state": agreement, **agreement_summary},
        contradiction_summary={"count": contradiction_count, "blocking": blocking},
        confidence=confidence,
        downstream_readiness=readiness,
        materiality_summary={"counts": dict(materialities), "source": "12D event materiality"},
        alert_summary={"counts": dict(alerts), "source": "12D alert eligibility; no notifications"},
        limitations=limitations,
        research_gaps=sorted(set(gaps)),
        created_at=_now(),
    )
    db.add(validation)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.validation_created",
        entity_type="trend_validation",
        entity_id=validation.id,
        metadata={"calculation_version": data.calculation_version, "analysis_id": str(analysis.id)},
        idempotency_key=f"trend-validation:{owner.id}:{fingerprint}",
    )
    for item in series:
        hypothesis_type = _direction_hypothesis(item)
        opposing = [
            str(other.source_id)
            for other in series
            if other.id != item.id
            and _comparable(item, other)
            and other.direction in {"INCREASING", "DECREASING"}
            and item.direction in {"INCREASING", "DECREASING"}
            and other.direction != item.direction
        ]
        item_rows = [row for row in observations if str(row.id) in set(item.observation_ids)]
        hfp = _fingerprint(
            {
                "validation": str(validation.id),
                "series": str(item.id),
                "hypothesis": hypothesis_type,
                "calculation_version": data.calculation_version,
            }
        )
        db.add(
            TrendValidationHypothesis(
                owner_id=owner.id,
                validation_id=validation.id,
                context_id=context.id,
                signal_definition_id=item.signal_definition_id,
                hypothesis_type=hypothesis_type,
                signal_semantics=f"Observed {item.measurement_type} signal movement",
                source_scope={
                    "source_ids": [str(item.source_id)],
                    "independent_source_count": source_coverage["independent_source_count"],
                },
                time_window={
                    "start": item.time_start.isoformat() if item.time_start else None,
                    "end": item.time_end.isoformat() if item.time_end else None,
                },
                geography=item.geography_scope,
                granularity=item.granularity,
                supporting_source_ids=[str(item.source_id)],
                opposing_source_ids=opposing,
                supporting_signal_ids=[str(item.signal_definition_id)],
                supporting_analysis_ids=[str(analysis.id)],
                supporting_series_ids=[str(item.id)],
                supporting_change_event_ids=[
                    str(event.id)
                    for event in change_events
                    if event.signal_definition_id == item.signal_definition_id
                    and (event.source_id is None or event.source_id == item.source_id)
                ],
                supporting_observation_ids=[str(row.id) for row in item_rows],
                supporting_evidence_ids=[
                    str(row.evidence_id) for row in item_rows if row.evidence_id
                ],
                support_count=1 if item.sample_size else 0,
                opposition_count=len(opposing),
                unknown_count=(
                    1 if item.direction not in {"INCREASING", "DECREASING", "STABLE"} else 0
                ),
                agreement=agreement,
                confidence=confidence,
                readiness=readiness,
                materiality=(
                    next(
                        (
                            event.materiality
                            for event in change_events
                            if event.source_id == item.source_id
                        ),
                        "UNKNOWN",
                    )
                ),
                momentum=(
                    next(
                        (
                            event.momentum
                            for event in change_events
                            if event.source_id == item.source_id
                        ),
                        "UNKNOWN",
                    )
                ),
                limitations=list(limitations),
                hypothesis_fingerprint=hfp,
                created_at=_now(),
            )
        )
    for contradiction_item in contradictions:
        contradiction_left: Any = contradiction_item["left"]
        contradiction_right: Any = contradiction_item["right"]
        ids = sorted([str(contradiction_left.id), str(contradiction_right.id)])
        cfp = _fingerprint(
            {"validation": str(validation.id), "type": contradiction_item["type"], "series": ids}
        )
        db.add(
            TrendValidationContradiction(
                owner_id=owner.id,
                validation_id=validation.id,
                context_id=context.id,
                contradiction_type=contradiction_item["type"],
                severity="BLOCKING",
                supporting_source_ids=[str(contradiction_left.source_id)],
                opposing_source_ids=[str(contradiction_right.source_id)],
                series_ids=ids,
                evidence_ids=sorted(
                    set(contradiction_left.observation_ids + contradiction_right.observation_ids)
                ),
                time_windows=[
                    {
                        "start": (
                            contradiction_left.time_start.isoformat()
                            if contradiction_left.time_start
                            else None
                        ),
                        "end": (
                            contradiction_left.time_end.isoformat()
                            if contradiction_left.time_end
                            else None
                        ),
                    },
                    {
                        "start": (
                            contradiction_right.time_start.isoformat()
                            if contradiction_right.time_start
                            else None
                        ),
                        "end": (
                            contradiction_right.time_end.isoformat()
                            if contradiction_right.time_end
                            else None
                        ),
                    },
                ],
                reason=contradiction_item["reason"],
                limitations=[
                    "Only semantically comparable evidence is classified as contradictory."
                ],
                contradiction_fingerprint=cfp,
                created_at=_now(),
            )
        )
    for gap in sorted(set(gaps)):
        recommendation = {
            "SINGLE_SOURCE_ONLY": "Add an independent canonical source.",
            "INSUFFICIENT_HISTORY": "Collect more observed periods.",
            "MISSING_PERIODS": "Refresh the missing historical periods.",
            "STALE_EVIDENCE": "Refresh stale evidence before current use.",
            "CONTRADICTORY_SOURCES": "Review opposing comparable sources.",
            "INCOMPATIBLE_SOURCES": (
                "Align signal semantics, unit, scale, geography, or " "granularity."
            ),
        }.get(gap, "Review the evidence lineage and collect bounded additional evidence.")
        db.add(
            TrendValidationGap(
                owner_id=owner.id,
                validation_id=validation.id,
                context_id=context.id,
                gap_type=gap,
                priority="HIGH" if gap in {"BROKEN_LINEAGE", "CONTRADICTORY_SOURCES"} else "MEDIUM",
                detail={"validation_id": str(validation.id)},
                recommendation=recommendation,
                created_at=_now(),
            )
        )
    db.commit()
    db.refresh(validation)
    return validation


def list_validations(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[TrendValidation], int]:
    query = select(TrendValidation).where(
        TrendValidation.owner_id == owner.id, TrendValidation.context_id == context_id
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return list(
        db.scalars(
            query.order_by(TrendValidation.created_at.desc(), TrendValidation.id)
            .offset(offset)
            .limit(limit)
        )
    ), int(total)


def current_validation(db: Session, owner: User, context_id: uuid.UUID) -> TrendValidation | None:
    return db.scalar(
        select(TrendValidation)
        .where(TrendValidation.owner_id == owner.id, TrendValidation.context_id == context_id)
        .order_by(TrendValidation.created_at.desc(), TrendValidation.id.desc())
    )


def list_hypotheses(
    db: Session, owner: User, validation_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[TrendValidationHypothesis]:
    return list(
        db.scalars(
            select(TrendValidationHypothesis)
            .where(
                TrendValidationHypothesis.owner_id == owner.id,
                TrendValidationHypothesis.validation_id == validation_id,
            )
            .order_by(TrendValidationHypothesis.created_at, TrendValidationHypothesis.id)
            .offset(offset)
            .limit(limit)
        )
    )


def list_contradictions(
    db: Session, owner: User, validation_id: uuid.UUID
) -> list[TrendValidationContradiction]:
    return list(
        db.scalars(
            select(TrendValidationContradiction)
            .where(
                TrendValidationContradiction.owner_id == owner.id,
                TrendValidationContradiction.validation_id == validation_id,
            )
            .order_by(TrendValidationContradiction.created_at, TrendValidationContradiction.id)
        )
    )


def list_gaps(db: Session, owner: User, validation_id: uuid.UUID) -> list[TrendValidationGap]:
    return list(
        db.scalars(
            select(TrendValidationGap)
            .where(
                TrendValidationGap.owner_id == owner.id,
                TrendValidationGap.validation_id == validation_id,
            )
            .order_by(TrendValidationGap.created_at, TrendValidationGap.id)
        )
    )


def list_sources(db: Session, owner: User, validation: TrendValidation) -> list[dict[str, object]]:
    ids = [
        uuid.UUID(str(value))
        for value in cast(list[Any], validation.source_coverage.get("source_ids", []))
    ]
    rows = db.scalars(
        select(IntelligenceSource).where(
            IntelligenceSource.owner_id == owner.id,
            IntelligenceSource.id.in_(ids),
        )
    )
    return [
        {
            "id": str(row.id),
            "display_name": row.display_name,
            "provider": row.provider,
            "source_type": row.source_type,
            "independent_identity": _source_identity(row),
        }
        for row in rows
    ]


def validation_operations(db: Session, owner: User) -> dict[str, object]:
    rows = list(db.scalars(select(TrendValidation).where(TrendValidation.owner_id == owner.id)))
    hypotheses = list(
        db.scalars(
            select(TrendValidationHypothesis).where(TrendValidationHypothesis.owner_id == owner.id)
        )
    )
    contradictions = list(
        db.scalars(
            select(TrendValidationContradiction).where(
                TrendValidationContradiction.owner_id == owner.id
            )
        )
    )
    return {
        "validation_count": len(rows),
        "validated_count": sum(row.status == "VALIDATED" for row in rows),
        "partial_validation_count": sum(row.status == "PARTIALLY_VALIDATED" for row in rows),
        "insufficient_validation_count": sum(row.status == "INSUFFICIENT_EVIDENCE" for row in rows),
        "contradictory_validation_count": sum(row.status == "CONTRADICTORY" for row in rows),
        "stale_validation_count": sum(row.status == "STALE" for row in rows),
        "hypothesis_count": len(hypotheses),
        "high_confidence_count": sum(row.confidence == "HIGH" for row in rows),
        "moderate_confidence_count": sum(row.confidence == "MODERATE" for row in rows),
        "low_confidence_count": sum(row.confidence == "LOW" for row in rows),
        "unknown_confidence_count": sum(row.confidence == "UNKNOWN" for row in rows),
        "research_required_count": sum(
            row.downstream_readiness == "RESEARCH_REQUIRED" for row in rows
        ),
        "contradiction_count": len(contradictions),
        "single_source_count": sum("SINGLE_SOURCE_ONLY" in row.research_gaps for row in rows),
        "latest_validation_activity": max((row.created_at for row in rows), default=None),
    }


def doctor(db: Session, owner: User) -> dict[str, int]:
    """Owner-scoped 12E hard counters; all counters describe evidence integrity only."""
    checks = {
        "orphan_validation": 0,
        "cross_owner_validation_context": 0,
        "validation_analysis_context_mismatch": 0,
        "validation_snapshot_mismatch": 0,
        "orphan_hypothesis": 0,
        "hypothesis_outside_validation_context": 0,
        "hypothesis_without_supporting_lineage": 0,
        "invalid_independent_source_count": 0,
        "agreement_across_incompatible_signals": 0,
        "agreement_across_incompatible_geography": 0,
        "agreement_across_incompatible_scale_unit_granularity": 0,
        "contradiction_across_non_comparable": 0,
        "invalid_evidence_coverage": 0,
        "invalid_sample_counts": 0,
        "invalid_period_coverage": 0,
        "high_confidence_zero_evidence": 0,
        "high_current_confidence_stale_only": 0,
        "cross_source_validated_single_source": 0,
        "high_confidence_blocking_contradiction": 0,
        "invalid_confidence": 0,
        "invalid_readiness": 0,
        "invalid_agreement": 0,
        "duplicate_logical_validation": 0,
        "duplicate_logical_hypothesis": 0,
        "broken_source_evidence_lineage": 0,
        "validation_forecast_output": 0,
        "validation_demand_output": 0,
        "validation_sales_output": 0,
        "validation_revenue_output": 0,
        "validation_market_size_output": 0,
        "validation_product_success_probability": 0,
        "validation_winning_product_score": 0,
        "validation_generic_trend_score": 0,
        "external_write_notification_exposure": 0,
    }
    validations = list(
        db.scalars(select(TrendValidation).where(TrendValidation.owner_id == owner.id))
    )
    contexts = {
        row.id: row
        for row in db.scalars(select(TrendContext).where(TrendContext.owner_id == owner.id))
    }
    analyses = {
        row.id: row
        for row in db.scalars(select(TrendAnalysis).where(TrendAnalysis.owner_id == owner.id))
    }
    snapshots = {
        row.id: row
        for row in db.scalars(select(TrendSnapshot).where(TrendSnapshot.owner_id == owner.id))
    }
    sources = {
        row.id: row
        for row in db.scalars(
            select(IntelligenceSource).where(IntelligenceSource.owner_id == owner.id)
        )
    }
    evidence = {
        row.id
        for row in db.scalars(
            select(IntelligenceEvidence).where(IntelligenceEvidence.owner_id == owner.id)
        )
    }
    hypotheses = list(
        db.scalars(
            select(TrendValidationHypothesis).where(TrendValidationHypothesis.owner_id == owner.id)
        )
    )
    contradictions = list(
        db.scalars(
            select(TrendValidationContradiction).where(
                TrendValidationContradiction.owner_id == owner.id
            )
        )
    )
    counts = Counter(row.input_fingerprint for row in validations)
    checks["duplicate_logical_validation"] = sum(
        value - 1 for value in counts.values() if value > 1
    )
    hypothesis_counts = Counter(
        (row.validation_id, row.hypothesis_fingerprint) for row in hypotheses
    )
    checks["duplicate_logical_hypothesis"] = sum(
        value - 1 for value in hypothesis_counts.values() if value > 1
    )
    validation_ids = {row.id for row in validations}
    for validation_row in validations:
        analysis = analyses.get(validation_row.analysis_id)
        snapshot = snapshots.get(validation_row.snapshot_id)
        context = contexts.get(validation_row.context_id)
        if not analysis or not snapshot or not context:
            checks["orphan_validation"] += 1
            continue
        if analysis.context_id != validation_row.context_id:
            checks["validation_analysis_context_mismatch"] += 1
        if snapshot.context_id != validation_row.context_id:
            checks["validation_snapshot_mismatch"] += 1
        if validation_row.confidence not in CONFIDENCE_STATES:
            checks["invalid_confidence"] += 1
        if validation_row.downstream_readiness not in READINESS_STATES:
            checks["invalid_readiness"] += 1
        state = cast(Any, validation_row.agreement_summary).get("state")
        if state not in AGREEMENT_STATES:
            checks["invalid_agreement"] += 1
        independent = cast(Any, validation_row.source_coverage).get("independent_source_count", 0)
        source_count = cast(Any, validation_row.source_coverage).get("source_count", 0)
        if independent > source_count:
            checks["invalid_independent_source_count"] += 1
        ratio = cast(Any, validation_row.time_coverage).get("coverage_ratio", 0)
        if not isinstance(ratio, (int, float)) or ratio < 0 or ratio > 1:
            checks["invalid_period_coverage"] += 1
        if validation_row.confidence == "HIGH" and not cast(
            Any, validation_row.evidence_coverage
        ).get("observation_count"):
            checks["high_confidence_zero_evidence"] += 1
        if validation_row.confidence == "HIGH" and validation_row.freshness_state == "STALE":
            checks["high_current_confidence_stale_only"] += 1
        if validation_row.confidence == "HIGH" and cast(
            Any, validation_row.contradiction_summary
        ).get("blocking"):
            checks["high_confidence_blocking_contradiction"] += 1
        if (
            validation_row.confidence in {"HIGH", "MODERATE"}
            and source_count < 2
            and state == "AGREE"
        ):
            checks["cross_source_validated_single_source"] += 1
        forbidden = json.dumps(
            {
                "coverage": validation_row.evidence_coverage,
                "limitations": validation_row.limitations,
                "gaps": validation_row.research_gaps,
            }
        ).lower()
        for key, tokens in {
            "validation_forecast_output": ("forecast", "prediction"),
            "validation_demand_output": ("demand",),
            "validation_sales_output": ("sales",),
            "validation_revenue_output": ("revenue",),
            "validation_market_size_output": ("market size",),
            "validation_product_success_probability": ("product success",),
            "validation_winning_product_score": ("winning product score",),
            "validation_generic_trend_score": ("trend score",),
        }.items():
            if any(token in forbidden for token in tokens):
                checks[key] += 1
    for hypothesis_row in hypotheses:
        if hypothesis_row.validation_id not in validation_ids:
            checks["orphan_hypothesis"] += 1
            continue
        if (
            not hypothesis_row.supporting_analysis_ids
            or not hypothesis_row.supporting_series_ids
            or not hypothesis_row.supporting_observation_ids
        ):
            checks["hypothesis_without_supporting_lineage"] += 1
        if any(
            value not in sources
            for value in (uuid.UUID(item) for item in hypothesis_row.supporting_source_ids if item)
        ):
            checks["broken_source_evidence_lineage"] += 1
        if any(
            value not in evidence
            for value in (
                uuid.UUID(item) for item in hypothesis_row.supporting_evidence_ids if item
            )
        ):
            checks["broken_source_evidence_lineage"] += 1
    for row in contradictions:
        if (
            hypothesis_row.validation_id not in validation_ids
            or row.contradiction_type not in CONTRADICTION_TYPES
        ):
            checks["contradiction_across_non_comparable"] += 1
    return checks
