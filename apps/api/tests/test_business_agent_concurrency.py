"""PostgreSQL-backed concurrency certification for Slice 9G."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.intelligence.business_agent_models import (
    BusinessAgentApproval,
    BusinessAgentArtifact,
    BusinessAgentAttempt,
    BusinessAgentCheckpoint,
    BusinessAgentFinding,
    BusinessAgentGoal,
    BusinessAgentPlan,
    BusinessAgentRun,
    BusinessAgentStep,
    BusinessAgentToolInvocation,
)
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as api:
        yield api, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _parallel(*calls: Callable[[], object]) -> list[object]:
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(call) for call in calls]
        return [future.result() for future in futures]


def _owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Business Agent Concurrency Owner",
            "email": "business-agent-concurrency@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _goal(api: TestClient, key: str) -> dict[str, object]:
    response = api.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": "Find three winning products for Amazon India within INR 300000 capital.",
            "idempotency_key": key,
            "provenance": {"source": "owner_input", "trace": key},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _run(api: TestClient, goal_id: str, key: str, max_steps: int = 20) -> dict[str, object]:
    response = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
        json={"idempotency_key": key, "max_steps": max_steps},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approval(api: TestClient, run_id: str) -> str:
    response = api.get(
        f"/api/v1/intelligence/business-agent/runs/{run_id}/approvals", headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return str(response.json()[0]["id"])


def _start(api: TestClient, run_id: str) -> object:
    return api.post(f"/api/v1/intelligence/business-agent/runs/{run_id}/start", headers=ORIGIN)


@pytest.mark.parametrize("round_number", [1, 2, 3])
def test_business_agent_postgres_concurrency_matrix(
    client: tuple[TestClient, sessionmaker[Session]], round_number: int
) -> None:
    api, factory = client
    _owner(api)

    goal_payload = {
        "raw_goal": "Find three winning products for Amazon India within INR 300000 capital.",
        "idempotency_key": f"concurrent-goal-{round_number}",
        "provenance": {"source": "owner_input"},
    }
    goal_responses = _parallel(
        lambda: api.post(
            "/api/v1/intelligence/business-agent/goals", json=goal_payload, headers=ORIGIN
        ),
        lambda: api.post(
            "/api/v1/intelligence/business-agent/goals", json=goal_payload, headers=ORIGIN
        ),
    )
    assert [response.status_code for response in goal_responses] == [201, 201]
    goal_ids = {response.json()["id"] for response in goal_responses}
    assert len(goal_ids) == 1
    goal_id = str(next(iter(goal_ids)))
    plan = api.post(f"/api/v1/intelligence/business-agent/goals/{goal_id}/plan", headers=ORIGIN)
    assert plan.status_code == 200, plan.text

    run_payload = {"idempotency_key": f"concurrent-run-{round_number}", "max_steps": 20}
    run_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
            json=run_payload,
            headers=ORIGIN,
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
            json=run_payload,
            headers=ORIGIN,
        ),
    )
    assert [response.status_code for response in run_responses] == [201, 201]
    run_ids = {response.json()["id"] for response in run_responses}
    assert len(run_ids) == 1
    run_id = str(next(iter(run_ids)))

    start_responses = _parallel(lambda: _start(api, run_id), lambda: _start(api, run_id))
    assert [response.status_code for response in start_responses] == [200, 200]
    assert {response.json()["status"] for response in start_responses} == {"WAITING_APPROVAL"}
    assert all(response.json()["result"]["external_writes"] == [] for response in start_responses)
    assert all(
        response.json()["result"]["integrated_slices"] == ["9A", "9B", "9C", "9D", "9E", "9F"]
        for response in start_responses
    )

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(BusinessAgentGoal)) == 1
        assert db.scalar(select(func.count()).select_from(BusinessAgentRun)) == 1
        assert db.scalar(select(func.count()).select_from(BusinessAgentAttempt)) == 9
        assert db.scalar(select(func.count()).select_from(BusinessAgentCheckpoint)) == 9
        assert db.scalar(select(func.count()).select_from(BusinessAgentToolInvocation)) == 9
        assert db.scalar(select(func.count()).select_from(BusinessAgentArtifact)) == 1
        assert db.scalar(select(func.count()).select_from(BusinessAgentFinding)) == 1
        assert db.scalar(select(func.count()).select_from(BusinessAgentApproval)) == 1
        steps = list(db.scalars(select(BusinessAgentStep).order_by(BusinessAgentStep.created_at)))
        assert [step.status for step in steps] == ["COMPLETED"] * 9
        assert all(step.dependency_keys for step in steps[1:])

    approval_id = _approval(api, run_id)
    approved = api.post(
        f"/api/v1/intelligence/business-agent/approvals/{approval_id}/approve",
        json={"note": "Concurrency certification approval."},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    retry_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{run_id}/retry", headers=ORIGIN
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{run_id}/retry", headers=ORIGIN
        ),
    )
    assert [response.status_code for response in retry_responses] == [200, 200]
    assert {response.json()["status"] for response in retry_responses} == {"COMPLETED"}

    approve_goal = _goal(api, f"approval-approve-{round_number}")
    approve_run = _run(api, str(approve_goal["id"]), f"approval-run-{round_number}")
    assert _start(api, str(approve_run["id"])).status_code == 200
    approve_id = _approval(api, str(approve_run["id"]))
    approve_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/approvals/{approve_id}/approve",
            json={"note": "Concurrent approve."},
            headers=ORIGIN,
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/approvals/{approve_id}/approve",
            json={"note": "Concurrent approve."},
            headers=ORIGIN,
        ),
    )
    assert [response.status_code for response in approve_responses] == [200, 200]
    assert {response.json()["status"] for response in approve_responses} == {"APPROVED"}

    mixed_goal = _goal(api, f"approval-mixed-{round_number}")
    mixed_run = _run(api, str(mixed_goal["id"]), f"mixed-run-{round_number}")
    assert _start(api, str(mixed_run["id"])).status_code == 200
    mixed_id = _approval(api, str(mixed_run["id"]))
    mixed_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/approvals/{mixed_id}/approve",
            json={"note": "Concurrent decision."},
            headers=ORIGIN,
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/approvals/{mixed_id}/reject",
            json={"note": "Concurrent decision."},
            headers=ORIGIN,
        ),
    )
    assert sorted(response.status_code for response in mixed_responses) == [200, 409]
    with factory() as db:
        mixed_approval = db.get(BusinessAgentApproval, mixed_id)
        assert mixed_approval is not None
        assert mixed_approval.status in {"APPROVED", "REJECTED"}

    lifecycle_goal = _goal(api, f"lifecycle-{round_number}")
    lifecycle_run = _run(api, str(lifecycle_goal["id"]), f"lifecycle-run-{round_number}")
    lifecycle_id = str(lifecycle_run["id"])
    lifecycle_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{lifecycle_id}/pause", headers=ORIGIN
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{lifecycle_id}/cancel", headers=ORIGIN
        ),
    )
    assert sorted(response.status_code for response in lifecycle_responses) in (
        [200, 200],
        [200, 409],
    )
    lifecycle_state = api.get(
        f"/api/v1/intelligence/business-agent/runs/{lifecycle_id}", headers=ORIGIN
    )
    assert lifecycle_state.status_code == 200
    assert lifecycle_state.json()["status"] in {"PAUSED", "CANCELLED"}

    resume_goal = _goal(api, f"resume-cancel-{round_number}")
    resume_run = _run(api, str(resume_goal["id"]), f"resume-cancel-run-{round_number}")
    resume_id = str(resume_run["id"])
    assert (
        api.post(
            f"/api/v1/intelligence/business-agent/runs/{resume_id}/pause", headers=ORIGIN
        ).status_code
        == 200
    )
    resume_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{resume_id}/resume", headers=ORIGIN
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{resume_id}/cancel", headers=ORIGIN
        ),
    )
    assert sorted(response.status_code for response in resume_responses) in ([200, 200], [200, 409])
    final_resume = api.get(f"/api/v1/intelligence/business-agent/runs/{resume_id}", headers=ORIGIN)
    assert final_resume.status_code == 200
    assert final_resume.json()["status"] == "CANCELLED"

    budget_goal = _goal(api, f"budget-race-{round_number}")
    budget_run = _run(api, str(budget_goal["id"]), f"budget-run-{round_number}", max_steps=1)
    budget_id = str(budget_run["id"])
    budget_responses = _parallel(lambda: _start(api, budget_id), lambda: _start(api, budget_id))
    assert [response.status_code for response in budget_responses] == [200, 200]
    budget = api.get(f"/api/v1/intelligence/business-agent/runs/{budget_id}", headers=ORIGIN)
    assert budget.status_code == 200
    assert budget.json()["status"] == "BUDGET_EXHAUSTED"
    assert budget.json()["usage"]["steps"] <= 1

    with factory() as db:
        budget_record = db.get(BusinessAgentRun, uuid.UUID(budget_id))
        assert budget_record is not None
        budget_record.budget = {**budget_record.budget, "max_steps": 20}
        db.commit()
    budget_retry_responses = _parallel(
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{budget_id}/retry", headers=ORIGIN
        ),
        lambda: api.post(
            f"/api/v1/intelligence/business-agent/runs/{budget_id}/retry", headers=ORIGIN
        ),
    )
    assert [response.status_code for response in budget_retry_responses] == [200, 200]
    assert {response.json()["status"] for response in budget_retry_responses} == {
        "WAITING_APPROVAL"
    }

    with factory() as db:
        budget_attempts = list(
            db.scalars(select(BusinessAgentAttempt).where(BusinessAgentAttempt.run_id == budget_id))
        )
        budget_artifacts = list(
            db.scalars(
                select(BusinessAgentArtifact).where(BusinessAgentArtifact.run_id == budget_id)
            )
        )
        budget_findings = list(
            db.scalars(select(BusinessAgentFinding).where(BusinessAgentFinding.run_id == budget_id))
        )
        budget_approvals = list(
            db.scalars(
                select(BusinessAgentApproval).where(BusinessAgentApproval.run_id == budget_id)
            )
        )
        assert len(budget_attempts) == 9
        assert len(budget_artifacts) == 1
        assert len(budget_findings) == 1
        assert len(budget_approvals) == 1

    with factory() as db:
        goals = list(db.scalars(select(BusinessAgentGoal)))
        plans = list(db.scalars(select(BusinessAgentPlan)))
        runs = list(db.scalars(select(BusinessAgentRun)))
        attempts = list(db.scalars(select(BusinessAgentAttempt)))
        invocations = list(db.scalars(select(BusinessAgentToolInvocation)))
        artifacts = list(db.scalars(select(BusinessAgentArtifact)))
        findings = list(db.scalars(select(BusinessAgentFinding)))
        approvals = list(db.scalars(select(BusinessAgentApproval)))
        assert len({(item.owner_id, item.idempotency_key) for item in goals}) == len(goals)
        assert len({(item.owner_id, item.idempotency_key) for item in runs}) == len(runs)
        assert len({(item.run_id, item.step_id, item.attempt_number) for item in attempts}) == len(
            attempts
        )
        assert len(
            {(item.run_id, item.step_id, item.capability_id) for item in invocations}
        ) == len(invocations)
        assert len({item.run_id for item in approvals}) == len(approvals)
        goal_ids = {item.id for item in goals}
        plan_ids = {item.id for item in plans}
        run_ids = {item.id for item in runs}
        step_ids = {item.id for item in db.scalars(select(BusinessAgentStep))}
        assert all(item.goal_id in goal_ids and item.plan_id in plan_ids for item in runs)
        assert all(item.run_id in run_ids for item in artifacts)
        assert all(item.run_id in run_ids for item in findings)
        assert all(item.run_id in run_ids and item.step_id in step_ids for item in attempts)
        assert all(item.run_id in run_ids and item.step_id in step_ids for item in invocations)
        assert all(item.run_id in run_ids for item in db.scalars(select(BusinessAgentCheckpoint)))
        assert all(item.run_id in run_ids for item in approvals)
        assert all(
            item.status in {"COMPLETED", "WAITING_APPROVAL", "CANCELLED", "BUDGET_EXHAUSTED"}
            for item in runs
        )
        assert all(
            item.status in {"COMPLETED", "QUEUED", "RUNNING"}
            for item in db.scalars(select(BusinessAgentStep))
        )
        assert all(
            int(item.usage.get("steps", 0)) <= int(item.budget.get("max_steps", 20))
            for item in runs
        )

    doctor = api.get("/api/v1/intelligence/business-agent/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["status"] == "PASS"
    assert doctor.json()["checks"]["duplicate_idempotency"] == 0
