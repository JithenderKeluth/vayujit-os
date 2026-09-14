"""Deterministic, replay-safe baseline scenarios over current authoritative lineage."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence import scenario_service as service
from vayujit_api.intelligence.scenario_analysis import SCORING_VERSION, calculate, compare
from vayujit_api.intelligence.scenario_models import SourcingScenarioContext
from vayujit_api.intelligence.scenario_schemas import GenerateRequest, ScenarioCreate

LABELS = {
    "LOWEST_COST": "LOWEST_COST",
    "LOWEST_CAPITAL": "LOWEST_CAPITAL",
    "FASTEST": "FASTEST_SUPPLY",
    "LOWEST_RISK": "LOWEST_RISK",
    "BEST_RESILIENCE": "MAXIMUM_RESILIENCE",
    "BEST_BALANCED": "BALANCED",
}


def _candidate_inputs(
    context: SourcingScenarioContext, data: GenerateRequest
) -> list[ScenarioCreate]:
    target = int(context.settings["target_quantity"])
    candidates = [
        data.basis.model_copy(
            update={
                "name": f"Baseline: {allocation.supplier_id}",
                "scenario_type": "SINGLE_SUPPLIER",
                "allocations": [allocation.model_copy(update={"quantity": target})],
            }
        )
        for allocation in sorted(data.basis.allocations, key=lambda row: str(row.supplier_id))
    ]
    if len(data.basis.allocations) > 1:
        candidates.append(
            data.basis.model_copy(
                update={"name": "Diversified baseline", "scenario_type": "MULTI_SUPPLIER"}
            )
        )
    return candidates


def generate(
    db: Session, owner: User, context_id: uuid.UUID, data: GenerateRequest
) -> dict[str, Any]:
    """Persist only evidence-complete, distinct candidates; resume partial batches by key."""
    service.lock_owner(db, owner)
    context = service.owned(db, SourcingScenarioContext, owner, context_id)
    if sum(row.quantity for row in data.basis.allocations) != context.settings["target_quantity"]:
        raise HTTPException(422, "Candidate quantities must equal the target quantity.")
    planned: list[tuple[str, ScenarioCreate, dict[str, Any], list[dict[str, Any]]]] = []
    for candidate in _candidate_inputs(context, data):
        source = service.lineage(db, owner, context, candidate)
        result = calculate(context.settings, candidate.model_dump(mode="json"), source)
        if (
            result["missing_dimensions"]
            or result["status"] == "BLOCKED"
            or result["moq_feasibility"] != "FEASIBLE"
            or any(
                warning in result["warnings"]
                for warning in ("CAPITAL_LIMIT_EXCEEDED", "MARGIN_BELOW_TARGET")
            )
        ):
            continue
        signature = service.digest(
            [(str(a.supplier_id), a.quantity) for a in candidate.allocations]
        )
        candidate = candidate.model_copy(
            update={
                "idempotency_key": f"gen:{service.digest([data.idempotency_key, signature])[:40]}"
            }
        )
        planned.append((signature, candidate, result, source))
    if not planned:
        raise HTTPException(409, "No evidence-complete eligible baseline scenario is available.")
    lineage_snapshot = [(signature, service.digest(source)) for signature, _, _, source in planned]
    request = {"input": data.model_dump(mode="json"), "lineage": lineage_snapshot}
    batch_key = f"generation:{context.id}:{data.idempotency_key}"
    prior = service.replay(db, owner, batch_key, request)
    if prior:
        return prior

    stable_rows = [
        {"id": signature, "name": candidate.name, "result": result}
        for signature, candidate, result, _ in planned
    ]
    ranked = compare(stable_rows)
    persisted = {
        signature: service.create_scenario(db, owner, context.id, candidate)
        for signature, candidate, _, _ in planned
    }
    generated = [
        {
            "id": persisted[row["id"]]["id"],
            "version_id": persisted[row["id"]]["version_id"],
            "name": row["name"],
            "labels": [LABELS[label] for label in row["labels"] if label in LABELS],
            "score": row["score"],
            "result": row["result"],
        }
        for row in ranked["scenarios"]
    ]
    selected = ranked["recommended_version_id"]
    # Candidate writes commit independently so an interrupted batch is resumable.
    # Reacquire the owner lock before recording the batch completion marker.
    service.lock_owner(db, owner)
    prior = service.replay(db, owner, batch_key, request)
    if prior:
        return prior
    return service.record(
        db,
        owner,
        context,
        batch_key,
        "SOURCING_SCENARIOS_GENERATED",
        request,
        {
            "generated": generated,
            "recommended_version_id": (persisted[selected]["version_id"] if selected else None),
            "scoring_version": SCORING_VERSION,
            "explanation": (
                "Complete candidates only; relative score uses stated versioned "
                "weights and current lineage. Human review required."
            ),
            "external_dispatch": False,
        },
    )
