"""Focused 11G Review Intelligence Business Agent integration coverage."""

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
REVIEW_CAPABILITIES = {
    "REVIEW_INGESTION",
    "REVIEW_ANALYSIS",
    "REVIEW_GAP_ANALYSIS",
    "REVIEW_CHANGE_ANALYSIS",
    "REVIEW_WINNING_PRODUCT_PROJECTION",
}
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


def _setup_owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Review Agent Owner",
            "email": "review-agent@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_review_capabilities_plan_run_and_operations_are_bounded(client: TestClient) -> None:
    _setup_owner(client)

    capabilities = client.get("/api/v1/intelligence/business-agent/capabilities", headers=ORIGIN)
    assert capabilities.status_code == 200
    review_specs = {
        item["id"]: item for item in capabilities.json() if item["id"] in REVIEW_CAPABILITIES
    }
    assert set(review_specs) == REVIEW_CAPABILITIES
    assert all(item["side_effect_class"] == "INTERNAL_WRITE" for item in review_specs.values())
    assert all(item["availability"] == "LOCAL" for item in review_specs.values())

    legacy = client.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": "Find three winning products for Amazon India within INR 300000 capital.",
            "idempotency_key": "review-legacy-goal",
        },
        headers=ORIGIN,
    )
    assert legacy.status_code == 201, legacy.text
    legacy_plan = client.post(
        f"/api/v1/intelligence/business-agent/goals/{legacy.json()['id']}/plan",
        headers=ORIGIN,
    )
    assert legacy_plan.status_code == 200
    assert len(legacy_plan.json()["steps"]) == 9
    assert not any(
        step["capability_id"] in REVIEW_CAPABILITIES for step in legacy_plan.json()["steps"]
    )

    goal = client.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": (
                "Find winning products using Review Intelligence customer-feedback evidence."
            ),
            "idempotency_key": "review-enabled-goal",
            "structured_goal": {
                "marketplace": "AMAZON_IN",
                "include_review_intelligence": True,
            },
        },
        headers=ORIGIN,
    )
    assert goal.status_code == 201, goal.text
    goal_id = goal.json()["id"]
    plan = client.post(f"/api/v1/intelligence/business-agent/goals/{goal_id}/plan", headers=ORIGIN)
    assert plan.status_code == 200, plan.text
    assert {step["capability_id"] for step in plan.json()["steps"]} >= REVIEW_CAPABILITIES
    assert all(
        step["side_effect_class"] == "INTERNAL_WRITE"
        for step in plan.json()["steps"]
        if step["capability_id"] in REVIEW_CAPABILITIES
    )

    created = client.post(
        f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
        json={"idempotency_key": "review-enabled-run", "max_steps": 20},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    started = client.post(
        f"/api/v1/intelligence/business-agent/runs/{created.json()['id']}/start",
        headers=ORIGIN,
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "WAITING_APPROVAL"
    assert body["result"]["review_enabled"] is True
    assert set(body["result"]["review_capabilities"]) == REVIEW_CAPABILITIES
    assert body["result"]["external_writes"] == []
    assert body["result"]["review_evidence_gaps"]
    assert body["artifacts"]
    assert body["findings"]
    assert all(
        item["evidence_ids"]
        for item in body["findings"]
        if item["finding_type"].startswith("REVIEW_")
    )
    serialized = started.text
    assert "Ignore previous" not in serialized
    assert "provider output" not in serialized.casefold()
    assert "token" not in serialized.casefold()

    operations = client.get("/api/v1/intelligence/business-agent/operations/review", headers=ORIGIN)
    assert operations.status_code == 200, operations.text
    assert operations.json()["owner_scoped"] is True
    assert operations.json()["review_runs"] == 1
    assert operations.json()["external_writes"] == []

    doctor = client.get("/api/v1/intelligence/business-agent/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS"
    counters = doctor.json()["checks"]["review_hard_counters"]
    assert counters["total"] == 0
    assert doctor.json()["checks"]["review"]["external_writes"] is False
