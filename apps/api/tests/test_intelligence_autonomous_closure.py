# ruff: noqa: E501
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import test_ai_integration as fixtures
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchAttempt,
    AutonomousResearchChange,
    AutonomousResearchClaim,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchRecovery,
    AutonomousResearchReport,
    AutonomousResearchSchedule,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.autonomous_planner import RECOVERY_FAILURE_CODES

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def _payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "mission_type": "FULL_OPPORTUNITY_RESEARCH",
        "goal": "Certify a bounded local autonomous research mission",
        "market": "IN",
        "category": "home",
        "scope": {},
        "idempotency_key": f"closure-{uuid.uuid4()}",
        "provider_mode": "LOCAL_DETERMINISTIC",
        "max_tasks": 20,
        "max_provider_calls": 20,
        "max_retries": 2,
    }
    value.update(overrides)
    return value


def _mission(client, **overrides: object) -> dict[str, object]:
    response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json=_payload(**overrides),
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _db():
    assert fixtures.factory is not None
    return fixtures.factory()


def test_audit_change_materiality_alerts_and_replay_are_idempotent(client) -> None:
    setup_context(client)
    mission = _mission(client)
    run = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/run",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert run.status_code == 200, run.text
    report = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/reports?format=html",
        headers=ORIGIN,
    )
    assert report.status_code == 200
    change_payload = {
        "change_type": "score",
        "previous": {"score": 70},
        "current": {"score": 55},
    }
    first = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/changes/detect",
        json=change_payload,
        headers=ORIGIN,
    )
    repeated = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/changes/detect",
        json=change_payload,
        headers=ORIGIN,
    )
    assert first.status_code == 200 and repeated.status_code == 200
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["materiality"] == "MATERIAL"
    alerts = client.get(
        f"/api/v1/intelligence/autonomous/alerts?mission_id={mission['id']}", headers=ORIGIN
    )
    assert alerts.status_code == 200 and alerts.json()
    with _db() as db:
        actions = set(db.scalars(select(AuditEvent.action)))
        assert {
            "mission.created",
            "mission.started",
            "plan.generated",
            "task.started",
            "task.completed",
            "evidence.accepted",
            "report.generated",
            "research.change_detected",
        } <= actions
        assert db.scalar(select(func.count()).select_from(AutonomousResearchChange)) == 1
        assert db.scalar(select(func.count()).select_from(AutonomousResearchAlert)) >= 1
        assert db.scalar(select(func.count()).select_from(AutonomousResearchClaim)) > 0


def test_scheduler_materialization_and_catch_up_are_bounded(client) -> None:
    setup_context(client)
    mission = _mission(client, budget_policy={"catch_up_policy": "RUN_LATEST"})
    scheduled = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/schedule",
        json={
            "scheduled_for": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "frequency": "daily",
            "catch_up_policy": "RUN_LATEST",
        },
        headers=ORIGIN,
    )
    assert scheduled.status_code == 200, scheduled.text
    first = client.post("/api/v1/intelligence/autonomous/scheduler/materialize-due", headers=ORIGIN)
    second = client.post(
        "/api/v1/intelligence/autonomous/scheduler/materialize-due", headers=ORIGIN
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["materialized"] == 1
    assert second.json()["materialized"] == 0
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(AutonomousResearchSchedule)) == 1


