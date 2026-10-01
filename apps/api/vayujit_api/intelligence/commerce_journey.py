"""Projection-only guided commerce journey over existing intelligence records."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import (
    BusinessAgentGoal,
    BusinessAgentPlan,
    BusinessAgentRun,
)
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.economic_integration_service import decision_brief_for_opportunity
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.product_opportunity_scoring_models import ProductOpportunityDecision
from vayujit_api.intelligence.scenario_models import (
    SourcingScenario,
    SourcingScenarioContext,
    SourcingScenarioDecision,
    SourcingScenarioVersion,
)
from vayujit_api.intelligence.shortlisting_models import SupplierShortlistContext
from vayujit_api.intelligence.supplier_models import SupplierSearch

STAGES = ("GOAL", "RESEARCH", "COMPARE", "SOURCE", "VERIFY", "ECONOMICS", "DECIDE", "LAUNCH")
STATUSES = ("NOT_STARTED", "READY", "IN_PROGRESS", "COMPLETED", "BLOCKED", "NEEDS_REVIEW")


def _count(db: Session, model: type[Any], owner_id: uuid.UUID) -> int:
    return int(
        db.scalar(select(func.count()).select_from(model).where(model.owner_id == owner_id)) or 0
    )


def _meaningful_opportunity(row: ProductOpportunity) -> bool:
    profile = row.intelligence_profile or {}
    if str(row.name).casefold() in {
        "business agent product opportunity",
        "candidate product",
        "product opportunity 1",
        "test product",
        "example product",
    }:
        return False
    return bool(profile.get("normalized_product_concept") or (row.category and row.product_concept))


def _latest_goal(
    db: Session, owner_id: uuid.UUID, goal_id: uuid.UUID | None = None
) -> BusinessAgentGoal | None:
    statement = select(BusinessAgentGoal).where(BusinessAgentGoal.owner_id == owner_id)
    if goal_id is not None:
        statement = statement.where(BusinessAgentGoal.id == goal_id)
    return db.scalar(
        statement.order_by(BusinessAgentGoal.updated_at.desc(), BusinessAgentGoal.created_at.desc())
    )


def _action(
    code: str, title: str, detail: str, route: str, entity_id: uuid.UUID | None = None
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "detail": detail,
        "route": route,
        "entity_id": entity_id,
        "human_controlled": True,
    }


def project_journey(
    db: Session, owner: User, goal_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    goal = _latest_goal(db, owner.id, goal_id)
    if goal is None:
        return None

    plans = int(
        db.scalar(
            select(func.count())
            .select_from(BusinessAgentPlan)
            .where(
                BusinessAgentPlan.owner_id == owner.id,
                BusinessAgentPlan.goal_id == goal.id,
            )
        )
        or 0
    )
    runs = int(
        db.scalar(
            select(func.count())
            .select_from(BusinessAgentRun)
            .where(
                BusinessAgentRun.owner_id == owner.id,
                BusinessAgentRun.goal_id == goal.id,
            )
        )
        or 0
    )
    goal_run_ids = list(
        db.scalars(
            select(BusinessAgentRun.id)
            .where(BusinessAgentRun.owner_id == owner.id, BusinessAgentRun.goal_id == goal.id)
            .order_by(BusinessAgentRun.created_at.desc())
        )
    )
    opportunity_rows = list(
        db.scalars(
            select(ProductOpportunity).where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.lifecycle_status != "archived",
            )
        )
    )
    meaningful_owner_opportunities = [
        row for row in opportunity_rows if _meaningful_opportunity(row)
    ]
    prefixes = tuple(f"business-agent:{run_id}:candidate:" for run_id in goal_run_ids)
    meaningful_opportunities = [
        row
        for row in meaningful_owner_opportunities
        if any(row.idempotency_key.startswith(prefix) for prefix in prefixes)
        or (
            (goal.structured_goal or {}).get("product_opportunity_id")
            and str(row.id) == str((goal.structured_goal or {}).get("product_opportunity_id"))
        )
    ]
    meaningful_ids = {row.id for row in meaningful_opportunities}
    opportunities = len(meaningful_opportunities)
    empty_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    scoped_ids = meaningful_ids or {empty_id}
    scoped_product_ids = {
        row.product_id for row in meaningful_opportunities if row.product_id is not None
    }
    goal_product_id = (goal.structured_goal or {}).get("product_id")
    try:
        if goal_product_id:
            scoped_product_ids.add(uuid.UUID(str(goal_product_id)))
    except (TypeError, ValueError):
        pass
    if not scoped_product_ids:
        scoped_product_ids = {empty_id}
    product_selection_query = (
        select(func.count())
        .select_from(ProductOpportunityDecision)
        .where(
            ProductOpportunityDecision.owner_id == owner.id,
            ProductOpportunityDecision.action == "shortlist",
            ProductOpportunityDecision.opportunity_id.in_(scoped_ids),
        )
    )
    product_selections = int(db.scalar(product_selection_query) or 0)
    latest_product_selection = db.scalar(
        select(ProductOpportunityDecision)
        .where(
            ProductOpportunityDecision.owner_id == owner.id,
            ProductOpportunityDecision.action == "shortlist",
            ProductOpportunityDecision.opportunity_id.in_(scoped_ids),
        )
        .order_by(ProductOpportunityDecision.created_at.desc())
    )
    downstream_ids = (
        {latest_product_selection.opportunity_id}
        if latest_product_selection is not None
        else {empty_id}
    )
    downstream_product_ids = (
        {
            selected.product_id
            for selected in opportunity_rows
            if latest_product_selection is not None
            and selected.id == latest_product_selection.opportunity_id
            and selected.product_id is not None
        }
        if latest_product_selection is not None
        else {empty_id}
    )
    # Product-linked downstream records may be created from the authoritative
    # goal product even when the selected opportunity itself is product-less.
    if latest_product_selection is not None and not downstream_product_ids:
        try:
            if goal_product_id:
                downstream_product_ids = {uuid.UUID(str(goal_product_id))}
        except (TypeError, ValueError):
            pass
    if not downstream_product_ids:
        downstream_product_ids = {empty_id}
    suppliers = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierSearch)
            .where(
                SupplierSearch.owner_id == owner.id,
                or_(
                    SupplierSearch.opportunity_id.in_(downstream_ids),
                    SupplierSearch.product_id.in_(downstream_product_ids),
                ),
                SupplierSearch.status == "completed",
            )
        )
        or 0
    )
    shortlists = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierShortlistContext)
            .where(
                SupplierShortlistContext.owner_id == owner.id,
                or_(
                    SupplierShortlistContext.opportunity_id.in_(downstream_ids),
                    SupplierShortlistContext.product_id.in_(downstream_product_ids),
                ),
            )
        )
        or 0
    )
    # A product-linked shortlist is the durable handoff proving supplier options
    # exist even when the discovery fixture does not persist a SupplierSearch row.
    suppliers = max(suppliers, shortlists)
    due_diligence = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierDueDiligenceContext)
            .where(
                SupplierDueDiligenceContext.owner_id == owner.id,
                or_(
                    SupplierDueDiligenceContext.opportunity_id.in_(downstream_ids),
                    SupplierDueDiligenceContext.product_id.in_(downstream_product_ids),
                ),
            )
        )
        or 0
    )
    due_diligence_ready = int(
        db.scalar(
            select(func.count())
            .select_from(SupplierDueDiligenceContext)
            .where(
                SupplierDueDiligenceContext.owner_id == owner.id,
                SupplierDueDiligenceContext.status.in_({"SUFFICIENT", "CLOSED"}),
                or_(
                    SupplierDueDiligenceContext.opportunity_id.in_(downstream_ids),
                    SupplierDueDiligenceContext.product_id.in_(downstream_product_ids),
                ),
            )
        )
        or 0
    )
    scenarios = int(
        db.scalar(
            select(func.count())
            .select_from(SourcingScenarioContext)
            .where(
                SourcingScenarioContext.owner_id == owner.id,
                or_(
                    SourcingScenarioContext.opportunity_id.in_(downstream_ids),
                    SourcingScenarioContext.product_id.in_(downstream_product_ids),
                ),
            )
        )
        or 0
    ) + int(
        db.scalar(
            select(func.count())
            .select_from(SourcingScenario)
            .join(
                SourcingScenarioContext,
                SourcingScenarioContext.id == SourcingScenario.context_id,
            )
            .where(
                SourcingScenario.owner_id == owner.id,
                or_(
                    SourcingScenarioContext.opportunity_id.in_(downstream_ids),
                    SourcingScenarioContext.product_id.in_(downstream_product_ids),
                ),
            )
        )
        or 0
    )
    decisions = int(
        db.scalar(
            select(func.count())
            .select_from(SourcingScenarioDecision)
            .join(
                SourcingScenarioVersion,
                SourcingScenarioVersion.id == SourcingScenarioDecision.version_id,
            )
            .join(SourcingScenario, SourcingScenario.id == SourcingScenarioVersion.scenario_id)
            .join(
                SourcingScenarioContext,
                SourcingScenarioContext.id == SourcingScenario.context_id,
            )
            .where(
                SourcingScenarioDecision.owner_id == owner.id,
                or_(
                    SourcingScenarioContext.opportunity_id.in_(downstream_ids),
                    SourcingScenarioContext.product_id.in_(downstream_product_ids),
                ),
            )
        )
        or 0
    )
    economics_brief: dict[str, Any] | None = None
    if latest_product_selection is not None:
        try:
            economics_brief = decision_brief_for_opportunity(
                db, owner, latest_product_selection.opportunity_id
            )
        except Exception:
            economics_brief = None
    raw_commerce_decisions = (goal.provenance or {}).get("commerce_decisions")
    commerce_decisions: list[dict[str, Any]] = (
        [row for row in raw_commerce_decisions if isinstance(row, dict)]
        if isinstance(raw_commerce_decisions, list)
        else []
    )
    latest_commerce_decision = commerce_decisions[-1] if commerce_decisions else None
    explicit_proceed = bool(
        latest_commerce_decision
        and latest_commerce_decision.get("action") == "PROCEED_TO_LAUNCH_PREPARATION"
    )
    run = db.scalar(
        select(BusinessAgentRun)
        .where(BusinessAgentRun.owner_id == owner.id, BusinessAgentRun.goal_id == goal.id)
        .order_by(BusinessAgentRun.created_at.desc())
    )
    run_active = bool(run and run.status in {"QUEUED", "RUNNING"})
    run_needs_review = bool(
        run and run.status in {"WAITING_APPROVAL", "PARTIAL", "BUDGET_EXHAUSTED"}
    )
    goal_done = goal.status not in {"DRAFT", "FAILED", "CANCELLED"}
    stages: list[dict[str, Any]] = [
        {
            "key": "GOAL",
            "label": "Goal",
            "status": "COMPLETED" if goal_done else "IN_PROGRESS",
            "route": "/intelligence/business-agent",
            "entity_id": goal.id,
        },
        {
            "key": "RESEARCH",
            "label": "Research",
            "status": (
                "IN_PROGRESS"
                if run_active
                else (
                    "NEEDS_REVIEW"
                    if run_needs_review
                    else (
                        "COMPLETED"
                        if plans and runs and opportunities > 0
                        else ("NEEDS_REVIEW" if plans and runs else "READY")
                    )
                )
            ),
            "route": "/intelligence/business-agent",
            "entity_id": goal.id,
        },
        {
            "key": "COMPARE",
            "label": "Compare",
            "status": (
                "COMPLETED"
                if product_selections
                else (
                    "IN_PROGRESS"
                    if opportunities > 1
                    else ("BLOCKED" if opportunities == 0 else "READY")
                )
            ),
            "route": "/intelligence/product-opportunities",
            "entity_id": None,
        },
        {
            "key": "SOURCE",
            "label": "Source",
            "status": (
                "BLOCKED" if not product_selections else ("COMPLETED" if suppliers else "READY")
            ),
            "route": "/intelligence/sourcing",
            "entity_id": None,
        },
        {
            "key": "VERIFY",
            "label": "Verify",
            "status": (
                "COMPLETED" if due_diligence_ready else ("READY" if shortlists else "BLOCKED")
            ),
            "route": "/intelligence/due-diligence",
            "entity_id": None,
        },
        {
            "key": "ECONOMICS",
            "label": "Economics",
            "status": (
                "COMPLETED"
                if (
                    economics_brief
                    and economics_brief.get("decision_readiness") == "READY_FOR_HUMAN_DECISION"
                )
                else (
                    "BLOCKED"
                    if not product_selections or not due_diligence_ready
                    else ("IN_PROGRESS" if economics_brief or scenarios else "READY")
                )
            ),
            "route": "/intelligence/sourcing-economics",
            "entity_id": (
                latest_product_selection.opportunity_id if latest_product_selection else None
            ),
        },
        {
            "key": "DECIDE",
            "label": "Decide",
            "status": (
                "COMPLETED"
                if commerce_decisions or decisions
                else (
                    "READY"
                    if economics_brief
                    and economics_brief.get("decision_readiness") == "READY_FOR_HUMAN_DECISION"
                    else ("NEEDS_REVIEW" if economics_brief else "BLOCKED")
                )
            ),
            "route": "/intelligence/sourcing-economics",
            "entity_id": (
                latest_product_selection.opportunity_id if latest_product_selection else None
            ),
        },
        {
            "key": "LAUNCH",
            "label": "Launch",
            "status": "READY" if explicit_proceed else "BLOCKED",
            "route": "/marketplaces/listings",
            "entity_id": None,
        },
    ]
    stage_reasons = {
        "GOAL": (
            "The business outcome is confirmed." if goal_done else "Confirm a business outcome."
        ),
        "RESEARCH": (
            "Review the research run and its evidence."
            if run_needs_review
            else (
                "Meaningful product evidence is available."
                if opportunities
                else "Create meaningful research evidence."
            )
        ),
        "COMPARE": (
            "Explicitly select one product before sourcing."
            if not product_selections
            else "A human product selection is recorded."
        ),
        "SOURCE": (
            "Select a researched product before finding suppliers."
            if not product_selections
            else (
                "Supplier candidates are available for review."
                if suppliers
                else "Find supplier options for the selected product."
            )
        ),
        "VERIFY": (
            "Create a shortlist before verification."
            if not shortlists
            else (
                "Resolve supplier evidence gaps."
                if not due_diligence_ready
                else "Supplier verification evidence is sufficient."
            )
        ),
        "ECONOMICS": (
            "Complete product selection and supplier verification first."
            if not product_selections or not due_diligence_ready
            else "Review known costs and explicit assumptions."
        ),
        "DECIDE": (
            "Review the evidence-backed brief and make a human decision."
            if economics_brief
            else "Economics must be decision-ready first."
        ),
        "LAUNCH": (
            "A human proceed decision is required."
            if not explicit_proceed
            else "Launch preparation remains human-controlled."
        ),
    }
    completed = sum(stage["status"] == "COMPLETED" for stage in stages)
    if not plans:
        next_action = _action(
            "REVIEW_PLAN",
            "Review the research plan",
            "Turn this goal into a reviewable plan before research runs.",
            "/intelligence/business-agent",
            goal.id,
        )
    elif run_active:
        next_action = _action(
            "CONTINUE_RESEARCH",
            "Continue research",
            "Review the active Business Agent run and its evidence.",
            "/intelligence/business-agent",
            goal.id,
        )
    elif run_needs_review:
        next_action = _action(
            "REVIEW_RESEARCH",
            "Review research results",
            (
                "Research produced evidence with gaps or an approval boundary. "
                "Review it before comparing products."
            ),
            "/intelligence/business-agent",
            goal.id,
        )
    elif opportunities == 0:
        next_action = _action(
            "RESEARCH_OPPORTUNITIES",
            "Research product opportunities",
            "Build evidence before comparing alternatives.",
            "/intelligence/product-opportunities",
        )
    elif not product_selections:
        next_action = _action(
            "COMPARE_OPPORTUNITIES",
            "Compare product opportunities",
            "Review the evidence and explicitly select a product before sourcing.",
            "/intelligence/product-opportunities",
        )
    elif not suppliers:
        next_action = _action(
            "FIND_SUPPLIERS",
            "Find supplier options",
            "Discover supplier candidates for the selected product.",
            "/intelligence/sourcing",
        )
    elif not shortlists:
        next_action = _action(
            "COMPARE_SUPPLIERS",
            "Compare suppliers",
            "Create a human-reviewed shortlist.",
            "/intelligence/supplier-shortlisting",
        )
    elif not due_diligence_ready:
        next_action = _action(
            "VERIFY_SUPPLIERS",
            "Verify suppliers",
            "Resolve supplier evidence gaps before economics.",
            "/intelligence/due-diligence",
        )
    elif not scenarios and economics_brief is None:
        next_action = _action(
            "CALCULATE_COSTS",
            "Calculate sourcing economics",
            "Review landed-cost scenarios and assumptions.",
            "/intelligence/sourcing-economics",
            latest_product_selection.opportunity_id if latest_product_selection else None,
        )
    elif not (commerce_decisions or decisions):
        next_action = _action(
            "REVIEW_DECISION",
            "Review the decision brief",
            "Review evidence, assumptions, and make the decision explicitly; "
            "no launch is automatic.",
            "/intelligence/sourcing-economics",
            latest_product_selection.opportunity_id if latest_product_selection else None,
        )
    else:
        next_action = _action(
            "PREPARE_LAUNCH",
            "Prepare launch",
            "Open listings and complete the launch steps under human control.",
            "/marketplaces/listings",
        )

    stage_blockers = {
        "GOAL": [] if goal_done else ["goal_confirmation"],
        "RESEARCH": (
            []
            if plans and runs and opportunities
            else ["business_agent_plan", "research_run", "meaningful_product_evidence"]
        ),
        "COMPARE": (
            []
            if product_selections
            else (
                ["meaningful_product_evidence"]
                if opportunities
                else ["meaningful_product_evidence"]
            )
        ),
        "SOURCE": (
            []
            if product_selections and suppliers
            else (["human_product_selection"] if not product_selections else ["supplier_discovery"])
        ),
        "VERIFY": (
            []
            if due_diligence_ready
            else (["supplier_shortlist"] if not shortlists else ["supplier_verification"])
        ),
        "ECONOMICS": (
            []
            if product_selections and due_diligence_ready and (scenarios or economics_brief)
            else ["product_selection", "supplier_verification"]
        ),
        "DECIDE": (
            []
            if economics_brief
            and economics_brief.get("decision_readiness") == "READY_FOR_HUMAN_DECISION"
            else ["decision_ready_economics"]
        ),
        "LAUNCH": [] if explicit_proceed else ["human_proceed_decision"],
    }
    stage_evidence = {
        "GOAL": {"confirmed": goal_done},
        "RESEARCH": {"plans": plans, "runs": runs, "opportunities": opportunities},
        "COMPARE": {"human_product_selections": product_selections},
        "SOURCE": {"supplier_candidates": suppliers, "shortlist_contexts": shortlists},
        "VERIFY": {"contexts": due_diligence, "ready_contexts": due_diligence_ready},
        "ECONOMICS": {"scenarios": scenarios, "decision_brief": economics_brief is not None},
        "DECIDE": {"decisions": len(commerce_decisions) + decisions},
        "LAUNCH": {"proceed_decision": explicit_proceed},
    }
    for stage in stages:
        stage.setdefault("reason", stage_reasons[stage["key"]])
        stage["blocking_prerequisites"] = stage_blockers[stage["key"]]
        stage["completion_evidence"] = stage_evidence[stage["key"]]
        stage["next_action"] = next_action["code"]

    context = dict(goal.structured_goal or {})
    raw_commerce_context = context.get("commerce_context")
    commerce_context = dict(raw_commerce_context) if isinstance(raw_commerce_context, dict) else {}
    selected_opportunity = (
        next(
            (row for row in opportunity_rows if row.id == latest_product_selection.opportunity_id),
            None,
        )
        if latest_product_selection
        else None
    )
    if selected_opportunity is not None:
        commerce_context.update(
            {
                "selected_product_opportunity_id": str(selected_opportunity.id),
                "product_opportunity_id": str(selected_opportunity.id),
                "product_id": (
                    str(selected_opportunity.product_id)
                    if selected_opportunity.product_id
                    else None
                ),
                "product_name": selected_opportunity.name,
                "category": selected_opportunity.category or None,
                "marketplace": selected_opportunity.target_marketplace
                or commerce_context.get("marketplace"),
            }
        )
    data_mode = str((goal.provenance or {}).get("mode") or "UNKNOWN").upper()
    trust_mode = (
        "LOCAL_FIXTURE"
        if data_mode in {"LOCAL_DETERMINISTIC", "LOCAL_FIXTURE"}
        else ("LIVE_READ_ONLY" if data_mode == "LIVE_READ_ONLY" else "UNKNOWN")
    )
    confirmed = bool((goal.provenance or {}).get("commerce_context_confirmed"))
    return {
        "id": goal.id,
        "goal_id": goal.id,
        "status": "COMPLETED" if explicit_proceed else "IN_PROGRESS",
        "stages": stages,
        "completed_stage_count": completed,
        "total_stage_count": len(stages),
        "next_action": next_action,
        "counts": {
            "plans": plans,
            "runs": runs,
            "opportunities": opportunities,
            "suppliers": suppliers,
            "shortlists": shortlists,
            "due_diligence": due_diligence,
            "verified_due_diligence": due_diligence_ready,
            "scenarios": scenarios,
            "decisions": decisions,
            "selected_opportunities": product_selections,
        },
        "context": {"confirmed": confirmed, "values": commerce_context},
        "trust": {
            "mode": trust_mode,
            "label": (
                "Local demo data — not live market evidence"
                if trust_mode == "LOCAL_FIXTURE"
                else trust_mode
            ),
        },
        "context_confirmation": {
            "required": not confirmed,
            "source": "USER_CONFIRMED" if confirmed else "SYSTEM_DERIVED",
        },
        "remaining_requirements": [
            stage["label"]
            for stage in stages
            if stage["status"] in {"READY", "BLOCKED", "NEEDS_REVIEW"}
        ],
        "human_controlled": True,
    }


def next_action_for(db: Session, owner: User, goal_id: uuid.UUID | None = None) -> dict[str, Any]:
    journey = project_journey(db, owner, goal_id)
    if journey is None:
        return {
            "journey_id": None,
            "next_action": _action(
                "CREATE_GOAL",
                "Start with a business goal",
                "Describe the outcome you want to achieve.",
                "/intelligence/business-agent",
            ),
            "human_controlled": True,
        }
    return {
        "journey_id": journey["id"],
        "next_action": journey["next_action"],
        "human_controlled": True,
    }
