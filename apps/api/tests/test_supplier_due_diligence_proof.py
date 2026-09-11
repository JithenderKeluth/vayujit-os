from __future__ import annotations

import uuid
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import AutonomousResearchEvidence
from vayujit_api.intelligence.due_diligence_models import (
    SupplierDueDiligenceAssessment,
    SupplierDueDiligenceContext,
    SupplierEvidenceGap,
    SupplierResearchPlan,
    SupplierResearchTask,
)

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _create_due_context(client: Any, suffix: str) -> str:
    base = setup_context(client)
    supplier = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": f"Proof Supplier {suffix}",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "local due-diligence proof fixture",
        },
        headers=ORIGIN,
    )
    assert supplier.status_code == 201, supplier.text
    reconciled = client.post(
        "/api/v1/intelligence/cross-marketplace/suppliers/reconcile",
        json={"supplier_ids": [supplier.json()["id"]]},
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200, reconciled.text
    created = client.post(
        "/api/v1/intelligence/supplier-due-diligence/contexts",
        json={
            "supplier_id": reconciled.json()[0]["id"],
            "product_id": base["product"]["id"],
            "idempotency_key": f"proof-context-{suffix}",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    context_id = created.json()["id"]
    assessed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/assess",
        headers=ORIGIN,
    )
    assert assessed.status_code == 200, assessed.text
    return context_id


def _gaps(client: Any, context_id: str) -> list[dict[str, Any]]:
    response = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/gaps",
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_due_diligence_action_and_evidence_outcome_matrix(client: Any) -> None:
    context_id = _create_due_context(client, "actions")
    first, second = _gaps(client, context_id)[:2]

    started = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{first['id']}/start_research",
        json={"reason": "Start bounded proof research"},
        headers=ORIGIN,
    )
    assert started.status_code == 200, started.text
    replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{first['id']}/start_research",
        json={"reason": "Start bounded proof research"},
        headers=ORIGIN,
    )
    assert replay.status_code == 200 and replay.json()["idempotent_reuse"] is True
    duplicate = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{first['id']}/start_research",
        json={"reason": "A different active request"},
        headers=ORIGIN,
    )
    assert duplicate.status_code == 409

    selected = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/research_selected_gaps",
        json={"selected_gap_ids": [second["id"]], "reason": "Research a bounded subset"},
        headers=ORIGIN,
    )
    assert selected.status_code == 200, selected.text
    mixed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/research_selected_gaps",
        json={"selected_gap_ids": [second["id"], str(uuid.uuid4())], "reason": "mixed"},
        headers=ORIGIN,
    )
    assert mixed.status_code == 404

    cancelled = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{first['id']}/cancel_research",
        json={"reason": "Stop this proof run"},
        headers=ORIGIN,
    )
    assert cancelled.status_code == 200, cancelled.text
    cancelled_replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{first['id']}/cancel_research",
        json={"reason": "Stop this proof run again"},
        headers=ORIGIN,
    )
    assert cancelled_replay.status_code == 409

    no_reason = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/waive_gap",
        json={"reason": ""},
        headers=ORIGIN,
    )
    assert no_reason.status_code == 422
    review = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/mark_for_human_review",
        json={"reason": "Owner review required"},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    waived = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/waive_gap",
        json={"reason": "Bounded residual risk accepted"},
        headers=ORIGIN,
    )
    assert waived.status_code == 200 and waived.json()["status"] == "WAIVED_BY_HUMAN"
    waived_replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/waive_gap",
        json={"reason": "Bounded residual risk accepted"},
        headers=ORIGIN,
    )
    assert waived_replay.status_code == 200 and waived_replay.json()["idempotent_reuse"] is True
    reopened = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{second['id']}/reopen_gap",
        json={"reason": "Reopen for fresh proof"},
        headers=ORIGIN,
    )
    assert reopened.status_code == 200 and reopened.json()["status"] == "MISSING"

    plans = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        headers=ORIGIN,
    )
    assert plans.status_code == 200 and plans.json()
    executed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plans.json()[0]['id']}/run",
        headers=ORIGIN,
    )
    assert executed.status_code == 200, executed.text
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        evidence = list(db.scalars(select(AutonomousResearchEvidence)).all())
        assert evidence
        assert all(item.verification_status == "SUPPORTED" for item in evidence)
        assert all(item.freshness_status == "FRESH" for item in evidence)
        evidence[0].verification_status = "REJECTED"
        evidence[-1].freshness_status = "STALE"
        gap = db.scalar(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.context_id == uuid.UUID(context_id),
                SupplierEvidenceGap.status.not_in(["RESOLVED", "WAIVED_BY_HUMAN"]),
            )
        )
        assert gap is not None
        gap.status = "CONTRADICTORY"
        gap.contradiction_state = "material"
        db.commit()
    detail = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}",
        headers=ORIGIN,
    )
    assert detail.status_code == 200
    assert detail.json()["readiness"] in {"REVIEW_REQUIRED", "RESEARCH_REQUIRED"}
    assert detail.json()["explanation"]["reasons"]
    assert any(
        item["status"] not in {"RESOLVED", "WAIVED_BY_HUMAN"} for item in detail.json()["gaps"]
    )


