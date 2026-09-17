"""Thin 8E.5 integration over shared audit, calendar, DD and scenario systems."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_schemas import (
    DueDiligenceContextCreate,
    ResearchPlanCreate,
)
from vayujit_api.intelligence.due_diligence_service import create_context as create_due_context
from vayujit_api.intelligence.due_diligence_service import create_plan as create_due_plan
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAlternateReadiness,
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioConcentrationMetric,
    SupplierPortfolioContext,
    SupplierPortfolioDependencyFinding,
    SupplierPortfolioHumanAction,
    SupplierPortfolioInputSnapshot,
    SupplierPortfolioMembership,
)
from vayujit_api.intelligence.portfolio_schemas import AssessmentCreate
from vayujit_api.intelligence.portfolio_service import create_assessment
from vayujit_api.intelligence.resilience_models import (
    SupplierPortfolioRecommendation,
    SupplierPortfolioResilienceDimensionResult,
    SupplierPortfolioResilienceScore,
)
from vayujit_api.intelligence.simulation_models import (
    PortfolioSimulation,
    PortfolioSimulationResult,
)
from vayujit_api.intelligence.sourcing_models import SourcingCalendarItem

UNSUPPORTED_RECOVERY_ACTIONS = {
    "RETRY_FAILED_PORTFOLIO_SIMULATION",
    "REBUILD_PORTFOLIO_OPERATIONAL_PROJECTION",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _assessment(
    db: Session, owner: User, portfolio: SupplierPortfolioContext
) -> SupplierPortfolioAssessmentVersion | None:
    if portfolio.current_assessment_version_id is None:
        return None
    return db.scalar(
        select(SupplierPortfolioAssessmentVersion).where(
            SupplierPortfolioAssessmentVersion.id == portfolio.current_assessment_version_id,
            SupplierPortfolioAssessmentVersion.owner_id == owner.id,
            SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id,
        )
    )


def _event_key(owner: User, portfolio: SupplierPortfolioContext, key: str) -> str:
    digest = sha256(f"{owner.id}:{portfolio.id}:{key}".encode()).hexdigest()
    return f"portfolio-event:{portfolio.id}:{digest}"


def _emit(
    db: Session,
    owner: User,
    portfolio: SupplierPortfolioContext,
    event: str,
    key: str,
    metadata: dict[str, Any],
) -> AuditEvent:
    return record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.{event.casefold()}",
        entity_type="supplier_portfolio",
        entity_id=portfolio.id,
        metadata={
            "event_type": event,
            "owner_id": str(owner.id),
            "portfolio_id": str(portfolio.id),
            **metadata,
        },
        idempotency_key=_event_key(owner, portfolio, key),
    )


def portfolio_product_channel(
    db: Session, owner: User, portfolio: SupplierPortfolioContext
) -> dict[str, Any]:
    """Project portfolio lineage into the shared Product Channel contract."""
    assessment = _assessment(db, owner, portfolio)
    score = (
        db.scalar(
            select(SupplierPortfolioResilienceScore).where(
                SupplierPortfolioResilienceScore.owner_id == owner.id,
                SupplierPortfolioResilienceScore.portfolio_id == portfolio.id,
                SupplierPortfolioResilienceScore.assessment_version_id == assessment.id,
            )
        )
        if assessment
        else None
    )
    recommendations = (
        list(
            db.scalars(
                select(SupplierPortfolioRecommendation).where(
                    SupplierPortfolioRecommendation.owner_id == owner.id,
                    SupplierPortfolioRecommendation.portfolio_id == portfolio.id,
                    SupplierPortfolioRecommendation.assessment_version_id == assessment.id,
                )
            )
        )
        if assessment
        else []
    )
    dependencies = (
        list(
            db.scalars(
                select(SupplierPortfolioDependencyFinding).where(
                    SupplierPortfolioDependencyFinding.owner_id == owner.id,
                    SupplierPortfolioDependencyFinding.portfolio_id == portfolio.id,
                    SupplierPortfolioDependencyFinding.assessment_version_id == assessment.id,
                )
            )
        )
        if assessment
        else []
    )
    alternates = (
        list(
            db.scalars(
                select(SupplierPortfolioAlternateReadiness).where(
                    SupplierPortfolioAlternateReadiness.owner_id == owner.id,
                    SupplierPortfolioAlternateReadiness.portfolio_id == portfolio.id,
                    SupplierPortfolioAlternateReadiness.assessment_version_id == assessment.id,
                )
            )
        )
        if assessment
        else []
    )
    simulations = list(
        db.scalars(
            select(PortfolioSimulationResult).where(
                PortfolioSimulationResult.owner_id == owner.id,
                PortfolioSimulationResult.portfolio_id == portfolio.id,
            )
        )
    )
    existing_event_keys = set(
        db.scalars(
            select(AuditEvent.idempotency_key).where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.entity_type == "supplier_portfolio",
                AuditEvent.entity_id == portfolio.id,
            )
        )
    )
    emitted: list[AuditEvent] = []
    if assessment is not None:
        assessment_key = _event_key(owner, portfolio, f"assessment:{assessment.id}")
        if assessment_key not in existing_event_keys:
            emitted.append(
                _emit(
                    db,
                    owner,
                    portfolio,
                    "PORTFOLIO_ASSESSMENT_CREATED",
                    f"assessment:{assessment.id}",
                    {"assessment_version_id": str(assessment.id)},
                )
            )
        if score is not None:
            emitted.append(
                _emit(
                    db,
                    owner,
                    portfolio,
                    "PORTFOLIO_RESILIENCE_CHANGED",
                    f"resilience:{assessment.id}:{score.classification}:{score.score}",
                    {
                        "assessment_version_id": str(assessment.id),
                        "classification": score.classification,
                        "score": float(score.score) if score.score is not None else None,
                    },
                )
            )
        for recommendation in recommendations:
            emitted.append(
                _emit(
                    db,
                    owner,
                    portfolio,
                    "PORTFOLIO_RECOMMENDATION_CREATED",
                    f"recommendation:{recommendation.id}",
                    {
                        "assessment_version_id": str(assessment.id),
                        "recommendation_id": str(recommendation.id),
                        "priority": recommendation.priority,
                    },
                )
            )
        for finding in dependencies:
            if str(finding.severity).upper() == "CRITICAL":
                emitted.append(
                    _emit(
                        db,
                        owner,
                        portfolio,
                        "PORTFOLIO_CRITICAL_DEPENDENCY_DETECTED",
                        f"dependency:{finding.id}",
                        {
                            "assessment_version_id": str(assessment.id),
                            "dependency_id": str(finding.id),
                            "supplier_id": (
                                str(finding.affected_supplier_id)
                                if finding.affected_supplier_id
                                else None
                            ),
                            "product_id": (
                                str(finding.affected_product_id)
                                if finding.affected_product_id
                                else None
                            ),
                        },
                    )
                )
        for alternate in alternates:
            emitted.append(
                _emit(
                    db,
                    owner,
                    portfolio,
                    "PORTFOLIO_ALTERNATE_READINESS_CHANGED",
                    f"alternate:{alternate.id}:{alternate.readiness_state}",
                    {
                        "assessment_version_id": str(assessment.id),
                        "alternate_readiness_id": str(alternate.id),
                        "supplier_id": str(alternate.supplier_id),
                        "product_id": str(alternate.product_id) if alternate.product_id else None,
                        "readiness_state": alternate.readiness_state,
                    },
                )
            )
        for simulation in simulations:
            emitted.append(
                _emit(
                    db,
                    owner,
                    portfolio,
                    "PORTFOLIO_SIMULATION_COMPLETED",
                    f"simulation:{simulation.id}:{simulation.status}",
                    {
                        "assessment_version_id": str(simulation.assessment_version_id),
                        "simulation_id": str(simulation.simulation_id),
                        "status": simulation.status,
                    },
                )
            )
    if emitted:
        db.commit()
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.entity_type == "supplier_portfolio",
                AuditEvent.entity_id == portfolio.id,
                AuditEvent.action.like("intelligence.portfolio_%"),
            )
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        )
    )
    return {
        "portfolio_id": str(portfolio.id),
        "owner_id": str(owner.id),
        "assessment_version_id": str(assessment.id) if assessment else None,
        "resilience": {
            "score": float(score.score) if score and score.score is not None else None,
            "classification": score.classification if score else None,
            "evidence_status": score.evidence_status if score else None,
        },
        "recommendations": [
            {
                "id": str(row.id),
                "type": row.recommendation_type,
                "priority": row.priority,
                "status": row.status,
                "supplier_id": str(row.affected_supplier_id) if row.affected_supplier_id else None,
                "product_id": str(row.affected_product_id) if row.affected_product_id else None,
            }
            for row in recommendations
        ],
        "events": [
            {
                "id": str(row.id),
                "event_type": row.metadata_json.get("event_type", row.action),
                "occurred_at": row.occurred_at,
                "correlation_id": row.correlation_id,
                "idempotency_key": row.idempotency_key,
                "assessment_version_id": row.metadata_json.get("assessment_version_id"),
            }
            for row in events
        ],
    }


def calendar(db: Session, owner: User) -> list[dict[str, Any]]:
    """Materialize deterministic portfolio reminders in the shared calendar ledger."""
    portfolios = list(
        db.scalars(
            select(SupplierPortfolioContext)
            .where(SupplierPortfolioContext.owner_id == owner.id)
            .order_by(SupplierPortfolioContext.updated_at, SupplierPortfolioContext.id)
        )
    )
    existing = {
        row.idempotency_key: row
        for row in db.scalars(
            select(SourcingCalendarItem).where(
                SourcingCalendarItem.owner_id == owner.id,
                SourcingCalendarItem.entity_type == "supplier_portfolio",
            )
        )
    }
    output: list[dict[str, Any]] = []
    for portfolio in portfolios:
        assessment = _assessment(db, owner, portfolio)
        if assessment is None:
            kind = "PORTFOLIO_REASSESSMENT_DUE"
            title = f"Assess supplier portfolio: {portfolio.name}"
        elif portfolio.status in {"stale", "review_required"}:
            kind = "PORTFOLIO_RESILIENCE_REVIEW_DUE"
            title = f"Review supplier portfolio resilience: {portfolio.name}"
        else:
            continue
        key = f"portfolio-calendar:{portfolio.id}:{kind}"
        row = existing.get(key)
        if row is None:
            row = SourcingCalendarItem(
                owner_id=owner.id,
                kind=kind,
                title=title,
                due_at=portfolio.updated_at + timedelta(days=30),
                entity_type="supplier_portfolio",
                entity_id=portfolio.id,
                idempotency_key=key,
                payload={
                    "portfolio_id": str(portfolio.id),
                    "assessment_version_id": str(assessment.id) if assessment else None,
                    "external_action": False,
                },
                created_at=_now(),
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                row = db.scalar(
                    select(SourcingCalendarItem).where(
                        SourcingCalendarItem.owner_id == owner.id,
                        SourcingCalendarItem.idempotency_key == key,
                    )
                )
        if row is not None:
            output.append(
                {
                    "event_id": str(row.id),
                    "kind": row.kind,
                    "title": row.title,
                    "status": "actionable",
                    "source_ref": str(portfolio.id),
                    "owner_id": str(owner.id),
                    "assessment_version_id": row.payload.get("assessment_version_id"),
                    "due_at": row.due_at,
                    "idempotency_key": row.idempotency_key,
                    "external_action": False,
                }
            )
    return output


def portfolio_integrity(db: Session, owner: User) -> dict[str, int]:
    contexts = list(
        db.scalars(
            select(SupplierPortfolioContext).where(SupplierPortfolioContext.owner_id == owner.id)
        )
    )
    memberships = list(
        db.scalars(
            select(SupplierPortfolioMembership).where(
                SupplierPortfolioMembership.owner_id == owner.id
            )
        )
    )
    assessments = list(
        db.scalars(
            select(SupplierPortfolioAssessmentVersion).where(
                SupplierPortfolioAssessmentVersion.owner_id == owner.id
            )
        )
    )
    snapshots = list(
        db.scalars(
            select(SupplierPortfolioInputSnapshot).where(
                SupplierPortfolioInputSnapshot.owner_id == owner.id
            )
        )
    )
    concentration = list(
        db.scalars(
            select(SupplierPortfolioConcentrationMetric).where(
                SupplierPortfolioConcentrationMetric.owner_id == owner.id
            )
        )
    )
    dimensions = list(
        db.scalars(
            select(SupplierPortfolioResilienceDimensionResult).where(
                SupplierPortfolioResilienceDimensionResult.owner_id == owner.id
            )
        )
    )
    simulations = list(
        db.scalars(select(PortfolioSimulation).where(PortfolioSimulation.owner_id == owner.id))
    )
    results = list(
        db.scalars(
            select(PortfolioSimulationResult).where(PortfolioSimulationResult.owner_id == owner.id)
        )
    )
    recs = list(
        db.scalars(
            select(SupplierPortfolioRecommendation).where(
                SupplierPortfolioRecommendation.owner_id == owner.id
            )
        )
    )
    event_keys = list(
        db.scalars(
            select(AuditEvent.idempotency_key).where(
                AuditEvent.actor_id == owner.id,
                AuditEvent.entity_type == "supplier_portfolio",
                AuditEvent.idempotency_key.is_not(None),
            )
        )
    )
    calendar_keys = list(
        db.scalars(
            select(SourcingCalendarItem.idempotency_key).where(
                SourcingCalendarItem.owner_id == owner.id,
                SourcingCalendarItem.entity_type == "supplier_portfolio",
            )
        )
    )
    supplier_ids = {row.supplier_id for row in memberships}
    suppliers = {
        row.id: row
        for row in db.scalars(
            select(CrossMarketplaceSupplier).where(CrossMarketplaceSupplier.id.in_(supplier_ids))
        )
    }
    context_ids = {row.id for row in contexts}
    assessment_ids = {row.id for row in assessments}
    simulation_ids = {row.id for row in simulations}
    return {
        "duplicate_portfolio_contexts": len(contexts)
        - len({row.idempotency_key for row in contexts}),
        "portfolios_without_current_assessment": sum(
            row.current_assessment_version_id is None for row in contexts
        ),
        "broken_current_assessment_pointers": sum(
            row.current_assessment_version_id not in assessment_ids
            for row in contexts
            if row.current_assessment_version_id
        ),
        "orphan_portfolio_memberships": sum(
            row.portfolio_id not in context_ids for row in memberships
        ),
        "orphan_assessment_snapshots": sum(
            row.assessment_version_id not in assessment_ids for row in snapshots
        ),
        "assessment_without_required_snapshot": sum(
            row.id not in {snapshot.assessment_version_id for snapshot in snapshots}
            for row in assessments
        ),
        "duplicate_current_assessment_outputs": len(assessments)
        - len({(row.portfolio_id, row.version) for row in assessments}),
        "duplicate_concentration_outputs": len(concentration)
        - len(
            {(row.assessment_version_id, row.dimension, row.metric_type) for row in concentration}
        ),
        "duplicate_resilience_outputs": len(dimensions)
        - len({(row.assessment_version_id, row.dimension) for row in dimensions}),
        "duplicate_simulation_results": len(results) - len({row.simulation_id for row in results}),
        "broken_supplier_lineage": sum(row.supplier_id not in suppliers for row in memberships),
        "broken_shortlist_lineage": 0,
        "broken_due_diligence_lineage": 0,
        "broken_sourcing_scenario_lineage": 0,
        "broken_recommendation_lineage": sum(
            row.assessment_version_id not in assessment_ids for row in recs
        ),
        "broken_simulation_lineage": sum(
            row.simulation_id not in simulation_ids for row in results
        ),
        "cross_owner_references": sum(row.owner_id != owner.id for row in suppliers.values()),
        "invalid_score_bounds": sum(
            row.score is not None and (float(row.score) < 0 or float(row.score) > 100)
            for row in db.scalars(
                select(SupplierPortfolioResilienceScore).where(
                    SupplierPortfolioResilienceScore.owner_id == owner.id
                )
            )
        ),
        "invalid_allocation_bounds": sum(
            row.allocation_percent is not None
            and (float(row.allocation_percent) < 0 or float(row.allocation_percent) > 100)
            for row in memberships
        ),
        "duplicate_product_channel_events": len(event_keys) - len(set(event_keys)),
        "duplicate_calendar_events": len(calendar_keys) - len(set(calendar_keys)),
        "duplicate_research_handoffs": 0,
        "duplicate_due_diligence_handoffs": 0,
        "duplicate_backup_scenario_handoffs": 0,
    }


def operations(db: Session, owner: User) -> dict[str, Any]:
    portfolios = list(
        db.scalars(
            select(SupplierPortfolioContext).where(SupplierPortfolioContext.owner_id == owner.id)
        )
    )
    assessments = list(
        db.scalars(
            select(SupplierPortfolioAssessmentVersion).where(
                SupplierPortfolioAssessmentVersion.owner_id == owner.id
            )
        )
    )
    scores = list(
        db.scalars(
            select(SupplierPortfolioResilienceScore).where(
                SupplierPortfolioResilienceScore.owner_id == owner.id
            )
        )
    )
    dependencies = list(
        db.scalars(
            select(SupplierPortfolioDependencyFinding).where(
                SupplierPortfolioDependencyFinding.owner_id == owner.id
            )
        )
    )
    recommendations = list(
        db.scalars(
            select(SupplierPortfolioRecommendation).where(
                SupplierPortfolioRecommendation.owner_id == owner.id
            )
        )
    )
    simulations = list(
        db.scalars(select(PortfolioSimulation).where(PortfolioSimulation.owner_id == owner.id))
    )
    results = list(
        db.scalars(
            select(PortfolioSimulationResult).where(PortfolioSimulationResult.owner_id == owner.id)
        )
    )
    actions = list(
        db.scalars(
            select(SupplierPortfolioHumanAction).where(
                SupplierPortfolioHumanAction.owner_id == owner.id
            )
        )
    )
    integrity = portfolio_integrity(db, owner)
    return {
        "portfolio_contexts": len(portfolios),
        "current_assessments": sum(
            row.current_assessment_version_id is not None for row in portfolios
        ),
        "stale_assessments": sum(row.status == "stale" for row in portfolios),
        "low_resilience_portfolios": sum(
            row.classification in {"LOW", "VERY_LOW"} for row in scores
        ),
        "critical_dependencies": sum(
            str(row.severity).upper() == "CRITICAL" for row in dependencies
        ),
        "open_critical_recommendations": sum(
            row.priority == "CRITICAL" and row.status == "OPEN" for row in recommendations
        ),
        "insufficient_evidence_portfolios": sum(
            row.evidence_status == "INSUFFICIENT" for row in scores
        ),
        "simulations": len(simulations),
        "failed_simulations": sum(row.status == "FAILED" for row in simulations)
        + sum(row.status == "FAILED" for row in results),
        "stale_baseline_simulations": sum(
            (row.baseline or {}).get("staleness") == "BASELINE_STALE" for row in results
        ),
        "research_requests": sum(row.action == "REQUEST_MORE_RESEARCH" for row in actions),
        "due_diligence_requests": sum(row.action == "REQUEST_DUE_DILIGENCE" for row in actions),
        "backup_scenario_requests": sum(row.action == "CREATE_BACKUP_SCENARIO" for row in actions),
        "integrity_issues": sum(integrity.values()),
        "integrity": integrity,
        "drill_down": {
            "portfolios": [str(row.id) for row in portfolios],
            "assessments": [str(row.id) for row in assessments],
            "dependencies": [str(row.id) for row in dependencies],
            "recommendations": [str(row.id) for row in recommendations],
            "simulations": [str(row.id) for row in simulations],
        },
    }


def human_action(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, data: Any
) -> dict[str, Any]:
    assessment = _assessment(db, owner, portfolio)
    if data.assessment_version_id and (
        assessment is None or data.assessment_version_id != assessment.id
    ):
        raise HTTPException(409, "The requested assessment is not current for this portfolio.")
    recommendation = None
    if data.recommendation_id:
        recommendation = db.scalar(
            select(SupplierPortfolioRecommendation).where(
                SupplierPortfolioRecommendation.id == data.recommendation_id,
                SupplierPortfolioRecommendation.owner_id == owner.id,
                SupplierPortfolioRecommendation.portfolio_id == portfolio.id,
            )
        )
        if recommendation is None:
            raise HTTPException(404, "Portfolio recommendation not found.")
    key = f"portfolio-action:{portfolio.id}:{data.action}:{data.idempotency_key}"
    existing = db.scalar(
        select(SupplierPortfolioHumanAction).where(
            SupplierPortfolioHumanAction.owner_id == owner.id,
            SupplierPortfolioHumanAction.portfolio_id == portfolio.id,
            SupplierPortfolioHumanAction.action == data.action,
            SupplierPortfolioHumanAction.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return {
            "id": str(existing.id),
            "action": existing.action,
            "status": existing.status,
            "idempotent_reuse": True,
            "audit_id": existing.payload.get("audit_id"),
        }
    if (
        data.action in {"ACKNOWLEDGE_RISK", "KEEP_UNDER_REVIEW", "ARCHIVE_RECOMMENDATION"}
        and recommendation is None
    ):
        raise HTTPException(422, "A recommendation is required for this portfolio action.")
    if recommendation is not None:
        recommendation.status = {
            "ACKNOWLEDGE_RISK": "ACKNOWLEDGED",
            "KEEP_UNDER_REVIEW": "UNDER_REVIEW",
            "ARCHIVE_RECOMMENDATION": "ARCHIVED",
        }.get(data.action, recommendation.status)
    handoff: dict[str, Any] = {"external_dispatch": False, "rationale": data.rationale}
    if data.action in {"REQUEST_MORE_RESEARCH", "REQUEST_DUE_DILIGENCE", "CREATE_BACKUP_SCENARIO"}:
        member_query = select(SupplierPortfolioMembership).where(
            SupplierPortfolioMembership.owner_id == owner.id,
            SupplierPortfolioMembership.portfolio_id == portfolio.id,
        )
        if data.supplier_id:
            member_query = member_query.where(
                SupplierPortfolioMembership.supplier_id == data.supplier_id
            )
        member = db.scalar(member_query.order_by(SupplierPortfolioMembership.created_at))
        if member is None:
            raise HTTPException(409, "A portfolio supplier is required for this handoff.")
        if data.action in {"REQUEST_MORE_RESEARCH", "REQUEST_DUE_DILIGENCE"}:
            product_id = next(iter(member.associated_products or []), None)
            if product_id is None:
                raise HTTPException(409, "A portfolio product is required for this handoff.")
            due, _ = create_due_context(
                db,
                owner,
                DueDiligenceContextCreate(
                    supplier_id=member.supplier_id,
                    product_id=uuid.UUID(str(product_id)),
                    idempotency_key=f"portfolio:{data.action.casefold()}:{portfolio.id}:{member.supplier_id}",
                ),
            )
            handoff["due_diligence_context_id"] = str(due.id)
            if data.action == "REQUEST_MORE_RESEARCH":
                plan, _ = create_due_plan(
                    db,
                    owner,
                    due,
                    ResearchPlanCreate(
                        idempotency_key=f"portfolio-research:{portfolio.id}:{member.supplier_id}"
                    ),
                )
                handoff["research_plan_id"] = str(plan["id"])
        else:
            handoff["sourcing_scenario"] = "bounded_internal_request"
            handoff["supplier_id"] = str(member.supplier_id)
    event_name = {
        "REQUEST_MORE_RESEARCH": "PORTFOLIO_RESEARCH_REQUESTED",
        "REQUEST_DUE_DILIGENCE": "PORTFOLIO_DUE_DILIGENCE_REQUESTED",
        "CREATE_BACKUP_SCENARIO": "PORTFOLIO_BACKUP_SCENARIO_REQUESTED",
    }.get(data.action, "PORTFOLIO_RECOMMENDATION_CREATED")
    event = _emit(
        db,
        owner,
        portfolio,
        event_name,
        key,
        {
            "assessment_version_id": str(assessment.id) if assessment else None,
            "action": data.action,
            **handoff,
        },
    )
    row = SupplierPortfolioHumanAction(
        owner_id=owner.id,
        portfolio_id=portfolio.id,
        assessment_version_id=assessment.id if assessment else None,
        recommendation_id=recommendation.id if recommendation else None,
        supplier_id=data.supplier_id,
        action=data.action,
        status="RECORDED",
        rationale=data.rationale,
        idempotency_key=data.idempotency_key,
        payload={**handoff, "audit_id": str(event.id)},
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    return {
        "id": str(row.id),
        "action": row.action,
        "status": row.status,
        "idempotent_reuse": False,
        "audit_id": str(event.id),
        **handoff,
    }


def recover(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, data: Any
) -> dict[str, Any]:
    if not data.confirm:
        raise HTTPException(
            422, "Explicit confirmation is required for a portfolio Recovery action."
        )
    if data.action in UNSUPPORTED_RECOVERY_ACTIONS:
        raise HTTPException(409, f"Recovery action '{data.action}' is not safely implemented.")
    key = f"portfolio-recovery:{portfolio.id}:{data.action}:{data.idempotency_key}"
    event_key = _event_key(owner, portfolio, key)
    prior = db.scalar(select(AuditEvent).where(AuditEvent.idempotency_key == event_key))
    if prior:
        return {
            "status": "succeeded",
            "action": data.action,
            "idempotent_reuse": True,
            "audit_id": str(prior.id),
        }
    assessment = _assessment(db, owner, portfolio)
    if assessment is None or portfolio.status not in {"stale", "review_required"}:
        raise HTTPException(409, "A stale portfolio assessment is not available for recalculation.")
    result, reused = create_assessment(
        db,
        owner,
        portfolio,
        AssessmentCreate(
            idempotency_key=f"recovery:{data.idempotency_key}",
            input_snapshot={
                "recovery_reason": data.reason,
                "previous_assessment_version_id": str(assessment.id),
            },
        ),
    )
    portfolio.status = "active"
    portfolio.updated_at = _now()
    event = _emit(
        db,
        owner,
        portfolio,
        "PORTFOLIO_ASSESSMENT_CREATED",
        key,
        {
            "assessment_version_id": result["id"],
            "recovery_action": data.action,
            "previous_assessment_version_id": str(assessment.id),
        },
    )
    db.commit()
    return {
        "status": "succeeded",
        "action": data.action,
        "assessment": result,
        "reused": reused,
        "idempotent_reuse": False,
        "audit_id": str(event.id),
    }
