"""Executable scenario action for the existing Operations Recovery endpoint."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence import scenario_service as service
from vayujit_api.intelligence.scenario_schemas import VersionCommand


def recalculate_stale(
    db: Session,
    owner: User,
    scenario_id: uuid.UUID,
    command: VersionCommand,
) -> dict[str, Any]:
    service.lock_owner(db, owner)
    scenario, version = service.current(db, owner, scenario_id)
    key = f"recalculate:{scenario.id}:{command.idempotency_key}"
    prior = service.replay(db, owner, key, command.model_dump(mode="json"))
    if prior:
        return prior
    if service.freshness(db, owner, scenario, version) == "CURRENT":
        raise HTTPException(409, "Scenario is current; no stale recalculation is needed.")
    event = record_event(
        db,
        actor_id=owner.id,
        action="operations.sourcing_scenario_recovery",
        entity_type="sourcing_scenario",
        entity_id=scenario.id,
        metadata={
            "status": "requested",
            "scenario_version": version.version,
            "idempotency_key": command.idempotency_key,
            "recovery_action": "RECALCULATE_STALE_SCENARIO",
        },
        idempotency_key=f"scenario-recovery:{owner.id}:{scenario.id}:{command.idempotency_key}",
    )
    result = service.recalculate(db, owner, scenario.id, command)
    return {**result, "recovery_action": "RECALCULATE_STALE_SCENARIO", "audit_id": str(event.id)}


SCENARIO_RECOVERY_ACTION_REGISTRY: Mapping[
    str, Callable[[Session, User, uuid.UUID, VersionCommand], dict[str, Any]]
] = MappingProxyType({"RECALCULATE_STALE_SCENARIO": recalculate_stale})

UNSUPPORTED_SCENARIO_RECOVERY_ACTIONS = frozenset(
    {
        "RETRY_SCENARIO_CALCULATION",
        "RETRY_SCENARIO_RESEARCH_REQUEST",
        "REPAIR_SCENARIO_PROJECTION",
    }
)
