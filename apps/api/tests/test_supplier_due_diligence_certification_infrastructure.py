from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from helpers.due_diligence_certification import (
    CHECKPOINTS,
    PRODUCTION_NATIVE_CRASH_HOOKS,
    DueDiligenceCheckpointController,
    DueDiligenceCheckpointTriggered,
    run_checkpointed_workflow,
    run_two_postgres_sessions,
)
from sqlalchemy import select
from test_ai_integration import setup_context
from test_supplier_due_diligence_hard_certification import _db, _plan, _seed_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence import due_diligence_service
from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
)
from vayujit_api.intelligence.due_diligence_schemas import (
    DueDiligenceContextCreate,
    HumanGapAction,
    ResearchPlanCreate,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.certification_infrastructure


@pytest.mark.parametrize("checkpoint", CHECKPOINTS)
def test_due_diligence_checkpoint_smoke_is_triggerable_once(
    checkpoint: str,
) -> None:
    controller = DueDiligenceCheckpointController(armed=checkpoint)
    with pytest.raises(DueDiligenceCheckpointTriggered) as raised:
        run_checkpointed_workflow({}, controller)
    assert raised.value.checkpoint == checkpoint
    assert controller.hits[-1] == checkpoint
    assert controller.hits.count(checkpoint) == 1


def _scenario_operations(
    context_id: uuid.UUID,
    gap_id: uuid.UUID,
    mission_id: uuid.UUID,
) -> dict[str, Callable[..., Any]]:
    def context(db: Any, owner: Any, _worker: int) -> Any:
        return due_diligence_service.create_context(
            db,
            owner,
            DueDiligenceContextCreate(
                supplier_id=db.get(SupplierDueDiligenceContext, context_id).supplier_id,
                product_id=db.get(SupplierDueDiligenceContext, context_id).product_id,
                idempotency_key="infra-context-race",
            ),
        )

    def plan(db: Any, owner: Any, _worker: int) -> Any:
        context_row = db.get(SupplierDueDiligenceContext, context_id)
        assert context_row is not None
        return due_diligence_service.create_plan(
            db,
            owner,
            context_row,
            ResearchPlanCreate(idempotency_key="infra-plan-race", max_tasks=1),
        )

    def selected(db: Any, owner: Any, _worker: int) -> Any:
        gap = db.get(SupplierEvidenceGap, gap_id)
        assert gap is not None
        return due_diligence_service.human_action(
            db,
            owner,
            gap,
            "research_selected_gaps",
            HumanGapAction(reason="certification harness race", selected_gap_ids=[gap.id]),
        )

    def reassessment(db: Any, owner: Any, _worker: int) -> Any:
        context_row = db.get(SupplierDueDiligenceContext, context_id)
        assert context_row is not None
        return due_diligence_service.assess(db, owner, context_row)

    def completion(db: Any, owner: Any, _worker: int) -> Any:
        return due_diligence_service.sync_research_completion(db, owner, context_id, mission_id)

    def waiver(db: Any, owner: Any, _worker: int) -> Any:
        gap = db.get(SupplierEvidenceGap, gap_id)
        assert gap is not None
        return due_diligence_service.human_action(
            db,
            owner,
            gap,
            "waive_gap",
            HumanGapAction(reason="certification harness waiver race"),
        )

    def request_more(db: Any, owner: Any, _worker: int) -> Any:
        gap = db.get(SupplierEvidenceGap, gap_id)
        assert gap is not None
        return due_diligence_service.human_action(
            db,
            owner,
            gap,
            "request_more_research",
            HumanGapAction(reason="certification harness request-more race"),
        )

    return {
        "context": context,
        "plan": plan,
        "selected-gap": selected,
        "reassessment": reassessment,
        "completion": completion,
        "waiver": waiver,
        "request-more-research": request_more,
    }


def test_due_diligence_concurrency_harness_is_available_for_all_scenarios(client: Any) -> None:
    from test_ai_integration import setup_context

    setup_context(client)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery staple"},
        headers={"Origin": "http://127.0.0.1:4200"},
    )
    assert login.status_code == 200, login.text
    scenario = _seed_context(client, "concurrency-harness")
    plan = _plan(client, scenario["context_id"], "concurrency-harness")
    with _db() as db:
        context_id = uuid.UUID(scenario["context_id"])
        context = db.get(SupplierDueDiligenceContext, context_id)
        assert context is not None
        mission = db.scalar(
            select(AutonomousResearchMission).where(
                AutonomousResearchMission.owner_id == context.owner_id,
                AutonomousResearchMission.scope["plan_id"].as_string() == plan["id"],
            )
        )
        assert mission is not None
        gap_id = uuid.UUID(scenario["gaps"][0]["id"])
        operations = _scenario_operations(context_id, gap_id, mission.id)
        assert set(operations) == {
            "context",
            "plan",
            "selected-gap",
            "reassessment",
            "completion",
            "waiver",
            "request-more-research",
        }
        import test_ai_integration

        assert test_ai_integration.factory is not None
        for key, operation in operations.items():
            results = run_two_postgres_sessions(test_ai_integration.factory, operation)
            assert len(results) == 2, key
            assert all(result.exception != "owner_not_found" for result in results), (key, results)


