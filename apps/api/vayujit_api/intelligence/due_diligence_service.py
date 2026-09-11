from __future__ import annotations

import html
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchClaim,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.cross_marketplace_models import (
    CrossMarketplaceSupplier,
    CrossMarketplaceSupplierLink,
)
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceAssessment,
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
    SupplierResearchPlan,
    SupplierResearchTask,
)
from vayujit_api.intelligence.due_diligence_schemas import (
    DueDiligenceContextCreate,
    HumanGapAction,
    ResearchPlanCreate,
)
from vayujit_api.intelligence.website_models import WebsiteObservation
from vayujit_api.products.models import Product


def _now() -> datetime:
    return datetime.now(UTC)


def _owned(db: Session, model: Any, owner: User, ident: uuid.UUID, message: str):
    row = db.scalar(select(model).where(model.id == ident, model.owner_id == owner.id))
    if row is None:
        raise HTTPException(404, message)
    return row


def _supplier_view(s: CrossMarketplaceSupplier) -> dict[str, Any]:
    return dict(s.view_json or {})


def create_context(db: Session, owner: User, data: DueDiligenceContextCreate):
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
            {"identity": f"due-diligence-context:{owner.id}:{data.idempotency_key}"},
        )
    existing = db.scalar(
        select(SupplierDueDiligenceContext).where(
            SupplierDueDiligenceContext.owner_id == owner.id,
            SupplierDueDiligenceContext.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    _owned(db, CrossMarketplaceSupplier, owner, data.supplier_id, "Supplier not found.")
    if data.product_id:
        _owned(db, Product, owner, data.product_id, "Product not found.")
    row = SupplierDueDiligenceContext(
        owner_id=owner.id,
        supplier_id=data.supplier_id,
        product_id=data.product_id,
        opportunity_id=data.opportunity_id,
        shortlist_context_id=data.shortlist_context_id,
        shortlist_version_id=data.shortlist_version_id,
        recommendation_id=data.recommendation_id,
        requirement_id=data.requirement_id,
        idempotency_key=data.idempotency_key,
        status="OPEN",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, False


def _gap_spec(
    context: SupplierDueDiligenceContext, supplier: CrossMarketplaceSupplier
) -> list[dict[str, Any]]:
    view = _supplier_view(supplier)
    specs: list[dict[str, Any]] = []

    def add(
        dim: str,
        state: str,
        severity: str,
        reason: str,
        classification: str = "REQUIRED",
        evidence: list[Any] | None = None,
        confidence: float = 0.0,
    ):
        score = {"CRITICAL": 100, "HIGH": 75, "MEDIUM": 50, "LOW": 25}[severity]
        specs.append(
            {
                "dimension": dim,
                "status": state,
                "severity": severity,
                "classification": classification,
                "reason": reason,
                "required_evidence": [dim.lower()],
                "evidence_refs": evidence or [],
                "confidence": confidence,
                "freshness_state": supplier.freshness_status or "unknown",
                "contradiction_state": "present" if view.get("contradictions") else "none",
                "priority_score": score + (25 if state in {"MISSING", "CONTRADICTORY"} else 0),
                "priority_level": severity,
            }
        )

    if supplier.identity_state != "MATCH":
        add(
            "IDENTITY",
            "WEAK" if supplier.identity_state == "POSSIBLE_MATCH" else "MISSING",
            "HIGH",
            "Supplier identity is not verified.",
        )
    if not view.get("capabilities"):
        add(
            "MANUFACTURING_CAPABILITY",
            "MISSING",
            "HIGH",
            "No supplier capability evidence is available.",
        )
    if not view.get("certifications"):
        add("CERTIFICATION", "MISSING", "HIGH", "No certification evidence is available.")
    if not view.get("facilities"):
        add("FACILITY", "MISSING", "MEDIUM", "No facility evidence is available.")
    if supplier.freshness_status in {"stale", "expired"}:
        add("FRESHNESS", "STALE", "HIGH", "Supplier evidence is stale.")
    if supplier.source_diversity_score is None or float(supplier.source_diversity_score or 0) < 2:
        add(
            "SOURCE_DIVERSITY",
            "WEAK",
            "MEDIUM",
            "Evidence lacks independent source diversity.",
            "RECOMMENDED",
        )
    risk_value = view.get("risk_state", view.get("risk"))
    if isinstance(risk_value, dict):
        risk_state = str(risk_value.get("level", risk_value.get("state", "unknown"))).casefold()
    else:
        risk_state = str(risk_value).casefold() if risk_value is not None else ""
    risk_blocked = (
        risk_state in {"unknown", "unresolved", "unsupported", "stale", "contradicted"}
        or (risk_state and supplier.freshness_status in {"stale", "expired"})
        or (risk_state and bool(view.get("contradictions")))
    )
    if risk_state in {"high", "critical"}:
        add("RISK", "MISSING", "CRITICAL", "High supplier risk requires documented evidence.")
    elif risk_blocked:
        add(
            "RISK",
            "WEAK" if risk_state in {"unknown", "unresolved"} else "INSUFFICIENT",
            "HIGH" if risk_state in {"stale", "contradicted"} else "MEDIUM",
            "Supplier risk evidence is unresolved, stale, unsupported, or contradicted.",
        )
    if "reputation" in view and not view.get("reputation"):
        add(
            "REPUTATION",
            "WEAK",
            "LOW",
            "Reputation evidence is useful for review but is not required for sourcing readiness.",
            "OPTIONAL",
        )
    if view.get("contradictions"):
        add(
            "CONTRADICTION",
            "CONTRADICTORY",
            "CRITICAL",
            "Material supplier evidence contradiction requires review.",
        )
    return specs


def assess(db: Session, owner: User, context: SupplierDueDiligenceContext):
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
            {"identity": f"due-diligence-assess:{owner.id}:{context.id}"},
        )
        db.refresh(context)
    supplier = _owned(
        db, CrossMarketplaceSupplier, owner, context.supplier_id, "Supplier not found."
    )
    version = context.current_assessment_version + 1
    specs = _gap_spec(context, supplier)
    readiness = (
        "SUFFICIENT"
        if not specs
        else (
            "REVIEW_REQUIRED"
            if any(x["severity"] in {"CRITICAL", "HIGH"} for x in specs)
            else "INSUFFICIENT_EVIDENCE"
        )
    )
    summary = {
        "open_gaps": len(specs),
        "critical_gaps": sum(x["severity"] == "CRITICAL" for x in specs),
        "high_gaps": sum(x["severity"] == "HIGH" for x in specs),
        "readiness": readiness,
        "scoring_version": "due-diligence-v1",
    }
    db.add(
        SupplierDueDiligenceAssessment(
            owner_id=owner.id,
            context_id=context.id,
            version=version,
            readiness=readiness,
            summary=summary,
            created_at=_now(),
        )
    )
    for item in specs:
        db.add(
            SupplierEvidenceGap(
                owner_id=owner.id,
                context_id=context.id,
                supplier_id=context.supplier_id,
                product_id=context.product_id,
                assessment_version=version,
                **item,
                created_at=_now(),
                updated_at=_now(),
            )
        )
    context.current_assessment_version = version
    context.status = (
        readiness if readiness in {"SUFFICIENT", "REVIEW_REQUIRED"} else "RESEARCH_REQUIRED"
    )
    context.updated_at = _now()
    db.commit()
    return {
        "assessment_version": version,
        **summary,
        "gaps": [{**x, "assessment_version": version} for x in specs],
    }


def create_plan(
    db: Session,
    owner: User,
    context: SupplierDueDiligenceContext,
    data: ResearchPlanCreate,
    selected_gap_ids: set[uuid.UUID] | None = None,
):
    if context.current_assessment_version == 0:
        assess(db, owner, context)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:identity))"),
            {"identity": f"due-diligence-plan:{owner.id}:{context.id}:{data.idempotency_key}"},
        )
        db.refresh(context)
    existing = db.scalar(
        select(SupplierResearchPlan).where(
            SupplierResearchPlan.owner_id == owner.id,
            SupplierResearchPlan.context_id == context.id,
            SupplierResearchPlan.assessment_version == context.current_assessment_version,
            SupplierResearchPlan.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return serialize_plan(existing), True
    active_plan = db.scalar(
        select(SupplierResearchPlan)
        .where(
            SupplierResearchPlan.owner_id == owner.id,
            SupplierResearchPlan.context_id == context.id,
            SupplierResearchPlan.assessment_version == context.current_assessment_version,
            SupplierResearchPlan.status.in_({"READY", "RUNNING"}),
        )
        .order_by(SupplierResearchPlan.created_at.desc())
    )
    if active_plan is not None:
        return serialize_plan(active_plan), True
    gap_query = (
        select(SupplierEvidenceGap)
        .where(
            SupplierEvidenceGap.owner_id == owner.id,
            SupplierEvidenceGap.context_id == context.id,
            SupplierEvidenceGap.assessment_version == context.current_assessment_version,
            SupplierEvidenceGap.status != "RESOLVED",
        )
        .order_by(SupplierEvidenceGap.priority_score.desc())
    )
    if selected_gap_ids is not None:
        gap_query = gap_query.where(SupplierEvidenceGap.id.in_(selected_gap_ids))
    gaps = list(db.scalars(gap_query.limit(data.max_tasks)))
    plan = SupplierResearchPlan(
        owner_id=owner.id,
        context_id=context.id,
        supplier_id=context.supplier_id,
        assessment_version=context.current_assessment_version,
        status="READY" if gaps else "COMPLETED",
        priority=max([float(g.priority_score or 0) for g in gaps], default=0),
        budget={
            "max_tasks": data.max_tasks,
            "max_sources": data.max_sources,
            "max_provider_calls": data.max_provider_calls,
            "max_runtime_seconds": 300,
        },
        allowed_methods=[
            "WEBSITE_RESEARCH",
            "MARKETPLACE_RESEARCH",
            "EVIDENCE_VERIFICATION",
            "FRESHNESS_RECHECK",
        ],
        prohibited_methods=["SUPPLIER_CONTACT", "RFQ", "PURCHASE", "PAYMENT"],
        reason="Deterministic evidence-gap coverage.",
        idempotency_key=data.idempotency_key,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(plan)
    db.flush()
    mission = AutonomousResearchMission(
        owner_id=owner.id,
        mission_type="SUPPLIER_VERIFICATION",
        goal="Bounded supplier due-diligence evidence research",
        scope={"due_diligence_context_id": str(context.id), "plan_id": str(plan.id)},
        product_id=context.product_id,
        supplier_id=context.supplier_id,
        research_profile={"source": "due_diligence"},
        ruleset={"contact_supplier": False},
        source_policy={"mode": "LOCAL_FIXTURE", "allowed": plan.allowed_methods},
        budget_policy=plan.budget,
        provider_mode="LOCAL_DETERMINISTIC",
        correlation_id=f"due-diligence-{context.id}",
        status="QUEUED",
        idempotency_key=f"due-diligence:{plan.id}",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(mission)
    db.flush()
    from vayujit_api.intelligence.autonomous_models import AutonomousResearchTask

    for gap in gaps:
        task_type = (
            "FRESHNESS_RECHECK"
            if gap.dimension == "FRESHNESS"
            else (
                "CONTRADICTION_RESEARCH"
                if gap.dimension == "CONTRADICTION"
                else "EVIDENCE_VERIFICATION"
            )
        )
        due_task = SupplierResearchTask(
            owner_id=owner.id,
            plan_id=plan.id,
            gap_id=gap.id,
            task_type=task_type,
            status="QUEUED",
            priority=gap.priority_score,
            idempotency_key=f"{data.idempotency_key}:{gap.dimension}",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(due_task)
        db.flush()
        shared_task = AutonomousResearchTask(
            owner_id=owner.id,
            mission_id=mission.id,
            task_type=task_type,
            dependency_ids=[],
            source_class="INTERNAL",
            priority=int(gap.priority_score or 0),
            status="QUEUED",
            attempt_count=0,
            checkpoint={
                "role": "supplier_due_diligence",
                "due_diligence_task_id": str(due_task.id),
                "required_evidence_classes": [gap.dimension],
            },
            result_projection={},
            idempotency_key=f"{mission.id}:{due_task.id}",
            correlation_id=mission.correlation_id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(shared_task)
        db.flush()
        due_task.shared_execution_id = shared_task.id
    db.commit()
    db.refresh(plan)
    return serialize_plan(plan), False


def serialize_plan(p: SupplierResearchPlan) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "context_id": str(p.context_id),
        "assessment_version": p.assessment_version,
        "status": p.status,
        "priority": float(p.priority or 0),
        "budget": p.budget,
        "allowed_methods": p.allowed_methods,
        "prohibited_methods": p.prohibited_methods,
        "reason": p.reason,
    }


def _gap_lineage(db: Session, owner: User, gap: SupplierEvidenceGap) -> dict[str, object]:
    references = [
        str(item) for item in [*(gap.evidence_refs or []), *(gap.resolution_evidence_refs or [])]
    ]
    evidence_rows: list[AutonomousResearchEvidence] = []
    ids: list[uuid.UUID] = []
    for value in references:
        try:
            ids.append(uuid.UUID(value))
        except (ValueError, AttributeError):
            continue
    if ids:
        evidence_rows = list(
            db.scalars(
                select(AutonomousResearchEvidence).where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    AutonomousResearchEvidence.id.in_(ids),
                )
            )
        )
    claims = list(
        db.scalars(
            select(AutonomousResearchClaim).where(
                AutonomousResearchClaim.owner_id == owner.id,
                AutonomousResearchClaim.task_id.in_(
                    [row.task_id for row in evidence_rows] if evidence_rows else [uuid.uuid4()]
                ),
            )
        )
    )
    observations = (
        [
            observation
            for observation in db.scalars(
                select(WebsiteObservation).where(WebsiteObservation.owner_id == owner.id)
            )
            if any(str(item.id) in (observation.evidence_ids or []) for item in evidence_rows)
        ]
        if evidence_rows
        else []
    )
    return {
        "context_id": str(gap.context_id),
        "assessment_version": gap.assessment_version,
        "gap_id": str(gap.id),
        "evidence_refs": references,
        "evidence": [
            {
                "id": str(row.id),
                "verification_status": row.verification_status,
                "freshness_status": row.freshness_status,
                "observed_at": row.observed_at.isoformat(),
            }
            for row in evidence_rows
        ],
        "claim_ids": [str(row.id) for row in claims],
        "observation_ids": [str(row.id) for row in observations],
        "observation_versions": [
            {
                "id": str(row.id),
                "identity": row.observation_identity,
                "previous_observation_id": (
                    str(row.previous_observation_id) if row.previous_observation_id else None
                ),
                "verification": row.verification,
                "freshness": row.freshness,
            }
            for row in observations
        ],
        "verification_state": [row.verification_status for row in evidence_rows],
        "resolution_reason": "accepted_evidence" if gap.status == "RESOLVED" else None,
        "human_waiver": gap.status == "WAIVED_BY_HUMAN",
    }


def context_json(db: Session, owner: User, context: SupplierDueDiligenceContext) -> dict[str, Any]:
    assessment = db.scalar(
        select(SupplierDueDiligenceAssessment)
        .where(SupplierDueDiligenceAssessment.context_id == context.id)
        .order_by(SupplierDueDiligenceAssessment.version.desc())
    )
    gaps = list(
        db.scalars(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.context_id == context.id,
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.assessment_version == context.current_assessment_version,
            )
        )
    )
    readiness = assessment.readiness if assessment else "NOT_ASSESSED"
    open_gaps = [gap for gap in gaps if gap.status not in {"RESOLVED", "WAIVED_BY_HUMAN"}]
    explanation_reasons: list[str] = []
    if any(
        gap.contradiction_state not in {"none", ""} or gap.status == "CONTRADICTORY"
        for gap in open_gaps
    ):
        explanation_reasons.append("Material contradiction remains.")
    if any(
        gap.freshness_state in {"stale", "expired"} or gap.status == "STALE" for gap in open_gaps
    ):
        explanation_reasons.append("Stale or expired evidence requires review.")
    if any(gap.classification == "REQUIRED" for gap in open_gaps):
        explanation_reasons.append("Required evidence or risk verification remains unresolved.")
    if not explanation_reasons and readiness == "REVIEW_REQUIRED":
        explanation_reasons.append("Human review is required before sourcing.")
    return {
        "id": str(context.id),
        "supplier_id": str(context.supplier_id),
        "product_id": str(context.product_id) if context.product_id else None,
        "status": context.status,
        "assessment_version": context.current_assessment_version,
        "readiness": readiness,
        "summary": assessment.summary if assessment else {},
        "explanation": {
            "status": readiness,
            "reasons": explanation_reasons,
            "blocking_gap_ids": [
                str(gap.id) for gap in open_gaps if gap.severity in {"HIGH", "CRITICAL"}
            ],
        },
        "gaps": [
            {
                "id": str(g.id),
                "dimension": g.dimension,
                "status": g.status,
                "severity": g.severity,
                "classification": g.classification,
                "reason": g.reason,
                "confidence": float(g.confidence or 0),
                "freshness": g.freshness_state,
                "contradiction": g.contradiction_state,
                "priority_score": float(g.priority_score or 0),
                "evidence_count": len((g.evidence_refs or []) + (g.resolution_evidence_refs or [])),
                "resolution_type": g.resolution_type,
                "resolution_evidence_ids": [
                    str(item) for item in (g.resolution_evidence_refs or [])
                ],
                "resolution_observation_ids": [
                    str(item) for item in (g.resolution_observation_ids or [])
                ],
                "resolved_at": g.resolved_at.isoformat() if g.resolved_at else None,
                "resolved_by": str(g.resolved_by) if g.resolved_by else None,
                "verification_state": _gap_lineage(db, owner, g)["verification_state"],
                "lineage": _gap_lineage(db, owner, g),
            }
            for g in gaps
        ],
    }


def human_action(
    db: Session, owner: User, gap: SupplierEvidenceGap, action: str, data: HumanGapAction
):
    normalized = action.strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "waive": "waive_gap",
        "reopen": "reopen_gap",
        "research": "start_research",
        "research_selected": "research_selected_gaps",
    }
    normalized = aliases.get(normalized, normalized)
    transitions = {
        "start_research": "RESEARCHING",
        "research_selected_gaps": "RESEARCHING",
        "request_more_research": "RESEARCHING",
        "cancel_research": "BLOCKED",
        "waive_gap": "WAIVED_BY_HUMAN",
        "reopen_gap": "MISSING",
        "mark_for_human_review": "BLOCKED",
    }
    if normalized not in transitions:
        raise HTTPException(400, "Unsupported due-diligence action.")
    reason = data.reason.strip()
    idempotency_key = f"due-diligence:{normalized}:{gap.id}:{reason}"
    existing_event = db.scalar(
        select(AuditEvent).where(AuditEvent.idempotency_key == idempotency_key)
    )
    if existing_event is not None:
        metadata = existing_event.metadata_json or {}
        return {
            "id": str(existing_event.entity_id),
            "status": str(metadata.get("resulting_state", gap.status)),
            "action": normalized,
            "previous_status": metadata.get("previous_state"),
            "idempotency_key": idempotency_key,
            "idempotent_reuse": True,
            "research_intent_id": metadata.get("research_intent_id"),
        }
    if normalized == "waive_gap" and not reason:
        raise HTTPException(422, "A waiver reason is required.")
    context = _owned(
        db,
        SupplierDueDiligenceContext,
        owner,
        gap.context_id,
        "Due-diligence context not found.",
    )
    selected_ids = set(data.selected_gap_ids or [])
    if normalized == "research_selected_gaps":
        if not selected_ids:
            selected_ids = {gap.id}
        if gap.id not in selected_ids:
            raise HTTPException(422, "The action gap must be included in selected_gap_ids.")
        selected_gaps = list(
            db.scalars(
                select(SupplierEvidenceGap).where(
                    SupplierEvidenceGap.owner_id == owner.id,
                    SupplierEvidenceGap.context_id == context.id,
                    SupplierEvidenceGap.assessment_version == context.current_assessment_version,
                    SupplierEvidenceGap.id.in_(selected_ids),
                )
            )
        )
        if len(selected_gaps) != len(selected_ids):
            raise HTTPException(404, "One or more selected evidence gaps were not found.")
    else:
        selected_gaps = [gap]
        selected_ids = {gap.id}
    if normalized in {"start_research", "research_selected_gaps", "request_more_research"}:
        if context.status in {"CLOSED", "SUFFICIENT"}:
            raise HTTPException(409, "Research is not valid for a closed or sufficient context.")
        for candidate in selected_gaps:
            if candidate.status in {"RESOLVED", "WAIVED_BY_HUMAN"}:
                raise HTTPException(409, "Research cannot start for a resolved or waived gap.")
            active = db.scalar(
                select(SupplierResearchTask.id)
                .join(SupplierResearchPlan, SupplierResearchPlan.id == SupplierResearchTask.plan_id)
                .where(
                    SupplierResearchTask.owner_id == owner.id,
                    SupplierResearchTask.gap_id == candidate.id,
                    SupplierResearchTask.status.in_({"QUEUED", "RUNNING"}),
                    SupplierResearchPlan.context_id == context.id,
                )
            )
            if active is not None and normalized != "request_more_research":
                raise HTTPException(409, "Research is already active for this gap.")
    if normalized == "waive_gap" and gap.status in {"RESOLVED", "WAIVED_BY_HUMAN"}:
        raise HTTPException(409, "This gap is already resolved or waived.")
    if normalized == "reopen_gap" and gap.status not in {
        "RESOLVED",
        "WAIVED_BY_HUMAN",
        "BLOCKED",
    }:
        raise HTTPException(409, "Only resolved, waived, or blocked gaps can be reopened.")
    if normalized == "cancel_research" and gap.status != "RESEARCHING":
        raise HTTPException(409, "Only active research can be cancelled.")
    research_intent_id: str | None = None
    if normalized in {"start_research", "research_selected_gaps", "request_more_research"}:
        plan_value, _ = create_plan(
            db,
            owner,
            context,
            ResearchPlanCreate(
                idempotency_key=f"action:{idempotency_key}",
                max_tasks=(
                    max(1, len(selected_ids)) if normalized == "research_selected_gaps" else 1
                ),
            ),
            selected_gap_ids=selected_ids,
        )
        if plan_value["status"] == "COMPLETED":
            raise HTTPException(409, "No researchable evidence gaps remain.")
        research_intent_id = str(plan_value["id"])
    previous_status = gap.status
    result_gap = gap
    if normalized == "reopen_gap":
        latest_gaps = list(
            db.scalars(
                select(SupplierEvidenceGap).where(
                    SupplierEvidenceGap.owner_id == owner.id,
                    SupplierEvidenceGap.context_id == context.id,
                    SupplierEvidenceGap.assessment_version == context.current_assessment_version,
                )
            )
        )
        next_version = context.current_assessment_version + 1
        db.add(
            SupplierDueDiligenceAssessment(
                owner_id=owner.id,
                context_id=context.id,
                version=next_version,
                readiness="REVIEW_REQUIRED",
                summary={
                    "open_gaps": sum(
                        row.status not in {"RESOLVED", "WAIVED_BY_HUMAN"} for row in latest_gaps
                    ),
                    "reopened_gap_id": str(gap.id),
                    "reopened_from_version": context.current_assessment_version,
                },
                created_at=_now(),
            )
        )
        for row in latest_gaps:
            reopened = row.id == gap.id
            clone = SupplierEvidenceGap(
                owner_id=owner.id,
                context_id=row.context_id,
                supplier_id=row.supplier_id,
                product_id=row.product_id,
                assessment_version=next_version,
                dimension=row.dimension,
                status="MISSING" if reopened else row.status,
                severity=row.severity,
                classification=row.classification,
                reason=row.reason,
                required_evidence=row.required_evidence,
                evidence_refs=row.evidence_refs,
                confidence=row.confidence,
                freshness_state=row.freshness_state,
                contradiction_state=row.contradiction_state,
                priority_score=row.priority_score,
                priority_level=row.priority_level,
                resolution_evidence_refs=[] if reopened else row.resolution_evidence_refs,
                resolution_type=None if reopened else row.resolution_type,
                resolution_observation_ids=[] if reopened else row.resolution_observation_ids,
                resolved_by=None if reopened else row.resolved_by,
                resolved_at=None if reopened else row.resolved_at,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(clone)
            if reopened:
                result_gap = clone
        context.current_assessment_version = next_version
        context.status = "REVIEW_REQUIRED"
        context.updated_at = _now()
    elif normalized == "cancel_research":
        active_tasks = list(
            db.scalars(
                select(SupplierResearchTask)
                .join(SupplierResearchPlan, SupplierResearchPlan.id == SupplierResearchTask.plan_id)
                .where(
                    SupplierResearchTask.owner_id == owner.id,
                    SupplierResearchTask.gap_id == gap.id,
                    SupplierResearchTask.status.in_({"QUEUED", "RUNNING"}),
                    SupplierResearchPlan.context_id == context.id,
                )
            )
        )
        for due_task in active_tasks:
            due_task.status = "CANCELLED"
            due_task.updated_at = _now()
            if due_task.shared_execution_id:
                shared_task = db.get(AutonomousResearchTask, due_task.shared_execution_id)
                if shared_task is not None and shared_task.status in {"QUEUED", "RUNNING"}:
                    shared_task.status = "CANCELLED"
                    shared_task.updated_at = _now()
        gap.status = "BLOCKED"
        gap.updated_at = _now()
        context.status = "BLOCKED"
        context.updated_at = _now()
    else:
        for candidate in selected_gaps:
            candidate.status = transitions[normalized]
            candidate.resolution_type = "human_waiver" if normalized == "waive_gap" else None
            candidate.resolved_by = owner.id if normalized == "waive_gap" else None
            candidate.resolved_at = _now() if normalized == "waive_gap" else None
            candidate.updated_at = _now()
        if normalized in {"start_research", "research_selected_gaps", "request_more_research"}:
            context.status = "RESEARCH_IN_PROGRESS"
            context.updated_at = _now()
    db.commit()
    record_event(
        db,
        actor_id=owner.id,
        action=f"supplier.due_diligence.{normalized}",
        entity_type="supplier_evidence_gap",
        entity_id=result_gap.id,
        metadata={
            "reason": reason[:200],
            "previous_state": previous_status,
            "resulting_state": result_gap.status,
            "context_id": str(result_gap.context_id),
            "research_intent_id": research_intent_id,
            "selected_gap_ids": [str(item) for item in sorted(selected_ids, key=str)],
        },
        idempotency_key=idempotency_key,
    )
    db.commit()
    return {
        "id": str(result_gap.id),
        "status": result_gap.status,
        "action": normalized,
        "previous_status": previous_status,
        "idempotency_key": idempotency_key,
        "idempotent_reuse": False,
        "research_intent_id": research_intent_id,
    }


def _observation_for_evidence(
    db: Session, owner: User, evidence: AutonomousResearchEvidence, gap: SupplierEvidenceGap
) -> WebsiteObservation:
    """Project verifier-accepted evidence through the existing observation ledger."""
    identity = f"due-diligence:{gap.id}:{evidence.id}:{evidence.content_hash}"
    existing = db.scalar(
        select(WebsiteObservation).where(
            WebsiteObservation.owner_id == owner.id,
            WebsiteObservation.observation_identity == identity,
        )
    )
    if existing is not None:
        return existing
    source = evidence.canonical_url or evidence.source_reference or "shared-research"
    domain = evidence.domain or "shared-research"
    row = WebsiteObservation(
        owner_id=owner.id,
        mission_id=evidence.mission_id,
        domain=domain[:255],
        page_url=source[:1000],
        observation_type="SUPPLIER_DUE_DILIGENCE",
        claim_type=gap.dimension,
        normalized_value=dict(evidence.normalized_value or {}),
        source_provided_state="RESEARCH_DERIVED",
        verification=evidence.verification_status,
        freshness=evidence.freshness_status,
        confidence=float(evidence.confidence or 0),
        content_hash=evidence.content_hash,
        evidence_ids=[str(evidence.id)],
        correlation_id=f"due-diligence:{gap.context_id}",
        observation_identity=identity,
        retrieved_at=evidence.retrieved_at,
        created_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def _recompute_shared_risk(
    db: Session, owner: User, context: SupplierDueDiligenceContext
) -> dict[str, object]:
    """Re-use canonical supplier reconciliation as the shared risk authority."""
    canonical = _owned(
        db, CrossMarketplaceSupplier, owner, context.supplier_id, "Supplier not found."
    )
    before = dict(_supplier_view(canonical).get("risk") or {})
    source_ids = list(
        db.scalars(
            select(CrossMarketplaceSupplierLink.supplier_id).where(
                CrossMarketplaceSupplierLink.owner_id == owner.id,
                CrossMarketplaceSupplierLink.canonical_supplier_id == canonical.id,
            )
        )
    )
    if source_ids:
        from vayujit_api.intelligence.cross_marketplace_service import reconcile

        reconcile(db, owner, source_ids)
        db.expire(canonical)
        db.refresh(canonical)
    after = dict(_supplier_view(canonical).get("risk") or {})
    reference = f"supplier-risk:{canonical.id}:{canonical.updated_at.isoformat()}"
    return {"reference": reference, "before": before, "after": after}


def sync_research_completion(
    db: Session, owner: User, context_id: uuid.UUID, mission_id: uuid.UUID
) -> dict[str, object]:
    """Project shared autonomous task completion into the due-diligence ledger."""
    context = db.scalar(
        select(SupplierDueDiligenceContext).where(
            SupplierDueDiligenceContext.id == context_id,
            SupplierDueDiligenceContext.owner_id == owner.id,
        )
    )
    if context is None:
        return {"updated": 0, "assessment_version": 0}
    current_assessment = db.scalar(
        select(SupplierDueDiligenceAssessment).where(
            SupplierDueDiligenceAssessment.owner_id == owner.id,
            SupplierDueDiligenceAssessment.context_id == context.id,
            SupplierDueDiligenceAssessment.version == context.current_assessment_version,
        )
    )
    if (
        current_assessment is not None
        and isinstance(current_assessment.summary, dict)
        and current_assessment.summary.get("reassessed_after_execution") == str(mission_id)
    ):
        return {
            "updated": 0,
            "assessment_version": context.current_assessment_version,
            "replayed": True,
        }
    due_tasks = list(
        db.scalars(
            select(SupplierResearchTask)
            .join(SupplierResearchPlan, SupplierResearchPlan.id == SupplierResearchTask.plan_id)
            .where(
                SupplierResearchTask.owner_id == owner.id,
                SupplierResearchPlan.context_id == context.id,
                SupplierResearchPlan.supplier_id == context.supplier_id,
            )
        )
    )
    shared_ids = [
        item.shared_execution_id for item in due_tasks if item.shared_execution_id is not None
    ]
    shared_tasks = {
        row.id: row
        for row in db.scalars(
            select(AutonomousResearchTask).where(
                AutonomousResearchTask.owner_id == owner.id,
                AutonomousResearchTask.mission_id == mission_id,
                AutonomousResearchTask.id.in_(shared_ids or [uuid.uuid4()]),
            )
        )
    }
    latest_gaps = list(
        db.scalars(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.context_id == context.id,
                SupplierEvidenceGap.assessment_version == context.current_assessment_version,
            )
        )
    )
    if not latest_gaps:
        return {"updated": 0, "assessment_version": context.current_assessment_version}
    resolved_gap_ids: set[uuid.UUID] = set()
    resolution_observations: dict[uuid.UUID, list[str]] = {}
    trigger_evidence_ids: set[str] = set()
    trigger_claim_ids: set[str] = set()
    trigger_verification_results: set[str] = set()
    trigger_observation_ids: set[str] = set()
    contradictory_gap_ids: set[uuid.UUID] = set()
    for due_task in due_tasks:
        shared_id = due_task.shared_execution_id
        if shared_id is None:
            continue
        shared = shared_tasks.get(shared_id)
        if shared is None:
            continue
        due_task.status = shared.status
        due_task.updated_at = _now()
        evidence = list(
            db.scalars(
                select(AutonomousResearchEvidence).where(
                    AutonomousResearchEvidence.owner_id == owner.id,
                    AutonomousResearchEvidence.task_id == shared.id,
                )
            )
        )
        due_task.result = {
            "execution_id": str(shared.id),
            "status": shared.status,
            "evidence_ids": [str(item.id) for item in evidence],
            "verification_states": [item.verification_status for item in evidence],
            "freshness_states": [item.freshness_status for item in evidence],
        }
        claims = list(
            db.scalars(
                select(AutonomousResearchClaim).where(
                    AutonomousResearchClaim.owner_id == owner.id,
                    AutonomousResearchClaim.task_id == shared.id,
                )
            )
        )
        contradictory_claim = any(
            claim.verification_status in {"CONTRADICTED", "CONFLICTING", "REJECTED"}
            for claim in claims
        )
        trigger_evidence_ids.update(str(item.id) for item in evidence)
        trigger_claim_ids.update(str(item.id) for item in claims)
        trigger_verification_results.update(str(item.verification_status) for item in evidence)
        accepted = [
            item
            for item in evidence
            if item.verification_status in {"VERIFIED", "SUPPORTED"}
            and item.freshness_status not in {"STALE", "EXPIRED"}
            and not contradictory_claim
        ]
        current_gap = next((gap for gap in latest_gaps if gap.id == due_task.gap_id), None)
        observations = (
            [_observation_for_evidence(db, owner, item, current_gap) for item in accepted]
            if current_gap is not None
            else []
        )
        if observations:
            resolution_observations[due_task.gap_id] = [str(item.id) for item in observations]
            trigger_observation_ids.update(str(item.id) for item in observations)
        if contradictory_claim:
            contradictory_gap_ids.add(due_task.gap_id)
        if accepted and shared.status == "COMPLETED":
            resolved_gap_ids.add(due_task.gap_id)
    risk_recomputation = _recompute_shared_risk(db, owner, context)
    next_version = context.current_assessment_version + 1
    for gap in latest_gaps:
        resolution_refs: list[str]
        resolution_at: datetime | None
        if gap.id in resolved_gap_ids:
            gap_status = "RESOLVED"
            candidate = next(
                (
                    task.result.get("evidence_ids", [])
                    for task in due_tasks
                    if task.gap_id == gap.id
                ),
                [],
            )
            resolution_refs = (
                [str(item) for item in candidate] if isinstance(candidate, list) else []
            )
            resolution_at = _now()
        else:
            gap_status = "CONTRADICTORY" if gap.id in contradictory_gap_ids else gap.status
            resolution_refs = [str(item) for item in (gap.resolution_evidence_refs or [])]
            resolution_at = gap.resolved_at
        db.add(
            SupplierEvidenceGap(
                owner_id=owner.id,
                context_id=context.id,
                supplier_id=gap.supplier_id,
                product_id=gap.product_id,
                assessment_version=next_version,
                dimension=gap.dimension,
                status=gap_status,
                severity=gap.severity,
                classification=gap.classification,
                reason=gap.reason,
                required_evidence=gap.required_evidence,
                evidence_refs=gap.evidence_refs,
                confidence=gap.confidence,
                freshness_state=gap.freshness_state,
                contradiction_state=(
                    "present" if gap.id in contradictory_gap_ids else gap.contradiction_state
                ),
                priority_score=gap.priority_score,
                priority_level=gap.priority_level,
                resolution_evidence_refs=resolution_refs,
                resolution_type=(
                    "evidence"
                    if gap.id in resolved_gap_ids
                    else "human_waiver" if gap.status == "WAIVED_BY_HUMAN" else None
                ),
                resolution_observation_ids=(
                    resolution_observations.get(gap.id, [])
                    if gap.id in resolved_gap_ids
                    else list(gap.resolution_observation_ids or [])
                ),
                resolved_by=(
                    owner.id
                    if gap.id in resolved_gap_ids or gap.status == "WAIVED_BY_HUMAN"
                    else gap.resolved_by
                ),
                created_at=_now(),
                updated_at=_now(),
                resolved_at=resolution_at,
            )
        )
    unresolved_required = sum(
        gap.classification == "REQUIRED" and gap.status not in {"RESOLVED", "WAIVED_BY_HUMAN"}
        for gap in latest_gaps
    )
    readiness = "REVIEW_REQUIRED" if unresolved_required else "SUFFICIENT"
    risk_lineage = {
        **risk_recomputation,
        "triggering_evidence_ids": sorted(trigger_evidence_ids),
        "triggering_claim_ids": sorted(trigger_claim_ids),
        "verification_results": sorted(trigger_verification_results),
        "observation_ids": sorted(trigger_observation_ids),
        "assessment_version": next_version,
    }
    assessment = SupplierDueDiligenceAssessment(
        owner_id=owner.id,
        context_id=context.id,
        version=next_version,
        readiness=readiness,
        summary={
            "open_gaps": sum(
                gap.status not in {"RESOLVED", "WAIVED_BY_HUMAN"} for gap in latest_gaps
            ),
            "required_open_gaps": unresolved_required,
            "reassessed_after_execution": str(mission_id),
            "risk_recomputation": risk_lineage,
        },
        created_at=_now(),
    )
    db.add(assessment)
    context.current_assessment_version = next_version
    context.status = readiness
    context.updated_at = _now()
    db.flush()
    risk_lineage["assessment_id"] = str(assessment.id)
    assessment.summary = {**assessment.summary, "risk_recomputation": risk_lineage}
    db.flush()
    return {"updated": len(due_tasks), "assessment_version": next_version}


def safe_report_value(value: Any) -> Any:
    """Recursively redact sensitive keys and connection-like values."""
    sensitive = {
        "authorization",
        "api_key",
        "apikey",
        "cookie",
        "credential",
        "credentials",
        "database_url",
        "dsn",
        "password",
        "path",
        "private",
        "raw_payload",
        "secret",
        "token",
        "url",
        "connection_string",
    }
    if isinstance(value, dict):
        return {
            str(key): safe_report_value(item)
            for key, item in value.items()
            if not any(part in str(key).casefold() for part in sensitive)
        }
    if isinstance(value, list):
        return [safe_report_value(item) for item in value]
    if isinstance(value, str):
        redacted = re.sub(
            r"(?:postgres(?:ql)?|mysql|sqlite)://\S+",
            "[redacted database reference]",
            value,
            flags=re.IGNORECASE,
        )
        return re.sub(
            r"(?:bearer\s+|api[_-]?key[=:]?)\S+",
            "[redacted credential]",
            redacted,
            flags=re.IGNORECASE,
        )
    return value


def render_report(value: dict[str, Any], format_name: str) -> dict[str, Any] | str:
    safe = safe_report_value(value)
    if format_name == "json":
        return safe
    if format_name == "markdown":
        return "# Supplier Due Diligence\\n\\n" + "\\n".join(
            f"- **{html.escape(str(key))}:** {html.escape(json.dumps(item, default=str))}"
            for key, item in safe.items()
        )
    if format_name == "html":
        return (
            "<article><h1>Supplier Due Diligence</h1>"
            + "".join(
                f"<p><strong>{html.escape(str(key))}</strong>: "
                f"{html.escape(json.dumps(item, default=str))}</p>"
                for key, item in safe.items()
            )
            + "</article>"
        )
    raise HTTPException(422, "Unsupported report format.")


def history(db: Session, owner: User, context: SupplierDueDiligenceContext) -> dict[str, Any]:
    assessments = list(
        db.scalars(
            select(SupplierDueDiligenceAssessment)
            .where(
                SupplierDueDiligenceAssessment.owner_id == owner.id,
                SupplierDueDiligenceAssessment.context_id == context.id,
            )
            .order_by(SupplierDueDiligenceAssessment.version)
        )
    )
    gaps = list(
        db.scalars(
            select(SupplierEvidenceGap)
            .where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.context_id == context.id,
            )
            .order_by(SupplierEvidenceGap.assessment_version, SupplierEvidenceGap.created_at)
        )
    )
    plans = list(
        db.scalars(
            select(SupplierResearchPlan)
            .where(
                SupplierResearchPlan.owner_id == owner.id,
                SupplierResearchPlan.context_id == context.id,
            )
            .order_by(SupplierResearchPlan.created_at)
        )
    )
    tasks = list(
        db.scalars(
            select(SupplierResearchTask)
            .join(SupplierResearchPlan, SupplierResearchPlan.id == SupplierResearchTask.plan_id)
            .where(
                SupplierResearchTask.owner_id == owner.id,
                SupplierResearchPlan.context_id == context.id,
            )
            .order_by(SupplierResearchTask.created_at)
        )
    )
    return {
        "context_id": str(context.id),
        "assessments": [
            {"version": row.version, "readiness": row.readiness, "summary": row.summary}
            for row in assessments
        ],
        "gap_transitions": [
            {
                "id": str(row.id),
                "assessment_version": row.assessment_version,
                "dimension": row.dimension,
                "status": row.status,
                "severity": row.severity,
                "classification": row.classification,
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
                "lineage": _gap_lineage(db, owner, row),
            }
            for row in gaps
        ],
        "research_plans": [serialize_plan(row) for row in plans],
        "research_tasks": [
            {
                "id": str(row.id),
                "plan_id": str(row.plan_id),
                "gap_id": str(row.gap_id),
                "status": row.status,
                "task_type": row.task_type,
                "shared_execution_id": (
                    str(row.shared_execution_id) if row.shared_execution_id else None
                ),
                "result": safe_report_value(row.result),
            }
            for row in tasks
        ],
        "readiness": context.status,
    }


def integrity_report(db: Session, owner: User) -> dict[str, int]:
    contexts = list(
        db.scalars(
            select(SupplierDueDiligenceContext).where(
                SupplierDueDiligenceContext.owner_id == owner.id
            )
        )
    )
    context_ids = {row.id for row in contexts}
    assessments = list(
        db.scalars(
            select(SupplierDueDiligenceAssessment).where(
                SupplierDueDiligenceAssessment.owner_id == owner.id
            )
        )
    )
    gaps = list(
        db.scalars(select(SupplierEvidenceGap).where(SupplierEvidenceGap.owner_id == owner.id))
    )
    plans = list(
        db.scalars(select(SupplierResearchPlan).where(SupplierResearchPlan.owner_id == owner.id))
    )
    tasks = list(
        db.scalars(select(SupplierResearchTask).where(SupplierResearchTask.owner_id == owner.id))
    )
    evidence = list(
        db.scalars(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner.id
            )
        )
    )
    autonomous_tasks = {
        row.id
        for row in db.scalars(
            select(AutonomousResearchTask).where(AutonomousResearchTask.owner_id == owner.id)
        )
    }
    missions = {
        row.id
        for row in db.scalars(
            select(AutonomousResearchMission).where(AutonomousResearchMission.owner_id == owner.id)
        )
    }
    plan_ids = {row.id for row in plans}
    evidence_ids = {str(row.id) for row in evidence}
    latest_assessment: dict[uuid.UUID, int] = {}
    for row in assessments:
        latest_assessment[row.context_id] = max(
            row.version, latest_assessment.get(row.context_id, 0)
        )
    context_keys = [row.idempotency_key for row in contexts]
    active_plans = [row for row in plans if row.status in {"READY", "RUNNING"}]
    active_tasks = [row for row in tasks if row.status in {"QUEUED", "RUNNING"}]
    plan_keys = [(row.context_id, row.assessment_version) for row in active_plans]
    task_keys = [(row.plan_id, row.gap_id) for row in active_tasks]
    calendar_keys = [
        f"SUPPLIER_DUE_DILIGENCE_REVIEW_DUE:{row.id}:{row.current_assessment_version}"
        for row in contexts
    ]
    return {
        "duplicate_contexts": len(context_keys) - len(set(context_keys)),
        "duplicate_active_plans": len(plan_keys) - len(set(plan_keys)),
        "duplicate_active_tasks": len(task_keys) - len(set(task_keys)),
        "orphan_gaps": sum(row.context_id not in context_ids for row in gaps),
        "orphan_gap_versions": sum(
            row.context_id not in context_ids
            or row.assessment_version > latest_assessment.get(row.context_id, 0)
            for row in gaps
        ),
        "orphan_tasks": sum(row.plan_id not in plan_ids for row in tasks),
        "broken_plan_task_lineage": sum(row.plan_id not in plan_ids for row in tasks),
        "broken_execution_lineage": sum(
            row.shared_execution_id is not None
            and row.shared_execution_id not in autonomous_tasks
            and row.shared_execution_id not in missions
            for row in tasks
        ),
        "broken_evidence_lineage": sum(
            bool(row.resolution_evidence_refs)
            and any(str(ref) not in evidence_ids for ref in row.resolution_evidence_refs)
            for row in gaps
        ),
        "cross_owner_references": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierEvidenceGap)
                .join(
                    CrossMarketplaceSupplier,
                    CrossMarketplaceSupplier.id == SupplierEvidenceGap.supplier_id,
                )
                .where(
                    SupplierEvidenceGap.owner_id == owner.id,
                    CrossMarketplaceSupplier.owner_id != owner.id,
                )
            )
            or 0
        ),
        "invalid_human_waivers": int(
            db.scalar(
                select(func.count())
                .select_from(SupplierEvidenceGap)
                .outerjoin(
                    AuditEvent,
                    (AuditEvent.entity_id == SupplierEvidenceGap.id)
                    & (
                        AuditEvent.action.in_(
                            ["supplier.due_diligence.waive", "supplier.due_diligence.waive_gap"]
                        )
                    )
                    & (AuditEvent.actor_id == owner.id),
                )
                .where(
                    SupplierEvidenceGap.owner_id == owner.id,
                    SupplierEvidenceGap.status == "WAIVED_BY_HUMAN",
                    AuditEvent.id.is_(None),
                )
            )
            or 0
        ),
        "resolved_gap_without_evidence_or_waiver": sum(
            row.status == "RESOLVED" and not row.resolution_evidence_refs for row in gaps
        ),
        "current_assessment_pointer_errors": sum(
            row.current_assessment_version != latest_assessment.get(row.id, 0) for row in contexts
        ),
        "duplicate_calendar_events": len(calendar_keys) - len(set(calendar_keys)),
    }


