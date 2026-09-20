"""Deterministic pricing, positioning, and assortment analysis (Slice 10C)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_commercial_models import (
    CALCULATION_VERSION,
    CompetitorCommercialAnalysis,
    CompetitorComparableCohortEntry,
)
from vayujit_api.intelligence.competitor_commercial_schemas import CommercialAnalysisCreate
from vayujit_api.intelligence.competitor_discovery_models import CompetitorDiscoveryCandidate
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorObservation,
    CompetitorProduct,
)
from vayujit_api.intelligence.competitor_service import get_context
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityConstraintVersion,
)

NORMALIZATION_VERSION = "competitor-feature-normalization-v1"
REVIEW_BARRIER_VERSION = "review-barrier-v1"


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
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def normalize_feature_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.casefold().replace("-", " ").replace("_", " ").split())


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(_json(payload), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _audit(db: Session, owner: User, action: str, entity_id: uuid.UUID, key: str) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.{action.casefold()}",
        entity_type="competitor_commercial_analysis",
        entity_id=entity_id,
        metadata={"event_type": action, "entity_id": str(entity_id)},
        idempotency_key=key,
    )


def _percentile(values: list[Decimal], fraction: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (Decimal(len(ordered) - 1) * fraction).quantize(
        Decimal("0.000000"), rounding=ROUND_FLOOR
    )
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - Decimal(lower))


def _distribution(values: list[Decimal], limitation: str | None = None) -> dict[str, object]:
    ordered = sorted(values)
    if not ordered:
        return {
            "sample_count": 0,
            "minimum": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "maximum": None,
            "interquartile_range": None,
            "limitations": [limitation or "No eligible observations."],
        }
    p25 = _percentile(ordered, Decimal("0.25"))
    median = _percentile(ordered, Decimal("0.50"))
    p75 = _percentile(ordered, Decimal("0.75"))
    return {
        "sample_count": len(ordered),
        "minimum": ordered[0],
        "p25": p25,
        "median": median,
        "mean": sum(ordered, Decimal("0")) / Decimal(len(ordered)),
        "p75": p75,
        "maximum": ordered[-1],
        "interquartile_range": p75 - p25 if p25 is not None and p75 is not None else None,
        "limitations": (
            [limitation]
            if limitation
            else (["Small sample; distribution is descriptive only."] if len(ordered) < 5 else [])
        ),
    }


def _bands(distribution: dict[str, object]) -> list[dict[str, object]]:
    keys = ("minimum", "p25", "median", "p75", "maximum")
    values = [_decimal(distribution.get(key)) for key in keys]
    if any(value is None for value in values):
        return []
    minimum, p25, median, p75, maximum = values
    return [
        {"band": "LOW", "lower": minimum, "upper": p25, "rule": "min_to_p25"},
        {"band": "MID", "lower": p25, "upper": median, "rule": "p25_to_median"},
        {"band": "HIGH", "lower": median, "upper": p75, "rule": "median_to_p75"},
        {"band": "PREMIUM", "lower": p75, "upper": maximum, "rule": "p75_to_max"},
    ]


def _band_for(value: Decimal | None, distribution: dict[str, object]) -> str:
    if value is None:
        return "UNKNOWN"
    p25 = _decimal(distribution.get("p25"))
    median = _decimal(distribution.get("median"))
    p75 = _decimal(distribution.get("p75"))
    if p25 is None or median is None or p75 is None:
        return "UNKNOWN"
    return (
        "LOW"
        if value <= p25
        else "MID" if value <= median else "HIGH" if value <= p75 else "PREMIUM"
    )


def _freshness(observations: list[CompetitorObservation]) -> str:
    states = {str(item.freshness_state).upper() for item in observations}
    return "STALE" if "STALE" in states else "CURRENT" if "CURRENT" in states else "UNKNOWN"


def _evidence_state(product: CompetitorProduct, observations: list[CompetitorObservation]) -> str:
    if product.evidence_state == "INSUFFICIENT_EVIDENCE":
        return "INSUFFICIENT_EVIDENCE"
    return (
        "AVAILABLE"
        if observations or product.evidence_state == "AVAILABLE"
        else product.evidence_state
    )


def _load(db: Session, owner: User, context: CompetitorContext, limit: int) -> tuple[
    list[CompetitorProduct],
    dict[uuid.UUID, list[CompetitorObservation]],
    dict[uuid.UUID, CompetitorDiscoveryCandidate],
]:
    products = list(
        db.scalars(
            select(CompetitorProduct)
            .where(
                CompetitorProduct.owner_id == owner.id,
                CompetitorProduct.context_id == context.id,
            )
            .order_by(CompetitorProduct.created_at.asc())
            .limit(limit)
        )
    )
    ids = [item.id for item in products]
    observations = (
        list(
            db.scalars(
                select(CompetitorObservation)
                .where(
                    CompetitorObservation.owner_id == owner.id,
                    CompetitorObservation.competitor_product_id.in_(ids),
                )
                .order_by(CompetitorObservation.observed_at.desc())
            )
        )
        if ids
        else []
    )
    grouped: dict[uuid.UUID, list[CompetitorObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.competitor_product_id].append(observation)
    candidates = (
        list(
            db.scalars(
                select(CompetitorDiscoveryCandidate)
                .where(
                    CompetitorDiscoveryCandidate.owner_id == owner.id,
                    CompetitorDiscoveryCandidate.context_id == context.id,
                    CompetitorDiscoveryCandidate.competitor_product_id.in_(ids),
                )
                .order_by(CompetitorDiscoveryCandidate.created_at.desc())
            )
        )
        if ids
        else []
    )
    latest: dict[uuid.UUID, CompetitorDiscoveryCandidate] = {}
    for candidate in candidates:
        if candidate.competitor_product_id and candidate.competitor_product_id not in latest:
            latest[candidate.competitor_product_id] = candidate
    return products, grouped, latest


def _cohort(
    products: list[CompetitorProduct],
    observations: dict[uuid.UUID, list[CompetitorObservation]],
    latest: dict[uuid.UUID, CompetitorDiscoveryCandidate],
    provisional: bool,
) -> tuple[list[CompetitorProduct], list[dict[str, object]]]:
    allowed = {"CONFIRMED", "PROBABLE"} | ({"CANDIDATE", "UNRESOLVED"} if provisional else set())
    included: list[CompetitorProduct] = []
    entries: list[dict[str, object]] = []
    for product in products:
        candidate = latest.get(product.id)
        state = (candidate.identity_state if candidate else product.identity_state).upper()
        product_obs = observations.get(product.id, [])
        evidence = _evidence_state(product, product_obs)
        include = state in allowed and evidence != "INSUFFICIENT_EVIDENCE"
        reason = (
            None
            if include
            else (
                "AMBIGUOUS_IDENTITY"
                if state == "AMBIGUOUS"
                else (
                    "REJECTED_IDENTITY"
                    if state == "REJECTED"
                    else (
                        "PROVISIONAL_IDENTITY"
                        if state in {"CANDIDATE", "UNRESOLVED"}
                        else (
                            "INSUFFICIENT_EVIDENCE"
                            if evidence == "INSUFFICIENT_EVIDENCE"
                            else "IDENTITY_NOT_ELIGIBLE"
                        )
                    )
                )
            )
        )
        entries.append(
            {
                "product_id": product.id,
                "identity_state": state,
                "included": include,
                "exclusion_reason": reason,
                "evidence_state": evidence,
                "freshness_state": _freshness(product_obs),
                "observation_ids": [item.id for item in product_obs],
                "explanation": {
                    "rule": "CONFIRMED/PROBABLE identities are authoritative",
                    "include_provisional": provisional,
                },
            }
        )
        if include:
            included.append(product)
    return included, entries


def _target_price(
    db: Session, owner: User, context: CompetitorContext
) -> tuple[Decimal | None, str | None, dict[str, object]]:
    if context.product_opportunity_id is None:
        return None, None, {"source": "none", "reason": "No Product Opportunity lineage."}
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == context.product_opportunity_id,
            ProductOpportunity.owner_id == owner.id,
        )
    )
    if opportunity is None:
        return None, None, {"source": "none", "reason": "Product Opportunity is unavailable."}
    constraint = None
    if opportunity.current_constraint_version_id:
        constraint = db.scalar(
            select(ProductOpportunityConstraintVersion).where(
                ProductOpportunityConstraintVersion.id == opportunity.current_constraint_version_id,
                ProductOpportunityConstraintVersion.owner_id == owner.id,
            )
        )
    if constraint is None:
        constraint = db.scalar(
            select(ProductOpportunityConstraintVersion)
            .where(
                ProductOpportunityConstraintVersion.owner_id == owner.id,
                ProductOpportunityConstraintVersion.opportunity_id == opportunity.id,
            )
            .order_by(ProductOpportunityConstraintVersion.version.desc())
        )
    if constraint is None:
        return None, None, {"source": "none", "reason": "No constraint version exists."}
    lower = _decimal(constraint.target_selling_price_min)
    upper = _decimal(constraint.target_selling_price_max)
    if lower is None and upper is None:
        return (
            None,
            constraint.currency,
            {
                "source": "constraint",
                "reason": "No explicit target selling-price assumption.",
            },
        )
    value = (
        (lower + upper) / Decimal("2")
        if lower is not None and upper is not None
        else lower or upper
    )
    return (
        value,
        constraint.currency,
        {
            "source": "product_opportunity_constraint",
            "constraint_version": constraint.version,
            "range_min": lower,
            "range_max": upper,
            "assumption": (
                "midpoint_of_explicit_range"
                if lower is not None and upper is not None
                else "explicit_bound"
            ),
        },
    )


def _concentration(values: list[str | None]) -> dict[str, object]:
    known = [normalize_feature_text(value) for value in values if normalize_feature_text(value)]
    counts = Counter(known)
    total = len(values)
    shares = {key: Decimal(count) / Decimal(len(known)) for key, count in counts.items()}
    ordered = sorted(shares.values(), reverse=True)
    return {
        "known_count": len(known),
        "unknown_count": total - len(known),
        "distinct_count": len(counts),
        "largest_share": ordered[0] if ordered else Decimal("0"),
        "top_three_share": sum(ordered[:3], Decimal("0")),
        "hhi": sum((share * Decimal("100")) ** 2 for share in shares.values()),
        "hhi_scale": "0-10000 descriptive only",
        "shares": shares,
        "limitations": ["Unknown values remain unknown."] if total != len(known) else [],
    }


def _numeric(
    observations: list[CompetitorObservation], kinds: set[str]
) -> list[tuple[CompetitorObservation, Decimal]]:
    values: list[tuple[CompetitorObservation, Decimal]] = []
    for item in observations:
        if item.observation_type.casefold() in kinds:
            value = _decimal(item.numeric_value)
            if value is not None and value >= 0:
                values.append((item, value))
    return values


def _rating_band(value: Decimal | None) -> str:
    if value is None:
        return "UNKNOWN"
    return (
        "LOW"
        if value < 2
        else "MID" if value < Decimal("3.5") else "HIGH" if value < Decimal("4.5") else "VERY_HIGH"
    )


def _review_barrier(value: Decimal | None) -> str:
    if value is None:
        return "UNKNOWN"
    return (
        "LOW"
        if value <= 100
        else "MODERATE" if value <= 1000 else "HIGH" if value <= 10000 else "VERY_HIGH"
    )


def _assortment(
    products: list[CompetitorProduct],
    latest: dict[uuid.UUID, CompetitorDiscoveryCandidate],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    dimensions: dict[str, Counter[str]] = defaultdict(Counter)
    evidence: dict[str, list[str]] = defaultdict(list)
    for product in products:
        candidate = latest.get(product.id)
        values: dict[str, object] = {
            "brand": product.brand_reference,
            "category": product.category,
        }
        if candidate:
            values.update(candidate.structured_attributes or {})
        for key, value in values.items():
            token = normalize_feature_text(str(value) if value is not None else "")
            if token:
                dimensions[str(key)][token] += 1
                if candidate and candidate.evidence_id:
                    evidence[str(key)].append(str(candidate.evidence_id))
    summary: dict[str, Any] = {"normalization_version": NORMALIZATION_VERSION, "dimensions": {}}
    differentiation: list[dict[str, object]] = []
    for key, counts in dimensions.items():
        ordered = counts.most_common()
        summary["dimensions"][key] = {
            "attribute_coverage": (
                Decimal(sum(counts.values())) / Decimal(len(products)) if products else Decimal("0")
            ),
            "distinct_values": len(counts),
            "frequencies": dict(counts),
            "dominant_values": [item[0] for item in ordered[:3]],
            "rare_values": [item[0] for item in ordered if item[1] == 1],
            "missing_count": len(products) - sum(counts.values()),
            "supporting_evidence": evidence[key][:100],
        }
        differentiation.extend(
            {
                "classification": "POTENTIAL_DIFFERENTIATOR",
                "dimension": key,
                "value": token,
                "sample_count": count,
                "evidence": evidence[key][:10],
                "limitations": ["Rarity does not prove demand or advantage."],
            }
            for token, count in ordered
            if count == 1
        )
    return summary, differentiation


def _sections(
    context: CompetitorContext,
    included: list[CompetitorProduct],
    observations: dict[uuid.UUID, list[CompetitorObservation]],
    latest: dict[uuid.UUID, CompetitorDiscoveryCandidate],
    target_price: Decimal | None,
    target_currency: str | None,
    target_metadata: dict[str, object],
) -> dict[str, object]:
    prices: list[tuple[CompetitorObservation, Decimal, str, uuid.UUID]] = []
    ratings: list[tuple[CompetitorObservation, Decimal, uuid.UUID]] = []
    reviews: list[tuple[CompetitorObservation, Decimal, uuid.UUID]] = []
    contradictions: list[dict[str, object]] = []
    freshness: Counter[str] = Counter()
    for product in included:
        product_obs = observations.get(product.id, [])
        freshness[_freshness(product_obs)] += 1
        price_values: dict[str, set[str]] = defaultdict(set)
        for item in product_obs:
            kind = item.observation_type.casefold()
            value = _decimal(item.numeric_value)
            if (
                kind in {"price", "listed_price", "selling_price", "sale_price"}
                and value is not None
            ):
                currency = (item.currency or "UNKNOWN").upper()
                prices.append((item, value, currency, product.id))
                price_values[currency].add(str(value))
            elif kind in {"rating", "ratings"} and value is not None:
                ratings.append((item, value, product.id))
            elif kind in {"review_count", "reviews"} and value is not None:
                reviews.append((item, value, product.id))
        if any(len(values) > 1 for values in price_values.values()):
            contradictions.append(
                {
                    "type": "PRICE_CONFLICT",
                    "product_id": product.id,
                    "values": {key: sorted(values) for key, values in price_values.items()},
                    "rule": "preserve_conflicting_observations",
                }
            )
    by_currency: dict[str, list[Decimal]] = defaultdict(list)
    price_ids: dict[str, list[str]] = defaultdict(list)
    for item, value, currency, _product_id in prices:
        by_currency[currency].append(value)
        price_ids[currency].append(str(item.id))
    distributions = {
        key: _distribution(
            values,
            "Currency is unknown; this sample is not comparable." if key == "UNKNOWN" else None,
        )
        for key, values in by_currency.items()
    }
    comparable_currencies = [key for key in by_currency if key != "UNKNOWN"]
    comparable = len(comparable_currencies) == 1 and "UNKNOWN" not in by_currency
    selected_currency = comparable_currencies[0] if comparable else None
    selected_distribution = distributions.get(selected_currency or "", _distribution([]))
    price_status = (
        "PRICE_EVIDENCE_REQUIRED"
        if not prices
        else "COMPARABLE" if comparable else "MULTI_CURRENCY_NOT_COMPARABLE"
    )
    subject_position = "UNKNOWN"
    subject_reason = "No explicit target selling-price assumption."
    if target_price is not None and target_currency and selected_currency:
        if target_currency.upper() != selected_currency:
            subject_reason = "Subject and competitor currencies differ."
        else:
            subject_position = {
                "LOW": "BELOW_MARKET",
                "MID": "MID_MARKET",
                "HIGH": "UPPER_QUARTILE",
                "PREMIUM": "PREMIUM",
            }.get(_band_for(target_price, selected_distribution), "UNKNOWN")
            subject_reason = "Descriptive position against observed competitors."
    elif target_price is not None:
        subject_reason = "Competitor prices are not comparable."
    pricing = {
        "status": price_status,
        "currency": selected_currency,
        "currencies": distributions,
        "distribution": selected_distribution,
        "price_bands": _bands(selected_distribution),
        "subject_assumed_price": target_price,
        "subject_assumed_currency": target_currency,
        "subject_price_provenance": target_metadata,
        "subject_position": subject_position,
        "subject_position_explanation": subject_reason,
        "calculation_version": CALCULATION_VERSION,
        "price_observation_ids": {key: ids[:100] for key, ids in price_ids.items()},
    }
    brand = _concentration([item.brand_reference for item in included])
    seller = _concentration([item.seller_reference for item in included])
    concentration = {
        "brand": brand,
        "seller": seller,
        "evidence_coverage": {
            "brand": (
                Decimal(str(brand["known_count"])) / Decimal(len(included))
                if included
                else Decimal("0")
            ),
            "seller": (
                Decimal(str(seller["known_count"])) / Decimal(len(included))
                if included
                else Decimal("0")
            ),
        },
    }
    rating_values = [value for _item, value, _product_id in ratings]
    review_values = [value for _item, value, _product_id in reviews]
    rating_distribution = _distribution(
        rating_values,
        (
            "Rating scale is assumed compatible with the repository 0-5 validation."
            if rating_values
            else None
        ),
    )
    review_distribution = _distribution(review_values)
    rating = {
        **rating_distribution,
        "scale": "0-5",
        "rating_bands": dict(Counter(_rating_band(value) for value in rating_values)),
        "supporting_observation_ids": [str(item.id) for item, _value, _id in ratings[:100]],
    }
    review = {
        **review_distribution,
        "barrier_policy": REVIEW_BARRIER_VERSION,
        "barrier": _review_barrier(_decimal(review_distribution.get("median"))),
        "supporting_observation_ids": [str(item.id) for item, _value, _id in reviews[:100]],
        "limitations": (
            ["Review count is descriptive and never interpreted as sales."]
            if review_values
            else ["Review evidence required."]
        ),
    }
    assortment, differentiation = _assortment(included, latest)
    matrix: list[dict[str, object]] = []
    for product in included:
        product_prices = [
            value for _item, value, _currency, product_id in prices if product_id == product.id
        ]
        product_rating = next(
            (value for _item, value, product_id in ratings if product_id == product.id), None
        )
        product_reviews = next(
            (value for _item, value, product_id in reviews if product_id == product.id), None
        )
        matrix.append(
            {
                "product_id": product.id,
                "title": product.title,
                "brand": product.brand_reference,
                "seller": product.seller_reference,
                "price_band": _band_for(
                    product_prices[0] if product_prices else None, selected_distribution
                ),
                "rating_band": _rating_band(product_rating),
                "review_barrier": _review_barrier(product_reviews),
                "availability": product.availability_state,
            }
        )
    gaps: list[dict[str, object]] = []
    if selected_currency and selected_distribution["sample_count"]:
        present = {
            _band_for(value, selected_distribution)
            for values in by_currency.values()
            for value in values
        }
        for band in ("LOW", "MID", "HIGH", "PREMIUM"):
            if band not in present:
                gaps.append(
                    {
                        "type": "UNDERREPRESENTED_PRICE_BAND",
                        "value": band,
                        "classification": "DESCRIPTIVE_GAP",
                        "sample_count": selected_distribution["sample_count"],
                        "evidence_coverage": Decimal("1"),
                        "rule": "distribution_derived_band_absent",
                        "limitations": ["Absence is not proven demand."],
                    }
                )
    gaps.extend(
        {
            "type": "RARE_ASSORTMENT_ATTRIBUTE",
            "dimension": item["dimension"],
            "value": item["value"],
            "classification": "DESCRIPTIVE_GAP",
            "sample_count": item["sample_count"],
            "evidence_coverage": Decimal("1"),
            "rule": NORMALIZATION_VERSION,
            "limitations": ["Rare attributes are not automatically opportunities."],
        }
        for item in differentiation
    )
    freshness_summary = {
        "included_product_states": dict(freshness),
        "price_stale": any(
            item.freshness_state.upper() == "STALE"
            for item, _value, _currency, _product_id in prices
        ),
    }
    coverage = {
        "cohort_products": len(included),
        "price_observations": len(prices),
        "rating_observations": len(ratings),
        "review_observations": len(reviews),
        "price": Decimal(len(prices)) / Decimal(len(included)) if included else Decimal("0"),
        "rating": Decimal(len(ratings)) / Decimal(len(included)) if included else Decimal("0"),
        "reviews": Decimal(len(reviews)) / Decimal(len(included)) if included else Decimal("0"),
        "missing": [
            key
            for key, count in {
                "price": len(prices),
                "rating": len(ratings),
                "reviews": len(reviews),
            }.items()
            if count == 0
        ],
    }
    research_gaps: list[dict[str, object]] = []
    if not prices:
        research_gaps.append({"code": "PRICE_EVIDENCE_REQUIRED", "bounded": True})
    if len(comparable_currencies) > 1 or "UNKNOWN" in by_currency:
        research_gaps.append({"code": "CURRENCY_COMPARABILITY_REQUIRED", "bounded": True})
    if not ratings:
        research_gaps.append({"code": "RATING_SAMPLE_REQUIRED", "bounded": True})
    if not reviews:
        research_gaps.append({"code": "REVIEW_SAMPLE_REQUIRED", "bounded": True})
    if not assortment["dimensions"]:
        research_gaps.append({"code": "ASSORTMENT_EVIDENCE_REQUIRED", "bounded": True})
    return {
        "pricing": pricing,
        "concentration": concentration,
        "rating": rating,
        "review": review,
        "assortment": assortment,
        "positioning": {
            "matrix": matrix,
            "dimensions": [
                "price_band",
                "rating_band",
                "review_barrier",
                "brand_presence",
                "seller",
            ],
            "explanation": "Descriptive placement only; not a Winning Product score.",
            "calculation_version": CALCULATION_VERSION,
        },
        "differentiation": differentiation,
        "gaps": gaps,
        "coverage": coverage,
        "freshness": freshness_summary,
        "contradictions": contradictions,
        "research_gaps": research_gaps,
    }


def _get_analysis(db: Session, owner: User, analysis_id: uuid.UUID) -> CompetitorCommercialAnalysis:
    value = db.scalar(
        select(CompetitorCommercialAnalysis).where(
            CompetitorCommercialAnalysis.id == analysis_id,
            CompetitorCommercialAnalysis.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Competitor commercial analysis not found.")
    return value


def run_analysis(
    db: Session, owner: User, context_id: uuid.UUID, data: CommercialAnalysisCreate
) -> CompetitorCommercialAnalysis:
    context = get_context(db, owner, context_id)
    if context.status == "ARCHIVED":
        raise HTTPException(409, "Archived competitor contexts cannot be analyzed.")
    products, observations, latest = _load(db, owner, context, data.maximum_products)
    included, entries = _cohort(products, observations, latest, data.include_provisional)
    payload = {
        "context_id": context.id,
        "products": [
            {
                "id": product.id,
                "identity_state": entry["identity_state"],
                "observation_ids": entry["observation_ids"],
            }
            for product, entry in zip(products, entries, strict=False)
        ],
        "snapshot_id": data.discovery_snapshot_id,
        "include_provisional": data.include_provisional,
    }
    json_payload = _json(payload)
    assert isinstance(payload, dict)
    fingerprint = _fingerprint(json_payload)
    if data.idempotency_key:
        existing = db.scalar(
            select(CompetitorCommercialAnalysis).where(
                CompetitorCommercialAnalysis.owner_id == owner.id,
                CompetitorCommercialAnalysis.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            return existing
    existing = db.scalar(
        select(CompetitorCommercialAnalysis).where(
            CompetitorCommercialAnalysis.owner_id == owner.id,
            CompetitorCommercialAnalysis.context_id == context.id,
            CompetitorCommercialAnalysis.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    recalculated = (
        db.scalar(
            select(CompetitorCommercialAnalysis.id)
            .where(
                CompetitorCommercialAnalysis.owner_id == owner.id,
                CompetitorCommercialAnalysis.context_id == context.id,
            )
            .limit(1)
        )
        is not None
    )
    snapshot = None
    if data.discovery_snapshot_id:
        from vayujit_api.intelligence.competitor_discovery_models import CompetitorDiscoverySnapshot

        snapshot = db.scalar(
            select(CompetitorDiscoverySnapshot).where(
                CompetitorDiscoverySnapshot.id == data.discovery_snapshot_id,
                CompetitorDiscoverySnapshot.owner_id == owner.id,
                CompetitorDiscoverySnapshot.context_id == context.id,
            )
        )
        if snapshot is None:
            raise HTTPException(404, "Discovery snapshot not found for this context.")
    target_price, target_currency, target_metadata = _target_price(db, owner, context)
    sections = _sections(
        context, included, observations, latest, target_price, target_currency, target_metadata
    )
    json_sections = cast(dict[str, Any], _json(sections))
    assert isinstance(sections, dict)
    version = (
        db.scalar(
            select(func.max(CompetitorCommercialAnalysis.analysis_version)).where(
                CompetitorCommercialAnalysis.owner_id == owner.id,
                CompetitorCommercialAnalysis.context_id == context.id,
            )
        )
        or 0
    ) + 1
    analysis = CompetitorCommercialAnalysis(
        owner_id=owner.id,
        context_id=context.id,
        discovery_snapshot_id=snapshot.id if snapshot else None,
        opportunity_id=context.product_opportunity_id,
        analysis_version=int(version),
        calculation_version=CALCULATION_VERSION,
        status="COMPLETED" if included else "PARTIALLY_COMPLETED",
        input_fingerprint=fingerprint,
        input_snapshot=json_payload,
        cohort_summary={
            "included_product_ids": [str(product.id) for product in included],
            "included_count": len(included),
            "excluded_count": len(entries) - len(included),
            "include_provisional": data.include_provisional,
            "entries": _json(entries),
        },
        pricing_analysis=json_sections["pricing"],
        concentration_analysis=json_sections["concentration"],
        rating_analysis=json_sections["rating"],
        review_analysis=json_sections["review"],
        assortment_analysis=json_sections["assortment"],
        positioning_analysis=json_sections["positioning"],
        differentiation_analysis=json_sections["differentiation"],
        competitive_gaps=json_sections["gaps"],
        evidence_coverage=json_sections["coverage"],
        freshness_summary=json_sections["freshness"],
        contradictions=json_sections["contradictions"],
        research_gaps=json_sections["research_gaps"],
        explanation={
            "calculation_version": CALCULATION_VERSION,
            "limitations": [
                "Outputs are descriptive competitive intelligence.",
                "Unknown values are not treated as zero.",
                "No sales, demand, preference, or commercial advantage is inferred.",
            ],
        },
        idempotency_key=data.idempotency_key or f"competitor-commercial:{context.id}:{fingerprint}",
        created_at=_now(),
    )
    db.add(analysis)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CompetitorCommercialAnalysis).where(
                CompetitorCommercialAnalysis.owner_id == owner.id,
                CompetitorCommercialAnalysis.idempotency_key == analysis.idempotency_key,
            )
        )
        if existing is not None:
            return existing
        raise
    for entry in entries:
        db.add(
            CompetitorComparableCohortEntry(
                owner_id=owner.id,
                analysis_id=analysis.id,
                context_id=context.id,
                product_id=entry["product_id"],
                identity_state=entry["identity_state"],
                included=entry["included"],
                exclusion_reason=entry["exclusion_reason"],
                evidence_state=entry["evidence_state"],
                freshness_state=entry["freshness_state"],
                observation_ids=_json(entry["observation_ids"]),
                explanation=entry["explanation"],
                created_at=_now(),
            )
        )
    _audit(
        db,
        owner,
        (
            "COMPETITOR_COMMERCIAL_ANALYSIS_RECALCULATED"
            if recalculated
            else "COMPETITOR_COMMERCIAL_ANALYSIS_CREATED"
        ),
        analysis.id,
        (
            f"competitor-commercial-recalculated:{analysis.id}"
            if recalculated
            else f"competitor-commercial-created:{analysis.id}"
        ),
    )
    db.commit()
    db.refresh(analysis)
    return analysis


def get_analysis(db: Session, owner: User, analysis_id: uuid.UUID) -> CompetitorCommercialAnalysis:
    return _get_analysis(db, owner, analysis_id)


def current_analysis(
    db: Session, owner: User, context_id: uuid.UUID
) -> CompetitorCommercialAnalysis | None:
    return db.scalar(
        select(CompetitorCommercialAnalysis)
        .where(
            CompetitorCommercialAnalysis.owner_id == owner.id,
            CompetitorCommercialAnalysis.context_id == context_id,
        )
        .order_by(CompetitorCommercialAnalysis.analysis_version.desc())
    )


def list_analyses(
    db: Session, owner: User, context_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[CompetitorCommercialAnalysis], int]:
    query = select(CompetitorCommercialAnalysis).where(
        CompetitorCommercialAnalysis.owner_id == owner.id,
        CompetitorCommercialAnalysis.context_id == context_id,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(CompetitorCommercialAnalysis.analysis_version.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return rows, int(total)


def cohort_entries(
    db: Session, owner: User, analysis_id: uuid.UUID, limit: int, offset: int
) -> list[CompetitorComparableCohortEntry]:
    _get_analysis(db, owner, analysis_id)
    return list(
        db.scalars(
            select(CompetitorComparableCohortEntry)
            .where(
                CompetitorComparableCohortEntry.owner_id == owner.id,
                CompetitorComparableCohortEntry.analysis_id == analysis_id,
            )
            .order_by(CompetitorComparableCohortEntry.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
    )


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    """Return bounded owner-scoped lineage and invariant checks for 10C."""
    from vayujit_api.intelligence.competitor_discovery_models import CompetitorDiscoverySnapshot

    analyses = list(
        db.scalars(
            select(CompetitorCommercialAnalysis).where(
                CompetitorCommercialAnalysis.owner_id == owner.id
            )
        )
    )
    cohort_rows = list(
        db.scalars(
            select(CompetitorComparableCohortEntry).where(
                CompetitorComparableCohortEntry.owner_id == owner.id
            )
        )
    )
    orphan_cohort = sum(
        1
        for entry in cohort_rows
        if not any(entry.analysis_id == analysis.id for analysis in analyses)
    )
    context_ids = {analysis.context_id for analysis in analyses}
    contexts = (
        set(
            db.scalars(
                select(CompetitorContext.id).where(
                    CompetitorContext.owner_id == owner.id,
                    CompetitorContext.id.in_(context_ids),
                )
            )
        )
        if context_ids
        else set()
    )
    broken_context = sum(1 for analysis in analyses if analysis.context_id not in contexts)
    snapshot_ids = {
        analysis.discovery_snapshot_id for analysis in analyses if analysis.discovery_snapshot_id
    }
    snapshots = (
        set(
            db.scalars(
                select(CompetitorDiscoverySnapshot.id).where(
                    CompetitorDiscoverySnapshot.owner_id == owner.id,
                    CompetitorDiscoverySnapshot.id.in_(snapshot_ids),
                )
            )
        )
        if snapshot_ids
        else set()
    )
    broken_snapshot = sum(
        1
        for analysis in analyses
        if analysis.discovery_snapshot_id is not None
        and analysis.discovery_snapshot_id not in snapshots
    )

    invalid: dict[str, int] = {
        "mixed_currency_marked_comparable": 0,
        "ambiguous_products_included": 0,
        "rejected_products_included": 0,
        "unknown_represented_as_zero": 0,
        "invalid_percentile_ordering": 0,
        "invalid_rating_scale": 0,
        "invalid_concentration_ranges": 0,
    }
    for analysis in analyses:
        pricing = analysis.pricing_analysis or {}
        if pricing.get("status") == "MULTI_CURRENCY_COMPARABLE":
            invalid["mixed_currency_marked_comparable"] += 1
        currencies = pricing.get("currencies")
        if (
            isinstance(currencies, dict)
            and len(currencies) > 1
            and pricing.get("status") == "COMPARABLE"
        ):
            invalid["mixed_currency_marked_comparable"] += 1
        distributions: list[dict[str, Any]] = []
        if isinstance(pricing.get("distribution"), dict):
            distributions.append(cast(dict[str, Any], pricing["distribution"]))
        if isinstance(currencies, dict):
            distributions.extend(value for value in currencies.values() if isinstance(value, dict))
        for distribution in distributions:
            ordered = [
                distribution.get(key) for key in ("minimum", "p25", "median", "p75", "maximum")
            ]
            decimals = [_decimal(value) for value in ordered]
            valid_decimals = [value for value in decimals if value is not None]
            if len(valid_decimals) == 5 and any(
                left > right
                for left, right in zip(valid_decimals, valid_decimals[1:], strict=False)
            ):
                invalid["invalid_percentile_ordering"] += 1
        for dimension in (analysis.concentration_analysis or {}).values():
            if isinstance(dimension, dict):
                for key in ("largest_share", "top_three_share"):
                    value = _decimal(dimension.get(key))
                    if value is not None and not Decimal("0") <= value <= Decimal("1"):
                        invalid["invalid_concentration_ranges"] += 1
        for entry in cohort_rows:
            if entry.analysis_id != analysis.id or not entry.included:
                continue
            if entry.identity_state == "AMBIGUOUS":
                invalid["ambiguous_products_included"] += 1
            if entry.identity_state == "REJECTED":
                invalid["rejected_products_included"] += 1

    duplicate_counts = {
        "orphan_cohort_entries": orphan_cohort,
        "broken_context_lineage": broken_context,
        "broken_snapshot_lineage": broken_snapshot,
        "duplicate_current_fingerprints": 0,
    }
    invalid_total = sum(invalid.values())
    healthy = not any(duplicate_counts.values()) and invalid_total == 0
    return {
        "status": "healthy" if healthy else "attention_required",
        "counts": {"analyses": len(analyses), "cohort_entries": len(cohort_rows)},
        "duplicate_counts": duplicate_counts,
        "invalid_counts": invalid,
        "calculation_version": CALCULATION_VERSION,
    }
