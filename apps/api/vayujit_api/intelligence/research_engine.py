# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.core.observability import correlation_id
from vayujit_api.identity.models import User
from vayujit_api.intelligence.closure import (
    economic_input,
    estimate_economics,
    evidence_quality,
    legal_risk_flags,
    source_diversity,
)
from vayujit_api.intelligence.models import (
    IntelligenceCompetitorProduct,
    IntelligenceCompetitorSnapshot,
    IntelligenceDifferentiation,
    IntelligenceEconomicEstimate,
    IntelligenceEvidence,
    IntelligenceOpportunity,
    IntelligencePainPoint,
    IntelligenceResearchCandidate,
    IntelligenceResearchCheckpoint,
    IntelligenceResearchMission,
    IntelligenceResearchReport,
    IntelligenceResearchRun,
    IntelligenceResearchSignal,
    IntelligenceReviewTheme,
    IntelligenceScoreEvaluation,
    IntelligenceSource,
    IntelligenceTrendObservation,
)
from vayujit_api.intelligence.policy import freshness_status
from vayujit_api.intelligence.service import now

SCORING_MODEL_VERSION = "winning-product-local-v1"
DEFAULT_WEIGHTS: dict[str, float] = {
    "demand": 0.18,
    "competition_opportunity": 0.16,
    "margin_potential": 0.16,
    "trend": 0.12,
    "differentiation": 0.12,
    "operational_simplicity": 0.10,
    "risk": 0.08,
    "evidence_confidence": 0.08,
}


@dataclass(frozen=True)
class Fixture:
    reference: str
    title: str
    category: str
    subcategory: str
    market: str
    prices: tuple[float, ...]
    demand: float
    competition: float
    trend: float
    trend_state: str
    complexity: float
    risk: float
    differentiation: float
    confidence: float
    review_count: int
    review_moat: bool
    seasonal: float
    stale: bool
    restrictions: tuple[tuple[str, str], ...]
    pain_points: tuple[tuple[str, int], ...]
    competitors: tuple[tuple[str, str, float, int, float], ...]
    attributes: dict[str, object]


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        "bamboo-organizer",
        "Bamboo Drawer Organizer",
        "home",
        "storage",
        "IN",
        (1499, 1599, 1699),
        82,
        28,
        78,
        "emerging",
        18,
        12,
        76,
        0.92,
        820,
        False,
        12,
        False,
        (),
        (("packaging damage", 18), ("size clarity", 12)),
        (("home-a", "HomeCo", 1399, 540, 4.2), ("home-b", "StoreLine", 1699, 320, 4.4)),
        {"weight_kg": 1.2, "length_cm": 42, "width_cm": 30, "height_cm": 6},
    ),
    Fixture(
        "glass-spice-jars",
        "Glass Spice Jar Set",
        "kitchen",
        "storage",
        "IN",
        (799, 899, 999),
        68,
        76,
        54,
        "stable",
        74,
        66,
        48,
        0.88,
        6800,
        True,
        8,
        True,
        (("glass", "BLOCK"), ("fragile", "REVIEW_REQUIRED")),
        (("breakage", 42), ("lid leakage", 28)),
        (("kitchen-a", "KitchenMax", 799, 6800, 4.5), ("kitchen-b", "JarWorld", 899, 7200, 4.4)),
        {"weight_kg": 2.8, "length_cm": 28, "width_cm": 20, "height_cm": 15},
    ),
    Fixture(
        "rechargeable-lamp",
        "Rechargeable Desk Lamp",
        "electronics",
        "lighting",
        "IN",
        (2299, 2499, 2699),
        76,
        62,
        70,
        "growing",
        55,
        58,
        68,
        0.84,
        4100,
        False,
        10,
        False,
        (("battery", "REVIEW_REQUIRED"), ("lithium_battery", "REVIEW_REQUIRED")),
        (("battery life", 31), ("charging port", 21)),
        (("lamp-a", "BrightLab", 2199, 4100, 4.1), ("lamp-b", "DeskGlow", 2599, 2900, 4.3)),
        {"weight_kg": 1.0, "length_cm": 18, "width_cm": 18, "height_cm": 35, "battery": True},
    ),
    Fixture(
        "wide-yoga-mat",
        "Extra Wide Yoga Mat",
        "fitness",
        "exercise",
        "IN",
        (1799, 1899),
        54,
        48,
        42,
        "seasonal",
        70,
        35,
        72,
        0.76,
        1200,
        False,
        75,
        False,
        (("oversized", "WARN"),),
        (("odor", 16), ("rolling edges", 14)),
        (("fitness-a", "FitWorld", 1699, 1200, 4.0),),
        {
            "weight_kg": 4.4,
            "length_cm": 190,
            "width_cm": 90,
            "height_cm": 2,
            "seasonal_peaks": ["Jan", "Jun"],
        },
    ),
    Fixture(
        "braided-usbc",
        "Braided USB-C Cable",
        "electronics",
        "accessories",
        "IN",
        (249, 299, 349),
        73,
        81,
        35,
        "declining",
        12,
        30,
        34,
        0.91,
        12500,
        True,
        5,
        False,
        (("electrical", "REVIEW_REQUIRED"),),
        (("fraying", 24),),
        (("cable-a", "CableHub", 199, 22000, 4.2), ("cable-b", "WireWorks", 299, 18000, 4.3)),
        {"weight_kg": 0.08, "length_cm": 200, "low_margin": True},
    ),
    Fixture(
        "festival-hamper",
        "Festival Gift Hamper",
        "gifting",
        "seasonal",
        "IN",
        (999, 1299, 1499),
        61,
        40,
        83,
        "seasonal",
        38,
        24,
        82,
        0.62,
        620,
        False,
        88,
        False,
        (),
        (("delivery timing", 19),),
        (("gift-a", "GiftLane", 1099, 620, 4.0),),
        {
            "weight_kg": 1.8,
            "length_cm": 30,
            "width_cm": 24,
            "height_cm": 18,
            "seasonal_peaks": ["Oct", "Nov"],
        },
    ),
    Fixture(
        "missing-evidence",
        "Modular Cable Box",
        "home",
        "organization",
        "IN",
        (),
        0,
        0,
        0,
        "insufficient_evidence",
        28,
        30,
        40,
        0.18,
        0,
        False,
        0,
        True,
        (),
        (),
        (),
        {"weight_kg": 1.0},
    ),
    Fixture(
        "powder-scoop",
        "Steel Protein Powder Scoop",
        "food_contact",
        "fitness",
        "IN",
        (399, 449),
        48,
        46,
        52,
        "stable",
        22,
        44,
        61,
        0.80,
        900,
        False,
        5,
        False,
        (("food_contact", "REVIEW_REQUIRED"), ("powder", "WARN")),
        (("handle sharpness", 12),),
        (("scoop-a", "NutriTools", 399, 900, 4.1),),
        {"weight_kg": 0.12, "length_cm": 18, "width_cm": 5, "height_cm": 5},
    ),
)