def sourcing_guard(db: Session, owner: User, context_id: uuid.UUID) -> dict[str, object]:
    """Evaluate internal sourcing readiness from the current due-diligence assessment."""
    context = _owned(
        db, SupplierDueDiligenceContext, owner, context_id, "Due-diligence context not found."
    )
    gaps = list(
        db.scalars(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.context_id == context.id,
                SupplierEvidenceGap.assessment_version == context.current_assessment_version,
            )
        )
    )
    open_gaps = [gap for gap in gaps if gap.status not in {"RESOLVED", "WAIVED_BY_HUMAN"}]
    required_open = [gap for gap in open_gaps if gap.classification == "REQUIRED"]
    critical_open = [gap for gap in open_gaps if gap.severity == "CRITICAL"]
    contradiction_open = [gap for gap in open_gaps if gap.contradiction_state not in {"none", ""}]
    verification_blockers = [
        gap
        for gap in open_gaps
        if gap.status in {"INSUFFICIENT", "STALE", "CONTRADICTORY", "BLOCKED"}
    ]
    if critical_open:
        outcome = "BLOCKED"
    elif required_open or contradiction_open or verification_blockers:
        outcome = "REVIEW_REQUIRED"
    else:
        outcome = "ALLOWED"
    return {
        "outcome": outcome,
        "context_id": str(context.id),
        "readiness": context.status,
        "required_unresolved": len(required_open),
        "critical_blockers": len(critical_open),
        "verification_blockers": len(verification_blockers),
        "material_contradictions": len(contradiction_open),
        "human_waivers": sum(gap.status == "WAIVED_BY_HUMAN" for gap in gaps),
        "external_dispatch": False,
    }


