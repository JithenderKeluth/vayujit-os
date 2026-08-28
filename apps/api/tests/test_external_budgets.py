from __future__ import annotations

import os

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_WEB_FETCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS"] = "example.org"


import uuid

import pytest
import test_ai_integration as integration
from fastapi import HTTPException
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission
from vayujit_api.intelligence.external_durability import (
    BudgetExhausted,
    consume_budget,
    normalize_budget_policy,
)
from vayujit_api.intelligence.external_models import ExternalResearchBudget

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _mission(client, budget: dict[str, object]) -> str:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "TREND_RESEARCH",
            "goal": "Bounded external budget test",
            "source_policy": {"external_research_enabled": True},
            "budget_policy": budget,
            "idempotency_key": f"budget-{uuid.uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_budget_policy_rejects_invalid_and_caps_platform_values() -> None:
    with pytest.raises(HTTPException):
        normalize_budget_policy({"max_searches": 0})
    with pytest.raises(HTTPException):
        normalize_budget_policy({"max_fetches": -1})
    with pytest.raises(HTTPException):
        normalize_budget_policy({"max_results": "10"})
    policy = normalize_budget_policy({"max_searches": 999999})
    assert policy.max_searches == 1000


def test_budget_snapshot_and_atomic_exhaustion(client) -> None:
    mission_id = _mission(client, {"max_searches": 1, "max_results": 2})
    first = client.get(f"/api/v1/intelligence/external/budgets/{mission_id}", headers=ORIGIN)
    assert first.status_code == 200
    assert first.json()["max_searches"] == 1
    assert first.json()["searches_used"] == 0
    context = {"mission_id": mission_id, "allowed_domains": ["example.org"], "max_results": 1}
    search = client.post(
        "/api/v1/intelligence/external/search", json={"query": "budget", **context}, headers=ORIGIN
    )
    assert search.status_code == 200, search.text
    repeated = client.post(
        "/api/v1/intelligence/external/search",
        json={"query": "different", **context},
        headers=ORIGIN,
    )
    assert repeated.status_code == 429
    assert "budget exhausted safely" in repeated.text.lower()
    final = client.get(f"/api/v1/intelligence/external/budgets/{mission_id}", headers=ORIGIN).json()
    assert final["searches_used"] == 1


def test_budget_ledger_rejects_overconsumption(client) -> None:
    _mission(client, {"max_results": 1})
    assert integration.factory is not None
    with integration.factory() as db:
        mission = db.scalar(select(AutonomousResearchMission))
        if mission is None:
            pytest.skip("fixture mission is created by the integration test")
        budget = db.scalar(
            select(ExternalResearchBudget).where(ExternalResearchBudget.mission_id == mission.id)
        )
        if budget is None:
            pytest.skip("fixture budget is not available")
        budget.max_results = 1
        db.commit()
        with pytest.raises(BudgetExhausted):
            consume_budget(db, budget, dimension="results", amount=budget.max_results + 1)