def test_due_diligence_integrity_self_proof_and_direct_id_safety(client: Any) -> None:
    context_id = _create_due_context(client, "integrity")
    plan_response = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        json={"idempotency_key": "integrity-plan", "max_tasks": 1},
        headers=ORIGIN,
    )
    assert plan_response.status_code == 200, plan_response.text
    plan_id = uuid.UUID(plan_response.json()["id"])
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        plan = db.get(SupplierResearchPlan, plan_id)
        task = db.scalar(
            select(SupplierResearchTask).where(SupplierResearchTask.plan_id == plan_id)
        )
        assert plan is not None and task is not None
        duplicate_plan = SupplierResearchPlan(
            owner_id=plan.owner_id,
            context_id=plan.context_id,
            supplier_id=plan.supplier_id,
            assessment_version=plan.assessment_version,
            version=plan.version + 1,
            status="READY",
            priority=plan.priority,
            budget=plan.budget,
            allowed_methods=plan.allowed_methods,
            prohibited_methods=plan.prohibited_methods,
            reason="corruption proof",
            idempotency_key="integrity-duplicate-plan",
        )
        db.add(duplicate_plan)
        duplicate_task = SupplierResearchTask(
            owner_id=task.owner_id,
            plan_id=task.plan_id,
            gap_id=task.gap_id,
            task_type=task.task_type,
            status="QUEUED",
            priority=task.priority,
            result={},
            idempotency_key="integrity-duplicate-task",
        )
        db.add(duplicate_task)
        task.shared_execution_id = uuid.uuid4()
        gap = db.get(SupplierEvidenceGap, task.gap_id)
        assert gap is not None
        gap.status = "RESOLVED"
        gap.resolution_evidence_refs = []
        context = db.get(SupplierDueDiligenceContext, uuid.UUID(context_id))
        assert context is not None
        context.current_assessment_version = 999
        db.commit()
    corrupt = client.get("/api/v1/intelligence/supplier-due-diligence/integrity", headers=ORIGIN)
    assert corrupt.status_code == 200
    counters = corrupt.json()
    assert counters["duplicate_active_plans"] >= 1
    assert counters["duplicate_active_tasks"] >= 1
    assert counters["broken_execution_lineage"] >= 1
    assert counters["resolved_gap_without_evidence_or_waiver"] >= 1
    assert counters["current_assessment_pointer_errors"] >= 1
    with test_ai_integration.factory() as db:
        db.delete(duplicate_task)
        db.delete(duplicate_plan)
        task = db.scalar(
            select(SupplierResearchTask).where(SupplierResearchTask.plan_id == plan_id)
        )
        assert task is not None
        task.shared_execution_id = None
        gap = db.get(SupplierEvidenceGap, task.gap_id)
        assert gap is not None
        gap.status = "MISSING"
        context = db.get(SupplierDueDiligenceContext, uuid.UUID(context_id))
        assert context is not None
        latest = db.scalar(
            select(SupplierDueDiligenceAssessment)
            .where(SupplierDueDiligenceAssessment.context_id == context.id)
            .order_by(SupplierDueDiligenceAssessment.version.desc())
        )
        assert latest is not None
        context.current_assessment_version = latest.version
        db.commit()
    clean = client.get("/api/v1/intelligence/supplier-due-diligence/integrity", headers=ORIGIN)
    assert clean.status_code == 200
    assert all(value == 0 for value in clean.json().values())
    for path in (
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{uuid.uuid4()}",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{uuid.uuid4()}/gaps",
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{uuid.uuid4()}/plans",
    ):
        response = client.get(path, headers=ORIGIN)
        assert response.status_code == 404
    response = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{uuid.uuid4()}/run",
        headers=ORIGIN,
    )
    assert response.status_code == 404


