"""Deterministic, evidence-backed demand and competition calculations."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.commerce.models import (
    MarketplaceListing,
    MarketplacePrice,
)
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_winning_product_service import (
    get_or_create_projection,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    CALCULATION_VERSION,
    ProductOpportunityIntelligenceOutput,
    intelligence_now,
)
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)

FRESHNESS_WINDOWS = ((timedelta(days=30), "fresh"), (timedelta(days=90), "aging"))


def _freshness(observed_at: datetime | None, now: datetime) -> dict[str, Any]:
    if observed_at is None:
        return {"state": "unknown", "observed_at": None, "age_days": None}
    value = observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC)
    age = max(now - value, timedelta(0))
    state = "stale"
    for window, candidate in FRESHNESS_WINDOWS:
        if age <= window:
            state = candidate
            break
    return {"state": state, "observed_at": value.isoformat(), "age_days": age.days}


def _dimension(
    name: str,
    *,
    value: Any,
    classification: str,
    evidence_state: str,
    explanation: str,
    supporting: list[dict[str, Any]],
    missing: list[str],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dimension": name,
        "value": value,
        "classification": classification,
        "evidence_state": evidence_state,
        "explanation": explanation,
        "supporting_evidence": supporting,
        "missing_evidence": missing,
        "freshness": freshness,
        "calculation_version": CALCULATION_VERSION,
    }


def _context(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[ProductOpportunity, ProductOpportunityAssessment, list[MarketplaceListing]]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    assessment = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.owner_id == owner.id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
        )
    )
    if opportunity is None or assessment is None:
        raise LookupError("Product opportunity assessment not found.")
    listings = []
    if opportunity.product_id is not None:
        listings = list(
            db.scalars(
                select(MarketplaceListing)
                .where(
                    MarketplaceListing.owner_id == owner.id,
                    MarketplaceListing.product_id == opportunity.product_id,
                    MarketplaceListing.status.not_in(("archived", "rejected")),
                )
                .order_by(MarketplaceListing.updated_at.desc())
                .limit(200)
            )
        )
    return opportunity, assessment, listings


def _prices(db: Session, owner: User, listings: list[MarketplaceListing]) -> list[MarketplacePrice]:
    if not listings:
        return []
    listing_ids = [row.id for row in listings]
    return list(
        db.scalars(
            select(MarketplacePrice).where(
                MarketplacePrice.owner_id == owner.id,
                MarketplacePrice.listing_id.in_(listing_ids),
                MarketplacePrice.effective_to.is_(None),
            )
        )
    )


def _price_groups(prices: list[MarketplacePrice], now: datetime) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Decimal]] = defaultdict(list)
    freshness: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for price in prices:
        groups[price.currency].append(Decimal(price.amount))
        freshness[price.currency].append(_freshness(price.effective_from, now))
    result: dict[str, dict[str, Any]] = {}
    for currency, values in sorted(groups.items()):
        states = freshness[currency]
        result[currency] = {
            "minimum": str(min(values)),
            "maximum": str(max(values)),
            "median": str(median(values)),
            "sample_size": len(values),
            "currency": currency,
            "freshness": {
                "state": (
                    "stale" if any(v["state"] == "stale" for v in states) else states[0]["state"]
                ),
                "observed_at": [v["observed_at"] for v in states],
            },
        }
    return result


def _hhi(values: list[Any]) -> float | None:
    if not values:
        return None
    counts = Counter(values)
    total = len(values)
    return round(sum((count / total) ** 2 for count in counts.values()), 4)


def _evidence_summary(
    listings: list[MarketplaceListing], prices: list[MarketplacePrice], now: datetime
) -> tuple[dict[str, Any], dict[str, Any]]:
    listing_refs = [
        {
            "type": "marketplace_listing",
            "id": str(row.id),
            "marketplace": row.marketplace,
            "observed_at": (
                (row.last_synchronized_at or row.remote_updated_at).isoformat()  # type: ignore[union-attr]
                if (row.last_synchronized_at or row.remote_updated_at)
                else None
            ),
        }
        for row in listings[:100]
    ]
    dates = [row.last_synchronized_at or row.remote_updated_at for row in listings]
    fresh = [_freshness(value, now) for value in dates]
    marketplaces = sorted({row.marketplace for row in listings})
    brands = sorted({str(row.brand_id) for row in listings})
    accounts = sorted({str(row.account_id) for row in listings})
    states = [item["state"] for item in fresh]
    overall = "unknown"
    if states:
        overall = "stale" if "stale" in states else "aging" if "aging" in states else "fresh"
    summary = {
        "listing_count": len(listings),
        "price_observation_count": len(prices),
        "marketplace_count": len(marketplaces),
        "brand_count": len(brands),
        "marketplace_account_count": len(accounts),
        "evidence_diversity": {
            "marketplaces": marketplaces,
            "brands": len(brands),
            "marketplace_accounts": len(accounts),
        },
        "freshness": {"state": overall, "observed_at": [item["observed_at"] for item in fresh]},
        "supporting_evidence": listing_refs,
    }
    snapshot = {
        "listing_ids": [str(row.id) for row in listings],
        "price_ids": [str(row.id) for row in prices],
        "captured_at": now.isoformat(),
        "calculation_version": CALCULATION_VERSION,
    }
    return summary, snapshot


def _demand(
    listings: list[MarketplaceListing], summary: dict[str, Any], now: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refs = summary["supporting_evidence"]
    freshness = summary["freshness"]
    evidence_state = "unknown" if not listings else "partial" if len(listings) == 1 else "available"
    gaps: list[dict[str, Any]] = []
    if not listings:
        gaps.append(
            {
                "code": "DEMAND_EVIDENCE_REQUIRED",
                "reason": "No marketplace listing observations are linked.",
            }
        )
    gaps.extend(
        [
            {
                "code": "SALES_EVIDENCE_REQUIRED",
                "reason": "No authoritative sales volume is persisted.",
            },
            {
                "code": "TREND_EVIDENCE_REQUIRED",
                "reason": "No historical search or trend observations are linked.",
            },
            {
                "code": "REVIEW_EVIDENCE_REQUIRED",
                "reason": "Review count and velocity are not persisted in marketplace listings.",
            },
        ]
    )
    dimensions = [
        _dimension(
            "MARKET_ACTIVITY",
            value=len(listings) if listings else None,
            classification="OBSERVED_FACT" if listings else "UNKNOWN",
            evidence_state=evidence_state,
            explanation=(
                "Count of persisted active/ready marketplace listing observations; "
                "this is activity, not sales."
            ),
            supporting=refs,
            missing=[] if listings else ["marketplace listings"],
            freshness=freshness,
        ),
        _dimension(
            "DEMAND_STRENGTH",
            value=None,
            classification="PROXY" if listings else "UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation=(
                "No sales or search-volume evidence is available; listing activity "
                "is not converted into sales."
            ),
            supporting=refs,
            missing=["sales volume", "search volume"],
            freshness=freshness,
        ),
        _dimension(
            "DEMAND_MOMENTUM",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation=(
                "A single current listing snapshot cannot establish "
                "strengthening or weakening demand."
            ),
            supporting=refs,
            missing=["historical demand observations"],
            freshness=freshness,
        ),
        _dimension(
            "DEMAND_STABILITY",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation="Stability requires repeated observations over time.",
            supporting=refs,
            missing=["repeated demand observations"],
            freshness=freshness,
        ),
        _dimension(
            "EVIDENCE_COVERAGE",
            value=summary["listing_count"] or None,
            classification="DERIVED_SIGNAL" if listings else "UNKNOWN",
            evidence_state=evidence_state,
            explanation="Coverage reflects the bounded number of linked listing observations only.",
            supporting=refs,
            missing=[] if listings else ["authoritative demand evidence"],
            freshness=freshness,
        ),
        _dimension(
            "EVIDENCE_FRESHNESS",
            value=freshness["state"],
            classification="OBSERVED_FACT" if listings else "UNKNOWN",
            evidence_state=evidence_state,
            explanation=(
                "Freshness is derived from listing synchronization timestamps; "
                "unknown timestamps remain unknown."
            ),
            supporting=refs,
            missing=(
                [] if listings and freshness["state"] != "unknown" else ["observation timestamp"]
            ),
            freshness=freshness,
        ),
    ]
    return dimensions, gaps


def _competition(
    listings: list[MarketplaceListing],
    prices: list[MarketplacePrice],
    summary: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refs = summary["supporting_evidence"]
    freshness = summary["freshness"]
    state = "unknown" if not listings else "partial" if len(listings) == 1 else "available"
    gaps: list[dict[str, Any]] = []
    if not listings:
        gaps.append(
            {
                "code": "COMPETITOR_SAMPLE_REQUIRED",
                "reason": "No marketplace listing sample is linked.",
            }
        )
    if not prices:
        gaps.append(
            {
                "code": "PRICE_EVIDENCE_REQUIRED",
                "reason": "No current marketplace price observations are linked.",
            }
        )
    brands = [str(row.brand_id) for row in listings]
    accounts = [str(row.account_id) for row in listings]
    price_groups = _price_groups(prices, now)
    dimensions = [
        _dimension(
            "COMPETITOR_DENSITY",
            value=len(listings) if listings else None,
            classification="OBSERVED_FACT" if listings else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "Bounded count of persisted marketplace listing observations; identity is "
                "not asserted as independent competitors."
            ),
            supporting=refs,
            missing=[] if listings else ["competitor sample"],
            freshness=freshness,
        ),
        _dimension(
            "BRAND_CONCENTRATION",
            value=_hhi(brands),
            classification="DERIVED_SIGNAL" if brands else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "HHI = sum of squared brand shares across the linked listing sample; "
                "it is not a business-risk conclusion."
            ),
            supporting=refs,
            missing=[] if brands else ["brand identities"],
            freshness=freshness,
        ),
        _dimension(
            "SELLER_CONCENTRATION",
            value=_hhi(accounts),
            classification="PROXY" if accounts else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "Marketplace account concentration is a bounded seller proxy because "
                "canonical seller identity is unavailable."
            ),
            supporting=refs,
            missing=[] if accounts else ["seller identity"],
            freshness=freshness,
        ),
        _dimension(
            "PRICE_COMPETITION",
            value=price_groups or None,
            classification="OBSERVED_FACT" if prices else "UNKNOWN",
            evidence_state="available" if prices else "unknown",
            explanation=(
                "Descriptive price distribution grouped by currency; mixed currencies "
                "are never combined."
            ),
            supporting=[{"type": "marketplace_price", "id": str(row.id)} for row in prices[:100]],
            missing=[] if prices else ["price observations"],
            freshness=freshness,
        ),
        _dimension(
            "REVIEW_BARRIER",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation=(
                "Review counts and distributions are not persisted in the current "
                "marketplace model."
            ),
            supporting=refs,
            missing=["review counts"],
            freshness=freshness,
        ),
        _dimension(
            "RATING_BARRIER",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation="Ratings are not persisted in the current marketplace model.",
            supporting=refs,
            missing=["rating observations"],
            freshness=freshness,
        ),
        _dimension(
            "LISTING_MATURITY",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation=(
                "Listing age history is not available as an authoritative " "observation series."
            ),
            supporting=refs,
            missing=["listing age history"],
            freshness=freshness,
        ),
        _dimension(
            "DIFFERENTIATION_OPPORTUNITY",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation=(
                "Differentiation requires verified feature and positioning evidence "
                "not present in listings alone."
            ),
            supporting=refs,
            missing=["product differentiation evidence"],
            freshness=freshness,
        ),
        _dimension(
            "EVIDENCE_COVERAGE",
            value=summary["listing_count"] or None,
            classification="DERIVED_SIGNAL" if listings else "UNKNOWN",
            evidence_state=state,
            explanation="Coverage is the bounded linked listing sample.",
            supporting=refs,
            missing=[] if listings else ["competition evidence"],
            freshness=freshness,
        ),
        _dimension(
            "EVIDENCE_FRESHNESS",
            value=freshness["state"],
            classification="OBSERVED_FACT" if listings else "UNKNOWN",
            evidence_state=state,
            explanation="Freshness is based on listing synchronization timestamps.",
            supporting=refs,
            missing=(
                [] if listings and freshness["state"] != "unknown" else ["observation timestamp"]
            ),
            freshness=freshness,
        ),
    ]
    return dimensions, gaps


def _competition_from_projection(
    projection: Any, now: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Adapt validated 10E data to the frozen 9B dimension contract."""
    payload = projection.projection if isinstance(projection.projection, dict) else {}
    analysis_value = payload.get("analysis")
    analysis: dict[str, Any] = (
        cast(dict[str, Any], analysis_value) if isinstance(analysis_value, dict) else {}
    )
    cohort_value = payload.get("cohort")
    cohort: dict[str, Any] = (
        cast(dict[str, Any], cohort_value) if isinstance(cohort_value, dict) else {}
    )
    freshness_value = analysis.get("freshness")
    freshness: dict[str, Any] = (
        cast(dict[str, Any], freshness_value) if isinstance(freshness_value, dict) else {}
    )
    freshness_state = {
        "state": str(projection.freshness_state).lower(),
        "observed_at": [payload.get("generated_at")],
    }
    source = {
        "type": "competitor_winning_product_projection",
        "id": str(projection.id),
        "source_state": projection.source_state,
        "context_id": str(projection.context_id) if projection.context_id else None,
        "analysis_id": (
            str(projection.competitor_analysis_id) if projection.competitor_analysis_id else None
        ),
        "comparison_id": (
            str(projection.change_comparison_id) if projection.change_comparison_id else None
        ),
        "contract_version": projection.contract_version,
        "freshness": projection.freshness_state,
        "contradictions": projection.contradiction_state,
        "change_context": payload.get("change_context"),
    }
    authoritative = cohort.get("authoritative_count")
    has_density = isinstance(authoritative, int) and authoritative > 0
    gaps = projection.research_gaps if isinstance(projection.research_gaps, list) else []
    state = (
        "available"
        if projection.source_state == "DEDICATED_COMPETITOR_INTELLIGENCE"
        else "insufficient_evidence"
    )
    pricing = analysis.get("pricing")
    pricing_value = pricing if isinstance(pricing, dict) and pricing else None
    pricing_state = "available" if pricing_value is not None else "insufficient_evidence"
    concentration_value = analysis.get("concentration")
    concentration: dict[str, Any] = (
        cast(dict[str, Any], concentration_value) if isinstance(concentration_value, dict) else {}
    )
    brand_value = concentration.get("brand")
    brand: dict[str, Any] = (
        cast(dict[str, Any], brand_value) if isinstance(brand_value, dict) else {}
    )
    seller_value = concentration.get("seller")
    seller: dict[str, Any] = (
        cast(dict[str, Any], seller_value) if isinstance(seller_value, dict) else {}
    )
    rating_value = analysis.get("rating")
    rating: dict[str, Any] = (
        cast(dict[str, Any], rating_value) if isinstance(rating_value, dict) else {}
    )
    review_value = analysis.get("review")
    review: dict[str, Any] = (
        cast(dict[str, Any], review_value) if isinstance(review_value, dict) else {}
    )
    differentiation = analysis.get("differentiation")
    dimensions = [
        _dimension(
            "COMPETITOR_DENSITY",
            value=authoritative if has_density else None,
            classification="OBSERVED_FACT" if has_density else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "Confirmed and probable 10C cohort entries only; ambiguous and rejected "
                "entries are excluded."
            ),
            supporting=[source],
            missing=[] if has_density else ["confirmed or probable competitor cohort"],
            freshness=freshness_state,
        ),
        _dimension(
            "BRAND_CONCENTRATION",
            value=brand.get("hhi"),
            classification="DERIVED_SIGNAL" if brand.get("hhi") is not None else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "Authoritative 10C brand concentration; no recomputation is performed in " "9B."
            ),
            supporting=[{**source, "concentration": brand}],
            missing=[] if brand.get("hhi") is not None else ["brand identities"],
            freshness=freshness_state,
        ),
        _dimension(
            "SELLER_CONCENTRATION",
            value=seller.get("hhi"),
            classification="DERIVED_SIGNAL" if seller.get("hhi") is not None else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "Authoritative 10C seller concentration kept independent from brand "
                "concentration."
            ),
            supporting=[{**source, "concentration": seller}],
            missing=[] if seller.get("hhi") is not None else ["seller identities"],
            freshness=freshness_state,
        ),
        _dimension(
            "PRICE_COMPETITION",
            value=pricing_value,
            classification="OBSERVED_FACT" if pricing_value is not None else "UNKNOWN",
            evidence_state=pricing_state,
            explanation=(
                "Authoritative 10C price distribution; mixed currencies remain " "non-comparable."
            ),
            supporting=[{**source, "pricing": pricing_value}],
            missing=[] if pricing_value is not None else ["price observations"],
            freshness=freshness_state,
        ),
        _dimension(
            "REVIEW_BARRIER",
            value=review.get("barrier"),
            classification="DERIVED_SIGNAL" if review.get("barrier") is not None else "UNKNOWN",
            evidence_state=state if review else "insufficient_evidence",
            explanation="Descriptive 10C review barrier; no demand or sales inference is made.",
            supporting=[{**source, "review": review}],
            missing=[] if review else ["review observations"],
            freshness=freshness_state,
        ),
        _dimension(
            "RATING_BARRIER",
            value=rating.get("barrier"),
            classification="DERIVED_SIGNAL" if rating.get("barrier") is not None else "UNKNOWN",
            evidence_state=state if rating else "insufficient_evidence",
            explanation="Descriptive 10C rating barrier only.",
            supporting=[{**source, "rating": rating}],
            missing=[] if rating else ["rating observations"],
            freshness=freshness_state,
        ),
        _dimension(
            "LISTING_MATURITY",
            value=None,
            classification="UNKNOWN",
            evidence_state="insufficient_evidence",
            explanation="Listing maturity is not a 10C authoritative dimension.",
            supporting=[source],
            missing=["listing age history"],
            freshness=freshness_state,
        ),
        _dimension(
            "DIFFERENTIATION_OPPORTUNITY",
            value=None,
            classification="UNKNOWN" if not differentiation else "OBSERVED_FACT",
            evidence_state=state if differentiation else "insufficient_evidence",
            explanation=(
                "Evidence-backed 10C differentiators remain descriptive and are not "
                "converted into demand opportunity."
            ),
            supporting=[{**source, "differentiation": differentiation}],
            missing=[] if differentiation else ["product differentiation evidence"],
            freshness=freshness_state,
        ),
        _dimension(
            "EVIDENCE_COVERAGE",
            value=analysis.get("evidence_coverage") if analysis else None,
            classification="DERIVED_SIGNAL" if analysis else "UNKNOWN",
            evidence_state=state,
            explanation="Coverage preserves 10C evidence lineage.",
            supporting=[source],
            missing=[] if analysis else ["competition evidence"],
            freshness=freshness_state,
        ),
        _dimension(
            "EVIDENCE_FRESHNESS",
            value=(
                freshness.get("state", projection.freshness_state)
                if isinstance(freshness, dict)
                else projection.freshness_state
            ),
            classification="OBSERVED_FACT" if analysis else "UNKNOWN",
            evidence_state=state,
            explanation=(
                "Freshness is copied from dedicated competitor evidence and never "
                "silently marked current."
            ),
            supporting=[source],
            missing=[] if analysis else ["observation timestamp"],
            freshness=freshness_state,
        ),
    ]
    return dimensions, gaps


