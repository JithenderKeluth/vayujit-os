"""Research handoff to the existing 8C planner; no new execution runtime."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.scenario_models import SourcingScenarioContext
from vayujit_api.intelligence.scenario_schemas import ScenarioCreate, VersionCommand
from vayujit_api.intelligence.scenario_service import (
    current,
    digest,
    lineage,
    lock_owner,
    owned,
    record,
    replay,
)


def request_research(
    db: Session,
    owner: User,
    scenario_id: uuid.UUID,
    data: VersionCommand,
) -> dict[str, Any]:
    """Persist intent before asking the existing 8C planner to enqueue bounded research."""
    from vayujit_api.intelligence.due_diligence_schemas import ResearchPlanCreate
    from vayujit_api.intelligence.due_diligence_service import create_plan

    lock_owner(db, owner)
    scenario, version = current(db, owner, scenario_id)
    context = owned(db, SourcingScenarioContext, owner, scenario.context_id)
    payload = data.model_dump(mode="json")
    key = f"research:{scenario.id}:{data.idempotency_key}"
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    if version.version != data.expected_version or scenario.status == "ARCHIVED":
        raise HTTPException(409, "Scenario version is not current or is archived.")
    intent_key = f"intent:{key}"
    intent = replay(db, owner, intent_key, payload)
    if intent is None:
        sources = lineage(
            db, owner, context, ScenarioCreate.model_validate(version.snapshot["request"])
        )
        intent = {
            "version_id": str(version.id),
            "contexts": [
                {"id": x["due_diligence_id"], "assessment_version": x["assessment_version"]}
                for x in sources
            ],
        }
        record(db, owner, context, intent_key, "SOURCING_RESEARCH_INTENT", payload, intent, version)
    plans = []
    for reference in intent["contexts"]:
        due = owned(db, SupplierDueDiligenceContext, owner, uuid.UUID(reference["id"]))
        if due.current_assessment_version != reference["assessment_version"]:
            raise HTTPException(
                409, "Due-diligence assessment changed; review before requesting research."
            )
        if due.current_assessment_version == 0:
            raise HTTPException(409, "Assess due diligence before requesting research.")
        plan, _ = create_plan(
            db,
            owner,
            due,
            ResearchPlanCreate(
                idempotency_key=f"scenario-{digest([intent_key, reference])}",
                max_tasks=10,
                max_sources=10,
                max_provider_calls=10,
            ),
        )
        plans.append(plan)
    # The authoritative planner commits its own records; reacquire before finalizing.
    lock_owner(db, owner)
    prior = replay(db, owner, key, payload)
    if prior:
        return prior
    return record(
        db,
        owner,
        context,
        key,
        "SOURCING_RESEARCH_REQUESTED",
        payload,
        {"version_id": str(version.id), "plans": plans, "external_dispatch": False},
        version,
    )
