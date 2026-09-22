"""Business Agent adapter for authoritative Trend Intelligence capabilities (12G)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.trend_analysis_models import TrendAnalysis
from vayujit_api.intelligence.trend_analysis_schemas import TrendAnalysisCreate
from vayujit_api.intelligence.trend_analysis_service import create_analysis
from vayujit_api.intelligence.trend_change_models import TrendChangeComparison
from vayujit_api.intelligence.trend_change_schemas import TrendChangeComparisonCreate
from vayujit_api.intelligence.trend_change_service import create_comparison
from vayujit_api.intelligence.trend_models import TrendContext, TrendObservation, TrendSnapshot
from vayujit_api.intelligence.trend_schemas import TrendSnapshotCreate
from vayujit_api.intelligence.trend_service import create_snapshot
from vayujit_api.intelligence.trend_validation_models import TrendValidation
from vayujit_api.intelligence.trend_validation_schemas import TrendValidationCreate
from vayujit_api.intelligence.trend_validation_service import create_validation
from vayujit_api.intelligence.trend_winning_product_service import get_or_create_projection

TREND_CAPABILITIES = frozenset(
    {
        "TREND_CONTEXT_RESOLUTION",
        "TREND_INGESTION",
        "TREND_ANALYSIS",
        "TREND_CHANGE_ANALYSIS",
        "TREND_VALIDATION",
        "TREND_WINNING_PRODUCT_PROJECTION",
    }
)


def _gap(
    code: str,
    *,
    context_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None,
) -> dict[str, object]:
    return {
        "status": "EVIDENCE_GAP",
        "gap_code": code,
        "evidence_gaps": [{"code": code, "kind": "TREND", "research_required": True}],
        "context_id": str(context_id) if context_id else None,
        "opportunity_id": str(opportunity_id) if opportunity_id else None,
        "external_mutation": False,
        "mode": "LOCAL_DETERMINISTIC",
    }


def resolve_context(
    db: Session, owner: User, opportunity: ProductOpportunity
) -> TrendContext | None:
    exact = list(
        db.scalars(
            select(TrendContext)
            .where(
                TrendContext.owner_id == owner.id,
                TrendContext.product_opportunity_id == opportunity.id,
            )
            .order_by(TrendContext.version.desc(), TrendContext.updated_at.desc())
        )
    )
    if exact:
        return exact[0]
    if opportunity.product_id is None:
        return None
    candidates = list(
        db.scalars(
            select(TrendContext)
            .where(
                TrendContext.owner_id == owner.id,
                TrendContext.product_id == opportunity.product_id,
                TrendContext.product_opportunity_id.is_(None),
            )
            .order_by(TrendContext.updated_at.desc(), TrendContext.id.desc())
        )
    )
    if len(candidates) > 1:
        raise HTTPException(
            status_code=409,
            detail="Trend context relationship is ambiguous for this opportunity.",
        )
    return candidates[0] if candidates else None


def _latest_analysis(db: Session, owner: User, context: TrendContext) -> TrendAnalysis | None:
    return db.scalar(
        select(TrendAnalysis)
        .where(
            TrendAnalysis.owner_id == owner.id,
            TrendAnalysis.context_id == context.id,
            TrendAnalysis.status == "COMPLETED",
        )
        .order_by(TrendAnalysis.created_at.desc(), TrendAnalysis.id.desc())
    )


def _latest_comparison(
    db: Session, owner: User, context: TrendContext, analysis: TrendAnalysis
) -> TrendChangeComparison | None:
    return db.scalar(
        select(TrendChangeComparison)
        .where(
            TrendChangeComparison.owner_id == owner.id,
            TrendChangeComparison.context_id == context.id,
            TrendChangeComparison.current_analysis_id == analysis.id,
            TrendChangeComparison.status == "COMPLETED",
        )
        .order_by(TrendChangeComparison.created_at.desc(), TrendChangeComparison.id.desc())
    )


def _latest_validation(
    db: Session, owner: User, context: TrendContext, analysis: TrendAnalysis
) -> TrendValidation | None:
    return db.scalar(
        select(TrendValidation)
        .where(
            TrendValidation.owner_id == owner.id,
            TrendValidation.context_id == context.id,
            TrendValidation.analysis_id == analysis.id,
        )
        .order_by(TrendValidation.validation_version.desc(), TrendValidation.created_at.desc())
    )


def _context_result(
    context: TrendContext | None, opportunity: ProductOpportunity
) -> dict[str, object]:
    if context is None:
        return _gap("TREND_CONTEXT_MISSING", opportunity_id=opportunity.id)
    return {
        "status": "SUCCEEDED",
        "context_id": str(context.id),
        "opportunity_id": str(opportunity.id),
        "context_status": context.status,
        "external_mutation": False,
        "mode": "LOCAL_DETERMINISTIC",
    }


def execute_trend_capability(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    capability_id: str,
) -> dict[str, object]:
    """Invoke existing Trend services; this adapter never computes Trend intelligence."""

    if capability_id not in TREND_CAPABILITIES:
        raise ValueError("Unsupported Trend capability.")
    context = resolve_context(db, owner, opportunity)
    if capability_id == "TREND_CONTEXT_RESOLUTION":
        return {"capability": capability_id, **_context_result(context, opportunity)}
    if context is None:
        return {
            "capability": capability_id,
            **_gap("TREND_CONTEXT_MISSING", opportunity_id=opportunity.id),
        }

    if capability_id == "TREND_INGESTION":
        count = db.scalar(
            select(TrendObservation.id)
            .where(
                TrendObservation.owner_id == owner.id,
                TrendObservation.context_id == context.id,
            )
            .limit(1)
        )
        if count is None:
            return {
                "capability": capability_id,
                **_gap("NO_TREND_EVIDENCE", context_id=context.id, opportunity_id=opportunity.id),
            }
        observation_count = len(
            list(
                db.scalars(
                    select(TrendObservation.id).where(
                        TrendObservation.owner_id == owner.id,
                        TrendObservation.context_id == context.id,
                    )
                )
            )
        )
        return {
            "capability": capability_id,
            "status": "SUCCEEDED",
            "context_id": str(context.id),
            "observation_count": observation_count,
            "evidence_source": "existing_owner_scoped_observations",
            "external_mutation": False,
            "mode": "LOCAL_DETERMINISTIC",
        }

    if capability_id == "TREND_ANALYSIS":
        observations = list(
            db.scalars(
                select(TrendObservation).where(
                    TrendObservation.owner_id == owner.id,
                    TrendObservation.context_id == context.id,
                    TrendObservation.quality_state != "INVALID",
                )
            )
        )
        if not observations:
            return {
                "capability": capability_id,
                **_gap("NO_TREND_EVIDENCE", context_id=context.id, opportunity_id=opportunity.id),
            }
        snapshot = db.scalar(
            select(TrendSnapshot)
            .where(
                TrendSnapshot.owner_id == owner.id,
                TrendSnapshot.context_id == context.id,
            )
            .order_by(TrendSnapshot.snapshot_version.desc())
        )
        if snapshot is None:
            snapshot = create_snapshot(
                db,
                owner,
                context,
                TrendSnapshotCreate(observation_ids=[row.id for row in observations]),
            )
        analysis = create_analysis(db, owner, context, TrendAnalysisCreate(snapshot_id=snapshot.id))
        return {
            "capability": capability_id,
            "status": "SUCCEEDED",
            "context_id": str(context.id),
            "snapshot_id": str(snapshot.id),
            "analysis_id": str(analysis.id),
            "readiness": analysis.readiness,
            "freshness": analysis.freshness_state,
            "evidence_gaps": [],
            "external_mutation": False,
            "mode": "LOCAL_DETERMINISTIC",
        }

    latest_analysis: TrendAnalysis | None = _latest_analysis(db, owner, context)
    if capability_id == "TREND_CHANGE_ANALYSIS":
        if latest_analysis is None:
            return {
                "capability": capability_id,
                "status": "NOT_APPLICABLE",
                "reason": "NO_HISTORY",
                "context_id": str(context.id),
                "external_mutation": False,
                "mode": "LOCAL_DETERMINISTIC",
            }
        analyses = list(
            db.scalars(
                select(TrendAnalysis)
                .where(
                    TrendAnalysis.owner_id == owner.id,
                    TrendAnalysis.context_id == context.id,
                    TrendAnalysis.status == "COMPLETED",
                )
                .order_by(TrendAnalysis.created_at.desc(), TrendAnalysis.id.desc())
            )
        )
        if len(analyses) < 2:
            return {
                "capability": capability_id,
                "status": "NOT_APPLICABLE",
                "reason": "NO_HISTORY",
                "context_id": str(context.id),
                "analysis_id": str(latest_analysis.id),
                "external_mutation": False,
                "mode": "LOCAL_DETERMINISTIC",
            }
        current, baseline = analyses[0], analyses[1]
        comparison = _latest_comparison(db, owner, context, current)
        if comparison is None:
            comparison, events = create_comparison(
                db,
                owner,
                context,
                TrendChangeComparisonCreate(
                    baseline_analysis_id=baseline.id,
                    current_analysis_id=current.id,
                    idempotency_key=f"business-agent-trend:{opportunity.id}:{baseline.id}:{current.id}",
                ),
            )
        else:
            events = []
        return {
            "capability": capability_id,
            "status": "SUCCEEDED",
            "context_id": str(context.id),
            "baseline_analysis_id": str(baseline.id),
            "analysis_id": str(current.id),
            "comparison_id": str(comparison.id),
            "event_count": len(events),
            "materialities": sorted(
                {
                    str(getattr(event, "materiality", ""))
                    for event in events
                    if getattr(event, "materiality", None)
                }
            ),
            "external_mutation": False,
            "mode": "LOCAL_DETERMINISTIC",
        }

    if latest_analysis is None:
        return {
            "capability": capability_id,
            **_gap("TREND_ANALYSIS_MISSING", context_id=context.id, opportunity_id=opportunity.id),
        }

    if capability_id == "TREND_VALIDATION":
        comparison = _latest_comparison(db, owner, context, latest_analysis)
        validation = _latest_validation(db, owner, context, latest_analysis)
        if validation is None:
            validation = create_validation(
                db,
                owner,
                context,
                TrendValidationCreate(
                    analysis_id=latest_analysis.id,
                    comparison_id=comparison.id if comparison else None,
                ),
            )
        return {
            "capability": capability_id,
            "status": "SUCCEEDED",
            "context_id": str(context.id),
            "analysis_id": str(latest_analysis.id),
            "comparison_id": str(comparison.id) if comparison else None,
            "validation_id": str(validation.id),
            "confidence": validation.confidence,
            "readiness": validation.downstream_readiness,
            "freshness": validation.freshness_summary.get("state", "UNKNOWN"),
            "agreement": validation.agreement_summary.get("state", "UNKNOWN"),
            "contradictions": validation.contradiction_summary.get("count", 0),
            "research_gaps": list(validation.research_gaps or []),
            "external_mutation": False,
            "mode": "LOCAL_DETERMINISTIC",
        }

    assessments = list(
        db.scalars(
            select(ProductOpportunityAssessment)
            .where(
                ProductOpportunityAssessment.owner_id == owner.id,
                ProductOpportunityAssessment.opportunity_id == opportunity.id,
            )
            .order_by(
                ProductOpportunityAssessment.version.desc(),
                ProductOpportunityAssessment.created_at.desc(),
            )
        )
    )
    if not assessments:
        return {
            "capability": capability_id,
            **_gap(
                "PRODUCT_OPPORTUNITY_ASSESSMENT_MISSING",
                context_id=context.id,
                opportunity_id=opportunity.id,
            ),
        }
    projection = get_or_create_projection(db, owner, opportunity, assessments[0])
    validation = _latest_validation(db, owner, context, latest_analysis)
    return {
        "capability": capability_id,
        "status": "SUCCEEDED",
        "context_id": str(context.id),
        "analysis_id": str(latest_analysis.id),
        "validation_id": str(validation.id) if validation else None,
        "projection_id": str(projection.id),
        "readiness": projection.readiness,
        "confidence": projection.evidence_confidence.get("state", "UNKNOWN"),
        "freshness": projection.freshness.get("state", "UNKNOWN"),
        "research_gaps": list(projection.research_gaps or []),
        "external_mutation": False,
        "mode": "LOCAL_DETERMINISTIC",
    }
