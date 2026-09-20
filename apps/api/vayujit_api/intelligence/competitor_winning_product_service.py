"""Authoritative, versioned adapter from competitor intelligence to 9B."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_change_models import (
    CALCULATION_VERSION as TEN_D_CALCULATION_VERSION,
)
from vayujit_api.intelligence.competitor_change_models import (
    CompetitorChangeComparison,
)
from vayujit_api.intelligence.competitor_commercial_models import (
    CALCULATION_VERSION as TEN_C_CALCULATION_VERSION,
)
from vayujit_api.intelligence.competitor_commercial_models import (
    CompetitorCommercialAnalysis,
    CompetitorComparableCohortEntry,
)
from vayujit_api.intelligence.competitor_models import CompetitorContext
from vayujit_api.intelligence.competitor_winning_product_models import (
    INTEGRATION_CONTRACT_VERSION,
    SOURCE_DEDICATED,
    SOURCE_INSUFFICIENT,
    CompetitorWinningProductProjection,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import CALCULATION_VERSION
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _json(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, tuple):
        return [_json(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(_json(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def find_context(db: Session, owner: User, opportunity_id: uuid.UUID) -> CompetitorContext | None:
    return db.scalar(
        select(CompetitorContext)
        .where(
            CompetitorContext.owner_id == owner.id,
            (
                (CompetitorContext.product_opportunity_id == opportunity_id)
                | (
                    (CompetitorContext.subject_type == "PRODUCT_OPPORTUNITY")
                    & (CompetitorContext.subject_reference == opportunity_id)
                )
            ),
        )
        .order_by(CompetitorContext.version.desc(), CompetitorContext.created_at.desc())
    )


def _analysis(
    db: Session, owner: User, context: CompetitorContext
) -> CompetitorCommercialAnalysis | None:
    return db.scalar(
        select(CompetitorCommercialAnalysis)
        .where(
            CompetitorCommercialAnalysis.owner_id == owner.id,
            CompetitorCommercialAnalysis.context_id == context.id,
            CompetitorCommercialAnalysis.status.in_(("COMPLETED", "PARTIALLY_COMPLETED")),
            CompetitorCommercialAnalysis.calculation_version == TEN_C_CALCULATION_VERSION,
        )
        .order_by(
            CompetitorCommercialAnalysis.analysis_version.desc(),
            CompetitorCommercialAnalysis.created_at.desc(),
        )
    )


def _comparison(
    db: Session, owner: User, context: CompetitorContext, analysis: CompetitorCommercialAnalysis
) -> CompetitorChangeComparison | None:
    return db.scalar(
        select(CompetitorChangeComparison)
        .where(
            CompetitorChangeComparison.owner_id == owner.id,
            CompetitorChangeComparison.context_id == context.id,
            CompetitorChangeComparison.current_analysis_id == analysis.id,
            CompetitorChangeComparison.status.in_(("COMPLETED", "PARTIALLY_COMPLETED")),
            CompetitorChangeComparison.calculation_version == TEN_D_CALCULATION_VERSION,
        )
        .order_by(
            CompetitorChangeComparison.comparison_version.desc(),
            CompetitorChangeComparison.created_at.desc(),
        )
    )


def _gaps(
    analysis: CompetitorCommercialAnalysis | None, comparison: CompetitorChangeComparison | None
) -> list[dict[str, object]]:
    values: dict[str, dict[str, object]] = {}
    if analysis is not None:
        for item in analysis.research_gaps or []:
            if isinstance(item, dict) and item.get("code"):
                values.setdefault(str(item["code"]), {**item, "origins": ["10C"]})
        required = {
            "PRICE_EVIDENCE_REQUIRED": analysis.pricing_analysis,
            "BRAND_IDENTITY_REQUIRED": analysis.concentration_analysis,
            "SELLER_IDENTITY_REQUIRED": analysis.concentration_analysis,
            "RATING_SAMPLE_REQUIRED": analysis.rating_analysis,
            "REVIEW_SAMPLE_REQUIRED": analysis.review_analysis,
            "FEATURE_EVIDENCE_REQUIRED": analysis.differentiation_analysis,
        }
        for code, section in required.items():
            if not section:
                values.setdefault(
                    code, {"code": code, "reason": "Evidence is not available.", "origins": ["10C"]}
                )
    if (
        comparison is not None
        and isinstance(comparison.summary, dict)
        and isinstance(
            cast(dict[str, object], comparison.summary).get("unresolved_count"), (int, str)
        )
        and int(
            cast(str | int, cast(dict[str, object], comparison.summary).get("unresolved_count", 0))
        )
        > 0
    ):
        values.setdefault(
            "COMPETITIVE_CHANGE_REVIEW_REQUIRED",
            {
                "code": "COMPETITIVE_CHANGE_REVIEW_REQUIRED",
                "reason": "Unresolved 10D changes require review.",
                "origins": ["10D"],
            },
        )
    return list(values.values())


def _projection_payload(
    context: CompetitorContext,
    analysis: CompetitorCommercialAnalysis | None,
    comparison: CompetitorChangeComparison | None,
    entries: list[CompetitorComparableCohortEntry],
    generated_at: datetime,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], str, str]:
    confirmed = sum(row.included and row.identity_state == "CONFIRMED" for row in entries)
    probable = sum(row.included and row.identity_state == "PROBABLE" for row in entries)
    ambiguous = sum(row.identity_state == "AMBIGUOUS" for row in entries)
    rejected = sum(row.identity_state == "REJECTED" for row in entries)
    if analysis is None:
        source = SOURCE_INSUFFICIENT
        freshness = "UNKNOWN"
        contradiction = "NONE"
        payload: dict[str, object] = {
            "context": {
                "id": str(context.id),
                "marketplace": context.marketplace,
                "market": context.market,
            },
            "cohort": {
                "confirmed_count": 0,
                "probable_count": 0,
                "ambiguous_count": ambiguous,
                "rejected_count": rejected,
                "authoritative_count": None,
            },
            "research_gaps": [
                {
                    "code": "COMPETITOR_ANALYSIS_REQUIRED",
                    "reason": "No current 10C analysis exists.",
                    "origins": ["10C"],
                }
            ],
            "generated_at": generated_at.isoformat(),
        }
        return (
            payload,
            {"source_state": source, "context_id": str(context.id)},
            cast(list[dict[str, object]], payload["research_gaps"]),
            source,
            freshness,
        )
    freshness_value = (
        analysis.freshness_summary.get("state", "UNKNOWN")
        if isinstance(analysis.freshness_summary, dict)
        else "UNKNOWN"
    )
    contradiction = "PRESENT" if analysis.contradictions else "NONE"
    gaps = _gaps(analysis, comparison)
    change_context = comparison.summary if comparison is not None else {"status": "UNAVAILABLE"}
    payload = {
        "context": {
            "id": str(context.id),
            "marketplace": context.marketplace,
            "market": context.market,
            "category": context.category,
            "currency": context.currency,
        },
        "analysis": {
            "id": str(analysis.id),
            "version": analysis.analysis_version,
            "calculation_version": analysis.calculation_version,
            "cohort_summary": analysis.cohort_summary,
            "pricing": analysis.pricing_analysis,
            "concentration": analysis.concentration_analysis,
            "rating": analysis.rating_analysis,
            "review": analysis.review_analysis,
            "assortment": analysis.assortment_analysis,
            "positioning": analysis.positioning_analysis,
            "differentiation": analysis.differentiation_analysis,
            "competitive_gaps": analysis.competitive_gaps,
            "evidence_coverage": analysis.evidence_coverage,
            "freshness": analysis.freshness_summary,
            "contradictions": analysis.contradictions,
        },
        "cohort": {
            "confirmed_count": confirmed,
            "probable_count": probable,
            "ambiguous_count": ambiguous,
            "rejected_count": rejected,
            "authoritative_count": confirmed + probable,
            "included_product_ids": analysis.cohort_summary.get("included_product_ids", []),
        },
        "change_context": (
            {
                "id": str(comparison.id),
                "version": comparison.comparison_version,
                "calculation_version": comparison.calculation_version,
                "summary": change_context,
            }
            if comparison
            else {"status": "UNAVAILABLE"}
        ),
        "research_gaps": gaps,
        "generated_at": generated_at.isoformat(),
    }
    evidence = {
        "context_id": str(context.id),
        "analysis_id": str(analysis.id),
        "comparison_id": str(comparison.id) if comparison else None,
        "source_state": SOURCE_DEDICATED,
        "freshness": freshness_value,
        "contradictions": contradiction,
    }
    return payload, evidence, gaps, SOURCE_DEDICATED, str(freshness_value).upper()


def get_or_create_projection(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    assessment: ProductOpportunityAssessment,
) -> CompetitorWinningProductProjection | None:
    context = find_context(db, owner, opportunity.id)
    if context is None:
        return None
    analysis = _analysis(db, owner, context)
    comparison = _comparison(db, owner, context, analysis) if analysis else None
    entries = (
        list(
            db.scalars(
                select(CompetitorComparableCohortEntry).where(
                    CompetitorComparableCohortEntry.owner_id == owner.id,
                    CompetitorComparableCohortEntry.analysis_id == analysis.id,
                )
            )
        )
        if analysis
        else []
    )
    generated_at = _now()
    payload, evidence, gaps, source, freshness = _projection_payload(
        context, analysis, comparison, entries, generated_at
    )
    fingerprint_payload: dict[str, object] = {
        "opportunity_id": str(opportunity.id),
        "assessment_id": str(assessment.id),
        "context_id": str(context.id),
        "analysis_id": str(analysis.id) if analysis else None,
        "comparison_id": str(comparison.id) if comparison else None,
        "contract_version": INTEGRATION_CONTRACT_VERSION,
        "nine_b": CALCULATION_VERSION,
    }
    fingerprint = _fingerprint(fingerprint_payload)
    existing = db.scalar(
        select(CompetitorWinningProductProjection).where(
            CompetitorWinningProductProjection.owner_id == owner.id,
            CompetitorWinningProductProjection.opportunity_id == opportunity.id,
            CompetitorWinningProductProjection.assessment_id == assessment.id,
            CompetitorWinningProductProjection.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    projection = CompetitorWinningProductProjection(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        context_id=context.id,
        competitor_analysis_id=analysis.id if analysis else None,
        change_comparison_id=comparison.id if comparison else None,
        source_state=source,
        contract_version=INTEGRATION_CONTRACT_VERSION,
        nine_b_calculation_version=CALCULATION_VERSION,
        ten_c_calculation_version=analysis.calculation_version if analysis else None,
        ten_d_calculation_version=comparison.calculation_version if comparison else None,
        input_fingerprint=fingerprint,
        projection=cast(dict[str, object], _json(payload)),
        evidence_summary=cast(dict[str, object], _json(evidence)),
        research_gaps=cast(list[dict[str, object]], _json(gaps)),
        freshness_state=freshness,
        contradiction_state=str(evidence.get("contradictions", "NONE")),
        created_at=generated_at,
    )
    db.add(projection)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.COMPETITOR_WINNING_PRODUCT_PROJECTION_CREATED",
        entity_type="competitor_winning_product_projection",
        entity_id=projection.id,
        metadata={
            "source_state": source,
            "opportunity_id": str(opportunity.id),
            "assessment_id": str(assessment.id),
        },
        idempotency_key=f"competitor-winning-projection:{projection.id}",
    )
    return projection
