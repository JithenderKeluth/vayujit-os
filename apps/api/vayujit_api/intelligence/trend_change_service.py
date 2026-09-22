"""Deterministic Trend 12D comparison, event, and momentum services."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.trend_analysis_models import TrendAnalysis, TrendAnalysisSeries
from vayujit_api.intelligence.trend_change_models import (
    ALERT_ELIGIBILITY,
    CALCULATION_VERSION,
    EVENT_STATUSES,
    MATERIALITY_LEVELS,
    MATERIALITY_POLICY_VERSION,
    MOMENTUM_STATES,
    TrendChangeComparison,
    TrendChangeEvent,
)
from vayujit_api.intelligence.trend_change_schemas import TrendChangeComparisonCreate
from vayujit_api.intelligence.trend_models import TrendContext, TrendSnapshot

NO_FORECAST = (
    "Describes observed historical signal movement only; it does not forecast future values, "
    "demand, sales, revenue, market size, or product success."
)


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _owned_analysis(
    db: Session, owner: User, context: TrendContext, analysis_id: uuid.UUID
) -> TrendAnalysis:
    row = db.scalar(
        select(TrendAnalysis).where(
            TrendAnalysis.id == analysis_id,
            TrendAnalysis.owner_id == owner.id,
            TrendAnalysis.context_id == context.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Trend analysis not found.")
    return row


def _snapshot(
    db: Session, owner: User, context: TrendContext, snapshot_id: uuid.UUID
) -> TrendSnapshot:
    row = db.scalar(
        select(TrendSnapshot).where(
            TrendSnapshot.id == snapshot_id,
            TrendSnapshot.owner_id == owner.id,
            TrendSnapshot.context_id == context.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Trend snapshot not found.")
    return row


def _analysis_time(db: Session, analysis: TrendAnalysis) -> datetime:
    snapshot = db.get(TrendSnapshot, analysis.snapshot_id)
    return snapshot.captured_at if snapshot is not None else analysis.created_at


def _series_key(series: TrendAnalysisSeries) -> str:
    return ":".join(
        (
            str(series.signal_definition_id),
            str(series.source_id),
            series.measurement_type,
            series.unit or "",
            str(series.scale or ""),
            series.geography_scope,
            series.country or "",
            series.region or "",
            series.city or "",
            series.marketplace or "",
            series.granularity,
        )
    )


def _series_map(db: Session, owner: User, analysis_id: uuid.UUID) -> dict[str, TrendAnalysisSeries]:
    rows = db.scalars(
        select(TrendAnalysisSeries).where(
            TrendAnalysisSeries.owner_id == owner.id, TrendAnalysisSeries.analysis_id == analysis_id
        )
    )
    return {_series_key(row): row for row in rows}


def _comparable(baseline: TrendAnalysisSeries | None, current: TrendAnalysisSeries | None) -> bool:
    if baseline is None or current is None:
        return False
    return (
        baseline.measurement_type == current.measurement_type
        and baseline.unit == current.unit
        and baseline.scale == current.scale
        and baseline.geography_scope == current.geography_scope
        and baseline.granularity == current.granularity
    )


def _stat(series: TrendAnalysisSeries, name: str) -> Decimal | None:
    return _decimal(series.statistics.get(name)) if isinstance(series.statistics, dict) else None


def _delta(
    baseline: Decimal | None, current: Decimal | None
) -> tuple[Decimal | None, Decimal | None, str | None]:
    if baseline is None or current is None:
        return None, None, None
    absolute = current - baseline
    if baseline == 0:
        return absolute, None, "ZERO_DENOMINATOR"
    return absolute, (absolute / baseline) * Decimal(100), None


def _momentum(
    current: TrendAnalysisSeries, baseline: TrendAnalysisSeries | None, comparable: bool
) -> str:
    if not comparable:
        return "NOT_COMPARABLE"
    if current.sample_size < 2 or current.readiness in {
        "INSUFFICIENT_EVIDENCE",
        "NOT_COMPARABLE",
        "UNSUPPORTED",
    }:
        return "INSUFFICIENT_EVIDENCE"
    direction = current.direction
    persistence = current.persistence
    if direction == "MIXED":
        return "MIXED"
    if direction == "STABLE" or persistence == "FLAT":
        return "STABLE"
    if direction not in {"INCREASING", "DECREASING"}:
        return "UNKNOWN"
    sign = "INCREASE" if direction == "INCREASING" else "DECREASE"
    if (
        baseline is not None
        and baseline.direction in {"INCREASING", "DECREASING"}
        and baseline.direction != direction
    ):
        return "REVERSING"
    if (
        persistence in {"PERSISTENT_INCREASE", "PERSISTENT_DECREASE"}
        and current.sample_size >= 3
        and current.missing_period_count == 0
    ):
        return f"SUSTAINED_{sign}"
    if baseline is None or baseline.direction != direction:
        return f"EMERGING_{sign}"
    return f"WEAKENING_{sign}"


def _materiality(
    absolute: Decimal | None,
    relative: Decimal | None,
    momentum: str,
    state_changed: bool,
    comparable: bool,
    sample: int,
) -> str:
    if not comparable or sample < 2:
        return "UNKNOWN"
    if momentum == "REVERSING":
        return "HIGH" if sample >= 3 else "MODERATE"
    magnitude = (
        abs(relative)
        if relative is not None
        else abs(absolute) if absolute is not None else Decimal(0)
    )
    if magnitude >= Decimal(25) or (state_changed and sample >= 4):
        return "HIGH"
    if magnitude >= Decimal(10) or state_changed:
        return "MODERATE"
    if magnitude > 0:
        return "LOW"
    return "IMMATERIAL"


def _alert(materiality: str, current: TrendAnalysisSeries, comparable: bool) -> tuple[str, str]:
    if not comparable or current.sample_size < 3 or current.readiness != "AVAILABLE":
        return "NO_ALERT", "insufficient or incomparable evidence"
    if current.freshness_state != "CURRENT":
        return "REVIEW", "current evidence is stale or freshness is unknown"
    if materiality == "HIGH":
        return "ALERT", "high observed materiality with sufficient current evidence"
    if materiality in {"MODERATE", "LOW"}:
        return "REVIEW", "observed change merits human review"
    return "NO_ALERT", "immaterial observed change"


def _event_types(
    baseline: TrendAnalysisSeries, current: TrendAnalysisSeries, absolute: Decimal | None
) -> list[str]:
    values: list[str] = []
    if absolute is not None:
        values.append(
            "SIGNAL_VALUE_INCREASED"
            if absolute > 0
            else "SIGNAL_VALUE_DECREASED" if absolute < 0 else "SIGNAL_VALUE_UNCHANGED"
        )
    if baseline.direction != current.direction:
        values.append(
            "DIRECTION_REVERSED"
            if {baseline.direction, current.direction} == {"INCREASING", "DECREASING"}
            else "DIRECTION_CHANGED"
        )
    if baseline.persistence != current.persistence:
        if current.persistence in {"PERSISTENT_INCREASE", "PERSISTENT_DECREASE"}:
            values.append("PERSISTENCE_STARTED")
        elif baseline.persistence in {"PERSISTENT_INCREASE", "PERSISTENT_DECREASE"}:
            values.append("PERSISTENCE_WEAKENED")
        else:
            values.append("PERSISTENCE_ENDED")
    if baseline.variability_state != current.variability_state:
        values.append(
            "VARIABILITY_INCREASED"
            if current.variability_state in {"MODERATE_VARIABILITY", "HIGH_VARIABILITY"}
            else (
                "VARIABILITY_DECREASED"
                if baseline.variability_state in {"MODERATE_VARIABILITY", "HIGH_VARIABILITY"}
                else "VARIABILITY_CHANGED"
            )
        )
    if baseline.freshness_state != current.freshness_state:
        values.append(
            "FRESHNESS_IMPROVED" if current.freshness_state == "CURRENT" else "FRESHNESS_DEGRADED"
        )
    if current.missing_period_count != baseline.missing_period_count:
        values.append(
            "MISSING_PERIODS_INCREASED"
            if current.missing_period_count > baseline.missing_period_count
            else "MISSING_PERIODS_DECREASED"
        )
    if current.sample_size > baseline.sample_size:
        values.append("COVERAGE_INCREASED")
    elif current.sample_size < baseline.sample_size:
        values.append("COVERAGE_DECREASED")
    return values or ["RESEARCH_GAP_RESOLVED"]


def _event(
    owner: User,
    context: TrendContext,
    comparison: TrendChangeComparison,
    event_type: str,
    baseline: TrendAnalysisSeries | None,
    current: TrendAnalysisSeries | None,
    key: str,
) -> TrendChangeEvent:
    comparable = _comparable(baseline, current)
    old_latest = _stat(baseline, "latest") if baseline else None
    new_latest = _stat(current, "latest") if current else None
    absolute, relative, reason = (
        _delta(old_latest, new_latest) if comparable else (None, None, "INCOMPATIBLE_SERIES")
    )
    momentum = _momentum(current, baseline, comparable) if current else "INSUFFICIENT_EVIDENCE"
    sample = current.sample_size if current else 0
    materiality = _materiality(
        absolute,
        relative,
        momentum,
        bool(
            baseline
            and current
            and (
                baseline.direction != current.direction
                or baseline.persistence != current.persistence
            )
        ),
        comparable,
        sample,
    )
    eligibility, alert_reason = (
        _alert(materiality, current, comparable)
        if current
        else ("NO_ALERT", "current evidence is absent")
    )
    limitations = [NO_FORECAST]
    if not comparable:
        limitations.append("Baseline and current cohorts are not directly comparable.")
    if current is None:
        limitations.append(
            "Current evidence is absent; disappearance is only possible, not confirmed."
        )
    if current is not None and current.sample_size < 3:
        limitations.append("CURRENT_SAMPLE_TOO_SMALL")
    event_fingerprint = _fingerprint(
        {
            "comparison": str(comparison.id),
            "event": event_type,
            "key": key,
            "old": str(old_latest),
            "new": str(new_latest),
        }
    )
    return TrendChangeEvent(
        owner_id=owner.id,
        context_id=context.id,
        comparison_id=comparison.id,
        signal_definition_id=(
            current.signal_definition_id
            if current
            else (baseline.signal_definition_id if baseline else None)
        ),
        source_id=current.source_id if current else (baseline.source_id if baseline else None),
        event_type=event_type,
        change_semantics="DERIVED_DETERMINISTIC_CHANGE",
        old_value={
            "latest": str(old_latest) if old_latest is not None else None,
            "direction": baseline.direction if baseline else None,
            "persistence": baseline.persistence if baseline else None,
        },
        new_value={
            "latest": str(new_latest) if new_latest is not None else None,
            "direction": current.direction if current else None,
            "persistence": current.persistence if current else None,
        },
        absolute_delta=absolute,
        relative_delta=relative,
        relative_reason=reason,
        momentum=momentum,
        materiality=materiality,
        materiality_policy_version=MATERIALITY_POLICY_VERSION,
        status="NEW",
        alert_eligibility=eligibility,
        alert_reason=alert_reason,
        baseline_reference=(
            {
                "series_id": str(baseline.id),
                "observation_ids": baseline.observation_ids,
                "sample_size": baseline.sample_size,
                "geography_scope": baseline.geography_scope,
                "granularity": baseline.granularity,
                "freshness_state": baseline.freshness_state,
                "evidence_ids": baseline.evidence_ids,
            }
            if baseline
            else {}
        ),
        current_reference=(
            {
                "series_id": str(current.id),
                "observation_ids": current.observation_ids,
                "sample_size": current.sample_size,
                "geography_scope": current.geography_scope,
                "granularity": current.granularity,
                "freshness_state": current.freshness_state,
                "evidence_ids": current.evidence_ids,
            }
            if current
            else {}
        ),
        evidence_references={
            "baseline_evidence_ids": baseline.evidence_ids if baseline else [],
            "current_evidence_ids": current.evidence_ids if current else [],
        },
        freshness_state=current.freshness_state if current else "UNKNOWN",
        limitations=limitations,
        event_fingerprint=event_fingerprint,
        created_at=_now(),
    )


def create_comparison(
    db: Session, owner: User, context: TrendContext, data: TrendChangeComparisonCreate
) -> tuple[TrendChangeComparison, list[TrendChangeEvent]]:
    baseline = _owned_analysis(db, owner, context, data.baseline_analysis_id)
    current = _owned_analysis(db, owner, context, data.current_analysis_id)
    if baseline.id == current.id:
        raise HTTPException(409, "Baseline and current analyses must be distinct.")
    baseline_time, current_time = _analysis_time(db, baseline), _analysis_time(db, current)
    if baseline_time >= current_time:
        raise HTTPException(409, "Current analysis must represent a later snapshot boundary.")
    if baseline.calculation_version != current.calculation_version:
        raise HTTPException(409, "Analyses use incompatible calculation contracts.")
    fingerprint = _fingerprint(
        {
            "owner": str(owner.id),
            "context": str(context.id),
            "baseline": str(baseline.id),
            "current": str(current.id),
            "calculation": CALCULATION_VERSION,
        }
    )
    existing = db.scalar(
        select(TrendChangeComparison).where(
            TrendChangeComparison.owner_id == owner.id,
            TrendChangeComparison.context_id == context.id,
            TrendChangeComparison.input_fingerprint == fingerprint,
        )
    )
    if existing:
        return existing, list(
            db.scalars(
                select(TrendChangeEvent)
                .where(TrendChangeEvent.comparison_id == existing.id)
                .order_by(TrendChangeEvent.created_at.asc())
            )
        )
    version = (
        db.scalar(
            select(func.max(TrendChangeComparison.comparison_version)).where(
                TrendChangeComparison.owner_id == owner.id,
                TrendChangeComparison.context_id == context.id,
            )
        )
        or 0
    ) + 1
    comparison = TrendChangeComparison(
        owner_id=owner.id,
        context_id=context.id,
        baseline_analysis_id=baseline.id,
        current_analysis_id=current.id,
        baseline_snapshot_id=baseline.snapshot_id,
        current_snapshot_id=current.snapshot_id,
        comparison_version=version,
        calculation_version=CALCULATION_VERSION,
        materiality_policy_version=MATERIALITY_POLICY_VERSION,
        input_fingerprint=fingerprint,
        summary={},
        limitations=[NO_FORECAST, "Momentum is descriptive and is not commercial attractiveness."],
        created_at=_now(),
    )
    db.add(comparison)
    db.flush()
    before = _series_map(db, owner, baseline.id)
    after = _series_map(db, owner, current.id)
    events: list[TrendChangeEvent] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old and new:
            comparable = _comparable(old, new)
            delta = _delta(_stat(old, "latest"), _stat(new, "latest"))[0] if comparable else None
            types = _event_types(old, new, delta) if comparable else ["COMPARABILITY_CHANGED"]
        elif new:
            types = ["EVIDENCE_APPEARED", "SOURCE_ADDED"]
        else:
            types = ["EVIDENCE_POSSIBLY_DISAPPEARED", "SOURCE_POSSIBLY_REMOVED"]
        for event_type in types:
            row = _event(owner, context, comparison, event_type, old, new, key)
            db.add(row)
            events.append(row)
    comparison.summary = {
        "event_count": len(events),
        "series_compared": len(set(before) & set(after)),
        "series_added": len(set(after) - set(before)),
        "series_removed": len(set(before) - set(after)),
        "momentum_states": dict(Counter(event.momentum for event in events)),
        "materiality": dict(Counter(event.materiality for event in events)),
        "alert_eligibility": dict(Counter(event.alert_eligibility for event in events)),
    }
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.change_comparison_created",
        entity_type="trend_change_comparison",
        entity_id=comparison.id,
        metadata={
            "event_count": len(events),
            "baseline_analysis_id": str(baseline.id),
            "current_analysis_id": str(current.id),
        },
        idempotency_key=f"trend-change-comparison:{owner.id}:{fingerprint}",
    )
    db.commit()
    db.refresh(comparison)
    return comparison, events


def list_comparisons(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[TrendChangeComparison], int]:
    query = (
        select(TrendChangeComparison)
        .where(
            TrendChangeComparison.owner_id == owner.id,
            TrendChangeComparison.context_id == context_id,
        )
        .order_by(TrendChangeComparison.created_at.desc())
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return list(db.scalars(query.offset(offset).limit(limit))), total


def comparison_or_404(
    db: Session, owner: User, context_id: uuid.UUID, comparison_id: uuid.UUID
) -> TrendChangeComparison:
    value = db.scalar(
        select(TrendChangeComparison).where(
            TrendChangeComparison.id == comparison_id,
            TrendChangeComparison.owner_id == owner.id,
            TrendChangeComparison.context_id == context_id,
        )
    )
    if value is None:
        raise HTTPException(404, "Trend change comparison not found.")
    return value


def list_events(
    db: Session,
    owner: User,
    context_id: uuid.UUID,
    comparison_id: uuid.UUID | None,
    limit: int,
    offset: int,
    filters: dict[str, str | None],
) -> tuple[list[TrendChangeEvent], int]:
    query = select(TrendChangeEvent).where(
        TrendChangeEvent.owner_id == owner.id, TrendChangeEvent.context_id == context_id
    )
    if comparison_id:
        query = query.where(TrendChangeEvent.comparison_id == comparison_id)
    for field, value in filters.items():
        if value:
            query = query.where(getattr(TrendChangeEvent, field) == value.upper())
    query = query.order_by(TrendChangeEvent.created_at.asc())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return list(db.scalars(query.offset(offset).limit(limit))), total


def doctor(db: Session, owner: User) -> dict[str, int]:
    comparisons = list(
        db.scalars(select(TrendChangeComparison).where(TrendChangeComparison.owner_id == owner.id))
    )
    events = list(db.scalars(select(TrendChangeEvent).where(TrendChangeEvent.owner_id == owner.id)))
    counters = {
        key: 0
        for key in (
            "orphan_comparison",
            "cross_owner_comparison_context",
            "same_analysis",
            "reversed_chronology",
            "comparison_missing_analysis_snapshot",
            "orphan_event",
            "event_outside_context",
            "invalid_decimal_delta",
            "relative_zero_denominator",
            "incompatible_numeric_comparison",
            "single_observation_sustained",
            "insufficient_sustained",
            "stale_current_momentum",
            "confirmed_disappearance",
            "invalid_materiality",
            "invalid_momentum",
            "invalid_status",
            "invalid_alert",
            "duplicate_logical_comparison",
            "duplicate_logical_event",
            "forecast_output",
            "demand_output",
            "sales_output",
            "revenue_output",
            "market_size_output",
            "winning_product_output",
            "generic_trend_score_output",
            "external_notification_exposure",
        )
    }
    fingerprints = Counter(item.input_fingerprint for item in comparisons)
    counters["duplicate_logical_comparison"] = sum(
        value - 1 for value in fingerprints.values() if value > 1
    )
    event_fingerprints = Counter(item.event_fingerprint for item in events)
    counters["duplicate_logical_event"] = sum(
        value - 1 for value in event_fingerprints.values() if value > 1
    )
    for comparison in comparisons:
        context = db.get(TrendContext, comparison.context_id)
        baseline = db.get(TrendAnalysis, comparison.baseline_analysis_id)
        current = db.get(TrendAnalysis, comparison.current_analysis_id)
        baseline_snapshot = db.get(TrendSnapshot, comparison.baseline_snapshot_id)
        current_snapshot = db.get(TrendSnapshot, comparison.current_snapshot_id)
        if context is None:
            counters["orphan_comparison"] += 1
        if (
            context is None
            or context.owner_id != comparison.owner_id
            or any(
                analysis is not None
                and (analysis.owner_id != comparison.owner_id or analysis.context_id != context.id)
                for analysis in (baseline, current)
            )
        ):
            counters["cross_owner_comparison_context"] += 1
        if comparison.baseline_analysis_id == comparison.current_analysis_id:
            counters["same_analysis"] += 1
        if (
            baseline is None
            or current is None
            or baseline_snapshot is None
            or current_snapshot is None
        ):
            counters["comparison_missing_analysis_snapshot"] += 1
        elif _analysis_time(db, baseline) >= _analysis_time(db, current):
            counters["reversed_chronology"] += 1
    for event in events:
        comparison_row = db.get(TrendChangeComparison, event.comparison_id)
        if comparison_row is None:
            counters["orphan_event"] += 1
        elif (
            event.context_id != comparison_row.context_id
            or event.owner_id != comparison_row.owner_id
        ):
            counters["event_outside_context"] += 1
        for value in (event.absolute_delta, event.relative_delta):
            if value is not None and _decimal(value) is None:
                counters["invalid_decimal_delta"] += 1
        if event.momentum.startswith("SUSTAINED"):
            current_ids = (
                event.current_reference.get("observation_ids", [])
                if isinstance(event.current_reference, dict)
                else []
            )
            if not isinstance(current_ids, list) or len(current_ids) < 3:
                counters["single_observation_sustained"] += 1
                counters["insufficient_sustained"] += 1
            if event.freshness_state == "STALE" and event.alert_eligibility == "ALERT":
                counters["stale_current_momentum"] += 1
        if event.event_type in {"EVIDENCE_DISAPPEARED", "SOURCE_REMOVED"}:
            counters["confirmed_disappearance"] += 1
        for token, key in (
            ("forecast", "forecast_output"),
            ("demand", "demand_output"),
            ("sales", "sales_output"),
            ("revenue", "revenue_output"),
            ("market size", "market_size_output"),
            ("winning product", "winning_product_output"),
            ("trend score", "generic_trend_score_output"),
        ):
            text = json.dumps({"old": event.old_value, "new": event.new_value}).lower()
            if token in text:
                counters[key] += 1
        if event.materiality not in MATERIALITY_LEVELS:
            counters["invalid_materiality"] += 1
        if event.momentum not in MOMENTUM_STATES:
            counters["invalid_momentum"] += 1
        if event.status not in EVENT_STATUSES:
            counters["invalid_status"] += 1
        if event.alert_eligibility not in ALERT_ELIGIBILITY:
            counters["invalid_alert"] += 1
        if event.relative_reason == "ZERO_DENOMINATOR" and event.relative_delta is not None:
            counters["relative_zero_denominator"] += 1
    return counters


def change_operations(db: Session, owner: User) -> dict[str, object]:
    comparisons = list(
        db.scalars(select(TrendChangeComparison).where(TrendChangeComparison.owner_id == owner.id))
    )
    events = list(db.scalars(select(TrendChangeEvent).where(TrendChangeEvent.owner_id == owner.id)))
    return {
        "change_comparisons": len(comparisons),
        "change_events": len(events),
        "new_change_events": sum(item.status == "NEW" for item in events),
        "ongoing_change_events": sum(item.status == "ONGOING" for item in events),
        "resolved_change_events": sum(item.status == "RESOLVED" for item in events),
        "moderate_high_materiality_events": sum(
            item.materiality in {"MODERATE", "HIGH"} for item in events
        ),
        "review_alert_eligible_events": sum(
            item.alert_eligibility in {"REVIEW", "ALERT"} for item in events
        ),
        "insufficient_change_comparisons": sum(
            item.momentum == "INSUFFICIENT_EVIDENCE" for item in events
        ),
        "not_comparable_change_events": sum(item.momentum == "NOT_COMPARABLE" for item in events),
        "latest_change_activity": max((item.created_at for item in events), default=None),
    }
