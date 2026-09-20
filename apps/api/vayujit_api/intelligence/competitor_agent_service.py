"""Bounded Business Agent orchestration over the existing competitor services."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_change_models import CompetitorChangeEvent
from vayujit_api.intelligence.competitor_change_schemas import ChangeComparisonCreate
from vayujit_api.intelligence.competitor_change_service import run_comparison
from vayujit_api.intelligence.competitor_commercial_models import CompetitorCommercialAnalysis
from vayujit_api.intelligence.competitor_commercial_schemas import CommercialAnalysisCreate
from vayujit_api.intelligence.competitor_commercial_service import run_analysis
from vayujit_api.intelligence.competitor_discovery_models import CompetitorDiscoveryRequest
from vayujit_api.intelligence.competitor_discovery_schemas import DiscoveryRequestCreate
from vayujit_api.intelligence.competitor_discovery_service import create_request, execute_request
from vayujit_api.intelligence.competitor_models import CompetitorContext
from vayujit_api.intelligence.competitor_schemas import ContextCreate
from vayujit_api.intelligence.competitor_service import create_context
from vayujit_api.intelligence.competitor_winning_product_models import (
    CompetitorWinningProductProjection,
)
from vayujit_api.intelligence.competitor_winning_product_service import get_or_create_projection
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    ProductOpportunityIntelligenceOutput,
)
from vayujit_api.intelligence.product_opportunity_intelligence_service import calculate_intelligence
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
    ProductOpportunityInputSnapshot,
    opportunity_now,
)
from vayujit_api.intelligence.product_opportunity_scoring_schemas import ScoreCalculateRequest
from vayujit_api.intelligence.product_opportunity_scoring_service import calculate_score
from vayujit_api.intelligence.product_opportunity_synthesis_schemas import SynthesisCalculateRequest
from vayujit_api.intelligence.product_opportunity_synthesis_service import calculate_synthesis


def _marketplace(goal: dict[str, object]) -> tuple[str, str]:
    value = str(goal.get("marketplace") or "AMAZON_IN")
    return value, "IN" if value.endswith("_IN") else "GLOBAL"


def _context(
    db: Session, owner: User, opportunity: ProductOpportunity, goal: dict[str, object]
) -> CompetitorContext:
    marketplace, market = _marketplace(goal)
    return create_context(
        db,
        owner,
        ContextCreate(
            subject_type="PRODUCT_OPPORTUNITY",
            subject_reference=opportunity.id,
            marketplace=marketplace,
            market=market,
            category=opportunity.category,
            currency="INR" if market == "IN" else None,
            status="ACTIVE",
            idempotency_key=f"business-agent-competitor-context:{opportunity.id}",
        ),
    )


def _fixture_candidates(context: CompetitorContext) -> list[dict[str, object]]:
    marketplace = context.marketplace
    return [
        {
            "source_mode": "LOCAL_FIXTURE",
            "source_identifier": f"agent-fixture:{context.id}:1",
            "listing_identifier": f"agent-fixture:{context.id}:1",
            "title": "Evidence Fixture Product One",
            "brand": "Fixture Brand One",
            "seller": "Fixture Seller One",
            "category": context.category,
            "marketplace": marketplace,
            "price_amount": "1299",
            "currency": context.currency or "INR",
            "rating": "4.2",
            "review_count": 120,
            "availability_state": "AVAILABLE",
        },
        {
            "source_mode": "LOCAL_FIXTURE",
            "source_identifier": f"agent-fixture:{context.id}:2",
            "listing_identifier": f"agent-fixture:{context.id}:2",
            "title": "Evidence Fixture Product Two",
            "brand": "Fixture Brand Two",
            "seller": "Fixture Seller Two",
            "category": context.category,
            "marketplace": marketplace,
            "price_amount": "1499",
            "currency": context.currency or "INR",
            "rating": "4.4",
            "review_count": 80,
            "availability_state": "AVAILABLE",
        },
    ]


def _discovery(db: Session, owner: User, context: CompetitorContext) -> dict[str, object]:
    request = create_request(
        db,
        owner,
        context.id,
        DiscoveryRequestCreate(
            marketplace=context.marketplace,
            market=context.market,
            category=context.category,
            filters={"fixture_candidates": _fixture_candidates(context)},
            maximum_candidates=50,
            provider_mode="LOCAL_FIXTURE",
            idempotency_key=f"business-agent-competitor-discovery:{context.id}",
        ),
    )
    request, candidates, snapshot = execute_request(db, owner, request)
    return {
        "context_id": str(context.id),
        "request_id": str(request.id),
        "snapshot_id": str(snapshot.id),
        "candidate_count": len(candidates),
        "confirmed_count": sum(item.identity_state == "CONFIRMED" for item in candidates),
        "probable_count": sum(item.identity_state == "PROBABLE" for item in candidates),
        "ambiguous_count": sum(item.identity_state == "AMBIGUOUS" for item in candidates),
        "rejected_count": sum(item.identity_state == "REJECTED" for item in candidates),
    }


def _assessment(
    db: Session, owner: User, opportunity: ProductOpportunity
) -> ProductOpportunityAssessment:
    if opportunity.current_assessment_id:
        current = db.scalar(
            select(ProductOpportunityAssessment).where(
                ProductOpportunityAssessment.id == opportunity.current_assessment_id,
                ProductOpportunityAssessment.owner_id == owner.id,
            )
        )
        if current is not None:
            return current
    constraint = None
    if opportunity.current_constraint_version_id:
        constraint = db.scalar(
            select(ProductOpportunityConstraintVersion).where(
                ProductOpportunityConstraintVersion.id == opportunity.current_constraint_version_id,
                ProductOpportunityConstraintVersion.owner_id == owner.id,
            )
        )
    if constraint is None:
        version = (
            int(
                db.scalar(
                    select(func.max(ProductOpportunityConstraintVersion.version)).where(
                        ProductOpportunityConstraintVersion.opportunity_id == opportunity.id
                    )
                )
                or 0
            )
            + 1
        )
        constraint = ProductOpportunityConstraintVersion(
            owner_id=owner.id,
            opportunity_id=opportunity.id,
            version=version,
            available_capital=None,
            marketplace=opportunity.target_marketplace,
            currency="INR" if str(opportunity.target_marketplace or "").endswith("_IN") else None,
            idempotency_key=f"business-agent-competitor-constraints:{opportunity.id}",
        )
        db.add(constraint)
        db.flush()
        opportunity.current_constraint_version_id = constraint.id
    version = (
        int(
            db.scalar(
                select(func.max(ProductOpportunityAssessment.version)).where(
                    ProductOpportunityAssessment.opportunity_id == opportunity.id
                )
            )
            or 0
        )
        + 1
    )
    snapshot = ProductOpportunityInputSnapshot(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        snapshot_version=version,
        payload={"source": "business_agent", "competitor_integration": True},
        evidence_state="partial",
    )
    db.add(snapshot)
    db.flush()
    assessment = ProductOpportunityAssessment(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        version=version,
        constraint_version_id=constraint.id,
        input_snapshot_id=snapshot.id,
        calculation_version="product-opportunity-foundation-v1",
        evidence_state="partial",
        status="created",
    )
    db.add(assessment)
    db.flush()
    opportunity.current_assessment_id = assessment.id
    opportunity.lifecycle_status = "assessed"
    opportunity.evidence_state = "partial"
    opportunity.updated_at = opportunity_now()
    db.flush()
    return assessment


def competitor_decision_brief(
    db: Session, owner: User, opportunity: ProductOpportunity
) -> dict[str, object]:
    """Return persisted competitor evidence for the human-review artifact."""
    context = db.scalar(
        select(CompetitorContext)
        .where(
            CompetitorContext.owner_id == owner.id,
            CompetitorContext.subject_reference == opportunity.id,
        )
        .order_by(CompetitorContext.created_at.desc())
    )
    if context is None:
        return {"status": "INSUFFICIENT_EVIDENCE", "research_gaps": ["competitor_context"]}
    request_count = int(
        db.scalar(
            select(func.count())
            .select_from(CompetitorDiscoveryRequest)
            .where(
                CompetitorDiscoveryRequest.owner_id == owner.id,
                CompetitorDiscoveryRequest.context_id == context.id,
            )
        )
        or 0
    )
    analysis = db.scalar(
        select(CompetitorCommercialAnalysis)
        .where(
            CompetitorCommercialAnalysis.owner_id == owner.id,
            CompetitorCommercialAnalysis.context_id == context.id,
        )
        .order_by(CompetitorCommercialAnalysis.created_at.desc())
    )
    projection = db.scalar(
        select(CompetitorWinningProductProjection)
        .where(
            CompetitorWinningProductProjection.owner_id == owner.id,
            CompetitorWinningProductProjection.opportunity_id == opportunity.id,
        )
        .order_by(CompetitorWinningProductProjection.created_at.desc())
    )
    competition = db.scalar(
        select(ProductOpportunityIntelligenceOutput)
        .where(
            ProductOpportunityIntelligenceOutput.owner_id == owner.id,
            ProductOpportunityIntelligenceOutput.opportunity_id == opportunity.id,
            ProductOpportunityIntelligenceOutput.kind == "competition",
        )
        .order_by(ProductOpportunityIntelligenceOutput.created_at.desc())
    )
    event_count = int(
        db.scalar(
            select(func.count())
            .select_from(CompetitorChangeEvent)
            .where(
                CompetitorChangeEvent.owner_id == owner.id,
                CompetitorChangeEvent.context_id == context.id,
            )
        )
        or 0
    )
    return {
        "status": projection.source_state if projection else "INSUFFICIENT_EVIDENCE",
        "context_id": str(context.id),
        "discovery_requests": request_count,
        "analysis_id": str(analysis.id) if analysis else None,
        "analysis_status": analysis.status if analysis else "MISSING",
        "competition_output_id": str(competition.id) if competition else None,
        "projection_id": str(projection.id) if projection else None,
        "projection": projection.projection if projection else {},
        "evidence_summary": projection.evidence_summary if projection else {},
        "research_gaps": (
            projection.research_gaps
            if projection
            else (analysis.research_gaps if analysis else ["competitor_analysis"])
        ),
        "freshness_state": projection.freshness_state if projection else "UNKNOWN",
        "contradiction_state": projection.contradiction_state if projection else "UNKNOWN",
        "change_events": event_count,
    }


def execute_competitor_capability(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    capability_id: str,
    goal: dict[str, object],
) -> dict[str, object]:
    """Run one existing competitor operation; never performs external mutation."""
    context = _context(db, owner, opportunity, goal)
    if capability_id == "COMPETITOR_DISCOVERY":
        return {"capability": capability_id, **_discovery(db, owner, context)}
    analysis = None
    if capability_id in {"COMPETITOR_ANALYSIS", "COMPETITOR_CHANGE_ANALYSIS"}:
        discovery = _discovery(db, owner, context)
        analysis = run_analysis(
            db,
            owner,
            context.id,
            CommercialAnalysisCreate(
                discovery_snapshot_id=uuid.UUID(str(discovery["snapshot_id"])),
                idempotency_key=f"business-agent-competitor-analysis:{context.id}",
            ),
        )
        assessment = _assessment(db, owner, opportunity)
        projection = get_or_create_projection(db, owner, opportunity, assessment)
        db.commit()
        result: dict[str, object] = {
            "capability": capability_id,
            "context_id": str(context.id),
            "analysis_id": str(analysis.id),
            "projection_id": str(projection.id) if projection else None,
            "projection_source": projection.source_state if projection else "INSUFFICIENT_EVIDENCE",
        }
        if capability_id == "COMPETITOR_ANALYSIS":
            return result
        try:
            comparison = run_comparison(
                db,
                owner,
                context.id,
                ChangeComparisonCreate(
                    current_analysis_id=analysis.id,
                    idempotency_key=f"business-agent-competitor-change:{context.id}",
                ),
            )
        except HTTPException as error:
            if error.status_code != 409:
                raise
            result["change_status"] = "NOT_APPLICABLE"
            result["change_reason"] = "Historical competitor analysis is not available."
            return result
        result["comparison_id"] = str(comparison.id)
        result["change_status"] = comparison.status
        return result
    if capability_id == "competition.intelligence":
        assessment = _assessment(db, owner, opportunity)
        demand = calculate_intelligence(db, owner, opportunity.id, assessment.id, "demand")
        competition = calculate_intelligence(
            db, owner, opportunity.id, assessment.id, "competition"
        )
        return {
            "capability": capability_id,
            "assessment_id": str(assessment.id),
            "demand_output_id": str(demand.id),
            "competition_output_id": str(competition.id),
            "competition_source": competition.input_snapshot.get("competition_source"),
        }
    if capability_id == "winning_product.score":
        assessment = _assessment(db, owner, opportunity)
        synthesis = calculate_synthesis(
            db,
            owner,
            opportunity.id,
            assessment.id,
            SynthesisCalculateRequest(idempotency_key=f"business-agent-synthesis:{assessment.id}"),
        )
        score = calculate_score(
            db,
            owner,
            opportunity.id,
            assessment.id,
            ScoreCalculateRequest(idempotency_key=f"business-agent-score:{assessment.id}"),
        )
        return {
            "capability": capability_id,
            "assessment_id": str(assessment.id),
            "synthesis_id": str(synthesis.id),
            "score_id": str(score.id),
            "classification": score.classification,
        }
    raise ValueError(f"Unsupported competitor capability: {capability_id}")