def test_due_diligence_complete_replay_matrix_preserves_current_state(client: Any) -> None:
    """Replay every exposed due-diligence input through the real shared APIs."""
    from helpers.due_diligence_certification import (
        assert_replay_ledger_unchanged,
        snapshot_replay_ledger,
    )

    from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext

    context_id = _create_due_context(client, "complete-replay")
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        context = db.get(SupplierDueDiligenceContext, uuid.UUID(context_id))
        assert context is not None
        supplier_id = str(context.supplier_id)
        product_id = str(context.product_id)
        context_key = context.idempotency_key

    # Context creation is idempotent; assessment versions are intentionally
    # append-only history and the current pointer advances exactly once per call.
    context_replay = client.post(
        "/api/v1/intelligence/supplier-due-diligence/contexts",
        json={
            "supplier_id": supplier_id,
            "product_id": product_id,
            "idempotency_key": context_key,
        },
        headers=ORIGIN,
    )
    assert context_replay.status_code == 200 and context_replay.json()["reused"] is True
    for _ in range(2):
        reassessed = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/assess",
            headers=ORIGIN,
        )
        assert reassessed.status_code == 200, reassessed.text

    gaps = _gaps(client, context_id)
    assert len(gaps) >= 3
    actions = (
        ("start_research", gaps[0]["id"], "replay-start"),
        ("research_selected_gaps", gaps[1]["id"], "replay-selected"),
        ("request_more_research", gaps[0]["id"], "replay-more"),
    )
    for action, gap_id, reason in actions:
        payload = {"reason": reason, "selected_gap_ids": [gap_id]}
        first = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/gaps/{gap_id}/{action}",
            json=payload,
            headers=ORIGIN,
        )
        assert first.status_code == 200, first.text
        replay = client.post(
            f"/api/v1/intelligence/supplier-due-diligence/gaps/{gap_id}/{action}",
            json=payload,
            headers=ORIGIN,
        )
        assert replay.status_code == 200 and replay.json()["idempotent_reuse"] is True

    waiver_gap = gaps[2]["id"]
    reviewed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{waiver_gap}/mark_for_human_review",
        json={"reason": "Replay review"},
        headers=ORIGIN,
    )
    assert reviewed.status_code == 200, reviewed.text
    waiver_payload = {"reason": "Replay waiver"}
    waived = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{waiver_gap}/waive_gap",
        json=waiver_payload,
        headers=ORIGIN,
    )
    assert waived.status_code == 200, waived.text
    waiver_replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{waiver_gap}/waive_gap",
        json=waiver_payload,
        headers=ORIGIN,
    )
    assert waiver_replay.status_code == 200 and waiver_replay.json()["idempotent_reuse"] is True

    plans = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        headers=ORIGIN,
    )
    assert plans.status_code == 200 and plans.json()
    plan = plans.json()[0]
    plan_replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        json={
            "idempotency_key": "action:due-diligence:start_research:"
            + gaps[0]["id"]
            + ":replay-start",
            "max_tasks": 1,
        },
        headers=ORIGIN,
    )
    assert plan_replay.status_code == 200 and plan_replay.json()["reused"] is True
    task_list = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan['id']}/tasks", headers=ORIGIN
    )
    assert task_list.status_code == 200 and task_list.json()
    assert (
        client.get(
            f"/api/v1/intelligence/supplier-due-diligence/plans/{plan['id']}/tasks", headers=ORIGIN
        ).json()
        == task_list.json()
    )

    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        before_run = snapshot_replay_ledger(db, owner.id, uuid.UUID(context_id))
    first_run = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan['id']}/run", headers=ORIGIN
    )
    assert first_run.status_code == 200, first_run.text
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        after_first_run = snapshot_replay_ledger(db, owner.id, uuid.UUID(context_id))
    replay_run = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan['id']}/run", headers=ORIGIN
    )
    assert replay_run.status_code == 200, replay_run.text
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        after_replay = snapshot_replay_ledger(db, owner.id, uuid.UUID(context_id))
    expected_run_delta = {key: after_first_run[key] - before_run[key] for key in before_run}
    actual_replay_delta = {key: after_replay[key] - after_first_run[key] for key in after_first_run}
    ledger_rows = [
        {
            "entity": key,
            "before": before_run[key],
            "expected_first_run_delta": expected_run_delta[key],
            "after_first_run": after_first_run[key],
            "expected_replay_delta": 0,
            "actual_replay_delta": actual_replay_delta[key],
            "after_replay": after_replay[key],
            "result": "PASS" if actual_replay_delta[key] == 0 else "FAIL",
        }
        for key in before_run
    ]
    assert all(row["result"] == "PASS" for row in ledger_rows), ledger_rows
    print("STORAGE LEDGER", ledger_rows)
    assert_replay_ledger_unchanged(after_first_run, after_replay)
    assert replay_run.json()["mission_id"] == first_run.json()["mission_id"]

    for path in (
        f"/api/v1/intelligence/supplier-shortlisting/product-channel/{product_id}",
        "/api/v1/intelligence/supplier-shortlisting/calendar",
    ):
        first_projection = client.get(path, headers=ORIGIN)
        second_projection = client.get(path, headers=ORIGIN)
        assert first_projection.status_code == second_projection.status_code == 200
        assert first_projection.json() == second_projection.json()

    recovery_payload = {
        "failure_code": "source_unavailable",
        "action": "retry",
        "idempotency_key": "complete-replay-recovery",
    }
    recovery = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/recovery",
        json=recovery_payload,
        headers=ORIGIN,
    )
    assert recovery.status_code == 200, recovery.text
    recovery_replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/recovery",
        json=recovery_payload,
        headers=ORIGIN,
    )
    assert recovery_replay.status_code == 200 and recovery_replay.json()["idempotent_reuse"] is True
    assert (
        client.get(
            f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}", headers=ORIGIN
        ).status_code
        == 200
    )


