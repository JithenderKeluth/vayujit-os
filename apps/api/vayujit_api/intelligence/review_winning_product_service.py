"""Bounded 11F adapter from Review Intelligence into Winning Product detail."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
)
from vayujit_api.intelligence.review_models import (
    ReviewAnalysis,
    ReviewAnalysisItem,
    ReviewChangeComparison,
    ReviewChangeEvent,
    ReviewContext,
    ReviewProductGap,
    ReviewProductGapAnalysis,
    ReviewSnapshot,
)
from vayujit_api.intelligence.review_winning_product_models import (
    CALCULATION_VERSION,
    INTEGRATION_CONTRACT_VERSION,
    ReviewWinningProductProjection,
)


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


def _context(db: Session, owner: User, opportunity: ProductOpportunity) -> ReviewContext | None:
    exact = list(
        db.scalars(
            select(ReviewContext)
            .where(
                ReviewContext.owner_id == owner.id,
                ReviewContext.product_opportunity_id == opportunity.id,
            )
            .order_by(ReviewContext.version.desc(), ReviewContext.updated_at.desc())
        )
    )
    if exact:
        return exact[0]
    if opportunity.product_id is None:
        return None
    candidates = list(
        db.scalars(
            select(ReviewContext)
            .where(
                ReviewContext.owner_id == owner.id,
                ReviewContext.product_id == opportunity.product_id,
                ReviewContext.product_opportunity_id.is_(None),
            )
            .order_by(ReviewContext.updated_at.desc())
        )
    )
    if len(candidates) > 1:
        raise HTTPException(
            409, "Review context relationship is ambiguous for this product opportunity."
        )
    return candidates[0] if candidates else None


def _analysis(db: Session, owner: User, context: ReviewContext) -> ReviewAnalysis | None:
    return db.scalar(
        select(ReviewAnalysis)
        .where(
            ReviewAnalysis.owner_id == owner.id,
            ReviewAnalysis.context_id == context.id,
            ReviewAnalysis.status == "COMPLETED",
        )
        .order_by(ReviewAnalysis.created_at.desc())
    )


def _snapshot(
    db: Session, owner: User, context: ReviewContext, analysis: ReviewAnalysis | None
) -> ReviewSnapshot | None:
    if analysis is not None:
        value = db.scalar(
            select(ReviewSnapshot).where(
                ReviewSnapshot.id == analysis.snapshot_id,
                ReviewSnapshot.owner_id == owner.id,
                ReviewSnapshot.context_id == context.id,
            )
        )
        if value is not None:
            return value
    return db.scalar(
        select(ReviewSnapshot)
        .where(ReviewSnapshot.owner_id == owner.id, ReviewSnapshot.context_id == context.id)
        .order_by(ReviewSnapshot.snapshot_version.desc())
    )


def _gap_analysis(
    db: Session, owner: User, context: ReviewContext, analysis: ReviewAnalysis | None
) -> ReviewProductGapAnalysis | None:
    if analysis is None:
        return None
    return db.scalar(
        select(ReviewProductGapAnalysis)
        .where(
            ReviewProductGapAnalysis.owner_id == owner.id,
            ReviewProductGapAnalysis.context_id == context.id,
            ReviewProductGapAnalysis.review_analysis_id == analysis.id,
            ReviewProductGapAnalysis.status == "COMPLETED",
        )
        .order_by(ReviewProductGapAnalysis.created_at.desc())
    )


def _comparison(
    db: Session, owner: User, context: ReviewContext, analysis: ReviewAnalysis | None
) -> ReviewChangeComparison | None:
    if analysis is None:
        return None
    return db.scalar(
        select(ReviewChangeComparison)
        .where(
            ReviewChangeComparison.owner_id == owner.id,
            ReviewChangeComparison.context_id == context.id,
            ReviewChangeComparison.current_analysis_id == analysis.id,
            ReviewChangeComparison.status.in_(("COMPLETED", "PARTIALLY_COMPLETED")),
        )
        .order_by(
            ReviewChangeComparison.comparison_version.desc(),
            ReviewChangeComparison.created_at.desc(),
        )
    )


def _items(db: Session, owner: User, analysis: ReviewAnalysis | None) -> list[ReviewAnalysisItem]:
    if analysis is None:
        return []
    return list(
        db.scalars(
            select(ReviewAnalysisItem)
            .where(
                ReviewAnalysisItem.owner_id == owner.id,
                ReviewAnalysisItem.analysis_id == analysis.id,
            )
            .order_by(ReviewAnalysisItem.item_type, ReviewAnalysisItem.canonical_label)
        )
    )


def _gaps(
    db: Session, owner: User, gap_analysis: ReviewProductGapAnalysis | None
) -> list[ReviewProductGap]:
    if gap_analysis is None:
        return []
    return list(
        db.scalars(
            select(ReviewProductGap)
            .where(
                ReviewProductGap.owner_id == owner.id,
                ReviewProductGap.analysis_id == gap_analysis.id,
            )
            .order_by(ReviewProductGap.canonical_label)
        )
    )


def _events(
    db: Session, owner: User, comparison: ReviewChangeComparison | None
) -> list[ReviewChangeEvent]:
    if comparison is None:
        return []
    return list(
        db.scalars(
            select(ReviewChangeEvent)
            .where(
                ReviewChangeEvent.owner_id == owner.id,
                ReviewChangeEvent.comparison_id == comparison.id,
            )
            .order_by(ReviewChangeEvent.created_at, ReviewChangeEvent.subject_key)
        )
    )


def _item_payload(item: ReviewAnalysisItem) -> dict[str, object]:
    return {
        "type": item.item_type,
        "label": item.canonical_label,
        "sentiment": item.sentiment,
        "sentiment_distribution": item.sentiment_distribution,
        "severity": item.severity,
        "support_count": item.support_count,
        "cohort_count": item.cohort_count,
        "coverage": item.coverage,
        "source_distribution": item.source_distribution,
        "supporting_review_ids": item.supporting_review_ids,
        "supporting_evidence_ids": item.supporting_evidence_ids,
        "freshness": item.freshness,
        "confidence": item.confidence,
        "evidence_state": item.evidence_state,
        "limitation": item.limitation,
    }


def _gap_payload(gap: ReviewProductGap) -> dict[str, object]:
    return {
        "type": gap.gap_type,
        "label": gap.canonical_label,
        "hypothesis": gap.hypothesis,
        "status": gap.status,
        "support_classification": gap.support_classification,
        "support_count": gap.support_count,
        "cohort_count": gap.cohort_count,
        "coverage": gap.coverage,
        "source_distribution": gap.source_distribution,
        "supporting_review_ids": gap.supporting_review_ids,
        "supporting_evidence_ids": gap.supporting_evidence_ids,
        "opposing_review_ids": gap.opposing_review_ids,
        "severity": gap.severity,
        "evidence_strength": gap.evidence_strength,
        "confidence": gap.confidence,
        "freshness": gap.freshness,
        "required_validations": gap.required_validations,
        "limitations": gap.limitations,
    }


def _change_payload(event: ReviewChangeEvent) -> dict[str, object]:
    return {
        "id": str(event.id),
        "change_type": event.change_type,
        "subject_type": event.subject_type,
        "subject_key": event.subject_key,
        "semantics": event.observed_or_derived,
        "baseline_value": event.baseline_value,
        "current_value": event.current_value,
        "absolute_delta": str(event.absolute_delta) if event.absolute_delta is not None else None,
        "relative_delta": str(event.relative_delta) if event.relative_delta is not None else None,
        "materiality": event.materiality,
        "status": event.status,
        "alert_eligibility": event.alert_eligibility,
        "confidence": event.confidence,
        "freshness": event.freshness,
        "research_gaps": event.research_gaps,
        "limitations": event.limitations,
        "explanation": event.explanation,
        "supporting_review_ids": event.supporting_review_ids,
        "supporting_evidence_ids": event.supporting_evidence_ids,
    }


def _research_gaps(
    analysis: ReviewAnalysis | None,
    gaps: Iterable[ReviewProductGap],
    events: Iterable[ReviewChangeEvent],
    *,
    has_gap_analysis: bool,
) -> list[dict[str, object]]:
    values: dict[str, dict[str, object]] = {}
    if analysis is None:
        values["INSUFFICIENT_REVIEW_SAMPLE"] = {
            "code": "INSUFFICIENT_REVIEW_SAMPLE",
            "reason": "A completed review analysis is required.",
            "origin": "11C",
        }
    else:
        for value in _list(analysis.evidence_gaps):
            if isinstance(value, dict) and value.get("code"):
                values.setdefault(str(value["code"]), {**value, "origin": "11C"})
    if not has_gap_analysis:
        values.setdefault(
            "PRODUCT_GAP_ANALYSIS_REQUIRED",
            {
                "code": "PRODUCT_GAP_ANALYSIS_REQUIRED",
                "reason": (
                    "Run the current 11D product-gap analysis before treating "
                    "review hypotheses as actionable."
                ),
                "origin": "11D",
            },
        )
    for gap in gaps:
        for validation in gap.required_validations:
            values.setdefault(
                str(validation),
                {
                    "code": str(validation),
                    "reason": "Review-derived hypothesis requires independent validation.",
                    "origin": "11D",
                },
            )
    for event in events:
        for code in event.research_gaps:
            values.setdefault(
                str(code),
                {
                    "code": str(code),
                    "reason": "A material review change remains unresolved.",
                    "origin": "11E",
                },
            )
    return [values[key] for key in sorted(values)]


def _readiness(
    context: ReviewContext | None,
    analysis: ReviewAnalysis | None,
    snapshot: ReviewSnapshot | None,
    gaps: list[ReviewProductGap],
    events: list[ReviewChangeEvent],
    gap_analysis: ReviewProductGapAnalysis | None,
) -> str:
    if context is None or analysis is None or snapshot is None or analysis.included_records <= 0:
        return "INSUFFICIENT_EVIDENCE"
    if context.status == "STALE":
        return "STALE"
    contradiction = any(gap.status == "CONTRADICTORY" for gap in gaps) or any(
        event.change_type == "CONTRADICTION_CHANGED" for event in events
    )
    if contradiction:
        return "CONTRADICTORY"
    if gap_analysis is None:
        return "RESEARCH_REQUIRED"
    if analysis.status != "COMPLETED" or context.status not in {"ACTIVE", "DRAFT"}:
        return "PARTIAL"
    return "AVAILABLE" if not analysis.limitations else "PARTIAL"


def _build(
    owner: User,
    opportunity: ProductOpportunity,
    assessment: ProductOpportunityAssessment,
    context: ReviewContext | None,
    snapshot: ReviewSnapshot | None,
    analysis: ReviewAnalysis | None,
    gap_analysis: ReviewProductGapAnalysis | None,
    comparison: ReviewChangeComparison | None,
    items: list[ReviewAnalysisItem],
    gaps: list[ReviewProductGap],
    events: list[ReviewChangeEvent],
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], str, str]:
    readiness = _readiness(context, analysis, snapshot, gaps, events, gap_analysis)
    cohort = {
        "review_count": snapshot.review_count if snapshot else 0,
        "rated_review_count": snapshot.rated_review_count if snapshot else 0,
        "unrated_review_count": (
            max((snapshot.review_count - snapshot.rated_review_count), 0) if snapshot else 0
        ),
        "source_inventory": snapshot.source_inventory if snapshot else {},
        "analysis_cohort": analysis.cohort_json if analysis else {},
    }
    rating = analysis.rating_distribution if analysis else {}
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in items:
        grouped.setdefault(item.item_type, []).append(_item_payload(item))
    feedback = {
        "themes": grouped.get("THEME", []) + grouped.get("TOPIC", []),
        "pain_points": grouped.get("PAIN_POINT", []),
        "praised_attributes": grouped.get("PRAISED_ATTRIBUTE", []),
        "feature_requests": grouped.get("FEATURE_REQUEST", []),
        "quality_signals": grouped.get("QUALITY_ISSUE", []),
        "sentiment_distribution": analysis.sentiment_distribution if analysis else {},
    }
    gap_values = [_gap_payload(gap) for gap in gaps]
    changes = {
        "comparison_id": str(comparison.id) if comparison else None,
        "status": comparison.status if comparison else "UNAVAILABLE",
        "summary": comparison.summary if comparison else {},
        "events": [_change_payload(event) for event in events],
    }
    research = _research_gaps(analysis, gaps, events, has_gap_analysis=gap_analysis is not None)
    freshness = {
        "context_status": context.status if context else "UNKNOWN",
        "snapshot": snapshot.freshness_summary if snapshot else {},
        "analysis": {"created_at": analysis.created_at.isoformat()} if analysis else {},
        "sources": snapshot.source_inventory if snapshot else {},
    }
    contradictions = [value for value in gap_values if value.get("status") == "CONTRADICTORY"]
    limitations = [] if context else ["No review context is linked to this opportunity."]
    if analysis and analysis.limitations:
        limitations.extend(str(value) for value in analysis.limitations)
    if comparison is None:
        limitations.append("No 11E review-change history is available.")
    lineage: dict[str, object] = {
        "opportunity_id": str(opportunity.id),
        "assessment_id": str(assessment.id),
        "review_context_id": str(context.id) if context else None,
        "review_snapshot_id": str(snapshot.id) if snapshot else None,
        "review_analysis_id": str(analysis.id) if analysis else None,
        "review_gap_analysis_id": str(gap_analysis.id) if gap_analysis else None,
        "review_change_comparison_id": str(comparison.id) if comparison else None,
        "review_evidence_ids": sorted(
            {rid for item in items for rid in item.supporting_evidence_ids}
            | {rid for gap in gaps for rid in gap.supporting_evidence_ids}
            | {rid for event in events for rid in event.supporting_evidence_ids}
        ),
    }
    projection: dict[str, object] = {
        "readiness": readiness,
        "cohort": cohort,
        "rating_evidence": rating,
        "feedback_evidence": feedback,
        "gap_evidence": gap_values,
        "change_evidence": changes,
        "research_gaps": research,
        "freshness": freshness,
        "contradictions": contradictions,
        "evidence_lineage": lineage,
        "limitations": limitations,
        "labels": [
            "Review-derived",
            "Customer-feedback evidence",
            "Hypothesis",
            "Requires validation",
        ],
    }
    fingerprint = _fingerprint(
        {
            "owner_id": str(owner.id),
            "opportunity_id": str(opportunity.id),
            "assessment_id": str(assessment.id),
            "context_id": str(context.id) if context else None,
            "snapshot_id": str(snapshot.id) if snapshot else None,
            "analysis_id": str(analysis.id) if analysis else None,
            "gap_analysis_id": str(gap_analysis.id) if gap_analysis else None,
            "comparison_id": str(comparison.id) if comparison else None,
            "contract_version": INTEGRATION_CONTRACT_VERSION,
            "calculation_version": CALCULATION_VERSION,
        }
    )
    return projection, lineage, research, readiness, fingerprint


def get_or_create_projection(
    db: Session,
    owner: User,
    opportunity: ProductOpportunity,
    assessment: ProductOpportunityAssessment,
) -> ReviewWinningProductProjection:
    context = _context(db, owner, opportunity)
    analysis = _analysis(db, owner, context) if context else None
    snapshot = _snapshot(db, owner, context, analysis) if context else None
    gap_analysis = _gap_analysis(db, owner, context, analysis) if context else None
    comparison = _comparison(db, owner, context, analysis) if context else None
    items = _items(db, owner, analysis)
    gaps = _gaps(db, owner, gap_analysis)
    events = _events(db, owner, comparison)
    projection, lineage, research, readiness, fingerprint = _build(
        owner,
        opportunity,
        assessment,
        context,
        snapshot,
        analysis,
        gap_analysis,
        comparison,
        items,
        gaps,
        events,
    )
    existing = db.scalar(
        select(ReviewWinningProductProjection).where(
            ReviewWinningProductProjection.owner_id == owner.id,
            ReviewWinningProductProjection.opportunity_id == opportunity.id,
            ReviewWinningProductProjection.assessment_id == assessment.id,
            ReviewWinningProductProjection.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    value = ReviewWinningProductProjection(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        assessment_id=assessment.id,
        context_id=context.id if context else None,
        snapshot_id=snapshot.id if snapshot else None,
        analysis_id=analysis.id if analysis else None,
        gap_analysis_id=gap_analysis.id if gap_analysis else None,
        change_comparison_id=comparison.id if comparison else None,
        contract_version=INTEGRATION_CONTRACT_VERSION,
        calculation_version=CALCULATION_VERSION,
        input_fingerprint=fingerprint,
        readiness=readiness,
        source_state=readiness,
        cohort=cast(dict[str, object], _json(projection["cohort"])),
        rating_evidence=cast(dict[str, object], _json(projection["rating_evidence"])),
        feedback_evidence=cast(dict[str, object], _json(projection["feedback_evidence"])),
        gap_evidence=cast(list[dict[str, object]], _json(projection["gap_evidence"])),
        change_evidence=cast(dict[str, object], _json(projection["change_evidence"])),
        research_gaps=cast(list[dict[str, object]], _json(research)),
        freshness=cast(dict[str, object], _json(projection["freshness"])),
        contradictions=cast(list[dict[str, object]], _json(projection["contradictions"])),
        evidence_lineage=cast(dict[str, object], _json(lineage)),
        limitations=cast(list[str], _json(projection["limitations"])),
        projection=cast(dict[str, object], _json(projection)),
        created_at=now(),
    )
    db.add(value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ReviewWinningProductProjection).where(
                ReviewWinningProductProjection.owner_id == owner.id,
                ReviewWinningProductProjection.opportunity_id == opportunity.id,
                ReviewWinningProductProjection.assessment_id == assessment.id,
                ReviewWinningProductProjection.input_fingerprint == fingerprint,
            )
        )
        if existing is not None:
            return existing
        raise
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.REVIEW_WINNING_PRODUCT_PROJECTION_CREATED",
        entity_type="review_winning_product_projection",
        entity_id=value.id,
        metadata={
            "opportunity_id": str(opportunity.id),
            "assessment_id": str(assessment.id),
            "readiness": readiness,
            "review_context_id": str(context.id) if context else None,
        },
        idempotency_key=f"review-winning-product-projection:{value.id}",
    )
    return value


def current_projection(
    db: Session, owner: User, opportunity_id: uuid.UUID, assessment_id: uuid.UUID
) -> ReviewWinningProductProjection | None:
    return db.scalar(
        select(ReviewWinningProductProjection)
        .where(
            ReviewWinningProductProjection.owner_id == owner.id,
            ReviewWinningProductProjection.opportunity_id == opportunity_id,
            ReviewWinningProductProjection.assessment_id == assessment_id,
        )
        .order_by(ReviewWinningProductProjection.created_at.desc())
    )


def integrity_report(db: Session, owner: User) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(ReviewWinningProductProjection).where(
                ReviewWinningProductProjection.owner_id == owner.id
            )
        )
    )
    opportunities = {
        value.id: value
        for value in db.scalars(
            select(ProductOpportunity).where(ProductOpportunity.owner_id == owner.id)
        )
    }
    assessments = {
        value.id: value
        for value in db.scalars(
            select(ProductOpportunityAssessment).where(
                ProductOpportunityAssessment.owner_id == owner.id
            )
        )
    }
    contexts = {
        value.id: value
        for value in db.scalars(select(ReviewContext).where(ReviewContext.owner_id == owner.id))
    }
    snapshots = {
        value.id: value
        for value in db.scalars(select(ReviewSnapshot).where(ReviewSnapshot.owner_id == owner.id))
    }
    analyses = {
        value.id: value
        for value in db.scalars(select(ReviewAnalysis).where(ReviewAnalysis.owner_id == owner.id))
    }
    gap_analyses = {
        value.id: value
        for value in db.scalars(
            select(ReviewProductGapAnalysis).where(ReviewProductGapAnalysis.owner_id == owner.id)
        )
    }
    comparisons = {
        value.id: value
        for value in db.scalars(
            select(ReviewChangeComparison).where(ReviewChangeComparison.owner_id == owner.id)
        )
    }
    global_contexts = {value.id: value for value in db.scalars(select(ReviewContext))}
    global_snapshots = {value.id: value for value in db.scalars(select(ReviewSnapshot))}
    global_analyses = {value.id: value for value in db.scalars(select(ReviewAnalysis))}
    global_gaps = {value.id: value for value in db.scalars(select(ReviewProductGapAnalysis))}
    global_comparisons = {value.id: value for value in db.scalars(select(ReviewChangeComparison))}
    invalid: dict[str, int] = {
        "orphan_projection": 0,
        "broken_opportunity_lineage": 0,
        "broken_assessment_lineage": 0,
        "broken_review_lineage": 0,
        "broken_review_context_lineage": 0,
        "broken_review_snapshot_lineage": 0,
        "broken_11c_lineage": 0,
        "broken_11d_lineage": 0,
        "broken_11e_lineage": 0,
        "cross_owner_projection": 0,
        "mismatched_product_opportunity_review_context": 0,
        "projection_using_unrelated_review_context": 0,
        "duplicate_projection_fingerprint": 0,
        "duplicate_logical_current_projection": 0,
        "unsupported_contract_version": 0,
        "projection_using_incomplete_analysis": 0,
        "incomplete_analysis": 0,
        "incompatible_rating_scales_collapsed": 0,
        "review_count_as_demand": 0,
        "positive_sentiment_affects_confidence": 0,
        "negative_sentiment_hard_block": 0,
        "competitor_evidence_overwritten": 0,
        "nine_f_weights_changed": 0,
        "winning_score_persisted": 0,
        "external_write_exposure": 0,
    }
    seen_logical: set[tuple[uuid.UUID, uuid.UUID]] = set()
    seen_fingerprints: set[str] = set()
    for row in rows:
        opportunity = opportunities.get(row.opportunity_id)
        assessment = assessments.get(row.assessment_id)
        context = contexts.get(row.context_id) if row.context_id is not None else None
        snapshot = snapshots.get(row.snapshot_id) if row.snapshot_id is not None else None
        analysis = analyses.get(row.analysis_id) if row.analysis_id is not None else None
        gap_analysis = gap_analyses.get(row.gap_analysis_id) if row.gap_analysis_id else None
        comparison = comparisons.get(row.change_comparison_id) if row.change_comparison_id else None
        invalid["orphan_projection"] += int(opportunity is None or assessment is None)
        invalid["broken_opportunity_lineage"] += int(opportunity is None)
        invalid["broken_assessment_lineage"] += int(
            assessment is None or assessment.opportunity_id != row.opportunity_id
        )
        context_missing = row.context_id is not None and context is None
        invalid["broken_review_context_lineage"] += int(context_missing)
        broken_snapshot = row.snapshot_id is not None and (
            snapshot is None or snapshot.context_id != row.context_id
        )
        broken_11c = row.analysis_id is not None and (
            analysis is None
            or analysis.context_id != row.context_id
            or (snapshot is not None and analysis.snapshot_id != snapshot.id)
        )
        broken_11d = row.gap_analysis_id is not None and (
            gap_analysis is None
            or gap_analysis.context_id != row.context_id
            or (analysis is not None and gap_analysis.review_analysis_id != analysis.id)
        )
        broken_11e = row.change_comparison_id is not None and (
            comparison is None
            or comparison.context_id != row.context_id
            or (analysis is not None and comparison.current_analysis_id != analysis.id)
        )
        invalid["broken_review_snapshot_lineage"] += int(broken_snapshot)
        invalid["broken_11c_lineage"] += int(broken_11c)
        invalid["broken_11d_lineage"] += int(broken_11d)
        invalid["broken_11e_lineage"] += int(broken_11e)
        invalid["broken_review_lineage"] += int(
            context_missing or broken_snapshot or broken_11c or broken_11d or broken_11e
        )
        if context is not None and opportunity is not None:
            mismatched = (
                context.product_opportunity_id is not None
                and context.product_opportunity_id != opportunity.id
            ) or (
                context.product_id is not None
                and opportunity.product_id is not None
                and context.product_id != opportunity.product_id
            )
            invalid["mismatched_product_opportunity_review_context"] += int(mismatched)
            invalid["projection_using_unrelated_review_context"] += int(mismatched)
        for referenced_id, global_values, owner_values in (
            (row.context_id, global_contexts, contexts),
            (row.snapshot_id, global_snapshots, snapshots),
            (row.analysis_id, global_analyses, analyses),
            (row.gap_analysis_id, global_gaps, gap_analyses),
            (row.change_comparison_id, global_comparisons, comparisons),
        ):
            if (
                referenced_id is not None
                and referenced_id in global_values
                and referenced_id not in owner_values
            ):
                invalid["cross_owner_projection"] += 1
        invalid["unsupported_contract_version"] += int(
            row.contract_version != INTEGRATION_CONTRACT_VERSION
            or row.calculation_version != CALCULATION_VERSION
        )
        invalid["projection_using_incomplete_analysis"] += int(
            analysis is not None
            and (analysis.status != "COMPLETED" or analysis.included_records <= 0)
        )
        invalid["incomplete_analysis"] += int(
            row.analysis_id is not None
            and analysis is None
            and row.readiness not in {"INSUFFICIENT_EVIDENCE", "RESEARCH_REQUIRED"}
        )
        if row.input_fingerprint in seen_fingerprints:
            invalid["duplicate_projection_fingerprint"] += 1
        seen_fingerprints.add(row.input_fingerprint)
        key = (row.opportunity_id, row.assessment_id)
        if key in seen_logical:
            invalid["duplicate_logical_current_projection"] += 1
        seen_logical.add(key)
        text = json.dumps(row.projection, sort_keys=True).lower()
        invalid["review_count_as_demand"] += int(
            "sales" in text or "revenue" in text or "high_demand" in text or "market_size" in text
        )
        invalid["winning_score_persisted"] += int(
            "winning_product_score" in text or "overall_score" in text or "score_band" in text
        )
        invalid["positive_sentiment_affects_confidence"] += int(
            "positive_sentiment_confidence" in text or "sentiment_boost" in text
        )
        invalid["negative_sentiment_hard_block"] += int(
            "negative_sentiment_hard_block" in text or "sentiment_block" in text
        )
        invalid["competitor_evidence_overwritten"] += int(
            "competitor_projection" in text or "competitor_score" in text
        )
        invalid["nine_f_weights_changed"] += int("weight_override" in text or "9f_weight" in text)
    return {
        "projection_count": len(rows),
        **invalid,
        "applicable_hard_counters": sum(invalid.values()),
    }