def operations(db: Session, owner: User) -> dict[str, int]:
    rows = list(
        db.execute(
            select(SupplierDueDiligenceContext.status, func.count())
            .where(SupplierDueDiligenceContext.owner_id == owner.id)
            .group_by(SupplierDueDiligenceContext.status)
        )
    )
    result = {
        "contexts_open": 0,
        "contexts_blocked": 0,
        "review_required_contexts": 0,
        "research_running": 0,
        "research_failed": 0,
        "critical_gaps": 0,
        "high_gaps": 0,
        "overdue_research": 0,
        "recovery_needed_tasks": 0,
    }
    for status, count in rows:
        if status in {"OPEN", "RESEARCH_REQUIRED", "REVIEW_REQUIRED"}:
            result["contexts_open"] += count
        if status == "BLOCKED":
            result["contexts_blocked"] += count
    result["critical_gaps"] = (
        db.scalar(
            select(func.count())
            .select_from(SupplierEvidenceGap)
            .where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.severity == "CRITICAL",
                SupplierEvidenceGap.status.not_in(["RESOLVED", "WAIVED_BY_HUMAN"]),
            )
        )
        or 0
    )
    result["high_gaps"] = (
        db.scalar(
            select(func.count())
            .select_from(SupplierEvidenceGap)
            .where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.severity == "HIGH",
                SupplierEvidenceGap.status.not_in(["RESOLVED", "WAIVED_BY_HUMAN"]),
            )
        )
        or 0
    )
    result["required_open_gaps"] = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierEvidenceGap)
            .where(
                SupplierEvidenceGap.owner_id == owner.id,
                SupplierEvidenceGap.classification == "REQUIRED",
                SupplierEvidenceGap.status.not_in(["RESOLVED", "WAIVED_BY_HUMAN"]),
            )
        )
        or 0
    )
    task_rows = list(
        db.execute(
            select(SupplierResearchTask.status, func.count())
            .where(SupplierResearchTask.owner_id == owner.id)
            .group_by(SupplierResearchTask.status)
        )
    )
    result["research_running"] = sum(
        count for status, count in task_rows if status in {"RUNNING", "QUEUED"}
    )
    result["research_failed"] = sum(
        count for status, count in task_rows if status in {"FAILED", "CANCELLED", "STALE"}
    )
    result["recovery_needed_tasks"] = result["research_failed"]
    return result