def _norm(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def _key(source_id: Any, fixture: Fixture) -> str:
    raw = "|".join((str(source_id), fixture.reference, fixture.market, _norm(fixture.title)))
    return hashlib.sha256(raw.encode()).hexdigest()


def _source(
    db: Session, user: User, source_class: str = "marketplace_fixture"
) -> IntelligenceSource:
    value = db.scalar(
        select(IntelligenceSource).where(
            IntelligenceSource.owner_id == user.id,
            IntelligenceSource.provider == f"local_deterministic:{source_class}",
        )
    )
    if value:
        return value
    stamp = now()
    value = IntelligenceSource(
        owner_id=user.id,
        source_type="internal_marketplace_data",
        display_name=f"Local {source_class.replace('_', ' ').title()} Fixtures",
        provider=f"local_deterministic:{source_class}",
        enabled=True,
        trust_classification="trusted_internal",
        access_method="internal",
        configuration_status="ready",
        terms_policy_status="not_applicable",
        metadata_json={
            "external_calls": False,
            "fixture_version": "slice2-v1",
            "source_class": source_class,
        },
        created_at=stamp,
        updated_at=stamp,
    )
    try:
        with db.begin_nested():
            db.add(value)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(IntelligenceSource).where(
                IntelligenceSource.owner_id == user.id,
                IntelligenceSource.provider == f"local_deterministic:{source_class}",
            )
        )
        if existing is None:
            raise
        return existing
    return value


