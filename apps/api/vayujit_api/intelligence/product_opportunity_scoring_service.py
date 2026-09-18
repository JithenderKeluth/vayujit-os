"""Deterministic, explainable Winning Product scoring over 9B-9E outputs."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_commercial_models import (
    ProductOpportunityCommercialOutput,
)
from vayujit_api.intelligence.product_opportunity_feasibility_models import (
    ProductOpportunitySourcingFeasibilityOutput,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    ProductOpportunityIntelligenceOutput,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunityAssessment
from vayujit_api.intelligence.product_opportunity_scoring_models import (
    CALCULATION_VERSION,
    PROFILE_VERSION,
    SCORING_MODEL_VERSION,
    ProductOpportunityDecision,
    ProductOpportunityScore,
)
from vayujit_api.intelligence.product_opportunity_scoring_schemas import (
    ComparisonRequest,
    DecisionRequest,
    ScoreCalculateRequest,
)
from vayujit_api.intelligence.product_opportunity_synthesis_models import (
    ProductOpportunityRiskEvidenceSynthesis,
)

CANONICAL_WEIGHTS: dict[str, Decimal] = {
    "DEMAND_ATTRACTIVENESS": Decimal("20"),
    "COMPETITIVE_OPPORTUNITY": Decimal("15"),
    "COMMERCIAL_VIABILITY": Decimal("20"),
    "CAPITAL_EFFICIENCY": Decimal("15"),
    "SUPPLIER_FEASIBILITY": Decimal("15"),
    "SOURCING_RESILIENCE": Decimal("10"),
    "DIFFERENTIATION_POTENTIAL": Decimal("5"),
}

DIMENSION_ORDER = tuple(CANONICAL_WEIGHTS)
SCORE_BANDS = (
    (Decimal("80"), "VERY_HIGH"),
    (Decimal("65"), "HIGH"),
    (Decimal("45"), "MODERATE"),
    (Decimal("25"), "LOW"),
    (Decimal("0"), "VERY_LOW"),
)


def _assessment(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityAssessment:
    row = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if row is None:
        raise LookupError("Product opportunity assessment not found.")
    return row


def _finite_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _clamp(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _dimension(output: Any, name: str) -> dict[str, Any] | None:
    if output is None:
        return None
    for item in output.dimensions or []:
        if isinstance(item, dict) and item.get("dimension") == name:
            return item
    return None


def _value(output: Any, name: str) -> Any:
    item = _dimension(output, name)
    return item.get("value") if item else None


def _state(item: dict[str, Any] | None) -> str:
    if not item:
        return "UNKNOWN"
    value = str(item.get("evidence_state", "unknown")).upper()
    return {
        "AVAILABLE": "AVAILABLE",
        "PARTIAL": "PARTIAL",
        "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
        "UNKNOWN": "UNKNOWN",
    }.get(value, "UNKNOWN")


def _number(value: Any) -> Decimal | None:
    if isinstance(value, dict):
        for key in (
            "value",
            "count",
            "eligible",
            "matched",
            "available_capital",
            "maximum_landed_cost",
        ):
            if key in value:
                parsed = _finite_decimal(value[key])
                if parsed is not None:
                    return parsed
        return None
    return _finite_decimal(value)


def _normalise(
    value: Decimal | None, low: Decimal, high: Decimal, *, inverse: bool = False
) -> Decimal | None:
    if value is None or high <= low:
        return None
    result = (value - low) * Decimal("100") / (high - low)
    if inverse:
        result = Decimal("100") - result
    return _round(_clamp(result))


def _band(score: Decimal | None) -> str:
    if score is None:
        return "UNAVAILABLE"
    return next(label for threshold, label in SCORE_BANDS if score >= threshold)


def _source_ids(outputs: Iterable[Any]) -> list[str]:
    return [str(row.id) for row in outputs if row is not None]


def _input_dimensions(
    intelligence: list[ProductOpportunityIntelligenceOutput],
    commercial: ProductOpportunityCommercialOutput | None,
    sourcing: ProductOpportunitySourcingFeasibilityOutput | None,
) -> dict[str, tuple[Decimal | None, str, str, str, list[str]]]:
    demand = next((row for row in intelligence if row.kind == "demand"), None)
    competition = next((row for row in intelligence if row.kind == "competition"), None)
    demand_activity = _number(_value(demand, "MARKET_ACTIVITY"))
    demand_score = _normalise(demand_activity, Decimal("0"), Decimal("10"))
    demand_item = _dimension(demand, "MARKET_ACTIVITY")
    if demand_item and demand_score is not None and _state(demand_item) == "AVAILABLE":
        demand_state = "AVAILABLE"
    elif demand_score is not None:
        demand_state = "PARTIAL"
    else:
        demand_state = "UNKNOWN"

    density = _number(_value(competition, "COMPETITOR_DENSITY"))
    price_item = _dimension(competition, "PRICE_COMPETITION")
    competition_score = (
        _normalise(density, Decimal("0"), Decimal("100"), inverse=True)
        if density is not None and price_item and _state(price_item) != "UNKNOWN"
        else None
    )
    competition_state = "PARTIAL" if competition_score is not None else "INSUFFICIENT_EVIDENCE"

    economics = commercial.economics if commercial else {}
    margin = _finite_decimal(economics.get("contribution_margin_percent"))
    commercial_score = _normalise(margin, Decimal("0"), Decimal("100"))
    commercial_item = _dimension(commercial, "MARGIN_VIABILITY")
    commercial_state = (
        _state(commercial_item) if commercial_score is not None else "INSUFFICIENT_EVIDENCE"
    )

    known_capital = _finite_decimal(economics.get("known_total_initial_capital"))
    constraint = commercial.constraint_snapshot if commercial else {}
    available_capital = _finite_decimal(constraint.get("available_capital"))
    capital_score = (
        _normalise(
            known_capital / available_capital * Decimal("100"),
            Decimal("0"),
            Decimal("100"),
            inverse=True,
        )
        if known_capital is not None and available_capital is not None and available_capital > 0
        else None
    )
    capital_state = "AVAILABLE" if capital_score is not None else "INSUFFICIENT_EVIDENCE"

    eligible = (
        _number(
            (sourcing.summary if sourcing else {}).get("supplier_availability", {}).get("eligible")
        )
        if sourcing
        else None
    )
    supplier_score = _normalise(eligible, Decimal("0"), Decimal("5"))
    supplier_state = "PARTIAL" if supplier_score is not None else "UNKNOWN"

    resilience_item = _dimension(sourcing, "SOURCING_RESILIENCE")
    resilience_value = _value(sourcing, "SOURCING_RESILIENCE")
    resilience_score = _normalise(_number(resilience_value), Decimal("0"), Decimal("5"))
    resilience_state = _state(resilience_item) if resilience_score is not None else "UNKNOWN"

    differentiation_item = _dimension(competition, "DIFFERENTIATION_OPPORTUNITY")
    differentiation_score = _normalise(
        _number(_value(competition, "DIFFERENTIATION_OPPORTUNITY")), Decimal("0"), Decimal("100")
    )
    differentiation_state = (
        _state(differentiation_item) if differentiation_score is not None else "UNKNOWN"
    )
    ids = _source_ids([demand, competition, commercial, sourcing])
    return {
        "DEMAND_ATTRACTIVENESS": (
            demand_score,
            demand_state,
            "MARKET_ACTIVITY",
            "Capped observed listing activity proxy; not sales.",
            ids,
        ),
        "COMPETITIVE_OPPORTUNITY": (
            competition_score,
            competition_state,
            "COMPETITOR_DENSITY",
            "Inverse density uses price evidence; sparse demand is not positive.",
            ids,
        ),
        "COMMERCIAL_VIABILITY": (
            commercial_score,
            commercial_state,
            "MARGIN_VIABILITY",
            "Contribution margin is normalized; contribution is not profit.",
            ids,
        ),
        "CAPITAL_EFFICIENCY": (
            capital_score,
            capital_state,
            "CAPITAL_EFFICIENCY",
            "Known initial capital is compared with the versioned available-capital constraint.",
            ids,
        ),
        "SUPPLIER_FEASIBILITY": (
            supplier_score,
            supplier_state,
            "SUPPLIER_AVAILABILITY",
            "Only eligible supplier count is used; discovery is not qualification.",
            ids,
        ),
        "SOURCING_RESILIENCE": (
            resilience_score,
            resilience_state,
            "SOURCING_RESILIENCE",
            "Resilience remains unknown without authoritative portfolio evidence.",
            ids,
        ),
        "DIFFERENTIATION_POTENTIAL": (
            differentiation_score,
            differentiation_state,
            "DIFFERENTIATION_OPPORTUNITY",
            "No differentiation is fabricated when competition evidence is unavailable.",
            ids,
        ),
    }


def _serialize_weights(weights: dict[str, Decimal]) -> dict[str, str]:
    return {key: str(value) for key, value in weights.items()}


def _score_row(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: ScoreCalculateRequest,
) -> ProductOpportunityScore:
    assessment = _assessment(db, owner, opportunity_id, assessment_id)
    weights = request.weights or CANONICAL_WEIGHTS
    profile_version = request.profile_version if request.weights else PROFILE_VERSION
    existing = db.scalar(
        select(ProductOpportunityScore).where(
            ProductOpportunityScore.owner_id == owner.id,
            ProductOpportunityScore.assessment_id == assessment_id,
            ProductOpportunityScore.scoring_model_version == SCORING_MODEL_VERSION,
            ProductOpportunityScore.profile_version == profile_version,
        )
    )
    if existing is not None:
        return existing
    intelligence = list(
        db.scalars(
            select(ProductOpportunityIntelligenceOutput).where(
                ProductOpportunityIntelligenceOutput.owner_id == owner.id,
                ProductOpportunityIntelligenceOutput.assessment_id == assessment_id,
            )
        )
    )
    commercial = db.scalar(
        select(ProductOpportunityCommercialOutput).where(
            ProductOpportunityCommercialOutput.owner_id == owner.id,
            ProductOpportunityCommercialOutput.assessment_id == assessment_id,
        )
    )
    sourcing = db.scalar(
        select(ProductOpportunitySourcingFeasibilityOutput).where(
            ProductOpportunitySourcingFeasibilityOutput.owner_id == owner.id,
            ProductOpportunitySourcingFeasibilityOutput.assessment_id == assessment_id,
        )
    )
    synthesis = db.scalar(
        select(ProductOpportunityRiskEvidenceSynthesis).where(
            ProductOpportunityRiskEvidenceSynthesis.owner_id == owner.id,
            ProductOpportunityRiskEvidenceSynthesis.assessment_id == assessment_id,
        )
    )
    dimensions = _input_dimensions(intelligence, commercial, sourcing)
    risks = synthesis.risks if synthesis else []
    blockers = [
        item
        for item in risks
        if isinstance(item, dict) and str(item.get("severity", "")).upper() == "HIGH"
    ]
    readiness = (
        str(synthesis.summary.get("assessment_readiness", "UNKNOWN")) if synthesis else "UNKNOWN"
    )
    confidence = str(synthesis.summary.get("confidence", "UNKNOWN")) if synthesis else "UNKNOWN"
    risk_level = "HIGH" if blockers else "MODERATE" if risks else "LOW"
    available = [
        key
        for key, (score, state, *_rest) in dimensions.items()
        if score is not None and state in {"AVAILABLE", "PARTIAL"}
    ]
    unavailable = [key for key in DIMENSION_ORDER if key not in available]
    if blockers:
        eligibility = "BLOCKED"
    elif len(available) >= 5:
        eligibility = "SCORABLE"
    elif len(available) >= 2:
        eligibility = "PARTIALLY_SCORABLE"
    else:
        eligibility = "INSUFFICIENT_EVIDENCE"
    total = sum((weights[key] for key in available), Decimal("0"))
    overall = None
    if eligibility in {"SCORABLE", "PARTIALLY_SCORABLE"} and total > 0:
        overall = _round(
            sum((dimensions[key][0] or Decimal("0")) * weights[key] for key in available) / total
        )
    classification = _band(overall)
    label = {
        "BLOCKED": "BLOCKED",
        "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
        "PARTIALLY_SCORABLE": "PROMISING_BUT_RESEARCH_REQUIRED",
    }.get(
        eligibility,
        (
            "STRONGER_CANDIDATE"
            if overall is not None and overall >= 65
            else "ECONOMICS_REQUIRE_REVIEW"
        ),
    )
    dimension_rows: list[dict[str, Any]] = []
    positive: list[str] = []
    negative: list[str] = []
    improvements: list[str] = []
    for key in DIMENSION_ORDER:
        score, state, source, explanation, sources = dimensions[key]
        contribution = (
            _round(score * weights[key] / total) if score is not None and total > 0 else None
        )
        dimension_rows.append(
            {
                "dimension": key,
                "raw_input": _value(commercial, source)
                or _value(sourcing, source)
                or _value(next((x for x in intelligence if _dimension(x, source)), None), source),
                "normalized_score": str(score) if score is not None else None,
                "weight": str(weights[key]),
                "weighted_contribution": str(contribution) if contribution is not None else None,
                "evidence_state": state,
                "source": source,
                "source_ids": sources,
                "explanation": explanation,
                "calculation_version": CALCULATION_VERSION,
            }
        )
        if score is not None and score >= 70:
            positive.append(f"{key} is supported by a normalized score of {score}.")
        if score is not None and score < 40:
            negative.append(f"{key} is weak at a normalized score of {score}.")
        if score is None:
            negative.append("MISSING_CRITICAL_EVIDENCE:" + key)
            improvements.append(f"Obtain authoritative evidence for {key}.")
    if blockers:
        negative.extend(str(item.get("explanation", "Authoritative blocker.")) for item in blockers)
    sensitivity: dict[str, Any] = (
        commercial.sensitivity
        if commercial is not None and isinstance(commercial.sensitivity, dict)
        else {}
    )
    scenario_values: list[dict[str, Any]] = [
        item for item in sensitivity.get("combined", []) if isinstance(item, dict)
    ]
    deltas: list[Decimal] = [
        item
        for item in (_finite_decimal(value.get("delta_contribution")) for value in scenario_values)
        if item is not None
    ]
    stability = (
        "UNKNOWN"
        if not deltas
        else (
            "STABLE"
            if max(abs(item) for item in deltas) <= Decimal("1")
            else (
                "MODERATELY_SENSITIVE"
                if max(abs(item) for item in deltas) <= Decimal("5")
                else "HIGHLY_SENSITIVE"
            )
        )
    )
    lineage = {
        "assessment": str(assessment.id),
        "intelligence": _source_ids(intelligence),
        "commercial": str(commercial.id) if commercial else None,
        "sourcing": str(sourcing.id) if sourcing else None,
        "synthesis": str(synthesis.id) if synthesis else None,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "lineage": lineage,
                "weights": _serialize_weights(weights),
                "model": SCORING_MODEL_VERSION,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    row = ProductOpportunityScore(
        owner_id=owner.id,
        opportunity_id=opportunity_id,
        assessment_id=assessment_id,
        scoring_model_version=SCORING_MODEL_VERSION,
        calculation_version=CALCULATION_VERSION,
        profile_version=profile_version,
        input_fingerprint=fingerprint,
        upstream_lineage=lineage,
        eligibility=eligibility,
        overall_score=overall,
        classification=classification,
        decision_label=label,
        confidence=confidence,
        risk_level=risk_level,
        assessment_readiness=readiness,
        evidence_state=assessment.evidence_state,
        dimensions=dimension_rows,
        unavailable_dimensions=unavailable,
        risk_adjustments=(
            [{"type": "BLOCKER", "effect": "NO_NORMAL_SCORE", "count": len(blockers)}]
            if blockers
            else []
        ),
        positive_drivers=positive,
        negative_drivers=negative,
        improvement_areas=improvements,
        sensitivity={"scenarios": scenario_values, "stability": stability, "label": "SCENARIO"},
        comparability={
            "status": (
                "COMPARABLE"
                if eligibility == "SCORABLE"
                else (
                    "PARTIALLY_COMPARABLE"
                    if eligibility == "PARTIALLY_SCORABLE"
                    else "NOT_COMPARABLE"
                )
            ),
            "reason": "Same model and assessment context required.",
        },
        weights=_serialize_weights(weights),
        idempotency_key=request.idempotency_key
        or f"opportunity-score:{assessment.id}:{profile_version}",
    )
    db.add(row)
    return row


def calculate_score(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    request: ScoreCalculateRequest,
) -> ProductOpportunityScore:
    return _score_row(db, owner, opportunity_id, assessment_id, request)


def get_score(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ProductOpportunityScore:
    _assessment(db, owner, opportunity_id, assessment_id)
    row = db.scalar(
        select(ProductOpportunityScore)
        .where(
            ProductOpportunityScore.owner_id == owner.id,
            ProductOpportunityScore.opportunity_id == opportunity_id,
            ProductOpportunityScore.assessment_id == assessment_id,
        )
        .order_by(ProductOpportunityScore.created_at.desc())
    )
    if row is None:
        raise LookupError("Product opportunity score not found.")
    return row


def score_history(
    db: Session, owner: User, opportunity_id: uuid.UUID
) -> list[ProductOpportunityScore]:
    return list(
        db.scalars(
            select(ProductOpportunityScore)
            .where(
                ProductOpportunityScore.owner_id == owner.id,
                ProductOpportunityScore.opportunity_id == opportunity_id,
            )
            .order_by(ProductOpportunityScore.created_at.desc())
        )
    )


def compare_scores(db: Session, owner: User, data: ComparisonRequest) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(ProductOpportunityScore).where(
                ProductOpportunityScore.owner_id == owner.id,
                ProductOpportunityScore.assessment_id.in_(data.assessment_ids),
            )
        )
    )
    by_id = {row.assessment_id: row for row in rows}
    missing = [str(item) for item in data.assessment_ids if item not in by_id]
    if missing:
        raise LookupError("Every comparison assessment must have a score for this owner.")
    model_versions = {row.scoring_model_version for row in rows}
    profile_versions = {row.profile_version for row in rows}
    comparable = (
        len(model_versions) == 1
        and len(profile_versions) == 1
        and all(row.eligibility == "SCORABLE" for row in rows)
    )
    return {
        "comparability": "COMPARABLE" if comparable else "NOT_COMPARABLE",
        "reason": "Scores must be scorable under one model and profile version for this owner.",
        "items": [
            row
            for row in sorted(
                rows,
                key=lambda item: (
                    -(float(item.overall_score) if item.overall_score is not None else -1),
                    str(item.assessment_id),
                ),
            )
        ],
    }


def rank_scores(db: Session, owner: User, data: ComparisonRequest) -> dict[str, Any]:
    comparison = compare_scores(db, owner, data)
    if comparison["comparability"] != "COMPARABLE":
        return {**comparison, "ranking": []}
    ranking = [
        {
            "rank": index,
            "assessment_id": str(row.assessment_id),
            "score_id": str(row.id),
            "score": row.overall_score,
            "classification": row.classification,
            "confidence": row.confidence,
            "readiness": row.assessment_readiness,
        }
        for index, row in enumerate(comparison["items"], 1)
    ]
    return {**comparison, "ranking": ranking}


def add_decision(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    data: DecisionRequest,
) -> ProductOpportunityDecision:
    score = get_score(db, owner, opportunity_id, assessment_id)
    key = data.idempotency_key or f"opportunity-decision:{score.id}:{data.action}"
    existing = db.scalar(
        select(ProductOpportunityDecision).where(
            ProductOpportunityDecision.owner_id == owner.id,
            ProductOpportunityDecision.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing
    row = ProductOpportunityDecision(
        owner_id=owner.id,
        opportunity_id=opportunity_id,
        assessment_id=assessment_id,
        score_id=score.id,
        action=data.action,
        rationale=data.rationale,
        idempotency_key=key,
    )
    db.add(row)
    return row


def model_definition() -> dict[str, Any]:
    return {
        "version": SCORING_MODEL_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "profile_version": PROFILE_VERSION,
        "weights": _serialize_weights(CANONICAL_WEIGHTS),
        "dimensions": list(DIMENSION_ORDER),
        "bands": [{"minimum": str(minimum), "label": label} for minimum, label in SCORE_BANDS],
        "missing_evidence": (
            "No missing dimension is converted to zero; unavailable dimensions remain explicit "
            "and suppress ordinary ranking."
        ),
        "confidence": "Displayed separately from attractiveness.",
        "risk": "Displayed separately; authoritative blockers suppress a normal score.",
    }
