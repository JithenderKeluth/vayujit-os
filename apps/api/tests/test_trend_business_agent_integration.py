"""Focused 12G Trend integration coverage through the existing Business Agent runtime."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    assert TEST_DATABASE_URL is not None and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Trend Agent Owner",
            "email": "trend-agent@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_trend_opt_in_plan_run_and_operations_are_bounded(client: TestClient) -> None:
    _owner(client)
    goal_response = client.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": "Evaluate products for Amazon India within INR 300000 capital.",
            "idempotency_key": "trend-goal-1",
            "include_trend_intelligence": True,
            "provenance": {"source": "owner_input"},
        },
        headers=ORIGIN,
    )
    assert goal_response.status_code == 201, goal_response.text
    goal = goal_response.json()
    assert goal["structured_goal"]["include_trend_intelligence"] is True

    plan_response = client.post(
        f"/api/v1/intelligence/business-agent/goals/{goal['id']}/plan", headers=ORIGIN
    )
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()
    trend_ids = [
        "TREND_CONTEXT_RESOLUTION",
        "TREND_INGESTION",
        "TREND_ANALYSIS",
        "TREND_CHANGE_ANALYSIS",
        "TREND_VALIDATION",
        "TREND_WINNING_PRODUCT_PROJECTION",
    ]
    step_ids = [step["capability_id"] for step in plan["steps"]]
    positions = [step_ids.index(capability_id) for capability_id in trend_ids]
    assert positions == sorted(positions)
    assert all(plan["steps"][index]["side_effect_class"] == "INTERNAL_WRITE" for index in positions)

    run_response = client.post(
        f"/api/v1/intelligence/business-agent/goals/{goal['id']}/runs",
        json={"idempotency_key": "trend-run-1", "max_steps": 32},
        headers=ORIGIN,
    )
    assert run_response.status_code == 201, run_response.text
    run_id = run_response.json()["id"]
    started = client.post(
        f"/api/v1/intelligence/business-agent/runs/{run_id}/start", headers=ORIGIN
    )
    assert started.status_code == 200, started.text
    result = started.json()
    assert result["status"] == "WAITING_APPROVAL"
    assert result["result"]["trend_enabled"] is True
    assert result["result"]["trend_capabilities"] == trend_ids
    assert result["result"]["trend_evidence_gaps"]
    assert result["result"]["external_writes"] == []
    brief_artifact = next(
        item for item in result["artifacts"] if item["artifact_type"] == "BUSINESS_DECISION_BRIEF"
    )
    assert brief_artifact["payload"]["trend_intelligence"]["semantic_boundary"]

    operations = client.get("/api/v1/intelligence/business-agent/operations/trend", headers=ORIGIN)
    assert operations.status_code == 200, operations.text
    operations_body = operations.json()
    assert operations_body["trend_runs"] == 1
    assert operations_body["external_writes"] == []
    assert operations_body["calendar_events"] == 0
    assert operations_body["worker_scheduler"] == "EXISTING BUSINESS AGENT RUNTIME"

    doctor = client.get("/api/v1/intelligence/business-agent/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200, doctor.text
    doctor_body = doctor.json()
    assert doctor_body["status"] == "PASS"
    assert doctor_body["checks"]["trend_hard_counters"]["total"] == 0
