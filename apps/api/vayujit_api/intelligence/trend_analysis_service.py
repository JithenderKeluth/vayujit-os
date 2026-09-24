"""Deterministic descriptive Trend 12C analysis over immutable snapshots."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.trend_analysis_models import (
    DIRECTION_STATES,
    PERSISTENCE_STATES,
    TrendAnalysis,
    TrendAnalysisGap,
    TrendAnalysisSeries,
)
from vayujit_api.intelligence.trend_analysis_schemas import TrendAnalysisCreate
from vayujit_api.intelligence.trend_models import (
    TrendContext,
    TrendObservation,
    TrendSignalDefinition,
    TrendSnapshot,
)
from vayujit_api.intelligence.trend_service import _now

CALCULATION_VERSION = "trend-analysis-v1"
NUMERIC_TYPES = {"COUNT", "DECIMAL", "INDEX", "PERCENTAGE", "ORDINAL"}
TIME_GRANULARITIES = {"HOURLY", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _decimal(value: Decimal | int | float | None) -> Decimal | None:
    if value is None:
        return None
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    return result if result.is_finite() else None


def _number(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _period_value(row: TrendObservation) -> datetime:
    return row.period_start or row.period_end or row.observed_at


def _cohort_key(row: TrendObservation) -> tuple[object, ...]:
    return (
        str(row.signal_definition_id),
        str(row.source_id),
        row.measurement_type,
        row.unit or "",
        _number(_decimal(row.scale)) or "",
        row.geography_scope,
        row.country or "",
        row.region or "",
        row.city or "",
        row.marketplace or "",
        row.granularity,
    )


def _movement(values: list[Decimal]) -> list[int]:
    return [1 if b > a else -1 if b < a else 0 for a, b in zip(values, values[1:], strict=False)]


def _direction(moves: list[int], sample_size: int) -> str:
    if sample_size < 2 or not moves:
        return "INSUFFICIENT_EVIDENCE"
    if all(item > 0 for item in moves):
        return "INCREASING"
    if all(item < 0 for item in moves):
        return "DECREASING"
    if all(item == 0 for item in moves):
        return "STABLE"
    return "MIXED"


def _persistence(moves: list[int], sample_size: int) -> str:
    if sample_size < 3 or not moves:
        return "INSUFFICIENT_EVIDENCE"
    if all(item > 0 for item in moves):
        return "PERSISTENT_INCREASE"
    if all(item < 0 for item in moves):
        return "PERSISTENT_DECREASE"
    if all(item == 0 for item in moves):
        return "FLAT"
    non_zero = [item for item in moves if item]
    if any(left != right for left, right in zip(non_zero, non_zero[1:], strict=False)):
        return "REVERSING"
    return "INTERMITTENT"


def _numeric_statistics(values: list[Decimal]) -> dict[str, object]:
    ordered = sorted(values)
    count = len(ordered)
    total = sum(ordered, Decimal(0))
    middle = (
        ordered[count // 2] if count % 2 else (ordered[count // 2 - 1] + ordered[count // 2]) / 2
    )
    return {
        "count": count,
        "minimum": _number(ordered[0]),
        "maximum": _number(ordered[-1]),
        "mean": _number(total / count),
        "median": _number(middle),
        "first": _number(values[0]),
        "latest": _number(values[-1]),
        "range": _number(ordered[-1] - ordered[0]),
    }


def _variability(values: list[Decimal]) -> tuple[str, dict[str, object]]:
    if len(values) < 2:
        return "UNKNOWN", {"range": None, "mean_absolute_change": None}
    moves = [abs(b - a) for a, b in zip(values, values[1:], strict=False)]
    result_range = max(values) - min(values)
    mean = abs(sum(values, Decimal(0)) / len(values))
    if result_range == 0:
        state = "STABLE"
    elif mean and result_range <= mean * Decimal("0.05"):
        state = "LOW_VARIABILITY"
    elif mean and result_range <= mean * Decimal("0.20"):
        state = "MODERATE_VARIABILITY"
    else:
        state = "HIGH_VARIABILITY"
    return state, {
        "range": _number(result_range),
        "mean_absolute_change": _number(sum(moves, Decimal(0)) / len(moves)),
    }


def _next_period(value: datetime, granularity: str) -> datetime:
    if granularity == "HOURLY":
        return value + timedelta(hours=1)
    if granularity == "DAILY":
        return value + timedelta(days=1)
    if granularity == "WEEKLY":
        return value + timedelta(weeks=1)
    if granularity == "QUARTERLY":
        month = ((value.month - 1) // 3) * 3 + 4
        year = value.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        return value.replace(year=year, month=month, day=1)
    month = value.month + 1
    year = value.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return value.replace(year=year, month=month, day=1)


def _period_key(value: datetime, granularity: str) -> str:
    if granularity == "HOURLY":
        return value.strftime("%Y-%m-%dT%H:00:00Z")
    if granularity == "DAILY":
        return value.strftime("%Y-%m-%d")
    if granularity == "WEEKLY":
        iso = value.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if granularity == "MONTHLY":
        return value.strftime("%Y-%m")
    if granularity == "QUARTERLY":
        return f"{value.year}-Q{((value.month - 1) // 3) + 1}"
    return value.isoformat()


def _missing_periods(
    rows: list[TrendObservation],
) -> tuple[int | None, int | None, Decimal | None, list[str]]:
    if len(rows) < 2 or rows[0].granularity not in TIME_GRANULARITIES:
        return (
            None,
            (
                len({_period_key(_period_value(row), rows[0].granularity) for row in rows})
                if rows
                else 0
            ),
            None,
            [],
        )
    granularity = rows[0].granularity
    values = sorted({_period_value(row) for row in rows})
    observed = {_period_key(value, granularity) for value in values}
    cursor = values[0]
    expected: list[str] = []
    while cursor <= values[-1] and len(expected) <= 10000:
        expected.append(_period_key(cursor, granularity))
        cursor = _next_period(cursor, granularity)
    missing = [item for item in expected if item not in observed]
    expected_count = len(expected)
    return (
        expected_count,
        len(observed),
        Decimal(len(observed)) / expected_count if expected_count else None,
        missing,
    )


def _freshness(rows: list[TrendObservation]) -> str:
    values = {row.freshness_state for row in rows}
    if not values or values == {"UNKNOWN"}:
        return "UNKNOWN"
    if values == {"CURRENT"}:
        return "CURRENT"
    if values == {"STALE"}:
        return "STALE"
    return "MIXED"


def _series_payload(rows: list[TrendObservation]) -> dict[str, object]:
    rows.sort(key=lambda row: (_period_value(row), str(row.id)))
    sample_size = len(rows)
    numeric = rows[0].measurement_type in NUMERIC_TYPES and all(
        row.value_numeric is not None for row in rows
    )
    values = [_decimal(row.value_numeric) for row in rows] if numeric else []
    numeric_values = [value for value in values if value is not None]
    moves = _movement(numeric_values) if numeric else []
    direction = (
        _direction(moves, sample_size)
        if numeric
        else ("INSUFFICIENT_EVIDENCE" if sample_size < 2 else "MIXED")
    )
    persistence = _persistence(moves, sample_size) if numeric else "INSUFFICIENT_EVIDENCE"
    variability_state, variability = _variability(numeric_values) if numeric else ("UNKNOWN", {})
    expected, observed_periods, ratio, missing = _missing_periods(rows)
    limitations: list[str] = []
    if sample_size == 0:
        readiness = "INSUFFICIENT_EVIDENCE"
        limitations.append("NO_OBSERVATIONS")
    elif sample_size == 1:
        readiness = "PARTIAL"
        limitations.extend(["SINGLE_OBSERVATION", "INSUFFICIENT_HISTORY"])
    elif not numeric and rows[0].measurement_type not in {"BOOLEAN", "CATEGORY", "ORDINAL"}:
        readiness = "UNSUPPORTED"
        limitations.append("UNSUPPORTED_VALUE_TYPE")
    else:
        readiness = "AVAILABLE" if not missing else "PARTIAL"
    statistics = (
        _numeric_statistics(numeric_values)
        if numeric_values
        else {
            "count": sample_size,
            "first": (
                rows[0].value_boolean
                if rows[0].measurement_type == "BOOLEAN"
                else rows[0].value_text
            ),
            "latest": (
                rows[-1].value_boolean
                if rows[-1].measurement_type == "BOOLEAN"
                else rows[-1].value_text
            ),
        }
    )
    change: dict[str, object] = {
        "baseline": None,
        "current": None,
        "absolute": None,
        "relative_percent": None,
        "relative_reason": None,
    }
    if numeric_values:
        baseline, current = numeric_values[0], numeric_values[-1]
        delta = current - baseline
        change.update(
            {
                "baseline": _number(baseline),
                "current": _number(current),
                "absolute": _number(delta),
                "sample_size": sample_size,
            }
        )
        if baseline == 0:
            change["relative_reason"] = "ZERO_DENOMINATOR"
        else:
            change["relative_percent"] = _number((delta / baseline) * Decimal(100))
    movement_counts = Counter(moves)
    movement = {
        "increase_count": movement_counts.get(1, 0),
        "decrease_count": movement_counts.get(-1, 0),
        "unchanged_count": movement_counts.get(0, 0),
        "reversal_count": sum(
            1
            for left, right in zip(moves, moves[1:], strict=False)
            if left and right and left != right
        ),
        "latest_direction": (
            "INCREASING"
            if moves and moves[-1] > 0
            else "DECREASING" if moves and moves[-1] < 0 else "STABLE" if moves else "UNKNOWN"
        ),
    }
    return {
        "readiness": readiness,
        "direction": direction,
        "persistence": persistence,
        "variability_state": variability_state,
        "variability": variability,
        "freshness_state": _freshness(rows),
        "sample_size": sample_size,
        "statistics": statistics,
        "change": change,
        "movement": movement,
        "expected_period_count": expected,
        "observed_period_count": observed_periods,
        "missing_period_count": len(missing),
        "coverage_ratio": _number(ratio),
        "missing_periods": missing,
        "limitations": limitations,
        "time_start": _period_value(rows[0]) if rows else None,
        "time_end": _period_value(rows[-1]) if rows else None,
    }


def _analysis_or_404(db: Session, owner: User, analysis_id: uuid.UUID) -> TrendAnalysis:
    value = db.scalar(
        select(TrendAnalysis).where(
            TrendAnalysis.id == analysis_id, TrendAnalysis.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(status_code=404, detail="Trend analysis not found.")
    return value


def create_analysis(
    db: Session, owner: User, context: TrendContext, data: TrendAnalysisCreate
) -> TrendAnalysis:
    snapshot = db.scalar(
        select(TrendSnapshot).where(
            TrendSnapshot.id == data.snapshot_id,
            TrendSnapshot.owner_id == owner.id,
            TrendSnapshot.context_id == context.id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Trend snapshot not found.")
    fingerprint = _fingerprint(
        {
            "snapshot_id": str(snapshot.id),
            "calculation_version": data.calculation_version,
            "signal": data.signal,
            "source_id": str(data.source_id) if data.source_id else None,
            "geography": data.geography,
            "granularity": data.granularity,
        }
    )
    existing = db.scalar(
        select(TrendAnalysis).where(
            TrendAnalysis.owner_id == owner.id,
            TrendAnalysis.context_id == context.id,
            TrendAnalysis.input_fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    observation_ids = [uuid.UUID(value) for value in snapshot.observation_ids]
    rows = (
        list(
            db.scalars(
                select(TrendObservation).where(
                    TrendObservation.owner_id == owner.id,
                    TrendObservation.context_id == context.id,
                    TrendObservation.id.in_(observation_ids),
                )
            )
        )
        if observation_ids
        else []
    )
    signal_types = {
        str(item.id): item.signal_type
        for item in db.scalars(
            select(TrendSignalDefinition).where(TrendSignalDefinition.owner_id == owner.id)
        )
    }
    selected: list[TrendObservation] = []
    excluded: Counter[str] = Counter()
    for row in rows:
        if (
            data.signal
            and str(row.signal_definition_id) != data.signal
            and signal_types.get(str(row.signal_definition_id)) != data.signal
            and row.canonical_metadata.get("signal_type") != data.signal
        ):
            excluded["INCOMPATIBLE_SIGNAL"] += 1
            continue
        if data.source_id and row.source_id != data.source_id:
            excluded["INCOMPATIBLE_SIGNAL"] += 1
            continue
        if data.geography and row.geography_scope != data.geography:
            excluded["INCOMPATIBLE_GEOGRAPHY"] += 1
            continue
        if data.granularity and row.granularity != data.granularity:
            excluded["INCOMPATIBLE_GRANULARITY"] += 1
            continue
        if row.quality_state == "INVALID":
            excluded["INSUFFICIENT_QUALITY"] += 1
            continue
        selected.append(row)
    groups: dict[tuple[object, ...], list[TrendObservation]] = defaultdict(list)
    for row in selected:
        groups[_cohort_key(row)].append(row)
    analysis_version = (
        db.scalar(
            select(func.max(TrendAnalysis.analysis_version)).where(
                TrendAnalysis.owner_id == owner.id, TrendAnalysis.context_id == context.id
            )
        )
        or 0
    ) + 1
    all_payloads = [_series_payload(list(group)) for group in groups.values()]
    incompatible = len(groups) > 1
    readiness = (
        "INSUFFICIENT_EVIDENCE"
        if not selected
        else "NOT_COMPARABLE" if incompatible else all_payloads[0]["readiness"]
    )
    if (
        selected
        and not incompatible
        and any(item["readiness"] == "PARTIAL" for item in all_payloads)
    ):
        readiness = "PARTIAL"
    freshness = _freshness(selected)
    min_period = min((_period_value(row) for row in selected), default=None)
    max_period = max((_period_value(row) for row in selected), default=None)
    analysis = TrendAnalysis(
        owner_id=owner.id,
        context_id=context.id,
        snapshot_id=snapshot.id,
        analysis_version=analysis_version,
        calculation_version=data.calculation_version,
        input_fingerprint=fingerprint,
        status="COMPLETED",
        readiness=readiness,
        included_observation_count=len(selected),
        excluded_observation_count=len(rows) - len(selected),
        included_reasons={"included": len(selected)},
        excluded_reasons=dict(excluded),
        time_coverage={
            "start": min_period.isoformat() if min_period else None,
            "end": max_period.isoformat() if max_period else None,
        },
        source_coverage={
            "source_count": len({str(row.source_id) for row in selected}),
            "observations_per_source": dict(Counter(str(row.source_id) for row in selected)),
        },
        signal_coverage={
            "signal_count": len({str(row.signal_definition_id) for row in selected}),
            "observations_per_signal": dict(
                Counter(str(row.signal_definition_id) for row in selected)
            ),
        },
        summary={
            "description": "Descriptive analysis of observed signal history.",
            "series_count": len(groups),
        },
        limitations=[],
        freshness_state=freshness,
        created_at=_now(),
    )
    if len(rows) == 0:
        analysis.limitations.append("NO_OBSERVATIONS")
    if len(groups) > 1:
        analysis.limitations.append("INCOMPATIBLE_SERIES_RETAINED_SEPARATELY")
    db.add(analysis)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(TrendAnalysis).where(
                TrendAnalysis.owner_id == owner.id,
                TrendAnalysis.context_id == context.id,
                TrendAnalysis.input_fingerprint == fingerprint,
            )
        )
        if existing is not None:
            return existing
        raise
    record_event(
        db,
        actor_id=owner.id,
        action="trend.analysis_created",
        entity_type="trend_analysis",
        entity_id=analysis.id,
        metadata={"calculation_version": data.calculation_version, "snapshot_id": str(snapshot.id)},
        idempotency_key=f"trend-analysis:{owner.id}:{fingerprint}",
    )
    for key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        payload = cast(dict[str, Any], _series_payload(list(group)))
        cohort_fingerprint = _fingerprint(key)
        first = group[0]
        series = TrendAnalysisSeries(
            owner_id=owner.id,
            analysis_id=analysis.id,
            context_id=context.id,
            signal_definition_id=first.signal_definition_id,
            source_id=first.source_id,
            cohort_fingerprint=cohort_fingerprint,
            measurement_type=first.measurement_type,
            unit=first.unit,
            scale=first.scale,
            geography_scope=first.geography_scope,
            country=first.country,
            region=first.region,
            city=first.city,
            marketplace=first.marketplace,
            granularity=first.granularity,
            readiness=payload["readiness"],
            direction=payload["direction"],
            persistence=payload["persistence"],
            variability_state=payload["variability_state"],
            freshness_state=payload["freshness_state"],
            sample_size=payload["sample_size"],
            included_observation_count=payload["sample_size"],
            excluded_observation_count=0,
            time_start=payload["time_start"],
            time_end=payload["time_end"],
            expected_period_count=payload["expected_period_count"],
            observed_period_count=payload["observed_period_count"],
            missing_period_count=payload["missing_period_count"],
            coverage_ratio=(
                Decimal(payload["coverage_ratio"]) if payload["coverage_ratio"] else None
            ),
            statistics={**payload["statistics"], "variability": payload["variability"]},
            change=payload["change"],
            movement=payload["movement"],
            missing_periods=payload["missing_periods"],
            limitations=payload["limitations"],
            observation_ids=[str(row.id) for row in group],
            evidence_ids=[str(row.evidence_id) for row in group if row.evidence_id],
            created_at=_now(),
        )
        db.add(series)
        db.flush()
        for gap_type, detail in (
            ("SINGLE_OBSERVATION", {"sample_size": 1}),
            ("INSUFFICIENT_HISTORY", {"sample_size": payload["sample_size"]}),
            ("MISSING_PERIODS", {"missing_periods": payload["missing_periods"]}),
            ("STALE_EVIDENCE", {"freshness_state": payload["freshness_state"]}),
            ("UNKNOWN_FRESHNESS", {"freshness_state": payload["freshness_state"]}),
        ):
            should_add = (
                (gap_type == "SINGLE_OBSERVATION" and payload["sample_size"] == 1)
                or (gap_type == "INSUFFICIENT_HISTORY" and payload["sample_size"] < 2)
                or (gap_type == "MISSING_PERIODS" and payload["missing_period_count"] > 0)
                or (gap_type == "STALE_EVIDENCE" and payload["freshness_state"] == "STALE")
                or (gap_type == "UNKNOWN_FRESHNESS" and payload["freshness_state"] == "UNKNOWN")
            )
            if should_add:
                db.add(
                    TrendAnalysisGap(
                        owner_id=owner.id,
                        analysis_id=analysis.id,
                        series_id=series.id,
                        gap_type=gap_type,
                        detail=detail,
                        created_at=_now(),
                    )
                )
    if not selected:
        db.add(
            TrendAnalysisGap(
                owner_id=owner.id,
                analysis_id=analysis.id,
                series_id=None,
                gap_type="NO_OBSERVATIONS",
                detail={},
                created_at=_now(),
            )
        )
    if incompatible:
        db.add(
            TrendAnalysisGap(
                owner_id=owner.id,
                analysis_id=analysis.id,
                series_id=None,
                gap_type="INCOMPATIBLE_UNITS",
                detail={"series_count": len(groups)},
                created_at=_now(),
            )
        )
    if len({str(row.source_id) for row in selected}) == 1 and selected:
        db.add(
            TrendAnalysisGap(
                owner_id=owner.id,
                analysis_id=analysis.id,
                series_id=None,
                gap_type="SINGLE_SOURCE_ONLY",
                detail={},
                created_at=_now(),
            )
        )
    db.commit()
    db.refresh(analysis)
    return analysis


def analysis_or_404(db: Session, owner: User, analysis_id: uuid.UUID) -> TrendAnalysis:
    return _analysis_or_404(db, owner, analysis_id)


def list_analyses(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[TrendAnalysis], int]:
    query = (
        select(TrendAnalysis)
        .where(TrendAnalysis.owner_id == owner.id, TrendAnalysis.context_id == context_id)
        .order_by(TrendAnalysis.created_at.desc(), TrendAnalysis.id.desc())
    )
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    return list(db.scalars(query.offset(offset).limit(limit))), total


def current_analysis(db: Session, owner: User, context_id: uuid.UUID) -> TrendAnalysis | None:
    return db.scalar(
        select(TrendAnalysis)
        .where(TrendAnalysis.owner_id == owner.id, TrendAnalysis.context_id == context_id)
        .order_by(TrendAnalysis.created_at.desc(), TrendAnalysis.id.desc())
    )


def list_series(
    db: Session,
    owner: User,
    analysis: TrendAnalysis,
    limit: int,
    offset: int,
    signal: str | None = None,
    source_id: uuid.UUID | None = None,
    geography: str | None = None,
    granularity: str | None = None,
    direction: str | None = None,
    readiness: str | None = None,
) -> tuple[list[TrendAnalysisSeries], int]:
    query = select(TrendAnalysisSeries).where(
        TrendAnalysisSeries.owner_id == owner.id, TrendAnalysisSeries.analysis_id == analysis.id
    )
    if signal:
        query = query.join(
            TrendSignalDefinition,
            TrendSignalDefinition.id == TrendAnalysisSeries.signal_definition_id,
        ).where(TrendSignalDefinition.signal_type == signal)
    if source_id:
        query = query.where(TrendAnalysisSeries.source_id == source_id)
    if geography:
        query = query.where(TrendAnalysisSeries.geography_scope == geography)
    if granularity:
        query = query.where(TrendAnalysisSeries.granularity == granularity)
    if direction:
        query = query.where(TrendAnalysisSeries.direction == direction)
    if readiness:
        query = query.where(TrendAnalysisSeries.readiness == readiness)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    return (
        list(
            db.scalars(
                query.order_by(TrendAnalysisSeries.time_start, TrendAnalysisSeries.id)
                .offset(offset)
                .limit(limit)
            )
        ),
        total,
    )


def list_gaps(
    db: Session, owner: User, analysis: TrendAnalysis, limit: int, offset: int
) -> list[TrendAnalysisGap]:
    return list(
        db.scalars(
            select(TrendAnalysisGap)
            .where(
                TrendAnalysisGap.owner_id == owner.id, TrendAnalysisGap.analysis_id == analysis.id
            )
            .order_by(TrendAnalysisGap.created_at, TrendAnalysisGap.id)
            .offset(offset)
            .limit(limit)
        )
    )


def analysis_operations(db: Session, owner: User) -> dict[str, object]:
    rows = list(db.scalars(select(TrendAnalysis).where(TrendAnalysis.owner_id == owner.id)))
    series_count = (
        db.scalar(
            select(func.count())
            .select_from(TrendAnalysisSeries)
            .where(TrendAnalysisSeries.owner_id == owner.id)
        )
        or 0
    )
    gap_count = (
        db.scalar(
            select(func.count())
            .select_from(TrendAnalysisGap)
            .where(TrendAnalysisGap.owner_id == owner.id)
        )
        or 0
    )
    return {
        "analysis_count": len(rows),
        "current_analyses": len({str(row.context_id) for row in rows}),
        "insufficient_evidence_analyses": sum(
            row.readiness == "INSUFFICIENT_EVIDENCE" for row in rows
        ),
        "not_comparable_analyses": sum(row.readiness == "NOT_COMPARABLE" for row in rows),
        "stale_analyses": sum(row.freshness_state in {"STALE", "MIXED"} for row in rows),
        "series_count": int(series_count),
        "evidence_gap_count": int(gap_count),
        "latest_analysis_activity": max((row.created_at for row in rows), default=None),
    }


def analysis_doctor(db: Session, owner: User) -> dict[str, int]:
    """Return hard, owner-scoped integrity counters for 12C."""
    counters = {
        "orphan_trend_analysis": 0,
        "cross_owner_analysis_context": 0,
        "analysis_without_snapshot": 0,
        "snapshot_context_mismatch": 0,
        "orphan_series_result": 0,
        "series_without_analysis": 0,
        "series_observation_outside_snapshot": 0,
        "superseded_correction_as_independent_sample": 0,
        "mixed_incompatible_measurement_types": 0,
        "mixed_incompatible_units": 0,
        "mixed_incompatible_scales": 0,
        "mixed_incompatible_geography": 0,
        "mixed_incompatible_granularity": 0,
        "invalid_sample_count": 0,
        "included_excluded_mismatch": 0,
        "invalid_decimal_statistics": 0,
        "relative_change_zero_denominator": 0,
        "invalid_direction": 0,
        "invalid_persistence": 0,
        "invalid_variability_state": 0,
        "single_observation_persistent": 0,
        "single_observation_direction": 0,
        "missing_history_stable": 0,
        "analysis_forecast_output": 0,
        "analysis_seasonality_output": 0,
        "analysis_demand_output": 0,
        "analysis_sales_output": 0,
        "analysis_revenue_output": 0,
        "analysis_winning_product_score": 0,
        "analysis_generic_trend_score": 0,
        "broken_evidence_lineage": 0,
        "duplicate_logical_analysis": 0,
        "external_write_exposure": 0,
    }
    analyses = list(db.scalars(select(TrendAnalysis).where(TrendAnalysis.owner_id == owner.id)))
    series = list(
        db.scalars(select(TrendAnalysisSeries).where(TrendAnalysisSeries.owner_id == owner.id))
    )
    snapshots = {
        row.id: row
        for row in db.scalars(select(TrendSnapshot).where(TrendSnapshot.owner_id == owner.id))
    }
    contexts = {
        row.id: row
        for row in db.scalars(select(TrendContext).where(TrendContext.owner_id == owner.id))
    }
    observations = {
        row.id: row
        for row in db.scalars(select(TrendObservation).where(TrendObservation.owner_id == owner.id))
    }
    fingerprint_counts = Counter(row.input_fingerprint for row in analyses)
    counters["duplicate_logical_analysis"] = sum(
        value - 1 for value in fingerprint_counts.values() if value > 1
    )
    analysis_ids = {row.id for row in analyses}
    for analysis in analyses:
        snapshot = snapshots.get(analysis.snapshot_id)
        if snapshot is None:
            counters["analysis_without_snapshot"] += 1
            counters["orphan_trend_analysis"] += 1
            continue
        if snapshot.context_id != analysis.context_id:
            counters["snapshot_context_mismatch"] += 1
        if analysis.context_id not in contexts:
            counters["cross_owner_analysis_context"] += 1
        if analysis.included_observation_count + analysis.excluded_observation_count != len(
            set(snapshot.observation_ids)
        ):
            counters["included_excluded_mismatch"] += 1
        forbidden = json.dumps(
            {"summary": analysis.summary, "limitations": analysis.limitations}
        ).lower()
        for key, tokens in {
            "analysis_forecast_output": ("forecast", "prediction"),
            "analysis_seasonality_output": ("seasonal", "seasonality"),
            "analysis_demand_output": ("demand",),
            "analysis_sales_output": ("sales",),
            "analysis_revenue_output": ("revenue",),
            "analysis_winning_product_score": ("winning product",),
            "analysis_generic_trend_score": ("trend score", "momentum score"),
        }.items():
            if any(token in forbidden for token in tokens):
                counters[key] += 1
    for row in series:
        if row.analysis_id not in analysis_ids:
            counters["series_without_analysis"] += 1
        analysis_match = next((item for item in analyses if item.id == row.analysis_id), None)
        snapshot_ids = (
            set(snapshots[analysis_match.snapshot_id].observation_ids)
            if analysis_match and analysis_match.snapshot_id in snapshots
            else set()
        )
        if any(value not in snapshot_ids for value in row.observation_ids):
            counters["series_observation_outside_snapshot"] += 1
        if (
            row.sample_size != len(row.observation_ids)
            or row.included_observation_count != row.sample_size
        ):
            counters["invalid_sample_count"] += 1
        if row.measurement_type not in NUMERIC_TYPES:
            if row.direction not in {"MIXED", "INSUFFICIENT_EVIDENCE"}:
                counters["invalid_direction"] += 1
            continue
        if row.direction not in DIRECTION_STATES:
            counters["invalid_direction"] += 1
        if row.persistence not in PERSISTENCE_STATES:
            counters["invalid_persistence"] += 1
        if row.variability_state not in {
            "STABLE",
            "LOW_VARIABILITY",
            "MODERATE_VARIABILITY",
            "HIGH_VARIABILITY",
            "UNKNOWN",
        }:
            counters["invalid_variability_state"] += 1
        change = row.change or {}
        try:
            for key in ("baseline", "current", "absolute", "relative_percent"):
                value = change.get(key)
                if value is not None and not Decimal(str(value)).is_finite():
                    counters["invalid_decimal_statistics"] += 1
        except Exception:
            counters["invalid_decimal_statistics"] += 1
        if (
            str(change.get("baseline")) in {"0", "0.0", "0.00"}
            and change.get("relative_percent") is not None
        ):
            counters["relative_change_zero_denominator"] += 1
        if row.sample_size == 1 and row.persistence not in {"INSUFFICIENT_EVIDENCE", "UNKNOWN"}:
            counters["single_observation_persistent"] += 1
        if row.sample_size == 1 and row.direction not in {"INSUFFICIENT_EVIDENCE", "UNKNOWN"}:
            counters["single_observation_direction"] += 1
        if row.missing_period_count and row.direction == "STABLE":
            counters["missing_history_stable"] += 1
        provider_ids = [
            observations[uuid.UUID(value)].provider_observation_id
            for value in row.observation_ids
            if uuid.UUID(value) in observations
            and observations[uuid.UUID(value)].provider_observation_id
        ]
        if len(provider_ids) != len(set(provider_ids)):
            counters["superseded_correction_as_independent_sample"] += 1
    return counters
