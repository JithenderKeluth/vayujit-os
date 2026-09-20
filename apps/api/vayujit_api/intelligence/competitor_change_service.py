"""Deterministic, evidence-backed competitive change comparison (Slice 10D)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_change_models import (
    ALERT_ELIGIBILITY,
    CALCULATION_VERSION,
    CHANGE_STATUSES,
    CHANGE_TYPES,
    MATERIALITY_LEVELS,
    MATERIALITY_POLICY_VERSION,
    CompetitorChangeAlertEligibility,
    CompetitorChangeComparison,
    CompetitorChangeEvent,
)
from vayujit_api.intelligence.competitor_change_schemas import (
    ChangeComparisonCreate,
    ChangeReviewRequest,
)
from vayujit_api.intelligence.competitor_commercial_models import CompetitorCommercialAnalysis
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorObservation,
    CompetitorProduct,
)
from vayujit_api.intelligence.competitor_service import get_context


def _now() -> datetime:
    return datetime.now(UTC)


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json(item) for item in value]
    return value


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_json(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _audit(
    db: Session,
    owner: User,
    action: str,
    entity_id: uuid.UUID,
    key: str,
    metadata: dict[str, object] | None = None,
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.{action.casefold()}",
        entity_type="competitor_change_comparison",
        entity_id=entity_id,
        metadata={"event_type": action, "entity_id": str(entity_id), **(metadata or {})},
        idempotency_key=key,
    )


def _analysis(db: Session, owner: User, analysis_id: uuid.UUID) -> CompetitorCommercialAnalysis:
    value = db.scalar(
        select(CompetitorCommercialAnalysis).where(
            CompetitorCommercialAnalysis.id == analysis_id,
            CompetitorCommercialAnalysis.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Commercial analysis not found.")
    return value


def _analysis_pair(
    db: Session, owner: User, context_id: uuid.UUID, data: ChangeComparisonCreate
) -> tuple[CompetitorCommercialAnalysis, CompetitorCommercialAnalysis]:
    baseline = (
        _analysis(db, owner, data.baseline_analysis_id) if data.baseline_analysis_id else None
    )
    current = _analysis(db, owner, data.current_analysis_id) if data.current_analysis_id else None
    rows = list(
        db.scalars(
            select(CompetitorCommercialAnalysis)
            .where(
                CompetitorCommercialAnalysis.owner_id == owner.id,
                CompetitorCommercialAnalysis.context_id == context_id,
            )
            .order_by(
                CompetitorCommercialAnalysis.analysis_version.desc(),
                CompetitorCommercialAnalysis.created_at.desc(),
            )
            .limit(2)
        )
    )
    if current is None:
        current = rows[0] if rows else None
    if baseline is None and current is not None:
        baseline = (
            rows[1]
            if len(rows) > 1 and rows[0].id == current.id
            else (rows[0] if rows and rows[0].id != current.id else None)
        )
    if baseline is None or current is None or baseline.id == current.id:
        raise HTTPException(409, "Two distinct commercial analyses are required for comparison.")
    if baseline.context_id != context_id or current.context_id != context_id:
        raise HTTPException(404, "Commercial analysis does not belong to this context.")
    if baseline.analysis_version >= current.analysis_version:
        baseline, current = current, baseline
    return baseline, current


def _ids(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _product_ids(analysis: CompetitorCommercialAnalysis) -> set[str]:
    ids = (
        analysis.cohort_summary.get("included_product_ids")
        if isinstance(analysis.cohort_summary, dict)
        else None
    )
    if isinstance(ids, list):
        return {str(item) for item in ids}
    return set()


def _input_products(analysis: CompetitorCommercialAnalysis) -> dict[str, dict[str, object]]:
    value = (
        analysis.input_snapshot.get("products")
        if isinstance(analysis.input_snapshot, dict)
        else None
    )
    if not isinstance(value, list):
        return {}
    return {
        str(item.get("id")): cast(dict[str, object], item)
        for item in value
        if isinstance(item, dict) and item.get("id")
    }


def _observations(
    db: Session, owner: User, analysis: CompetitorCommercialAnalysis, product_id: uuid.UUID
) -> list[CompetitorObservation]:
    entry = _input_products(analysis).get(str(product_id), {})
    ids = [uuid.UUID(str(item)) for item in _ids(entry.get("observation_ids")) if _valid_uuid(item)]
    if ids:
        return list(
            db.scalars(
                select(CompetitorObservation)
                .where(
                    CompetitorObservation.owner_id == owner.id,
                    CompetitorObservation.id.in_(ids),
                )
                .order_by(CompetitorObservation.observed_at.asc())
            )
        )
    return list(
        db.scalars(
            select(CompetitorObservation)
            .where(
                CompetitorObservation.owner_id == owner.id,
                CompetitorObservation.competitor_product_id == product_id,
            )
            .order_by(CompetitorObservation.observed_at.asc())
            .limit(200)
        )
    )


def _valid_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _product_state(
    db: Session,
    owner: User,
    analysis: CompetitorCommercialAnalysis,
    product_id: uuid.UUID,
    *,
    product_cache: dict[uuid.UUID, CompetitorProduct] | None = None,
    observation_cache: dict[uuid.UUID, list[CompetitorObservation]] | None = None,
) -> dict[str, object]:
    product = (
        product_cache.get(product_id)
        if product_cache is not None
        else db.scalar(
            select(CompetitorProduct).where(
                CompetitorProduct.owner_id == owner.id,
                CompetitorProduct.id == product_id,
            )
        )
    )
    if observation_cache is None:
        observations = _observations(db, owner, analysis, product_id)
    else:
        entry = _input_products(analysis).get(str(product_id), {})
        ids = {
            uuid.UUID(str(item)) for item in _ids(entry.get("observation_ids")) if _valid_uuid(item)
        }
        available = observation_cache.get(product_id, [])
        observations = [item for item in available if not ids or item.id in ids][:200]
    by_kind: dict[str, list[CompetitorObservation]] = {}
    for item in observations:
        by_kind.setdefault(item.observation_type.casefold(), []).append(item)

    def latest(kinds: set[str]) -> CompetitorObservation | None:
        values = [item for key, rows in by_kind.items() if key in kinds for item in rows]
        return values[-1] if values else None

    price = latest({"price", "listed_price", "selling_price", "sale_price"})
    rating = latest({"rating", "ratings"})
    reviews = latest({"review_count", "reviews"})
    availability = latest({"availability", "availability_state", "stock"})
    price_values: list[CompetitorObservation] = [
        item
        for key, rows in by_kind.items()
        if key in {"price", "listed_price", "selling_price", "sale_price"}
        for item in rows
        if item.numeric_value is not None
    ]
    price_contradictory = any(
        left.observed_at == right.observed_at
        and _decimal(left.numeric_value) != _decimal(right.numeric_value)
        for index, left in enumerate(price_values)
        for right in price_values[index + 1 :]
    )
    return {
        "product": product,
        "observations": observations,
        "price": price,
        "rating": rating,
        "reviews": reviews,
        "availability": availability,
        "price_value": _decimal(price.numeric_value) if price else None,
        "price_currency": (price.currency or "UNKNOWN").upper() if price else None,
        "price_contradictory": price_contradictory,
        "rating_value": _decimal(rating.numeric_value) if rating else None,
        "review_value": _decimal(reviews.numeric_value) if reviews else None,
        "availability_value": (
            availability.observed_value.get("value")
            if availability and isinstance(availability.observed_value, dict)
            else None
        )
        or (availability.numeric_value if availability else None)
        or (product.availability_state if product else "UNKNOWN"),
        "freshness": (
            "STALE"
            if any(item.freshness_state == "STALE" for item in observations)
            else (
                "CURRENT"
                if any(item.freshness_state == "CURRENT" for item in observations)
                else "UNKNOWN"
            )
        ),
        "evidence": "AVAILABLE" if observations else "UNKNOWN",
        "first_observed": observations[0].observed_at if observations else None,
        "last_observed": observations[-1].observed_at if observations else None,
    }


def _number(value: object) -> Decimal | None:
    return _decimal(value)


def _delta(old: Decimal | None, new: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    if old is None or new is None:
        return None, None
    absolute = new - old
    if old == 0:
        return absolute, None
    return absolute, (absolute / old) * Decimal("100")


def _materiality(
    change_type: str, absolute: Decimal | None, percentage: Decimal | None, *, unknown: bool = False
) -> str:
    if unknown:
        return "UNKNOWN"
    magnitude = (
        abs(percentage)
        if percentage is not None
        else abs(absolute) if absolute is not None else None
    )
    if magnitude is None:
        return "UNKNOWN"
    if change_type.startswith("PRICE_"):
        return (
            "HIGH"
            if magnitude >= 20
            else "MODERATE" if magnitude >= 10 else "LOW" if magnitude >= 5 else "IMMATERIAL"
        )
    if change_type == "RATING_CHANGED":
        return (
            "HIGH"
            if magnitude >= 1
            else (
                "MODERATE"
                if magnitude >= Decimal("0.5")
                else "LOW" if magnitude >= Decimal("0.2") else "IMMATERIAL"
            )
        )
    if change_type == "REVIEW_COUNT_CHANGED":
        return (
            "HIGH"
            if (percentage is not None and magnitude >= 100)
            else (
                "MODERATE"
                if (percentage is not None and magnitude >= 50)
                else "LOW" if magnitude >= 25 else "IMMATERIAL"
            )
        )
    if "CONCENTRATION" in change_type:
        return (
            "HIGH"
            if magnitude >= Decimal("0.20")
            else (
                "MODERATE"
                if magnitude >= Decimal("0.10")
                else "LOW" if magnitude >= Decimal("0.05") else "IMMATERIAL"
            )
        )
    return "MODERATE"


def _alert(materiality: str, evidence: str, freshness: str, status: str) -> tuple[str, str]:
    if status in {"UNRESOLVED", "POSSIBLY_REMOVED"} or evidence in {
        "UNKNOWN",
        "INSUFFICIENT_EVIDENCE",
        "CONTRADICTORY_EVIDENCE",
    }:
        return "NO_ALERT", "Evidence is insufficient or unresolved."
    if materiality == "HIGH" and freshness == "CURRENT":
        return "ALERT", "High materiality with current evidence."
    if materiality in {"MODERATE", "LOW"}:
        return "REVIEW", "Material change requires human review."
    return "NO_ALERT", "Change is immaterial or unknown."


def _event_payload(
    change_type: str,
    product_id: str | None,
    old: object,
    new: object,
    baseline: uuid.UUID,
    current: uuid.UUID,
) -> str:
    return _fingerprint(
        {
            "change_type": change_type,
            "product_id": product_id,
            "old": old,
            "new": new,
            "baseline": baseline,
            "current": current,
            "version": CALCULATION_VERSION,
        }
    )


def _new_event(
    db: Session,
    owner: User,
    context: CompetitorContext,
    comparison: CompetitorChangeComparison,
    *,
    change_type: str,
    product_id: uuid.UUID | None,
    old: object,
    new: object,
    old_numeric: Decimal | None = None,
    new_numeric: Decimal | None = None,
    unit: str | None = None,
    currency: str | None = None,
    baseline_reference: str | None = None,
    current_reference: str | None = None,
    evidence_references: dict[str, object] | None = None,
    first_observed: datetime | None = None,
    last_observed: datetime | None = None,
    freshness: str = "UNKNOWN",
    evidence: str = "UNKNOWN",
    verification: str = "UNKNOWN",
    observed_or_derived: str = "OBSERVED",
    forced_status: str | None = None,
) -> CompetitorChangeEvent | None:
    if change_type not in CHANGE_TYPES:
        return None
    absolute, percentage = _delta(old_numeric, new_numeric)
    currency_mismatch = (
        change_type.startswith("PRICE_")
        and old_numeric is not None
        and new_numeric is not None
        and currency is None
    )
    status = forced_status or (
        "UNRESOLVED"
        if currency_mismatch
        or evidence in {"UNKNOWN", "INSUFFICIENT_EVIDENCE", "CONTRADICTORY_EVIDENCE"}
        else "NEW"
    )
    materiality = _materiality(change_type, absolute, percentage, unknown=status == "UNRESOLVED")
    fingerprint = _event_payload(
        change_type,
        str(product_id) if product_id else None,
        old,
        new,
        comparison.baseline_analysis_id,
        comparison.current_analysis_id,
    )
    existing = db.scalar(
        select(CompetitorChangeEvent).where(
            CompetitorChangeEvent.owner_id == owner.id,
            CompetitorChangeEvent.event_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    previous = db.scalar(
        select(CompetitorChangeEvent)
        .where(
            CompetitorChangeEvent.owner_id == owner.id,
            CompetitorChangeEvent.context_id == context.id,
            CompetitorChangeEvent.product_id == product_id,
            CompetitorChangeEvent.change_type == change_type,
        )
        .order_by(CompetitorChangeEvent.created_at.desc())
        .limit(1)
    )
    persistence = (previous.persistence_count + 1) if previous else 1
    if (
        previous
        and previous.old_value == new
        and previous.new_value == old
        and status != "UNRESOLVED"
    ):
        status = "REVERTED"
    elif previous and previous.new_value == new and status == "NEW":
        status = "ONGOING"
    alert_eligibility, alert_reason = _alert(materiality, evidence, freshness, status)
    event = CompetitorChangeEvent(
        owner_id=owner.id,
        context_id=context.id,
        comparison_id=comparison.id,
        product_id=product_id,
        change_type=change_type,
        observed_or_derived=observed_or_derived,
        old_value=_json(old),
        new_value=_json(new),
        unit=unit,
        currency=currency,
        absolute_delta=absolute,
        percentage_delta=percentage,
        baseline_reference=baseline_reference,
        current_reference=current_reference,
        evidence_references=cast(dict[str, object], _json(evidence_references or {})),
        first_observed=first_observed,
        last_observed=last_observed,
        freshness_state=freshness,
        evidence_state=evidence,
        verification_state=verification,
        materiality=materiality,
        materiality_policy_version=MATERIALITY_POLICY_VERSION,
        status=status,
        confidence=Decimal("1") if evidence == "AVAILABLE" else Decimal("0"),
        alert_eligibility=alert_eligibility,
        alert_reason=alert_reason,
        persistence_count=persistence,
        previous_event_id=previous.id if previous else None,
        resolution_reference=(
            f"reverted-by:{comparison.id}"
            if status == "REVERTED"
            else f"resolved-by:{comparison.id}" if status == "RESOLVED" else None
        ),
        calculation_version=CALCULATION_VERSION,
        event_fingerprint=fingerprint,
        created_at=_now(),
    )
    db.add(event)
    db.flush()
    db.add(
        CompetitorChangeAlertEligibility(
            owner_id=owner.id,
            context_id=context.id,
            event_id=event.id,
            eligibility=alert_eligibility,
            reason=alert_reason,
            created_at=_now(),
        )
    )
    return event


def _observation_reference(state: dict[str, object], key: str) -> str | None:
    value = state.get(key)
    return str(value.id) if isinstance(value, CompetitorObservation) else None


def _compare_numeric(
    db: Session,
    owner: User,
    context: CompetitorContext,
    comparison: CompetitorChangeComparison,
    baseline: dict[str, object],
    current: dict[str, object],
    product_id: uuid.UUID,
    key: str,
    change_type_up: str,
    change_type_down: str,
    unit: str | None = None,
) -> CompetitorChangeEvent | None:
    old = cast(Decimal | None, baseline.get(f"{key}_value"))
    new = cast(Decimal | None, current.get(f"{key}_value"))
    if old is None and new is None:
        return None
    if key == "price" and (
        baseline.get("price_contradictory") or current.get("price_contradictory")
    ):
        assert old is not None and new is not None
        return _new_event(
            db,
            owner,
            context,
            comparison,
            change_type=change_type_up if new >= old else change_type_down,
            product_id=product_id,
            old=old,
            new=new,
            old_numeric=None,
            new_numeric=None,
            unit=unit,
            currency=None,
            evidence_references={
                "baseline": _observation_reference(baseline, key),
                "current": _observation_reference(current, key),
            },
            first_observed=cast(datetime | None, baseline.get("first_observed")),
            last_observed=cast(datetime | None, current.get("last_observed")),
            freshness="UNKNOWN",
            evidence="CONTRADICTORY_EVIDENCE",
            verification="UNRESOLVED",
        )
    currency = cast(str | None, baseline.get("price_currency")) if key == "price" else None
    new_currency = cast(str | None, current.get("price_currency")) if key == "price" else currency
    comparable_currency = (
        currency
        if currency and new_currency and currency == new_currency and currency != "UNKNOWN"
        else None
    )
    if key == "price" and old is not None and new is not None and comparable_currency is None:
        return _new_event(
            db,
            owner,
            context,
            comparison,
            change_type=change_type_up if new >= old else change_type_down,
            product_id=product_id,
            old=old,
            new=new,
            old_numeric=None,
            new_numeric=None,
            unit=unit,
            currency=None,
            evidence_references={
                "baseline": _observation_reference(baseline, key),
                "current": _observation_reference(current, key),
            },
            first_observed=cast(datetime | None, baseline.get("first_observed")),
            last_observed=cast(datetime | None, current.get("last_observed")),
            freshness="UNKNOWN",
            evidence="CONTRADICTORY_EVIDENCE",
            verification="UNRESOLVED",
        )
    if old is None or new is None or old == new:
        return None
    return _new_event(
        db,
        owner,
        context,
        comparison,
        change_type=change_type_up if new > old else change_type_down,
        product_id=product_id,
        old=old,
        new=new,
        old_numeric=old,
        new_numeric=new,
        unit=unit,
        currency=comparable_currency,
        baseline_reference=_observation_reference(baseline, key),
        current_reference=_observation_reference(current, key),
        evidence_references={
            "baseline": _observation_reference(baseline, key),
            "current": _observation_reference(current, key),
        },
        first_observed=cast(datetime | None, baseline.get("first_observed")),
        last_observed=cast(datetime | None, current.get("last_observed")),
        freshness=(
            "STALE"
            if "STALE" in {baseline.get("freshness"), current.get("freshness")}
            else "CURRENT"
        ),
        evidence=(
            "AVAILABLE"
            if baseline.get("evidence") == current.get("evidence") == "AVAILABLE"
            else "UNKNOWN"
        ),
        verification="VERIFIED",
    )


def _section_scalar(analysis: CompetitorCommercialAnalysis, section: str, *keys: str) -> object:
    value: object = getattr(analysis, section) or {}
    if not isinstance(value, dict):
        return None
    for key in keys:
        if key in value:
            return value[key]
    return None


def _compare_aggregate(
    db: Session,
    owner: User,
    context: CompetitorContext,
    comparison: CompetitorChangeComparison,
    baseline: CompetitorCommercialAnalysis,
    current: CompetitorCommercialAnalysis,
) -> list[CompetitorChangeEvent]:
    events: list[CompetitorChangeEvent] = []
    metrics = (
        ("brand", "largest_share", "BRAND_CONCENTRATION_CHANGED"),
        ("seller", "largest_share", "SELLER_CONCENTRATION_CHANGED"),
    )
    for dimension, key, change_type in metrics:
        old = _section_scalar(baseline, "concentration_analysis", dimension, key)
        new = _section_scalar(current, "concentration_analysis", dimension, key)
        old_d, new_d = _number(old), _number(new)
        if old_d is not None and new_d is not None and old_d != new_d:
            event = _new_event(
                db,
                owner,
                context,
                comparison,
                change_type=change_type,
                product_id=None,
                old=old_d,
                new=new_d,
                old_numeric=old_d,
                new_numeric=new_d,
                unit="share",
                evidence_references={
                    "baseline_analysis_id": str(baseline.id),
                    "current_analysis_id": str(current.id),
                },
                freshness="CURRENT",
                evidence="AVAILABLE",
                verification="DERIVED_10C",
                observed_or_derived="DERIVED",
            )
            if event:
                events.append(event)
    old_position = _section_scalar(baseline, "positioning_analysis", "subject_position")
    new_position = _section_scalar(current, "positioning_analysis", "subject_position")
    if old_position and new_position and old_position != new_position:
        event = _new_event(
            db,
            owner,
            context,
            comparison,
            change_type="POSITIONING_CHANGED",
            product_id=None,
            old=old_position,
            new=new_position,
            evidence_references={
                "baseline_analysis_id": str(baseline.id),
                "current_analysis_id": str(current.id),
            },
            freshness="CURRENT",
            evidence="AVAILABLE",
            verification="DERIVED_10C",
            observed_or_derived="DERIVED",
        )
        if event:
            events.append(event)
    for section, key, change_type in (
        ("evidence_coverage", "overall", "EVIDENCE_COVERAGE_CHANGED"),
        ("freshness_summary", "overall", "FRESHNESS_CHANGED"),
    ):
        old_value = _section_scalar(baseline, section, key)
        new_value = _section_scalar(current, section, key)
        if old_value != new_value and (old_value is not None or new_value is not None):
            event = _new_event(
                db,
                owner,
                context,
                comparison,
                change_type=change_type,
                product_id=None,
                old=old_value,
                new=new_value,
                evidence_references={
                    "baseline_analysis_id": str(baseline.id),
                    "current_analysis_id": str(current.id),
                },
                freshness="CURRENT",
                evidence="AVAILABLE",
                verification="DERIVED_10C",
                observed_or_derived="DERIVED",
            )
            if event:
                events.append(event)
    old_contradictions = len(baseline.contradictions or [])
    new_contradictions = len(current.contradictions or [])
    if old_contradictions != new_contradictions:
        event = _new_event(
            db,
            owner,
            context,
            comparison,
            change_type="CONTRADICTION_CHANGED",
            product_id=None,
            old=old_contradictions,
            new=new_contradictions,
            old_numeric=Decimal(old_contradictions),
            new_numeric=Decimal(new_contradictions),
            evidence_references={
                "baseline_analysis_id": str(baseline.id),
                "current_analysis_id": str(current.id),
            },
            freshness="CURRENT",
            evidence="AVAILABLE",
            verification="DERIVED_10C",
            observed_or_derived="DERIVED",
        )
        if event:
            events.append(event)
    return events


def _compare_assortment(
    db: Session,
    owner: User,
    context: CompetitorContext,
    comparison: CompetitorChangeComparison,
    baseline: CompetitorCommercialAnalysis,
    current: CompetitorCommercialAnalysis,
) -> list[CompetitorChangeEvent]:
    events: list[CompetitorChangeEvent] = []
    old_dims = (
        (baseline.assortment_analysis or {}).get("dimensions", {})
        if isinstance(baseline.assortment_analysis, dict)
        else {}
    )
    new_dims = (
        (current.assortment_analysis or {}).get("dimensions", {})
        if isinstance(current.assortment_analysis, dict)
        else {}
    )
    if not isinstance(old_dims, dict):
        old_dims = {}
    if not isinstance(new_dims, dict):
        new_dims = {}
    for dimension in sorted(set(old_dims) | set(new_dims)):
        old_raw = cast(dict[str, object], old_dims.get(dimension) or {}).get("dominant_values", [])
        new_raw = cast(dict[str, object], new_dims.get(dimension) or {}).get("dominant_values", [])
        old_values = {str(value) for value in cast(list[object], old_raw or [])}
        new_values = {str(value) for value in cast(list[object], new_raw or [])}
        for value in sorted(new_values - old_values):
            event = _new_event(
                db,
                owner,
                context,
                comparison,
                change_type="ASSORTMENT_ATTRIBUTE_ADDED",
                product_id=None,
                old=None,
                new={"dimension": dimension, "value": value},
                evidence_references={
                    "baseline_analysis_id": str(baseline.id),
                    "current_analysis_id": str(current.id),
                },
                freshness="CURRENT",
                evidence="AVAILABLE",
                verification="DERIVED_10C",
                observed_or_derived="DERIVED",
            )
            if event:
                events.append(event)
        for value in sorted(old_values - new_values):
            event = _new_event(
                db,
                owner,
                context,
                comparison,
                change_type="ASSORTMENT_ATTRIBUTE_REMOVED",
                product_id=None,
                old={"dimension": dimension, "value": value},
                new=None,
                evidence_references={
                    "baseline_analysis_id": str(baseline.id),
                    "current_analysis_id": str(current.id),
                },
                freshness="CURRENT",
                evidence="AVAILABLE",
                verification="DERIVED_10C",
                observed_or_derived="DERIVED",
            )
            if event:
                events.append(event)
    return events


def run_comparison(
    db: Session, owner: User, context_id: uuid.UUID, data: ChangeComparisonCreate
) -> CompetitorChangeComparison:
    context = get_context(db, owner, context_id)
    baseline, current = _analysis_pair(db, owner, context_id, data)
    payload = {
        "context_id": str(context_id),
        "baseline_analysis_id": str(baseline.id),
        "current_analysis_id": str(current.id),
        "baseline_snapshot_id": (
            str(data.baseline_snapshot_id or baseline.discovery_snapshot_id)
            if data.baseline_snapshot_id or baseline.discovery_snapshot_id
            else None
        ),
        "current_snapshot_id": (
            str(data.current_snapshot_id or current.discovery_snapshot_id)
            if data.current_snapshot_id or current.discovery_snapshot_id
            else None
        ),
        "calculation_version": CALCULATION_VERSION,
    }
    fingerprint = _fingerprint(payload)
    if data.idempotency_key:
        existing = db.scalar(
            select(CompetitorChangeComparison).where(
                CompetitorChangeComparison.owner_id == owner.id,
                CompetitorChangeComparison.idempotency_key == data.idempotency_key,
            )
        )
        if existing:
            return existing
    existing = db.scalar(
        select(CompetitorChangeComparison).where(
            CompetitorChangeComparison.owner_id == owner.id,
            CompetitorChangeComparison.context_id == context_id,
            CompetitorChangeComparison.input_fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    version = (
        int(
            db.scalar(
                select(func.max(CompetitorChangeComparison.comparison_version)).where(
                    CompetitorChangeComparison.owner_id == owner.id,
                    CompetitorChangeComparison.context_id == context_id,
                )
            )
            or 0
        )
        + 1
    )
    comparison = CompetitorChangeComparison(
        owner_id=owner.id,
        context_id=context_id,
        baseline_analysis_id=baseline.id,
        current_analysis_id=current.id,
        baseline_snapshot_id=data.baseline_snapshot_id or baseline.discovery_snapshot_id,
        current_snapshot_id=data.current_snapshot_id or current.discovery_snapshot_id,
        comparison_version=version,
        calculation_version=CALCULATION_VERSION,
        status="COMPLETED",
        input_fingerprint=fingerprint,
        input_snapshot=cast(dict[str, object], _json(payload)),
        summary={},
        idempotency_key=data.idempotency_key or f"competitor-change:{context_id}:{fingerprint}",
        created_at=_now(),
    )
    db.add(comparison)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorChangeComparison).where(
                CompetitorChangeComparison.owner_id == owner.id,
                CompetitorChangeComparison.idempotency_key == comparison.idempotency_key,
            )
        )
        if existing is not None:
            return existing
        raise
    events: list[CompetitorChangeEvent] = []
    baseline_ids, current_ids = _product_ids(baseline), _product_ids(current)
    removed = baseline_ids - current_ids
    added = current_ids - baseline_ids
    explicit_removed = (
        set(_ids(current.input_snapshot.get("removed_product_ids")))
        if isinstance(current.input_snapshot, dict)
        else set()
    )
    for product_text in sorted(added):
        pid = uuid.UUID(product_text) if _valid_uuid(product_text) else None
        event = _new_event(
            db,
            owner,
            context,
            comparison,
            change_type="COMPETITOR_ADDED",
            product_id=pid,
            old=None,
            new={"product_id": product_text},
            evidence_references={
                "baseline_analysis_id": str(baseline.id),
                "current_analysis_id": str(current.id),
            },
            freshness="CURRENT",
            evidence="AVAILABLE",
            verification="VERIFIED",
        )
        if event:
            events.append(event)
    for product_text in sorted(removed):
        pid = uuid.UUID(product_text) if _valid_uuid(product_text) else None
        confirmed = product_text in explicit_removed
        event = _new_event(
            db,
            owner,
            context,
            comparison,
            change_type="COMPETITOR_REMOVED" if confirmed else "POSSIBLY_REMOVED",
            product_id=pid,
            old={"product_id": product_text},
            new=None,
            evidence_references={
                "baseline_analysis_id": str(baseline.id),
                "current_analysis_id": str(current.id),
            },
            freshness="UNKNOWN",
            evidence="UNKNOWN" if not confirmed else "AVAILABLE",
            verification="UNRESOLVED" if not confirmed else "VERIFIED",
            forced_status="UNRESOLVED" if not confirmed else "RESOLVED",
        )
        if event:
            events.append(event)
    shared_product_ids = [
        uuid.UUID(product_text)
        for product_text in sorted(baseline_ids & current_ids)
        if _valid_uuid(product_text)
    ]
    product_rows = (
        list(
            db.scalars(
                select(CompetitorProduct).where(
                    CompetitorProduct.owner_id == owner.id,
                    CompetitorProduct.id.in_(shared_product_ids),
                )
            )
        )
        if shared_product_ids
        else []
    )
    product_cache = {item.id: item for item in product_rows}
    observation_rows = (
        list(
            db.scalars(
                select(CompetitorObservation)
                .where(
                    CompetitorObservation.owner_id == owner.id,
                    CompetitorObservation.competitor_product_id.in_(shared_product_ids),
                )
                .order_by(CompetitorObservation.observed_at.asc())
            )
        )
        if shared_product_ids
        else []
    )
    observation_cache: dict[uuid.UUID, list[CompetitorObservation]] = {}
    for item in observation_rows:
        observation_cache.setdefault(item.competitor_product_id, []).append(item)
    for pid in shared_product_ids:
        old_state = _product_state(
            db,
            owner,
            baseline,
            pid,
            product_cache=product_cache,
            observation_cache=observation_cache,
        )
        new_state = _product_state(
            db,
            owner,
            current,
            pid,
            product_cache=product_cache,
            observation_cache=observation_cache,
        )
        for key, up, down, unit in (
            ("price", "PRICE_INCREASED", "PRICE_DECREASED", "amount"),
            ("rating", "RATING_CHANGED", "RATING_CHANGED", "rating"),
            ("review", "REVIEW_COUNT_CHANGED", "REVIEW_COUNT_CHANGED", "count"),
        ):
            event = _compare_numeric(
                db, owner, context, comparison, old_state, new_state, pid, key, up, down, unit
            )
            if event:
                events.append(event)
        old_avail, new_avail = old_state.get("availability_value"), new_state.get(
            "availability_value"
        )
        if old_avail != new_avail and (old_avail is not None or new_avail is not None):
            event = _new_event(
                db,
                owner,
                context,
                comparison,
                change_type="AVAILABILITY_CHANGED",
                product_id=pid,
                old=old_avail,
                new=new_avail,
                evidence_references={
                    "baseline_analysis_id": str(baseline.id),
                    "current_analysis_id": str(current.id),
                },
                first_observed=cast(datetime | None, old_state.get("first_observed")),
                last_observed=cast(datetime | None, new_state.get("last_observed")),
                freshness="CURRENT",
                evidence="AVAILABLE",
                verification="VERIFIED",
            )
            if event:
                events.append(event)
    events.extend(_compare_aggregate(db, owner, context, comparison, baseline, current))
    events.extend(_compare_assortment(db, owner, context, comparison, baseline, current))
    counts = Counter(event.change_type for event in events)
    material = Counter(event.materiality for event in events)
    comparison.summary = cast(
        dict[str, object],
        _json(
            {
                "event_count": len(events),
                "change_type_counts": dict(counts),
                "materiality_counts": dict(material),
                "alert_eligible_count": sum(event.alert_eligibility == "ALERT" for event in events),
                "unresolved_count": sum(event.status == "UNRESOLVED" for event in events),
                "baseline_analysis_id": str(baseline.id),
                "current_analysis_id": str(current.id),
                "calculation_version": CALCULATION_VERSION,
            }
        ),
    )
    _audit(
        db,
        owner,
        "COMPETITOR_CHANGE_COMPARISON_EXECUTED",
        comparison.id,
        f"competitor-change-comparison:{comparison.id}",
        {"event_count": len(events)},
    )
    for event in events:
        if event.materiality in {"MODERATE", "HIGH"} and context.product_id:
            _audit(
                db,
                owner,
                "COMPETITOR_MATERIAL_CHANGE",
                event.id,
                f"competitor-material-change:{event.event_fingerprint}",
                {
                    "context_id": str(context.id),
                    "product_id": str(context.product_id),
                    "change_type": event.change_type,
                    "materiality": event.materiality,
                },
            )
    db.commit()
    db.refresh(comparison)
    return comparison


def get_comparison(
    db: Session, owner: User, comparison_id: uuid.UUID
) -> CompetitorChangeComparison:
    value = db.scalar(
        select(CompetitorChangeComparison).where(
            CompetitorChangeComparison.id == comparison_id,
            CompetitorChangeComparison.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Competitive change comparison not found.")
    return value


def list_events(
    db: Session,
    owner: User,
    context_id: uuid.UUID,
    limit: int,
    offset: int,
    *,
    change_type: str | None = None,
    materiality: str | None = None,
    status: str | None = None,
    product_id: uuid.UUID | None = None,
) -> tuple[list[CompetitorChangeEvent], int]:
    query = select(CompetitorChangeEvent).where(
        CompetitorChangeEvent.owner_id == owner.id, CompetitorChangeEvent.context_id == context_id
    )
    count_query = (
        select(func.count())
        .select_from(CompetitorChangeEvent)
        .where(
            CompetitorChangeEvent.owner_id == owner.id,
            CompetitorChangeEvent.context_id == context_id,
        )
    )
    for field, value in (
        (CompetitorChangeEvent.change_type, change_type.upper() if change_type else None),
        (CompetitorChangeEvent.materiality, materiality.upper() if materiality else None),
        (CompetitorChangeEvent.status, status.upper() if status else None),
        (CompetitorChangeEvent.product_id, product_id),
    ):
        if value is not None:
            query = query.where(field == value)
            count_query = count_query.where(field == value)
    return list(
        db.scalars(
            query.order_by(CompetitorChangeEvent.created_at.desc()).offset(offset).limit(limit)
        )
    ), int(db.scalar(count_query) or 0)


def current_events(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[CompetitorChangeEvent], int]:
    return list_events(db, owner, context_id, limit, offset)


def get_event(db: Session, owner: User, event_id: uuid.UUID) -> CompetitorChangeEvent:
    value = db.scalar(
        select(CompetitorChangeEvent).where(
            CompetitorChangeEvent.id == event_id, CompetitorChangeEvent.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Competitive change event not found.")
    return value


def review_event(
    db: Session, owner: User, event_id: uuid.UUID, data: ChangeReviewRequest
) -> CompetitorChangeEvent:
    event = get_event(db, owner, event_id)
    if data.status not in CHANGE_STATUSES:
        raise HTTPException(422, "Unsupported competitive change status.")
    if (
        data.status == "RESOLVED"
        and not event.resolution_reference
        and event.status not in {"REVERTED", "SUPERSEDED"}
    ):
        raise HTTPException(
            409, "A change cannot be resolved without resolution or reversion evidence."
        )
    event.status = data.status
    event.reviewed_at = _now()
    _audit(
        db,
        owner,
        "COMPETITOR_CHANGE_REVIEWED",
        event.id,
        f"competitor-change-review:{event.id}:{data.status}",
        {"status": data.status, "note": data.note},
    )
    db.commit()
    db.refresh(event)
    return event


def history(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[CompetitorChangeComparison], int]:
    query = select(CompetitorChangeComparison).where(
        CompetitorChangeComparison.owner_id == owner.id,
        CompetitorChangeComparison.context_id == context_id,
    )
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    return (
        list(
            db.scalars(
                query.order_by(CompetitorChangeComparison.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ),
        total,
    )


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    comparisons = list(
        db.scalars(
            select(CompetitorChangeComparison).where(
                CompetitorChangeComparison.owner_id == owner.id
            )
        )
    )
    events = list(
        db.scalars(select(CompetitorChangeEvent).where(CompetitorChangeEvent.owner_id == owner.id))
    )
    alerts = list(
        db.scalars(
            select(CompetitorChangeAlertEligibility).where(
                CompetitorChangeAlertEligibility.owner_id == owner.id
            )
        )
    )
    context_ids = {
        item.id
        for item in db.scalars(
            select(CompetitorContext).where(CompetitorContext.owner_id == owner.id)
        )
    }
    analysis_ids = {
        item.id
        for item in db.scalars(
            select(CompetitorCommercialAnalysis).where(
                CompetitorCommercialAnalysis.owner_id == owner.id
            )
        )
    }
    event_ids = {item.id for item in events}
    orphan_comparisons = sum(
        item.context_id not in context_ids
        or item.baseline_analysis_id not in analysis_ids
        or item.current_analysis_id not in analysis_ids
        for item in comparisons
    )
    orphan_events = sum(
        item.comparison_id not in {row.id for row in comparisons}
        or item.context_id not in context_ids
        for item in events
    )
    orphan_alerts = sum(item.event_id not in event_ids for item in alerts)
    duplicate_events = len(events) - len({item.event_fingerprint for item in events})
    duplicate_alerts = len(alerts) - len({item.event_id for item in alerts})
    invalid = {
        "invalid_decimal_deltas": 0,
        "percentage_with_zero_denominator": 0,
        "currency_mismatch": 0,
        "invalid_materiality": 0,
        "invalid_alert_eligibility": 0,
        "derived_without_10c_lineage": 0,
        "resolved_without_evidence": 0,
    }
    for event in events:
        if event.absolute_delta is not None and not _decimal(event.absolute_delta):
            invalid["invalid_decimal_deltas"] += 1
        if event.percentage_delta is not None and event.absolute_delta is None:
            invalid["percentage_with_zero_denominator"] += 1
        if (
            event.change_type.startswith("PRICE_")
            and event.percentage_delta is not None
            and event.currency is None
        ):
            invalid["currency_mismatch"] += 1
        if event.materiality not in MATERIALITY_LEVELS:
            invalid["invalid_materiality"] += 1
        if event.alert_eligibility not in ALERT_ELIGIBILITY:
            invalid["invalid_alert_eligibility"] += 1
        if event.observed_or_derived == "DERIVED" and event.verification_state != "DERIVED_10C":
            invalid["derived_without_10c_lineage"] += 1
        if event.status == "RESOLVED" and not event.resolution_reference:
            invalid["resolved_without_evidence"] += 1
    duplicates = {
        "orphan_comparisons": orphan_comparisons,
        "orphan_change_events": orphan_events,
        "orphan_alert_eligibility": orphan_alerts,
        "duplicate_logical_change_events": duplicate_events,
        "duplicate_alert_eligibility": duplicate_alerts,
    }
    healthy = not any(duplicates.values()) and not any(invalid.values())
    return {
        "status": "healthy" if healthy else "attention_required",
        "counts": {
            "comparisons": len(comparisons),
            "change_events": len(events),
            "alert_eligibility": len(alerts),
        },
        "duplicate_counts": duplicates,
        "invalid_counts": invalid,
        "calculation_version": CALCULATION_VERSION,
        "materiality_policy_version": MATERIALITY_POLICY_VERSION,
    }
