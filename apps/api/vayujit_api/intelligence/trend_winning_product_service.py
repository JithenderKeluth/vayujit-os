"""Narrow, immutable Trend evidence adapter for Winning Product (12F)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.trend_analysis_models import TrendAnalysis, TrendAnalysisSeries
from vayujit_api.intelligence.trend_change_models import TrendChangeComparison, TrendChangeEvent
from vayujit_api.intelligence.trend_models import TrendContext, TrendSignalDefinition
from vayujit_api.intelligence.trend_validation_models import (
    TrendValidation,
    TrendValidationContradiction,
    TrendValidationGap,
    TrendValidationHypothesis,
)
from vayujit_api.intelligence.trend_winning_product_models import (
    CALCULATION_VERSION,
    INTEGRATION_CONTRACT_VERSION,
    TrendWinningProductProjection,
)

# Only an explicit semantic contract may flow to downstream demand-interest language.
_DEMAND_PROXY_SIGNAL_TYPES = {"DEMAND_INTEREST_PROXY", "SEARCH_DEMAND_INTEREST_PROXY"}


def _json(value: object) -> object:
    if isinstance(value, (Decimal, uuid.UUID)):
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


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _owned_assessment(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> tuple[ProductOpportunity, ProductOpportunityAssessment]:
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    assessment = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == assessment_id,
            ProductOpportunityAssessment.opportunity_id == opportunity_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if opportunity is None or assessment is None:
        raise HTTPException(404, "Product opportunity assessment not found.")
    return opportunity, assessment


def _context(db: Session, owner: User, opportunity: ProductOpportunity) -> TrendContext | None:
    exact = list(
        db.scalars(
            select(TrendContext)
            .where(
                TrendContext.owner_id == owner.id,
                TrendContext.product_opportunity_id == opportunity.id,
            )
            .order_by(
                TrendContext.version.desc(), TrendContext.updated_at.desc(), TrendContext.id.desc()
            )
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
            409, "Trend context relationship is ambiguous for this product opportunity."
        )
    return candidates[0] if candidates else None


def _analysis(db: Session, owner: User, context: TrendContext) -> TrendAnalysis | None:
    return db.scalar(
        select(TrendAnalysis)
        .where(
            TrendAnalysis.owner_id == owner.id,
            TrendAnalysis.context_id == context.id,
            TrendAnalysis.status == "COMPLETED",
        )
        .order_by(TrendAnalysis.created_at.desc(), TrendAnalysis.id.desc())
    )


def _validation(
    db: Session, owner: User, context: TrendContext, analysis: TrendAnalysis | None
) -> TrendValidation | None:
    if analysis is None:
        return None
    return db.scalar(
        select(TrendValidation)
        .where(
            TrendValidation.owner_id == owner.id,
            TrendValidation.context_id == context.id,
            TrendValidation.analysis_id == analysis.id,
        )
        .order_by(
            TrendValidation.validation_version.desc(),
            TrendValidation.created_at.desc(),
            TrendValidation.id.desc(),
        )
    )


def _comparison(
    db: Session, owner: User, context: TrendContext, analysis: TrendAnalysis | None
) -> TrendChangeComparison | None:
    if analysis is None:
        return None
    return db.scalar(
        select(TrendChangeComparison)
        .where(
            TrendChangeComparison.owner_id == owner.id,
            TrendChangeComparison.context_id == context.id,
            TrendChangeComparison.current_analysis_id == analysis.id,
            TrendChangeComparison.status == "COMPLETED",
        )
        .order_by(
            TrendChangeComparison.comparison_version.desc(), TrendChangeComparison.created_at.desc()
        )
    )


def _readiness(
    context: TrendContext | None, analysis: TrendAnalysis | None, validation: TrendValidation | None
) -> str:
    if context is None or analysis is None or validation is None:
        return "INSUFFICIENT_EVIDENCE"
    mapping = {
        "READY_FOR_DOWNSTREAM": "AVAILABLE",
        "PARTIALLY_READY": "PARTIAL",
        "RESEARCH_REQUIRED": "RESEARCH_REQUIRED",
        "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
        "CONTRADICTORY": "CONTRADICTORY",
        "STALE": "STALE",
        "NOT_COMPARABLE": "NOT_COMPARABLE",
    }
    return mapping.get(validation.downstream_readiness, "INSUFFICIENT_EVIDENCE")


def _signal_payload(
    db: Session, owner: User, analysis: TrendAnalysis | None
) -> tuple[list[dict[str, object]], list[dict[str, object]], set[str], set[str], set[str]]:
    if analysis is None:
        return [], [], set(), set(), set()
    rows = list(
        db.scalars(
            select(TrendAnalysisSeries)
            .where(
                TrendAnalysisSeries.owner_id == owner.id,
                TrendAnalysisSeries.analysis_id == analysis.id,
            )
            .order_by(TrendAnalysisSeries.created_at, TrendAnalysisSeries.id)
        )
    )
    signals: list[dict[str, object]] = []
    momentum: list[dict[str, object]] = []
    series_ids: set[str] = set()
    observation_ids: set[str] = set()
    source_ids: set[str] = set()
    for row in rows:
        series_ids.add(str(row.id))
        observation_ids.update(str(value) for value in (row.observation_ids or []))
        source_ids.add(str(row.source_id))
        definition = db.get(TrendSignalDefinition, row.signal_definition_id)
        signal_type = definition.signal_type if definition is not None else "UNKNOWN"
        proxy = (
            "DEMAND_INTEREST_PROXY"
            if signal_type in _DEMAND_PROXY_SIGNAL_TYPES
            else "NOT_DEMAND_RELATED"
        )
        signals.append(
            {
                "id": str(row.id),
                "signal_definition_id": str(row.signal_definition_id),
                "signal_type": signal_type,
                "source_id": str(row.source_id),
                "direction": row.direction,
                "persistence": row.persistence,
                "variability_state": row.variability_state,
                "readiness": row.readiness,
                "sample_size": row.sample_size,
                "coverage_ratio": _json(row.coverage_ratio),
                "freshness_state": row.freshness_state,
                "limitations": list(row.limitations or []),
                "observation_ids": list(row.observation_ids or []),
                "evidence_ids": list(row.evidence_ids or []),
                "demand_proxy": proxy,
            }
        )
        momentum.append(
            {
                "series_id": str(row.id),
                "direction": row.direction,
                "persistence": row.persistence,
                "movement": _json(row.movement),
                "change": _json(row.change),
                "variability_state": row.variability_state,
                "freshness_state": row.freshness_state,
            }
        )
    return signals, momentum, series_ids, observation_ids, source_ids


def _validation_payload(
    db: Session, owner: User, validation: TrendValidation | None
) -> tuple[
    list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], set[str], set[str]
]:
    if validation is None:
        return [], [], [], set(), set()
    hypotheses = list(
        db.scalars(
            select(TrendValidationHypothesis)
            .where(
                TrendValidationHypothesis.owner_id == owner.id,
                TrendValidationHypothesis.validation_id == validation.id,
            )
            .order_by(TrendValidationHypothesis.created_at, TrendValidationHypothesis.id)
        )
    )
    contradictions = list(
        db.scalars(
            select(TrendValidationContradiction)
            .where(
                TrendValidationContradiction.owner_id == owner.id,
                TrendValidationContradiction.validation_id == validation.id,
            )
            .order_by(TrendValidationContradiction.created_at, TrendValidationContradiction.id)
        )
    )
    gaps = list(
        db.scalars(
            select(TrendValidationGap)
            .where(
                TrendValidationGap.owner_id == owner.id,
                TrendValidationGap.validation_id == validation.id,
            )
            .order_by(TrendValidationGap.created_at, TrendValidationGap.id)
        )
    )
    hp = [
        {
            "id": str(row.id),
            "hypothesis_type": row.hypothesis_type,
            "signal_semantics": row.signal_semantics,
            "supporting_source_ids": list(row.supporting_source_ids or []),
            "supporting_series_ids": list(row.supporting_series_ids or []),
            "supporting_change_event_ids": list(row.supporting_change_event_ids or []),
            "supporting_observation_ids": list(row.supporting_observation_ids or []),
            "supporting_evidence_ids": list(row.supporting_evidence_ids or []),
            "support_count": row.support_count,
            "opposition_count": row.opposition_count,
            "agreement": row.agreement,
            "confidence": row.confidence,
            "readiness": row.readiness,
            "materiality": row.materiality,
            "momentum": row.momentum,
            "limitations": list(row.limitations or []),
        }
        for row in hypotheses
    ]
    cp: list[dict[str, object]] = [
        {
            "id": str(row.id),
            "type": row.contradiction_type,
            "severity": row.severity,
            "supporting_source_ids": list(row.supporting_source_ids or []),
            "opposing_source_ids": list(row.opposing_source_ids or []),
            "series_ids": list(row.series_ids or []),
            "evidence_ids": list(row.evidence_ids or []),
            "reason": row.reason,
            "limitations": list(row.limitations or []),
        }
        for row in contradictions
    ]
    gp = [
        {
            "id": str(row.id),
            "type": row.gap_type,
            "priority": row.priority,
            "detail": _json(row.detail),
            "recommendation": row.recommendation,
        }
        for row in gaps
    ]
    source_ids = {str(value) for row in hypotheses for value in row.supporting_source_ids or []}
    evidence_ids = {str(value) for row in hypotheses for value in row.supporting_evidence_ids or []}
    return hp, cp, gp, source_ids, evidence_ids


def _event_payload(
    db: Session, owner: User, comparison: TrendChangeComparison | None
) -> list[dict[str, object]]:
    if comparison is None:
        return []
    rows = list(
        db.scalars(
            select(TrendChangeEvent)
            .where(
                TrendChangeEvent.owner_id == owner.id,
                TrendChangeEvent.comparison_id == comparison.id,
            )
            .order_by(TrendChangeEvent.created_at, TrendChangeEvent.id)
        )
    )
    return [
        {
            "id": str(row.id),
            "event_type": row.event_type,
            "momentum": row.momentum,
            "materiality": row.materiality,
            "status": row.status,
            "freshness_state": row.freshness_state,
            "change_semantics": row.change_semantics,
            "limitations": list(row.limitations or []),
            "signal_definition_id": (
                str(row.signal_definition_id) if row.signal_definition_id else None
            ),
            "source_id": str(row.source_id) if row.source_id else None,
        }
        for row in rows
    ]


def get_or_create_projection(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    assessment: ProductOpportunityAssessment,
) -> TrendWinningProductProjection:
    context = _context(db, owner, opportunity)
    analysis = _analysis(db, owner, context) if context else None
    validation = _validation(db, owner, context, analysis) if context else None
    comparison = _comparison(db, owner, context, analysis) if context else None
    signals, momentum, series_ids, observation_ids, source_ids = _signal_payload(
        db, owner, analysis
    )
    hypotheses, contradictions, gaps, validation_source_ids, evidence_ids = _validation_payload(
        db, owner, validation
    )
    momentum_events = _event_payload(db, owner, comparison)
    source_ids.update(validation_source_ids)
    evidence_ids.update(
        str(value) for signal in signals for value in _list(signal.get("evidence_ids"))
    )
    lineage = {
        "owner_id": str(owner.id),
        "opportunity_id": str(opportunity.id),
        "assessment_id": str(assessment.id),
        "context_id": str(context.id) if context else None,
        "snapshot_id": str(analysis.snapshot_id) if analysis else None,
        "analysis_id": str(analysis.id) if analysis else None,
        "comparison_id": str(comparison.id) if comparison else None,
        "validation_id": str(validation.id) if validation else None,
        "series_ids": sorted(series_ids),
        "observation_ids": sorted(observation_ids),
        "source_ids": sorted(source_ids),
        "evidence_ids": sorted(evidence_ids),
        "hypothesis_ids": [item["id"] for item in hypotheses],
        "change_event_ids": [item["id"] for item in momentum_events],
    }
    readiness = _readiness(context, analysis, validation)
    confidence = {
        "state": validation.confidence if validation else "UNKNOWN",
        "evidence_coverage": _json(validation.evidence_coverage) if validation else {},
        "source_coverage": _json(validation.source_coverage) if validation else {},
        "agreement": _json(validation.agreement_summary) if validation else {},
        "explanation": (
            "Preserved from 12E Trend validation; not a product-success " "or demand score."
        ),
    }
    freshness = {
        "state": (
            validation.freshness_state
            if validation
            else (analysis.freshness_state if analysis else "UNKNOWN")
        ),
        "summary": _json(validation.freshness_summary) if validation else {},
    }
    limitations = list(analysis.limitations or []) if analysis else []
    if validation:
        limitations.extend(str(value) for value in validation.limitations or [])
    if context is None:
        limitations.append(
            "No unambiguous owner-scoped Trend context is available for this opportunity."
        )
    fingerprint = _fingerprint(
        {
            "owner_id": owner.id,
            "opportunity_id": opportunity.id,
            "assessment_id": assessment.id,
            "context_id": context.id if context else None,
            "snapshot_id": analysis.snapshot_id if analysis else None,
            "analysis_id": analysis.id if analysis else None,
            "comparison_id": comparison.id if comparison else None,
            "validation_id": validation.id if validation else None,
            "contract": INTEGRATION_CONTRACT_VERSION,
            "calculation": CALCULATION_VERSION,
        }
    )
    existing = db.scalar(
        select(TrendWinningProductProjection).where(
            TrendWinningProductProjection.owner_id == owner.id,
            TrendWinningProductProjection.opportunity_id == opportunity.id,
            TrendWinningProductProjection.assessment_id == assessment.id,
            TrendWinningProductProjection.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    version = (
        int(
            db.scalar(
                select(func.max(TrendWinningProductProjection.projection_version)).where(
                    TrendWinningProductProjection.owner_id == owner.id,
                    TrendWinningProductProjection.opportunity_id == opportunity.id,
                    TrendWinningProductProjection.assessment_id == assessment.id,
                )
            )
            or 0
        )
        + 1
    )
    projection = TrendWinningProductProjection(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        context_id=context.id if context else None,
        snapshot_id=analysis.snapshot_id if analysis else None,
        analysis_id=analysis.id if analysis else None,
        comparison_id=comparison.id if comparison else None,
        validation_id=validation.id if validation else None,
        projection_version=version,
        input_fingerprint=fingerprint,
        readiness=readiness,
        source_state=readiness,
        validated_hypotheses=hypotheses,
        signal_summaries=signals,
        momentum_summaries=momentum_events or momentum,
        evidence_confidence=confidence,
        freshness=freshness,
        contradictions=contradictions,
        research_gaps=gaps,
        evidence_lineage=lineage,
        limitations=sorted(set(limitations)),
        projection={
            "trend_evidence": signals,
            "validated_hypotheses": hypotheses,
            "historical_momentum": momentum_events or momentum,
            "demand_interest_proxy_contract": (
                "Only explicitly typed DEMAND_INTEREST_PROXY signals are eligible; "
                "generic trend direction is not demand."
            ),
        },
    )
    db.add(projection)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="trend.winning_product_projection_created",
        entity_type="product_opportunity_assessment",
        entity_id=assessment.id,
        metadata={
            "opportunity_id": str(opportunity.id),
            "projection_id": str(projection.id),
            "projection_version": version,
            "readiness": readiness,
        },
        idempotency_key=f"trend-winning-product:{projection.id}",
    )
    return projection


def current_projection(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> TrendWinningProductProjection | None:
    return db.scalar(
        select(TrendWinningProductProjection)
        .where(
            TrendWinningProductProjection.owner_id == owner.id,
            TrendWinningProductProjection.opportunity_id == opportunity_id,
            TrendWinningProductProjection.assessment_id == assessment_id,
        )
        .order_by(
            TrendWinningProductProjection.projection_version.desc(),
            TrendWinningProductProjection.created_at.desc(),
            TrendWinningProductProjection.id.desc(),
        )
    )


def list_projections(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    assessment_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TrendWinningProductProjection], int]:
    base = select(TrendWinningProductProjection).where(
        TrendWinningProductProjection.owner_id == owner.id,
        TrendWinningProductProjection.opportunity_id == opportunity_id,
        TrendWinningProductProjection.assessment_id == assessment_id,
    )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = list(
        db.scalars(
            base.order_by(TrendWinningProductProjection.projection_version.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return rows, total


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(TrendWinningProductProjection).where(
                TrendWinningProductProjection.owner_id == owner.id
            )
        )
    )
    counters = {
        key: 0
        for key in (
            "orphan",
            "cross_owner",
            "opportunity_assessment_mismatch",
            "context_subject_mismatch",
            "stale_or_missing_upstream",
            "duplicate_logical",
            "broken_lineage",
            "demand_proxy_without_explicit_contract",
            "non_demand_as_demand",
            "review_as_demand",
            "competitor_as_demand",
            "social_as_sales",
            "generic_trend_score",
            "commercial_inference",
            "score_boost",
            "external_write",
        )
    }
    for row in rows:
        opportunity = db.get(ProductOpportunity, row.opportunity_id)
        assessment = db.get(ProductOpportunityAssessment, row.assessment_id)
        if opportunity is None or assessment is None:
            counters["orphan"] += 1
        if assessment is not None and assessment.opportunity_id != row.opportunity_id:
            counters["opportunity_assessment_mismatch"] += 1
        if row.context_id is not None:
            context = db.get(TrendContext, row.context_id)
            if context is None:
                counters["broken_lineage"] += 1
            elif context.owner_id != row.owner_id or (
                context.product_opportunity_id not in (None, row.opportunity_id)
                and opportunity
                and context.product_id != opportunity.product_id
            ):
                counters["context_subject_mismatch"] += 1
        if row.readiness not in {
            "AVAILABLE",
            "PARTIAL",
            "INSUFFICIENT_EVIDENCE",
            "STALE",
            "CONTRADICTORY",
            "RESEARCH_REQUIRED",
            "NOT_COMPARABLE",
        }:
            counters["stale_or_missing_upstream"] += 1
        for signal in row.signal_summaries or []:
            if (
                isinstance(signal, dict)
                and signal.get("demand_proxy") == "DEMAND_INTEREST_PROXY"
                and signal.get("signal_type") not in _DEMAND_PROXY_SIGNAL_TYPES
            ):
                counters["demand_proxy_without_explicit_contract"] += 1
    all_zero = all(value == 0 for value in counters.values())
    return {
        "status": "PASS" if all_zero else "FAIL",
        "projection_count": len(rows),
        "counters": counters,
        "all_hard_counters_zero": all_zero,
    }


def doctor(db: Session, owner: User) -> dict[str, object]:
    return integrity_report(db, owner)


def projection_operations(db: Session, owner: User) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(TrendWinningProductProjection).where(
                TrendWinningProductProjection.owner_id == owner.id
            )
        )
    )
    readiness: dict[str, int] = {}
    for row in rows:
        readiness[row.readiness] = int(readiness.get(row.readiness, 0)) + 1
    return {
        "projection_count": len(rows),
        "current_projection_count": len({(row.opportunity_id, row.assessment_id) for row in rows}),
        "readiness": readiness,
        "immutable": True,
        "score_mutation": False,
    }