def _evidence(
    db: Session,
    user: User,
    source: IntelligenceSource,
    run: IntelligenceResearchRun,
    fixture: Fixture,
) -> IntelligenceEvidence:
    key = f"fixture:{fixture.reference}:{run.ruleset_version}:{source.id}"
    value = db.scalar(
        select(IntelligenceEvidence).where(
            IntelligenceEvidence.owner_id == user.id,
            IntelligenceEvidence.idempotency_key == key,
        )
    )
    if value:
        return value
    observed = now() - (timedelta(days=60) if fixture.stale else timedelta(hours=3))
    value = IntelligenceEvidence(
        owner_id=user.id,
        source_id=source.id,
        research_run_id=run.id,
        source_reference=f"local://research-fixtures/{fixture.reference}",
        observed_at=observed,
        retrieved_at=now(),
        content_type="application/json",
        normalized_value={"fixture": fixture.reference, "attributes": fixture.attributes},
        excerpt_summary="Deterministic local fixture; not live marketplace data.",
        content_hash=hashlib.sha256(fixture.reference.encode()).hexdigest(),
        trust_classification="trusted_internal",
        verification_status="verified",
        freshness_status=freshness_status(observed),
        freshness_ttl_seconds=86400,
        metadata_json={"fixture": True, "external_calls": False},
        correlation_id=run.correlation_id or correlation_id() or "local-research",
        idempotency_key=key,
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(value)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(IntelligenceEvidence).where(
                IntelligenceEvidence.owner_id == user.id,
                IntelligenceEvidence.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        return existing
    return value


def _candidate(
    db: Session,
    user: User,
    run: IntelligenceResearchRun,
    source: IntelligenceSource,
    fixture: Fixture,
) -> IntelligenceResearchCandidate:
    key = _key(source.id, fixture)
    value = db.scalar(
        select(IntelligenceResearchCandidate).where(
            IntelligenceResearchCandidate.owner_id == user.id,
            IntelligenceResearchCandidate.deduplication_key == key,
        )
    )
    if value:
        return value
    stamp = now()
    value = IntelligenceResearchCandidate(
        owner_id=user.id,
        project_id=run.project_id,
        research_run_id=run.id,
        source_id=source.id,
        external_reference=fixture.reference,
        deduplication_key=key,
        title=fixture.title,
        normalized_title=_norm(fixture.title),
        category=fixture.category,
        subcategory=fixture.subcategory,
        market=fixture.market,
        source_reference=f"local://research-fixtures/{fixture.reference}",
        status="normalized",
        observed_price=statistics.median(fixture.prices) if fixture.prices else None,
        currency="INR",
        attributes=fixture.attributes,
        created_at=stamp,
        updated_at=stamp,
    )
    try:
        with db.begin_nested():
            db.add(value)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(IntelligenceResearchCandidate).where(
                IntelligenceResearchCandidate.owner_id == user.id,
                IntelligenceResearchCandidate.deduplication_key == key,
            )
        )
        if existing is None:
            raise
        return existing
    return value


def _signal(
    db: Session,
    user: User,
    candidate: IntelligenceResearchCandidate,
    evidence: IntelligenceEvidence | list[IntelligenceEvidence],
    kind: str,
    value: float | None,
    score: float | None,
    confidence: float,
    method: str,
    details: dict[str, object],
) -> None:
    evidence_rows = evidence if isinstance(evidence, list) else [evidence]
    if db.scalar(
        select(IntelligenceResearchSignal).where(
            IntelligenceResearchSignal.owner_id == user.id,
            IntelligenceResearchSignal.candidate_id == candidate.id,
            IntelligenceResearchSignal.signal_type == kind,
            IntelligenceResearchSignal.signal_version == 1,
        )
    ):
        return
    try:
        with db.begin_nested():
            db.add(
                IntelligenceResearchSignal(
                    owner_id=user.id,
                    candidate_id=candidate.id,
                    signal_type=kind,
                    value=value,
                    normalized_score=score,
                    source_evidence_ids=[str(item.id) for item in evidence_rows],
                    observed_at=evidence_rows[0].observed_at,
                    freshness=evidence_rows[0].freshness_status,
                    confidence=confidence,
                    calculation_method=method,
                    signal_version=1,
                    details=details,
                    created_at=now(),
                )
            )
            db.flush()
    except IntegrityError:
        return


def _prices(fixture: Fixture) -> dict[str, object]:
    if len(fixture.prices) < 2:
        return {"status": "insufficient_evidence", "observed_count": len(fixture.prices)}
    values = sorted(fixture.prices)
    median = statistics.median(values)
    spread = (max(values) - min(values)) / median if median else 0
    return {
        "status": "observed",
        "min": min(values),
        "max": max(values),
        "median": median,
        "p25": values[0],
        "p75": values[-1],
        "spread": spread,
        "stability": max(0, 1 - spread),
        "observed_count": len(values),
        "currency": "INR",
    }


def _supporting_rows(
    db: Session,
    user: User,
    candidate: IntelligenceResearchCandidate,
    fixture: Fixture,
    evidence: IntelligenceEvidence,
    source: IntelligenceSource,
) -> None:
    for ref, brand, price, reviews, rating in fixture.competitors:
        competitor = db.scalar(
            select(IntelligenceCompetitorProduct).where(
                IntelligenceCompetitorProduct.owner_id == user.id,
                IntelligenceCompetitorProduct.source_id == source.id,
                IntelligenceCompetitorProduct.external_reference == ref,
            )
        )
        if not competitor:
            competitor = IntelligenceCompetitorProduct(
                owner_id=user.id,
                source_id=source.id,
                external_reference=ref,
                title=f"{brand} {candidate.category}",
                brand=brand,
                created_at=now(),
            )
            try:
                with db.begin_nested():
                    db.add(competitor)
                    db.flush()
            except IntegrityError:
                competitor = db.scalar(
                    select(IntelligenceCompetitorProduct).where(
                        IntelligenceCompetitorProduct.owner_id == user.id,
                        IntelligenceCompetitorProduct.source_id == source.id,
                        IntelligenceCompetitorProduct.external_reference == ref,
                    )
                )
                if competitor is None:
                    raise
        if not db.scalar(
            select(IntelligenceCompetitorSnapshot).where(
                IntelligenceCompetitorSnapshot.owner_id == user.id,
                IntelligenceCompetitorSnapshot.competitor_id == competitor.id,
                IntelligenceCompetitorSnapshot.observed_at == evidence.observed_at,
            )
        ):
            try:
                with db.begin_nested():
                    db.add(
                        IntelligenceCompetitorSnapshot(
                            owner_id=user.id,
                            competitor_id=competitor.id,
                            evidence_id=evidence.id,
                            price=price,
                            currency="INR",
                            rating=rating,
                            review_count=reviews,
                            features={},
                            observed_at=evidence.observed_at,
                            created_at=now(),
                        )
                    )
                    db.flush()
            except IntegrityError:
                pass
    for issue, count in fixture.pain_points:
        if db.scalar(
            select(IntelligencePainPoint).where(
                IntelligencePainPoint.owner_id == user.id,
                IntelligencePainPoint.candidate_id == candidate.id,
                IntelligencePainPoint.issue == issue,
            )
        ):
            continue
        ids = [str(evidence.id)]
        rows = (
            IntelligencePainPoint(
                owner_id=user.id,
                candidate_id=candidate.id,
                issue=issue,
                frequency=count / 100,
                frequency_count=count,
                evidence_ids=ids,
                confidence=fixture.confidence,
                created_at=now(),
            ),
            IntelligenceReviewTheme(
                owner_id=user.id,
                candidate_id=candidate.id,
                theme_type="negative",
                label=issue,
                frequency_count=count,
                frequency_ratio=count / 100,
                evidence_ids=ids,
                confidence=fixture.confidence,
                created_at=now(),
            ),
            IntelligenceDifferentiation(
                owner_id=user.id,
                candidate_id=candidate.id,
                idea=f"Improve {issue}",
                classification="evidence_backed",
                rationale=f"Derived from {count}% complaint frequency.",
                evidence_ids=ids,
                created_at=now(),
            ),
        )
        for row in rows:
            try:
                with db.begin_nested():
                    db.add(row)
                    db.flush()
            except IntegrityError:
                pass


def score_candidate(
    db: Session,
    user: User,
    candidate: IntelligenceResearchCandidate,
    fixture: Fixture,
    evidence: IntelligenceEvidence,
    minimum_score: float = 45,
) -> IntelligenceScoreEvaluation:
    existing = db.scalar(
        select(IntelligenceScoreEvaluation).where(
            IntelligenceScoreEvaluation.owner_id == user.id,
            IntelligenceScoreEvaluation.candidate_id == candidate.id,
            IntelligenceScoreEvaluation.scoring_model_version == SCORING_MODEL_VERSION,
        )
    )
    if existing:
        return existing
    margin = (
        38
        if fixture.attributes.get("low_margin")
        else (
            min(
                100,
                max(
                    0,
                    (statistics.median(fixture.prices) - 200)
                    / max(statistics.median(fixture.prices), 1)
                    * 100,
                ),
            )
            if fixture.prices
            else 0
        )
    )
    dimensions = {
        "demand": fixture.demand,
        "competition_opportunity": 100 - fixture.competition,
        "margin_potential": margin,
        "trend": fixture.trend,
        "differentiation": fixture.differentiation,
        "operational_simplicity": 100 - fixture.complexity,
        "risk": 100 - fixture.risk,
        "evidence_confidence": fixture.confidence * 100,
    }
    contributions = {key: dimensions[key] * weight for key, weight in DEFAULT_WEIGHTS.items()}
    score = round(sum(contributions.values()), 3)
    restriction_rows = [
        {"rule": rule, "action": action, "reason": f"{rule} fixture policy."}
        for rule, action in fixture.restrictions
    ]
    blocked = any(row["action"] == "BLOCK" for row in restriction_rows)
    if blocked:
        recommendation = "BLOCKED"
    elif fixture.confidence < 0.45 or _prices(fixture)["status"] == "insufficient_evidence":
        recommendation = "RESEARCH_MORE"
    elif score >= 80:
        recommendation = "STRONG_OPPORTUNITY"
    elif score >= 65:
        recommendation = "PROMISING"
    elif score >= 45:
        recommendation = "REVIEW_REQUIRED"
    else:
        recommendation = "WEAK"
    critic: list[dict[str, object]] = []
    if fixture.review_moat:
        critic.append(
            {"type": "competition_moat", "reason": "Top competitor reviews create a moat."}
        )
    if fixture.stale:
        critic.append(
            {"type": "stale_evidence", "reason": "Observation is outside the fresh window."}
        )
    if fixture.seasonal >= 70:
        critic.append({"type": "seasonality", "reason": "Demand is strongly seasonal."})
    risk = {
        "operational": fixture.complexity,
        "compliance": 100 if blocked else fixture.risk,
        "ip": 10,
        "marketplace": fixture.competition,
        "financial": 100 - margin,
        "evidence": (1 - fixture.confidence) * 100,
        "classification": (
            "blocked"
            if blocked
            else "high" if fixture.risk >= 65 else "medium" if fixture.risk >= 35 else "low"
        ),
    }
    brand_value = fixture.attributes.get("brand")
    brand = brand_value if isinstance(brand_value, str) else None
    evaluation = IntelligenceScoreEvaluation(
        owner_id=user.id,
        candidate_id=candidate.id,
        scoring_model_version=SCORING_MODEL_VERSION,
        weights=DEFAULT_WEIGHTS,
        inputs={
            "price": _prices(fixture),
            "restrictions": restriction_rows,
            "supplier_availability": "UNKNOWN",
            "legal_risk": legal_risk_flags(
                title=fixture.title,
                brand=brand,
                attributes=fixture.attributes,
            ),
        },
        dimension_scores=dimensions,
        weighted_contributions=contributions,
        score=score,
        confidence=fixture.confidence,
        recommendation=recommendation,
        hard_blocked=blocked,
        risk_summary=risk,
        critic_findings=critic,
        reason=f"{recommendation}: deterministic local score {score:.1f}; no live metrics.",
        evidence_ids=[str(evidence.id)],
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(evaluation)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(IntelligenceScoreEvaluation).where(
                IntelligenceScoreEvaluation.owner_id == user.id,
                IntelligenceScoreEvaluation.candidate_id == candidate.id,
                IntelligenceScoreEvaluation.scoring_model_version == SCORING_MODEL_VERSION,
            )
        )
        if existing is None:
            raise
        return existing
    candidate.status = "rejected" if recommendation in {"BLOCKED", "WEAK"} else "evaluated"
    candidate.updated_at = now()
    if (
        not blocked
        and score >= minimum_score
        and not db.scalar(
            select(IntelligenceOpportunity).where(
                IntelligenceOpportunity.owner_id == user.id,
                IntelligenceOpportunity.candidate_id == candidate.id,
            )
        )
    ):
        opportunity = IntelligenceOpportunity(
            owner_id=user.id,
            candidate_id=candidate.id,
            research_run_id=candidate.research_run_id,
            title=candidate.title,
            category=candidate.category,
            market=candidate.market,
            status="review",
            score=score,
            confidence=fixture.confidence,
            hard_blocked=False,
            primary_reasons=[evaluation.reason],
            risk_summary=json.dumps(risk),
            evidence_count=1,
            freshness_state=evidence.freshness_status,
            created_at=now(),
            updated_at=now(),
        )
        try:
            with db.begin_nested():
                db.add(opportunity)
                db.flush()
        except IntegrityError:
            pass
        else:
            candidate.status = "promoted"
    return evaluation


def execute_research_run(
    db: Session,
    user: User,
    run: IntelligenceResearchRun,
    *,
    minimum_score: float = 45,
    crash_after_stage: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    if not settings.intelligence_enabled:
        raise HTTPException(503, "Intelligence is not enabled in this environment.")
    if not settings.intelligence_research_execution_enabled:
        raise HTTPException(
            503, "Intelligence research execution is not enabled in this environment."
        )
    checkpoint = db.scalar(
        select(IntelligenceResearchCheckpoint).where(
            IntelligenceResearchCheckpoint.owner_id == user.id,
            IntelligenceResearchCheckpoint.run_id == run.id,
        )
    )
    if not checkpoint:
        checkpoint = IntelligenceResearchCheckpoint(
            owner_id=user.id,
            run_id=run.id,
            stage="created",
            payload={},
            attempts=0,
            updated_at=now(),
        )
        db.add(checkpoint)
        db.flush()
    if run.status == "completed" and checkpoint.stage == "completed":
        return dict(run.summary_json)
    checkpoint.attempts += 1
    checkpoint.stage = "running"
    checkpoint.updated_at = now()
    run.status = "running"
    run.started_at = run.started_at or now()
    db.flush()
    checkpoint.payload = {
        **checkpoint.payload,
        "worker_claimed_at": checkpoint.updated_at.isoformat(),
        "provider_started_at": now().isoformat(),
    }
    if crash_after_stage == "running":
        db.commit()
        raise RuntimeError("local research worker crash checkpoint")
    source_classes = (
        "marketplace_fixture",
        "trend_fixture",
        "review_fixture",
        "pricing_fixture",
        "internal_fixture",
    )
    sources = {source_class: _source(db, user, source_class) for source_class in source_classes}
    source = sources["marketplace_fixture"]
    promoted = 0
    for fixture in FIXTURES:
        evidence_rows = [_evidence(db, user, item, run, fixture) for item in sources.values()]
        evidence = evidence_rows[0]
        candidate = _candidate(db, user, run, source, fixture)
        if "first_candidate_persisted_at" not in checkpoint.payload:
            checkpoint.payload = {
                **checkpoint.payload,
                "first_candidate_persisted_at": now().isoformat(),
            }
            db.flush()
        details = {"trend_state": fixture.trend_state, "seasonality_score": fixture.seasonal}
        for kind, value, score, method in (
            ("demand", fixture.demand, fixture.demand, "fixture demand proxy; not sales"),
            (
                "competition",
                fixture.competition,
                100 - fixture.competition,
                "inverse competition fixture",
            ),
            ("trend", fixture.trend, fixture.trend, f"fixture trend state: {fixture.trend_state}"),
            (
                "operational_complexity",
                fixture.complexity,
                100 - fixture.complexity,
                "handling factor model",
            ),
            ("risk", fixture.risk, 100 - fixture.risk, "risk dimension fixture"),
            (
                "differentiation",
                fixture.differentiation,
                fixture.differentiation,
                "review pain-point fixture",
            ),
            (
                "evidence_confidence",
                fixture.confidence,
                fixture.confidence * 100,
                "freshness and completeness",
            ),
        ):
            _signal(
                db,
                user,
                candidate,
                evidence,
                kind,
                value,
                score,
                fixture.confidence,
                method,
                details,
            )
        prices = _prices(fixture)
        _signal(
            db,
            user,
            candidate,
            evidence,
            "pricing",
            statistics.median(fixture.prices) if fixture.prices else None,
            70 if prices["status"] == "observed" else None,
            fixture.confidence,
            "observed fixture price distribution",
            prices,
        )
        _supporting_rows(db, user, candidate, fixture, evidence, source)
        _persist_closure_rows(db, user, run, candidate, fixture, evidence_rows)
        evaluation = score_candidate(db, user, candidate, fixture, evidence, minimum_score)
        promoted += int(
            evaluation.recommendation in {"STRONG_OPPORTUNITY", "PROMISING", "REVIEW_REQUIRED"}
            and not evaluation.hard_blocked
        )
    checkpoint.payload = {
        **checkpoint.payload,
        "candidate_processing_completed_at": now().isoformat(),
        "opportunity_promotion_completed_at": now().isoformat(),
    }
    if crash_after_stage == "provider":
        db.commit()
        raise RuntimeError("local research worker crash after provider checkpoint")
    checkpoint.stage = "completed"
    checkpoint.payload = {
        **checkpoint.payload,
        "candidates": len(FIXTURES),
        "promoted": promoted,
        "fixture_count": len(FIXTURES),
        "scoring_completed_at": now().isoformat(),
    }
    checkpoint.updated_at = now()
    run.status = "completed"
    run.completed_at = now()
    run.updated_at = now()
    run.summary_json = {
        "candidates": len(FIXTURES),
        "promoted": promoted,
        "provider": "local_deterministic",
    }
    db.commit()
    return dict(run.summary_json)


def run_mission(
    db: Session,
    user: User,
    mission: IntelligenceResearchMission,
    *,
    idempotency_key: str | None = None,
) -> IntelligenceResearchRun:
    from vayujit_api.intelligence.models import IntelligenceResearchProject

    project = db.scalar(
        select(IntelligenceResearchProject).where(
            IntelligenceResearchProject.id == mission.project_id,
            IntelligenceResearchProject.owner_id == user.id,
        )
    )
    if not project:
        raise HTTPException(404, "Research project not found.")
    key = idempotency_key or f"mission:{mission.id}:manual"
    run = db.scalar(
        select(IntelligenceResearchRun).where(
            IntelligenceResearchRun.owner_id == user.id,
            IntelligenceResearchRun.idempotency_key == key,
        )
    )
    if not run:
        stamp = now()
        run = IntelligenceResearchRun(
            owner_id=user.id,
            project_id=project.id,
            status="pending",
            correlation_id=correlation_id() or hashlib.sha256(key.encode()).hexdigest()[:32],
            ruleset_version=mission.ruleset_version,
            source_policy_reference="local-deterministic",
            summary_json={},
            idempotency_key=key,
            created_at=stamp,
            updated_at=stamp,
        )
        try:
            with db.begin_nested():
                db.add(run)
                db.flush()
        except IntegrityError:
            run = db.scalar(
                select(IntelligenceResearchRun).where(
                    IntelligenceResearchRun.owner_id == user.id,
                    IntelligenceResearchRun.idempotency_key == key,
                )
            )
            if run is None:
                raise
    run = db.scalar(
        select(IntelligenceResearchRun)
        .where(
            IntelligenceResearchRun.id == run.id,
            IntelligenceResearchRun.owner_id == user.id,
        )
        .with_for_update()
    )
    if run is None:
        raise HTTPException(404, "Research run not found.")
    execute_research_run(db, user, run, minimum_score=float(mission.minimum_score_threshold))
    mission.last_run_id = run.id
    mission.last_run_at = now()
    mission.status = "active" if mission.frequency != "manual" and mission.enabled else "completed"
    mission.updated_at = now()
    db.commit()
    return run


def generate_report(
    db: Session, user: User, run_id: Any, format: str
) -> IntelligenceResearchReport:
    if format not in {"json", "markdown", "html"}:
        raise HTTPException(422, "Only JSON, Markdown, and HTML reports are supported.")
    run = db.scalar(
        select(IntelligenceResearchRun).where(
            IntelligenceResearchRun.id == run_id,
            IntelligenceResearchRun.owner_id == user.id,
        )
    )
    if not run:
        raise HTTPException(404, "Research run not found.")
    checkpoint = db.scalar(
        select(IntelligenceResearchCheckpoint).where(
            IntelligenceResearchCheckpoint.owner_id == user.id,
            IntelligenceResearchCheckpoint.run_id == run.id,
        )
    )
    if checkpoint:
        checkpoint.payload = {
            **checkpoint.payload,
            "report_generation_started_at": now().isoformat(),
        }
        db.flush()
    existing = db.scalar(
        select(IntelligenceResearchReport).where(
            IntelligenceResearchReport.owner_id == user.id,
            IntelligenceResearchReport.run_id == run.id,
            IntelligenceResearchReport.format == format,
        )
    )
    if existing:
        if checkpoint:
            checkpoint.payload = {**checkpoint.payload, "report_ready_at": now().isoformat()}
            db.commit()
        return existing
    candidates = list(
        db.scalars(
            select(IntelligenceResearchCandidate).where(
                IntelligenceResearchCandidate.owner_id == user.id,
                IntelligenceResearchCandidate.research_run_id == run.id,
            )
        )
    )
    evaluations = list(
        db.scalars(
            select(IntelligenceScoreEvaluation).where(
                IntelligenceScoreEvaluation.owner_id == user.id,
                IntelligenceScoreEvaluation.candidate_id.in_(
                    [candidate.id for candidate in candidates]
                ),
            )
        )
    )
    payload = {
        "run_id": str(run.id),
        "provider": "local_deterministic",
        "sections": {
            "Executive Summary": run.summary_json,
            "Product": [
                {"id": str(candidate.id), "title": candidate.title, "category": candidate.category}
                for candidate in candidates
            ],
            "Scores": [
                {
                    "candidate_id": str(evaluation.candidate_id),
                    "score": float(evaluation.score),
                    "recommendation": evaluation.recommendation,
                    "dimensions": evaluation.dimension_scores,
                }
                for evaluation in evaluations
            ],
            "Rules": [
                {
                    "candidate_id": str(evaluation.candidate_id),
                    "risk": evaluation.risk_summary,
                    "critic": evaluation.critic_findings,
                }
                for evaluation in evaluations
            ],
            "Evidence Appendix": [
                {
                    "candidate_id": str(evaluation.candidate_id),
                    "evidence_ids": evaluation.evidence_ids,
                }
                for evaluation in evaluations
            ],
            "Assumptions": [
                "All metrics are local fixtures, not live marketplace facts.",
                "Economics are estimates until supplier evidence exists.",
            ],
        },
    }
    body = json.dumps(payload, indent=2, default=str)
    if format == "markdown":
        body = "# Local Research Report\n\n" + body
    elif format == "html":
        body = (
            "<html><body><h1>Local Research Report</h1><pre>"
            + body.replace("&", "&amp;").replace("<", "&lt;")
            + "</pre></body></html>"
        )
    report = IntelligenceResearchReport(
        owner_id=user.id,
        run_id=run.id,
        format=format,
        title="Local Deterministic Research Report",
        content=body,
        provenance_json={
            "run_id": str(run.id),
            "evidence_ids": [
                item for evaluation in evaluations for item in evaluation.evidence_ids
            ],
        },
        created_at=now(),
    )
    db.add(report)
    db.commit()
    if checkpoint:
        checkpoint.payload = {**checkpoint.payload, "report_ready_at": now().isoformat()}
        db.commit()
    return report


def _persist_closure_rows(
    db: Session,
    user: User,
    run: IntelligenceResearchRun,
    candidate: IntelligenceResearchCandidate,
    fixture: Fixture,
    evidence_rows: list[IntelligenceEvidence],
) -> None:
    """Persist append-only trend and one versioned economics estimate."""
    evidence = evidence_rows[0]
    source_metrics = source_diversity(
        [str(item.metadata_json.get("source_class", "unknown")) for item in evidence_rows],
        [str(item.id) for item in evidence_rows],
    )
    quality = evidence_quality(
        freshness=[item.freshness_status for item in evidence_rows],
        source_diversity_score=float(source_metrics["source_diversity_score"]),
        verification_states=[item.verification_status for item in evidence_rows],
        observation_count=len(evidence_rows),
        critical_signal_completeness=1.0 if fixture.prices else 0.5,
        stale_evidence_ratio=sum(
            item.freshness_status in {"stale", "expired"} for item in evidence_rows
        )
        / max(1, len(evidence_rows)),
    )
    if (
        db.scalar(
            select(IntelligenceTrendObservation).where(
                IntelligenceTrendObservation.owner_id == user.id,
                IntelligenceTrendObservation.candidate_id == candidate.id,
                IntelligenceTrendObservation.observed_at == evidence.observed_at,
            )
        )
        is None
    ):
        try:
            with db.begin_nested():
                db.add(
                    IntelligenceTrendObservation(
                        owner_id=user.id,
                        candidate_id=candidate.id,
                        market=fixture.market,
                        category=fixture.category,
                        trend_state=fixture.trend_state,
                        velocity=fixture.trend,
                        acceleration=fixture.trend - 50,
                        seasonality=fixture.seasonal,
                        confidence=fixture.confidence,
                        source_evidence_ids=[str(item.id) for item in evidence_rows],
                        observed_at=evidence.observed_at,
                        created_at=now(),
                        correlation_id=run.correlation_id,
                    )
                )
                db.flush()
        except IntegrityError:
            pass
    prices = statistics.median(fixture.prices) if fixture.prices else None
    economics = estimate_economics(
        {
            "selling_price": economic_input(
                prices,
                "OBSERVED" if prices else "UNKNOWN",
                evidence_id=str(evidence.id) if prices else None,
                confidence=fixture.confidence,
            ),
            "sourcing_cost": economic_input(
                prices * 0.38 if prices else None,
                "ESTIMATED",
                reason="local bounded sourcing proxy",
                confidence=0.35,
            ),
            "marketplace_fee": economic_input(
                prices * 0.15 if prices else None,
                "ASSUMED",
                reason="local marketplace fee assumption",
                confidence=0.3,
            ),
            "fulfilment": economic_input(
                80, "ASSUMED", reason="local fulfilment assumption", confidence=0.2
            ),
            "shipping": economic_input(
                60, "ASSUMED", reason="local shipping assumption", confidence=0.2
            ),
            "advertising_allowance": economic_input(
                prices * 0.05 if prices else None,
                "ASSUMED",
                reason="launch allowance",
                confidence=0.2,
            ),
            "return_allowance": economic_input(
                prices * 0.03 if prices else None,
                "ASSUMED",
                reason="return allowance",
                confidence=0.2,
            ),
            "tax_assumption": economic_input(
                prices * 0.05 if prices else None,
                "ASSUMED",
                reason="tax assumption is not verified",
                confidence=0.1,
            ),
        }
    )
    if (
        db.scalar(
            select(IntelligenceEconomicEstimate).where(
                IntelligenceEconomicEstimate.owner_id == user.id,
                IntelligenceEconomicEstimate.candidate_id == candidate.id,
                IntelligenceEconomicEstimate.model_version == "economics-v1",
            )
        )
        is None
    ):
        try:
            with db.begin_nested():
                db.add(
                    IntelligenceEconomicEstimate(
                        owner_id=user.id,
                        candidate_id=candidate.id,
                        model_version="economics-v1",
                        currency="INR",
                        inputs={
                            **economics["inputs"],
                            "source_diversity": source_metrics,
                            "evidence_quality": quality,
                        },
                        outputs=economics["outputs"],
                        confidence=economics["confidence"],
                        assumption_summary=economics["assumptions"],
                        created_at=now(),
                    )
                )
                db.flush()
        except IntegrityError:
            pass