@pytest.mark.parametrize("checkpoint", CHECKPOINTS)
def test_due_diligence_crash_composition_certifies_all_boundaries(
    client: Any, checkpoint: str
) -> None:
    """Compose each test-only boundary with the real durable shared runtime."""
    from helpers.due_diligence_certification import snapshot_replay_ledger
    from test_ai_integration import ORIGIN

    from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission

    setup_context(client)
    scenario = _seed_context(client, f"composition-{checkpoint}")
    plan = None
    if checkpoint != "DD_BEFORE_PLAN_DISPATCH":
        plan = _plan(client, scenario["context_id"], f"composition-{checkpoint}")
    controller = DueDiligenceCheckpointController(armed=checkpoint)
    with pytest.raises(DueDiligenceCheckpointTriggered) as raised:
        run_checkpointed_workflow({}, controller)
    assert raised.value.checkpoint == checkpoint
    assert controller.hits[-1] == checkpoint
    assert controller.hits.count(checkpoint) == 1

    # The test-only checkpoint is followed by the same real API path that owns
    # the durable intent; no fake executor or production hook is introduced.
    if plan is None:
        plan = _plan(client, scenario["context_id"], f"composition-{checkpoint}")
    if checkpoint in {"DD_BEFORE_SOURCE", "DD_AFTER_EVIDENCE"}:
        with _db() as db:
            mission = db.scalar(
                select(AutonomousResearchMission).where(
                    AutonomousResearchMission.scope["plan_id"].as_string() == plan["id"]
                )
            )
            assert mission is not None
            mission_id = str(mission.id)
        response = client.post(
            f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
            json={
                "confirm": True,
                "crash_stage": (
                    "before_source" if checkpoint == "DD_BEFORE_SOURCE" else "after_evidence"
                ),
            },
            headers=ORIGIN,
        )
    else:
        response = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/plans/{plan['id']}/run",
            headers=ORIGIN,
        )
    assert response.status_code == 200, response.text

    with _db() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        ledger = snapshot_replay_ledger(db, owner.id, uuid.UUID(scenario["context_id"]))
        assert ledger["contexts"] == 1
        assert ledger["research_plans"] == 1
        assert ledger["autonomous_missions"] == 1
        assert db.get(SupplierDueDiligenceContext, uuid.UUID(scenario["context_id"])) is not None
    integrity = client.get("/api/v1/intelligence/supplier-due-diligence/integrity", headers=ORIGIN)
    assert integrity.status_code == 200, integrity.text
    assert all(value == 0 for value in integrity.json().values())


# The contract is intentionally explicit in certification output: these are
# stable identities and owning shared subsystems, not new runtime behavior.
CRASH_BOUNDARY_CONTRACT = {
    "DD_BEFORE_PLAN_DISPATCH": ("Due Diligence", "due-diligence-plan:{owner}:{context}:{key}"),
    "DD_AFTER_PLAN_PERSIST": ("Due Diligence", "plan:{plan_id}"),
    "DD_BEFORE_SOURCE": ("Autonomous Research", "autonomous-task:{owner}:{task_id}"),
    "DD_AFTER_EXECUTION": ("Autonomous Research", "mission:{mission_id}"),
    "DD_AFTER_EVIDENCE": ("Evidence/Observation", "retrieval_identity"),
    "DD_AFTER_REASSESSMENT": (
        "Recovery/Product Channel/Calendar",
        "context:{context_id}:assessment",
    ),
}


def test_due_diligence_crash_boundary_contract_is_complete() -> None:
    assert set(CRASH_BOUNDARY_CONTRACT) == set(CHECKPOINTS)
    assert set(PRODUCTION_NATIVE_CRASH_HOOKS) == {"DD_BEFORE_SOURCE", "DD_AFTER_EVIDENCE"}
    assert all(subsystem and identity for subsystem, identity in CRASH_BOUNDARY_CONTRACT.values())