def test_crash_before_and_after_resume_without_duplicate_evidence(client) -> None:
    setup_context(client)
    before = _mission(client)
    first = client.post(
        f"/api/v1/intelligence/autonomous/missions/{before['id']}/run",
        json={"confirm": True, "crash_stage": "before_source"},
        headers=ORIGIN,
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/intelligence/autonomous/missions/{before['id']}/run",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert second.status_code == 200
    after = _mission(client)
    third = client.post(
        f"/api/v1/intelligence/autonomous/missions/{after['id']}/run",
        json={"confirm": True, "crash_stage": "after_evidence"},
        headers=ORIGIN,
    )
    assert third.status_code == 200
    fourth = client.post(
        f"/api/v1/intelligence/autonomous/missions/{after['id']}/run",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert fourth.status_code == 200
    with _db() as db:
        mission_ids = [before["id"], after["id"]]
        evidence = list(
            db.scalars(
                select(AutonomousResearchEvidence).where(
                    AutonomousResearchEvidence.mission_id.in_(mission_ids)
                )
            )
        )
        assert evidence
        assert len({item.retrieval_identity for item in evidence}) == len(evidence)


def test_recovery_matrix_and_recovery_idempotency(client) -> None:
    setup_context(client)
    mission = _mission(client)
    for index, failure_code in enumerate(RECOVERY_FAILURE_CODES):
        payload = {
            "failure_code": failure_code,
            "action": "retry",
            "idempotency_key": f"matrix-{index}",
        }
        response = client.post(
            f"/api/v1/intelligence/autonomous/missions/{mission['id']}/recovery",
            json=payload,
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
        repeated = client.post(
            f"/api/v1/intelligence/autonomous/missions/{mission['id']}/recovery",
            json=payload,
            headers=ORIGIN,
        )
        assert repeated.status_code == 200 and repeated.json()["idempotent_reuse"] is True
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(AutonomousResearchRecovery)) == len(
            RECOVERY_FAILURE_CODES
        )


def test_autonomous_storage_ledger_replay_and_integrity(client) -> None:
    setup_context(client)
    models = {
        "missions": AutonomousResearchMission,
        "tasks": AutonomousResearchTask,
        "attempts": AutonomousResearchAttempt,
        "evidence": AutonomousResearchEvidence,
        "claims": AutonomousResearchClaim,
        "contradictions": AutonomousResearchContradiction,
        "changes": AutonomousResearchChange,
        "schedules": AutonomousResearchSchedule,
        "recoveries": AutonomousResearchRecovery,
        "alerts": AutonomousResearchAlert,
        "reports": AutonomousResearchReport,
    }

    def counts() -> dict[str, int]:
        with _db() as db:
            return {
                name: int(db.scalar(select(func.count()).select_from(model)) or 0)
                for name, model in models.items()
            }

    before = counts()
    mission = _mission(client)
    run = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/run",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert run.status_code == 200
    report = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/reports",
        headers=ORIGIN,
    )
    assert report.status_code == 200
    after = counts()
    replay = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/run",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert replay.status_code == 200
    replay_counts = counts()
    assert after["missions"] == before["missions"] + 1
    assert after["tasks"] >= before["tasks"] + 1
    assert after["evidence"] >= before["evidence"] + 1
    assert replay_counts == after
    integrity = client.get("/api/v1/intelligence/autonomous/integrity", headers=ORIGIN)
    assert integrity.status_code == 200
    assert all(value == 0 or value == "N/A" for value in integrity.json()["counters"].values())
    print(f"AUTONOMOUS_STORAGE_BEFORE={before}")
    print(f"AUTONOMOUS_STORAGE_AFTER={after}")
    print(f"AUTONOMOUS_STORAGE_REPLAY={replay_counts}")


def test_canonical_e2e_history_report_and_integrity(client) -> None:
    setup_context(client)
    mission = _mission(
        client, mission_type="FULL_OPPORTUNITY_RESEARCH", scope={"provider_scenario": "conflicting"}
    )
    result = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/run",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert result.status_code == 200
    assert result.json()["status"] == "COMPLETED_WITH_WARNINGS"
    history = client.get(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/history", headers=ORIGIN
    )
    assert history.status_code == 200
    report = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission['id']}/reports?format=markdown",
        headers=ORIGIN,
    )
    assert report.status_code == 200
    contradiction = client.get(
        f"/api/v1/intelligence/autonomous/contradictions?mission_id={mission['id']}", headers=ORIGIN
    )
    assert contradiction.status_code == 200 and contradiction.json()
    integrity = client.get("/api/v1/intelligence/autonomous/integrity", headers=ORIGIN)
    assert integrity.status_code == 200 and integrity.json()["status"] == "PASS"
    with _db() as db:
        assert db.scalar(select(func.count()).select_from(AutonomousResearchMission)) == 1
        assert db.scalar(select(func.count()).select_from(AutonomousResearchTask)) >= 1
        assert db.scalar(select(func.count()).select_from(AutonomousResearchReport)) == 1
        assert db.scalar(select(func.count()).select_from(AutonomousResearchContradiction)) >= 1