def test_due_diligence_integrity_self_proof_covers_all_fourteen_counters(client: Any) -> None:
    """Each integrity counter is independently exercised then restored to zero."""
    from helpers.due_diligence_owners import OWNER_B, create_test_owner
    from sqlalchemy.exc import IntegrityError

    from vayujit_api.identity.router import current_user
    from vayujit_api.intelligence.due_diligence_models import (
        SupplierDueDiligenceContext,
        SupplierEvidenceGap,
        SupplierResearchPlan,
        SupplierResearchTask,
    )

    context_id = _create_due_context(client, "all-counters")
    plan_response = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        json={"idempotency_key": "all-counters-plan", "max_tasks": 1},
        headers=ORIGIN,
    )
    assert plan_response.status_code == 200, plan_response.text
    plan_id = uuid.UUID(plan_response.json()["id"])

    def counters() -> dict[str, int]:
        response = client.get(
            "/api/v1/intelligence/supplier-due-diligence/integrity", headers=ORIGIN
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert all(value == 0 for value in counters().values())
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        context = db.get(SupplierDueDiligenceContext, uuid.UUID(context_id))
        plan = db.get(SupplierResearchPlan, plan_id)
        gap = (
            db.scalar(
                select(SupplierEvidenceGap).where(
                    SupplierEvidenceGap.context_id == uuid.UUID(context_id),
                    SupplierEvidenceGap.assessment_version == context.current_assessment_version,
                )
            )
            if context is not None
            else None
        )
        task = db.scalar(
            select(SupplierResearchTask).where(SupplierResearchTask.plan_id == plan_id)
        )
        assert context is not None and plan is not None and gap is not None and task is not None
        owner_id = context.owner_id
        supplier_id = context.supplier_id
        context_version = context.current_assessment_version
        original_gap_state = {
            "assessment_version": gap.assessment_version,
            "status": gap.status,
            "resolution_evidence_refs": list(gap.resolution_evidence_refs or []),
            "supplier_id": gap.supplier_id,
            "shared_execution_id": task.shared_execution_id,
        }

        # B: the context idempotency constraint protects both current context
        # identity and the derived calendar identity.
        for label in ("duplicate_contexts", "duplicate_calendar_events"):
            duplicate = SupplierDueDiligenceContext(
                owner_id=owner_id,
                supplier_id=supplier_id,
                product_id=context.product_id,
                idempotency_key=context.idempotency_key,
                status="OPEN",
            )
            db.add(duplicate)
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()
            assert counters()[label] == 0

        # A: valid rows with distinct idempotency keys can expose duplicate
        # active logical plans and tasks; remove them after detector proof.
        duplicate_plan = SupplierResearchPlan(
            owner_id=plan.owner_id,
            context_id=plan.context_id,
            supplier_id=plan.supplier_id,
            assessment_version=plan.assessment_version,
            version=plan.version + 1,
            status="READY",
            priority=plan.priority,
            budget=plan.budget,
            allowed_methods=plan.allowed_methods,
            prohibited_methods=plan.prohibited_methods,
            reason="integrity counter proof",
            idempotency_key="all-counters-duplicate-plan",
        )
        db.add(duplicate_plan)
        db.commit()
        assert counters()["duplicate_active_plans"] >= 1
        db.delete(duplicate_plan)
        db.commit()

        duplicate_task = SupplierResearchTask(
            owner_id=task.owner_id,
            plan_id=task.plan_id,
            gap_id=task.gap_id,
            task_type=task.task_type,
            status="QUEUED",
            priority=task.priority,
            result={},
            idempotency_key="all-counters-duplicate-task",
        )
        db.add(duplicate_task)
        db.commit()
        assert counters()["duplicate_active_tasks"] >= 1
        db.delete(duplicate_task)
        db.commit()

        # B: FK constraints reject orphan gap/task/plan-task references.
        orphan_gap = SupplierEvidenceGap(
            owner_id=owner_id,
            context_id=uuid.uuid4(),
            supplier_id=supplier_id,
            product_id=context.product_id,
            assessment_version=context_version,
            dimension="OTHER",
            status="MISSING",
            severity="LOW",
            classification="OPTIONAL",
            reason="constraint proof",
        )
        db.add(orphan_gap)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert counters()["orphan_gaps"] == 0

        orphan_task = SupplierResearchTask(
            owner_id=owner_id,
            plan_id=uuid.uuid4(),
            gap_id=gap.id,
            task_type=task.task_type,
            status="QUEUED",
            priority=task.priority,
            result={},
            idempotency_key="all-counters-orphan-task",
        )
        db.add(orphan_task)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert counters()["orphan_tasks"] == 0
        assert counters()["broken_plan_task_lineage"] == 0

        # A: nullable lineage fields intentionally accept a bad reference so
        # the detector can prove it and the row can be restored.
        gap.assessment_version = context_version + 99
        db.commit()
        assert counters()["orphan_gap_versions"] >= 1
        gap.assessment_version = original_gap_state["assessment_version"]
        db.commit()

        task.shared_execution_id = uuid.uuid4()
        db.commit()
        assert counters()["broken_execution_lineage"] >= 1
        task.shared_execution_id = original_gap_state["shared_execution_id"]
        db.commit()

        gap.resolution_evidence_refs = [str(uuid.uuid4())]
        db.commit()
        assert counters()["broken_evidence_lineage"] >= 1
        gap.resolution_evidence_refs = original_gap_state["resolution_evidence_refs"]
        db.commit()

        gap.status = "WAIVED_BY_HUMAN"
        db.commit()
        assert counters()["invalid_human_waivers"] >= 1
        gap.status = original_gap_state["status"]
        db.commit()

        gap.status = "RESOLVED"
        gap.resolution_evidence_refs = []
        db.commit()
        assert counters()["resolved_gap_without_evidence_or_waiver"] >= 1
        gap.status = original_gap_state["status"]
        db.commit()

        context.current_assessment_version = context_version + 999
        db.commit()
        assert counters()["current_assessment_pointer_errors"] >= 1
        context.current_assessment_version = context_version
        db.commit()

    # A: cross-owner reference uses a real second owner/supplier and is then restored.
    with test_ai_integration.factory() as db:
        owner_b = create_test_owner(
            db, owner_id=OWNER_B, email="due-diligence-integrity-owner-b@example.com"
        )
    client.app.dependency_overrides[current_user] = lambda: owner_b
    supplier_b = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": "Integrity owner B supplier",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "integrity counter proof",
        },
        headers=ORIGIN,
    )
    assert supplier_b.status_code == 201, supplier_b.text
    reconciled = client.post(
        "/api/v1/intelligence/cross-marketplace/suppliers/reconcile",
        json={"supplier_ids": [supplier_b.json()["id"]]},
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200, reconciled.text
    client.app.dependency_overrides.pop(current_user, None)
    with test_ai_integration.factory() as db:
        gap = db.scalar(
            select(SupplierEvidenceGap).where(
                SupplierEvidenceGap.context_id == uuid.UUID(context_id)
            )
        )
        assert gap is not None
        original_supplier = gap.supplier_id
        gap.supplier_id = uuid.UUID(reconciled.json()[0]["id"])
        db.commit()
        assert counters()["cross_owner_references"] >= 1
        gap.supplier_id = original_supplier
        db.commit()

    clean = counters()
    assert all(value == 0 for value in clean.values()), clean
