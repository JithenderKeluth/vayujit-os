"""Bounded 11G orchestration adapter for Review Intelligence.

This module only coordinates existing 11A-11F services. It does not calculate
review semantics or create a second agent runtime.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.review_analysis_service import (
    create_analysis,
    current_analysis,
)
from vayujit_api.intelligence.review_change_service import (
    create_comparison,
    current_comparison,
)
from vayujit_api.intelligence.review_gap_service import (
    create_gap_analysis,
    current_gap_analysis,
)
from vayujit_api.intelligence.review_ingestion_service import execute_ingestion
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewContext,
    ReviewSnapshot,
)
from vayujit_api.intelligence.review_schemas import (
    ReviewAnalysisRequest,
    ReviewChangeComparisonRequest,
    ReviewIngestionRequest,
)
from vayujit_api.intelligence.review_winning_product_service import get_or_create_projection

REVIEW_CAPABILITIES = frozenset(
    {
        "REVIEW_INGESTION",
        "REVIEW_ANALYSIS",
        "REVIEW_GAP_ANALYSIS",
        "REVIEW_CHANGE_ANALYSIS",
        "REVIEW_WINNING_PRODUCT_PROJECTION",
    }
)


def review_enabled(goal: BusinessAgentGoal) -> bool:
    structured = goal.structured_goal or {}
    return bool(
        structured.get("include_review_intelligence")
        or structured.get("review_intelligence")
        or "review intelligence" in goal.raw_goal.casefold()
    )


def _uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except (TypeError, ValueError, AttributeError):
        return None


def _context(
    db: Session, owner: User, goal: BusinessAgentGoal, opportunity: ProductOpportunity
) -> ReviewContext | None:
    structured = goal.structured_goal or {}
    requested = _uuid(structured.get("review_context_id"))
    if requested is not None:
        context = db.scalar(
            select(ReviewContext).where(
                ReviewContext.id == requested,
                ReviewContext.owner_id == owner.id,
            )
        )
    else:
        context = db.scalar(
            select(ReviewContext)
            .where(
                ReviewContext.owner_id == owner.id,
                ReviewContext.product_opportunity_id == opportunity.id,
            )
            .order_by(ReviewContext.version.desc(), ReviewContext.updated_at.desc())
        )
    if context is None:
        return None
    if (
        context.product_opportunity_id is not None
        and context.product_opportunity_id != opportunity.id
    ):
        return None
    return context


def _gap(capability: str, gap_type: str, message: str) -> dict[str, object]:
    return {
        "capability": capability,
        "status": "EVIDENCE_GAP",
        "evidence_gaps": [{"type": gap_type, "message": message}],
        "external_mutation": False,
    }


def _snapshot(db: Session, owner: User, context: ReviewContext) -> ReviewSnapshot | None:
    return db.scalar(
        select(ReviewSnapshot)
        .where(
            ReviewSnapshot.owner_id == owner.id,
            ReviewSnapshot.context_id == context.id,
        )
        .order_by(ReviewSnapshot.snapshot_version.desc())
        .limit(1)
    )


def _analysis(
    db: Session, owner: User, context: ReviewContext, goal: BusinessAgentGoal
) -> ReviewAnalysis | None:
    value = current_analysis(db, owner, context.id)
    if value is not None:
        return value
    snapshot = _snapshot(db, owner, context)
    if snapshot is None:
        return None
    structured = goal.structured_goal or {}
    request = ReviewAnalysisRequest(
        snapshot_id=snapshot.id,
        mode="LOCAL_FIXTURE",
        idempotency_key=f"business-agent-review-analysis:{context.id}:{snapshot.id}",
        analysis_version=str(structured.get("review_analysis_version", "review-analysis-v1")),
        calculation_version=str(
            structured.get("review_calculation_version", "review-calculation-v1")
        ),
    )
    return create_analysis(db, owner, context, request)


def _gap_analysis(db: Session, owner: User, context: ReviewContext, analysis: ReviewAnalysis):
    value = current_gap_analysis(db, owner, context.id)
    return value or create_gap_analysis(db, owner, context, analysis.id)


def _change_analysis(db: Session, owner: User, context: ReviewContext, analysis: ReviewAnalysis):
    value = current_comparison(db, owner, context.id)
    if value is not None:
        return value
    prior = list(
        db.scalars(
            select(ReviewAnalysis)
            .where(
                ReviewAnalysis.owner_id == owner.id,
                ReviewAnalysis.context_id == context.id,
                ReviewAnalysis.id != analysis.id,
            )
            .order_by(ReviewAnalysis.created_at.desc())
            .limit(1)
        )
    )
    if not prior:
        return None
    return create_comparison(
        db,
        owner,
        context,
        ReviewChangeComparisonRequest(
            baseline_analysis_id=prior[0].id,
            current_analysis_id=analysis.id,
        ),
    )


def _assessment(
    db: Session, owner: User, goal: BusinessAgentGoal, opportunity: ProductOpportunity
) -> ProductOpportunityAssessment | None:
    structured = goal.structured_goal or {}
    requested = _uuid(structured.get("review_assessment_id"))
    assessment_id = requested or opportunity.current_assessment_id
    if assessment_id is None:
        return None
    return db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.owner_id == owner.id,
            ProductOpportunityAssessment.opportunity_id == opportunity.id,
        )
    )


def execute_review_capability(
    db: Session,
    owner: User,
    goal: BusinessAgentGoal,
    opportunity: ProductOpportunity,
    capability: str,
) -> dict[str, object]:
    """Execute one bounded step through an authoritative 11A-11F service."""
    if capability not in REVIEW_CAPABILITIES:
        raise ValueError("Unsupported Review Intelligence capability.")
    context = _context(db, owner, goal, opportunity)
    if context is None:
        return _gap(
            capability,
            "INSUFFICIENT_REVIEW_SAMPLE",
            "No owner-scoped ReviewContext is linked to this opportunity.",
        )
    if capability == "REVIEW_INGESTION":
        structured = goal.structured_goal or {}
        records = structured.get("review_records")
        if not isinstance(records, list):
            return _gap(
                capability,
                "INSUFFICIENT_REVIEW_SAMPLE",
                "No local fixture review dataset was supplied.",
            )
        request = ReviewIngestionRequest(
            provider="LOCAL_FIXTURE",
            mode="LOCAL_FIXTURE",
            records=[item for item in records if isinstance(item, dict)],
            idempotency_key=f"business-agent-review-ingestion:{context.id}",
        )
        batch, _, snapshot = execute_ingestion(db, owner, context, request)
        return {
            "capability": capability,
            "status": batch.status,
            "context_id": str(context.id),
            "batch_id": str(batch.id),
            "snapshot_id": str(snapshot.id) if snapshot else None,
            "accepted_count": batch.accepted_count,
            "rejected_count": batch.rejected_count,
            "external_mutation": False,
            "evidence_gaps": (
                []
                if snapshot is not None
                else [
                    {
                        "type": "INSUFFICIENT_REVIEW_SAMPLE",
                        "message": "The local fixture did not produce a usable snapshot.",
                    }
                ]
            ),
        }
    analysis = _analysis(db, owner, context, goal)
    if capability == "REVIEW_ANALYSIS":
        if analysis is None:
            return _gap(
                capability,
                "INSUFFICIENT_REVIEW_SAMPLE",
                "No usable ReviewSnapshot exists for analysis.",
            )
        return {
            "capability": capability,
            "status": analysis.status,
            "context_id": str(context.id),
            "analysis_id": str(analysis.id),
            "snapshot_id": str(analysis.snapshot_id),
            "included_records": analysis.included_records,
            "evidence_gaps": analysis.evidence_gaps,
            "external_mutation": False,
        }
    if analysis is None:
        return _gap(
            capability,
            "INSUFFICIENT_REVIEW_SAMPLE",
            "Review analysis is unavailable; downstream review steps were not fabricated.",
        )
    if capability == "REVIEW_GAP_ANALYSIS":
        value = _gap_analysis(db, owner, context, analysis)
        return {
            "capability": capability,
            "status": value.status,
            "context_id": str(context.id),
            "analysis_id": str(analysis.id),
            "gap_analysis_id": str(value.id),
            "gap_count": value.gap_count,
            "signal_count": value.signal_count,
            "external_mutation": False,
        }
    if capability == "REVIEW_CHANGE_ANALYSIS":
        value = _change_analysis(db, owner, context, analysis)
        if value is None:
            return _gap(
                capability,
                "NO_HISTORY",
                "No valid baseline/current ReviewAnalysis pair exists.",
            )
        return {
            "capability": capability,
            "status": value.status,
            "context_id": str(context.id),
            "analysis_id": str(analysis.id),
            "comparison_id": str(value.id),
            "event_count": int((value.summary or {}).get("event_count", 0)),
            "external_mutation": False,
        }
    assessment = _assessment(db, owner, goal, opportunity)
    if assessment is None:
        return _gap(
            capability,
            "PRODUCT_OPPORTUNITY_ASSESSMENT_REQUIRED",
            "A Product Opportunity assessment is required for the 11F projection.",
        )
    projection = get_or_create_projection(db, owner, opportunity, assessment)
    return {
        "capability": capability,
        "status": projection.readiness,
        "context_id": str(context.id),
        "assessment_id": str(assessment.id),
        "projection_id": str(projection.id),
        "readiness": projection.readiness,
        "evidence_gaps": list(projection.research_gaps or []),
        "external_mutation": False,
    }


def review_artifact_type(capability: str) -> str:
    return {
        "REVIEW_INGESTION": "REVIEW_SNAPSHOT",
        "REVIEW_ANALYSIS": "REVIEW_ANALYSIS",
        "REVIEW_GAP_ANALYSIS": "REVIEW_GAP_ANALYSIS",
        "REVIEW_CHANGE_ANALYSIS": "REVIEW_CHANGE_COMPARISON",
        "REVIEW_WINNING_PRODUCT_PROJECTION": "REVIEW_WINNING_PRODUCT_PROJECTION",
    }[capability]
