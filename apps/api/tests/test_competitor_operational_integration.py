"""Focused Slice 10F Business Agent competitor integration coverage."""

from __future__ import annotations

import os
import statistics
import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.intelligence.business_agent_models import (
    BusinessAgentArtifact,
    BusinessAgentToolInvocation,
)
from vayujit_api.intelligence.competitor_commercial_models import CompetitorCommercialAnalysis
from vayujit_api.intelligence.competitor_discovery_models import (
    CompetitorDiscoveryRequest,
)
from vayujit_api.intelligence.competitor_models import CompetitorContext
from vayujit_api.intelligence.competitor_winning_product_models import (
    CompetitorWinningProductProjection,
)
from vayujit_api.intelligence.product_opportunity_intelligence_models import (
    ProductOpportunityIntelligenceOutput,
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
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Competitor Agent Owner",
            "email": "competitor-agent@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def test_competitor_capabilities_are_internal_and_external_write_stays_disabled(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, _ = client
    _owner(api)
    capabilities = api.get("/api/v1/intelligence/business-agent/capabilities", headers=ORIGIN)
    assert capabilities.status_code == 200, capabilities.text
    values = {item["id"]: item for item in capabilities.json()}
    for key in ("COMPETITOR_DISCOVERY", "COMPETITOR_ANALYSIS", "COMPETITOR_CHANGE_ANALYSIS"):
        assert values[key]["side_effect_class"] == "INTERNAL_WRITE"
        assert values[key]["availability"] == "LOCAL"
    assert values["external.write"]["availability"] == "DISABLED"


def test_competitor_business_agent_run_projects_evidence_and_waits_for_approval(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _owner(api)
    goal = api.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": "Find competitor-backed winning products for Amazon India.",
            "structured_goal": {
                "marketplace": "AMAZON_IN",
                "capital": 300000,
                "include_competitor_intelligence": True,
            },
            "idempotency_key": "10f-goal",
        },
        headers=ORIGIN,
    )
    assert goal.status_code == 201, goal.text
    plan = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal.json()['id']}/plan", headers=ORIGIN
    )
    assert plan.status_code == 200, plan.text
    plan_steps = plan.json()["steps"]
    assert {item["capability_id"] for item in plan_steps} >= {
        "COMPETITOR_DISCOVERY",
        "COMPETITOR_ANALYSIS",
        "COMPETITOR_CHANGE_ANALYSIS",
    }
    assert any(item["side_effect_class"] == "INTERNAL_WRITE" for item in plan_steps)

    run = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal.json()['id']}/runs",
        json={"idempotency_key": "10f-run", "max_steps": 20},
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    started = api.post(
        f"/api/v1/intelligence/business-agent/runs/{run.json()['id']}/start", headers=ORIGIN
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "WAITING_APPROVAL", body
    assert body["result"]["external_writes"] == []
    assert {"10A", "10B", "10C", "10D", "10E", "10F"} <= set(body["result"]["integrated_slices"])
    assert body["artifacts"]
    assert "competitor_intelligence" in body["artifacts"][0]["payload"]
    assert body["tool_invocations"]

    with factory() as db:
        assert db.scalar(select(CompetitorContext)) is not None
        assert db.scalar(select(CompetitorDiscoveryRequest)) is not None
        assert db.scalar(select(CompetitorCommercialAnalysis)) is not None
        assert db.scalar(select(CompetitorWinningProductProjection)) is not None
        assert (
            db.scalar(
                select(ProductOpportunityIntelligenceOutput).where(
                    ProductOpportunityIntelligenceOutput.kind == "competition"
                )
            )
            is not None
        )
        assert db.scalar(select(BusinessAgentArtifact)) is not None
        assert db.scalar(select(BusinessAgentToolInvocation)) is not None
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "business_agent.competitor.capability_invoked" in actions


def test_competitor_run_read_projection_stays_bounded(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _owner(api)
    goal = api.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": "Evaluate competitor intelligence for Amazon India.",
            "structured_goal": {
                "marketplace": "AMAZON_IN",
                "capital": 100000,
                "competitor_intelligence": True,
            },
            "idempotency_key": "10f-benchmark-goal",
        },
        headers=ORIGIN,
    )
    assert goal.status_code == 201, goal.text
    run = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal.json()['id']}/runs",
        json={"idempotency_key": "10f-benchmark-run", "max_steps": 20},
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    started = api.post(
        f"/api/v1/intelligence/business-agent/runs/{run.json()['id']}/start", headers=ORIGIN
    )
    assert started.status_code == 200, started.text

    statements = {"count": 0}

    def count_queries(*_args: object) -> None:
        statements["count"] += 1

    engine = factory.kw["bind"]
    event.listen(engine, "after_cursor_execute", count_queries)
    samples: list[tuple[int, float]] = []
    try:
        for _ in range(3):
            statements["count"] = 0
            started_at = time.perf_counter()
            response = api.get(
                f"/api/v1/intelligence/business-agent/runs/{run.json()['id']}", headers=ORIGIN
            )
            elapsed = time.perf_counter() - started_at
            assert response.status_code == 200, response.text
            samples.append((statements["count"], elapsed))
    finally:
        event.remove(engine, "after_cursor_execute", count_queries)
    assert max(item[0] for item in samples) <= 30
    assert statistics.median(item[1] for item in samples) < 2
