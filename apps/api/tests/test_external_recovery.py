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
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_recovery_catalog_and_idempotent_execution(client) -> None:
    setup_context(client)
    catalog = client.get("/api/v1/intelligence/external/recovery/catalog")
    assert catalog.status_code == 200
    assert "reconcile" in catalog.json()["actions"]
    payload = {
        "action": "retry_after",
        "failure_code": "search_rate_limited",
        "idempotency_key": f"recovery-{uuid.uuid4()}",
        "correlation_id": "corr-recovery",
    }
    first = client.post("/api/v1/intelligence/external/recovery", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/intelligence/external/recovery", json=payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["idempotent_reuse"] is False
    assert second.json()["idempotent_reuse"] is True
    assert second.json()["available_actions"] == ["retry_after", "review_source", "cancel"]


@pytest.mark.parametrize(
    ("failure", "actions"),
    [
        ("unsafe_url", ["review_source", "skip_optional_source", "cancel"]),
        ("budget_exhausted", ["review_source", "skip_optional_source", "cancel"]),
        ("checkpoint_invalid", ["retry", "reconcile", "cancel"]),
    ],
)
def test_recovery_safety_matrix(client, failure: str, actions: list[str]) -> None:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/external/recovery",
        json={
            "action": actions[0],
            "failure_code": failure,
            "idempotency_key": f"matrix-{failure}-{uuid.uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert response.json()["available_actions"] == actions
