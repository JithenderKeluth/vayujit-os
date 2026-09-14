"""Read-only scenario projections for Operations, Calendar, and System Doctor."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.scenario_models import (
    InternalSourcingHandoff,
    ScenarioSupplierAllocation,
    SourcingScenario,
    SourcingScenarioContext,
    SourcingScenarioDecision,
    SourcingScenarioRecommendation,
    SourcingScenarioVersion,
)
from vayujit_api.intelligence.shortlisting_models import SupplierShortlistVersion


def integrity(db: Session, owner: User) -> dict[str, int]:
    contexts = list(
        db.scalars(
            select(SourcingScenarioContext).where(SourcingScenarioContext.owner_id == owner.id)
        )
    )
    scenarios = list(
        db.scalars(select(SourcingScenario).where(SourcingScenario.owner_id == owner.id))
    )
    versions = list(
        db.scalars(
            select(SourcingScenarioVersion).where(SourcingScenarioVersion.owner_id == owner.id)
        )
    )
    allocations = list(
        db.scalars(
            select(ScenarioSupplierAllocation).where(
                ScenarioSupplierAllocation.owner_id == owner.id
            )
        )
    )
    recommendations = list(
        db.scalars(
            select(SourcingScenarioRecommendation).where(
                SourcingScenarioRecommendation.owner_id == owner.id
            )
        )
    )
    decisions = list(
        db.scalars(
            select(SourcingScenarioDecision).where(SourcingScenarioDecision.owner_id == owner.id)
        )
    )
    handoffs = list(
        db.scalars(
            select(InternalSourcingHandoff).where(InternalSourcingHandoff.owner_id == owner.id)
        )
    )
    context_map = {row.id: row for row in contexts}
    scenario_map = {row.id: row for row in scenarios}
    version_map = {row.id: row for row in versions}
    current_pairs = {(row.scenario_id, row.version) for row in versions}
    supplier_ids = {row.supplier_id for row in allocations}
    due_ids = {row.due_diligence_id for row in allocations}
    shortlist_ids = {row.shortlist_version_id for row in contexts}
    suppliers = {
        row.id: row
        for row in db.scalars(
            select(CrossMarketplaceSupplier).where(CrossMarketplaceSupplier.id.in_(supplier_ids))
        )
    }
    diligence = {
        row.id: row
        for row in db.scalars(
            select(SupplierDueDiligenceContext).where(SupplierDueDiligenceContext.id.in_(due_ids))
        )
    }
    shortlists = {
        row.id: row
        for row in db.scalars(
            select(SupplierShortlistVersion).where(SupplierShortlistVersion.id.in_(shortlist_ids))
        )
    }

    def duplicate(values: Any) -> int:
        return sum(count - 1 for count in Counter(values).values() if count > 1)

    quantities: dict[Any, int] = {}
    for allocation in allocations:
        quantities[allocation.version_id] = (
            quantities.get(allocation.version_id, 0) + allocation.quantity
        )
    invalid = 0
    for version in versions:
        scenario = scenario_map.get(version.scenario_id)
        context = context_map.get(scenario.context_id) if scenario else None
        if context and quantities.get(version.id, 0) != context.settings["target_quantity"]:
            invalid += 1
    return {
        "duplicate_contexts": duplicate(row.idempotency_key for row in contexts),
        "duplicate_current_scenario_versions": duplicate(
            (row.scenario_id, row.version) for row in versions
        ),
        "broken_current_pointers": sum(
            (row.id, row.current_version) not in current_pairs for row in scenarios
        ),
        "duplicate_active_recommendations": duplicate(
            (row.context_id, row.version) for row in recommendations
        ),
        "invalid_allocations": invalid,
        "orphan_scenarios": sum(row.context_id not in context_map for row in scenarios),
        "orphan_versions": sum(row.scenario_id not in scenario_map for row in versions),
        "orphan_allocations": sum(row.version_id not in version_map for row in allocations),
        "broken_shortlist_lineage": sum(
            row.shortlist_version_id not in shortlists for row in contexts
        ),
        "broken_due_diligence_lineage": sum(
            row.due_diligence_id not in diligence
            or diligence[row.due_diligence_id].supplier_id != row.supplier_id
            for row in allocations
        ),
        "broken_supplier_lineage": sum(row.supplier_id not in suppliers for row in allocations),
        "broken_cost_lineage": sum(
            row.landed_cost_version != "sourcing-landed-cost-exact-v1" or "cost" not in row.result
            for row in versions
        ),
        "broken_recommendation_lineage": sum(
            row.scenario_version_id is not None and row.scenario_version_id not in version_map
            for row in recommendations
        ),
        "cross_owner_references": (
            sum(row.owner_id != owner.id for row in suppliers.values())
            + sum(row.owner_id != owner.id for row in diligence.values())
            + sum(row.owner_id != owner.id for row in shortlists.values())
        ),
        "approved_without_human_decision": sum(
            scenario.status == "APPROVED_FOR_INTERNAL_SOURCING"
            and not any(
                decision.action == "approve"
                and version_map.get(decision.version_id)
                and version_map[decision.version_id].scenario_id == scenario.id
                for decision in decisions
            )
            for scenario in scenarios
        ),
        "duplicate_sourcing_handoffs": duplicate(row.version_id for row in handoffs),
        "duplicate_calendar_events": duplicate(
            f"scenario:{row.id}:{row.current_version}:review"
            for row in scenarios
            if row.status == "REVIEW_REQUIRED"
        ),
    }


def overview(db: Session, owner: User) -> dict[str, Any]:
    scenarios = list(
        db.scalars(select(SourcingScenario).where(SourcingScenario.owner_id == owner.id))
    )
    return {
        "scenario_count": len(scenarios),
        "blocked": sum(row.status == "BLOCKED" for row in scenarios),
        "review_required": sum(row.status == "REVIEW_REQUIRED" for row in scenarios),
        "approved": sum(row.status == "APPROVED_FOR_INTERNAL_SOURCING" for row in scenarios),
        "external_dispatch": False,
        "integrity": integrity(db, owner),
    }


def product_channel(db: Session, owner: User, product_id: uuid.UUID) -> dict[str, Any]:
    """Project owner-scoped scenario status into the existing sourcing channel."""
    contexts = list(
        db.scalars(
            select(SourcingScenarioContext).where(
                SourcingScenarioContext.owner_id == owner.id,
                SourcingScenarioContext.product_id == product_id,
            )
        )
    )
    context_ids = [row.id for row in contexts]
    scenarios = list(
        db.scalars(
            select(SourcingScenario).where(
                SourcingScenario.owner_id == owner.id,
                SourcingScenario.context_id.in_(context_ids),
            )
        )
    )
    return {
        "status": "available" if scenarios else "not_started",
        "context_count": len(contexts),
        "scenario_count": len(scenarios),
        "review_required": sum(row.status == "REVIEW_REQUIRED" for row in scenarios),
        "blocked": sum(row.status == "BLOCKED" for row in scenarios),
        "approved": sum(row.status == "APPROVED_FOR_INTERNAL_SOURCING" for row in scenarios),
        "scenarios": [
            {
                "id": str(row.id),
                "context_id": str(row.context_id),
                "status": row.status,
                "current_version": row.current_version,
            }
            for row in scenarios
        ],
        "external_dispatch": False,
    }


def calendar(db: Session, owner: User) -> list[dict[str, Any]]:
    return [
        {
            "event_id": f"scenario:{row.id}:{row.current_version}:review",
            "kind": "SOURCING_SCENARIO_REVIEW_DUE",
            "title": f"Review sourcing scenario: {row.name}",
            "status": "actionable",
            "source_ref": str(row.id),
            "context_id": str(row.context_id),
            "owner_id": str(owner.id),
            "due_at": row.updated_at.isoformat(),
            "external_action": False,
        }
        for row in db.scalars(
            select(SourcingScenario).where(
                SourcingScenario.owner_id == owner.id,
                SourcingScenario.status.in_(["REVIEW_REQUIRED", "BLOCKED"]),
            )
        )
    ]


def doctor(db: Session, owner: User) -> dict[str, Any]:
    counters = integrity(db, owner)
    return {
        "status": "PASS" if not any(counters.values()) else "INTEGRITY_FAILURE",
        "integrity": counters,
        "mode": "LOCAL_DECISION_SUPPORT",
        "landed_cost": "SHARED_EXACT_MODE",
        "fx": "EXPLICIT_DATED_ASSUMPTIONS_ONLY",
        "production_certified": False,
    }
