from __future__ import annotations

import uuid
from typing import Any

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_due_diligence_canonical_research_and_owner_isolation(client: Any) -> None:
    context = setup_context(client)
    supplier_response = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": "Disposable Due Diligence Supplier",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "local due-diligence fixture",
        },
        headers=ORIGIN,
    )
    assert supplier_response.status_code == 201, supplier_response.text
    supplier_id = supplier_response.json()["id"]
    canonical = client.post(
        "/api/v1/intelligence/cross-marketplace/suppliers/reconcile",
        json={"supplier_ids": [supplier_id]},
        headers=ORIGIN,
    )
    assert canonical.status_code == 200, canonical.text
    canonical_id = canonical.json()[0]["id"]

    created = client.post(
        "/api/v1/intelligence/supplier-due-diligence/contexts",
        json={
            "supplier_id": canonical_id,
            "product_id": context["product"]["id"],
            "idempotency_key": "due-diligence-e2e-1",
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
    assert assessed.json()["assessment_version"] == 1
    gaps = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/gaps",
        headers=ORIGIN,
    )
    assert gaps.status_code == 200 and gaps.json()

    plan = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/plans",
        json={"idempotency_key": "due-diligence-plan-e2e-1", "max_tasks": 1},
        headers=ORIGIN,
    )
    assert plan.status_code == 200, plan.text
    plan_id = plan.json()["id"]
    recovery_payload = {
        "failure_code": "source_unavailable",
        "action": "retry",
        "idempotency_key": "due-diligence-recovery-e2e-1",
    }
    recovery = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/recovery",
        json=recovery_payload,
        headers=ORIGIN,
    )
    assert recovery.status_code == 200, recovery.text
    assert recovery.json()["action"] == "retry"
    recovery_replay = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/recovery",
        json=recovery_payload,
        headers=ORIGIN,
    )
    assert recovery_replay.status_code == 200, recovery_replay.text
    assert recovery_replay.json()["idempotent_reuse"] is True
    pre_execution_calendar = client.get(
        "/api/v1/intelligence/supplier-shortlisting/calendar", headers=ORIGIN
    )
    assert pre_execution_calendar.status_code == 200
    assert any(
        item.get("kind") == "SUPPLIER_RESEARCH_DUE"
        for item in pre_execution_calendar.json()
        if item.get("context_id") == context_id
    )
    executed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan_id}/run",
        headers=ORIGIN,
    )
    assert executed.status_code == 200, executed.text
    history = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/history",
        headers=ORIGIN,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()["assessments"]) == 2
    assert any(item["lineage"]["observation_ids"] for item in history.json()["gap_transitions"])
    guard = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/sourcing-guard",
        headers=ORIGIN,
    )
    assert guard.status_code == 200 and guard.json()["outcome"] in {
        "ALLOWED",
        "REVIEW_REQUIRED",
        "BLOCKED",
    }
    assert guard.json()["external_dispatch"] is False
    replayed = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/plans/{plan_id}/run",
        headers=ORIGIN,
    )
    assert replayed.status_code == 200, replayed.text
    replay_history = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/history",
        headers=ORIGIN,
    )
    assert len(replay_history.json()["assessments"]) == 2

    unresolved_gap = next(
        item for item in gaps.json() if item["status"] not in {"RESOLVED", "WAIVED_BY_HUMAN"}
    )
    review = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{unresolved_gap['id']}/mark_for_human_review",
        json={"reason": "Owner requires review"},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    waived = client.post(
        f"/api/v1/intelligence/supplier-due-diligence/gaps/{unresolved_gap['id']}/waive_gap",
        json={"reason": "Owner accepts bounded residual risk"},
        headers=ORIGIN,
    )
    assert waived.status_code == 200, waived.text
    assert waived.json()["status"] == "WAIVED_BY_HUMAN"
    detail = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}",
        headers=ORIGIN,
    )
    assert detail.status_code == 200
    assert detail.json()["readiness"] == "REVIEW_REQUIRED"
    assert detail.json()["summary"]["open_gaps"] >= 1
    explanation = detail.json()["explanation"]
    assert explanation["status"] == "REVIEW_REQUIRED"
    assert explanation["reasons"]
    risk_lineage = detail.json()["summary"].get("risk_recomputation", {})
    assert {
        "reference",
        "before",
        "after",
        "assessment_version",
        "triggering_evidence_ids",
        "triggering_claim_ids",
        "observation_ids",
    } <= set(risk_lineage)
    assert risk_lineage["assessment_version"] == detail.json()["assessment_version"]

    channel = client.get(
        f"/api/v1/intelligence/supplier-shortlisting/product-channel/{context['product']['id']}",
        headers=ORIGIN,
    )
    assert channel.status_code == 200
    due_projection = channel.json()["due_diligence"]
    assert due_projection and {
        "due_diligence_readiness",
        "required_open_gap_count",
        "critical_gap_count",
        "high_gap_count",
        "research_in_progress",
        "last_assessment_at",
        "latest_material_finding",
    } <= set(due_projection[0])

    calendar = client.get(
        "/api/v1/intelligence/supplier-shortlisting/calendar",
        headers=ORIGIN,
    )
    assert calendar.status_code == 200
    due_events = [item for item in calendar.json() if item.get("context_id") == context_id]
    assert {
        "SUPPLIER_DUE_DILIGENCE_REVIEW_DUE",
        "SUPPLIER_EVIDENCE_RECHECK_DUE",
        "SUPPLIER_VERIFICATION_REVIEW_DUE",
    } <= {item["kind"] for item in due_events}
    assert all(event["owner_id"] for event in due_events)
    assert all(event["supplier_id"] == canonical_id for event in due_events)
    assert all(event["due_at"] and event["source_ref"] for event in due_events)
    calendar_repeat = client.get(
        "/api/v1/intelligence/supplier-shortlisting/calendar",
        headers=ORIGIN,
    )
    assert [item.get("event_id") for item in due_events] == [
        item.get("event_id")
        for item in calendar_repeat.json()
        if item.get("context_id") == context_id
    ]

    operations = client.get(
        "/api/v1/intelligence/supplier-due-diligence/operations",
        headers=ORIGIN,
    )
    assert operations.status_code == 200
    assert {
        "contexts_open",
        "review_required_contexts",
        "research_running",
        "research_failed",
        "critical_gaps",
        "high_gaps",
        "required_open_gaps",
        "recovery_needed_tasks",
    } <= set(operations.json())

    report = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/report",
        headers=ORIGIN,
    )
    assert report.status_code == 200
    assert report.json()["id"] == context_id
    assert "database_url" not in str(report.json()).casefold()
    integrity = client.get(
        "/api/v1/intelligence/supplier-due-diligence/integrity",
        headers=ORIGIN,
    )
    assert integrity.status_code == 200
    assert all(value == 0 for value in integrity.json().values())

    foreign_context = client.get(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{uuid.uuid4()}",
        headers=ORIGIN,
    )
    assert foreign_context.status_code == 404