def calculate_intelligence(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    kind: str,
    idempotency_key: str | None = None,
) -> ProductOpportunityIntelligenceOutput:
    if kind not in ("demand", "competition"):
        raise ValueError("Unsupported intelligence kind.")
    opportunity, assessment, listings = _context(db, owner, opportunity_id, assessment_id)
    prices = _prices(db, owner, listings)
    now = intelligence_now()
    summary, snapshot = _evidence_summary(listings, prices, now)
    key = idempotency_key or f"opportunity-intelligence:{assessment.id}:{kind}"
    existing = db.scalar(
        select(ProductOpportunityIntelligenceOutput).where(
            ProductOpportunityIntelligenceOutput.owner_id == owner.id,
            ProductOpportunityIntelligenceOutput.assessment_id == assessment.id,
            ProductOpportunityIntelligenceOutput.kind == kind,
        )
    )
    if existing is not None:
        return existing
    if kind == "demand":
        dimensions, gaps = _demand(listings, summary, now)
    else:
        projection = get_or_create_projection(db, owner, opportunity, assessment)
        if projection is not None:
            dimensions, gaps = _competition_from_projection(projection, now)
            summary = {
                **summary,
                "competition_source": projection.source_state,
                "competition_projection_id": str(projection.id),
                "competition_analysis_id": (
                    str(projection.competitor_analysis_id)
                    if projection.competitor_analysis_id
                    else None
                ),
                "competition_change_comparison_id": (
                    str(projection.change_comparison_id)
                    if projection.change_comparison_id
                    else None
                ),
                "competition_ten_c_calculation_version": projection.ten_c_calculation_version,
                "competition_ten_d_calculation_version": projection.ten_d_calculation_version,
            }
            snapshot = {
                **snapshot,
                "competition_projection_id": str(projection.id),
                "competition_projection_fingerprint": projection.input_fingerprint,
                "competition_source": projection.source_state,
                "integration_contract_version": projection.contract_version,
                "ten_c_calculation_version": projection.ten_c_calculation_version,
                "ten_d_calculation_version": projection.ten_d_calculation_version,
            }
        else:
            dimensions, gaps = _competition(listings, prices, summary, now)
            source = "LEGACY_9B_EVIDENCE" if listings else "INSUFFICIENT_EVIDENCE"
            summary = {**summary, "competition_source": source}
            snapshot = {**snapshot, "competition_source": source}
    output = ProductOpportunityIntelligenceOutput(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        kind=kind,
        calculation_version=CALCULATION_VERSION,
        input_snapshot=snapshot,
        dimensions=dimensions,
        evidence_summary=summary,
        research_gaps=gaps,
        idempotency_key=key,
        notes="Derived intelligence only; no winner score or recommendation is produced.",
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output
