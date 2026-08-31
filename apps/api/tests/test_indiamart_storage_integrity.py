from __future__ import annotations

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchEvidence,
    AutonomousResearchRecovery,
    AutonomousResearchReport,
)
from vayujit_api.intelligence.indiamart_models import (
    IndiaMartDiscoveryRequest,
    IndiaMartDiscoveryResult,
)
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _counts(db) -> dict[str, int]:
    models = {
        "indiamart_requests": IndiaMartDiscoveryRequest,
        "indiamart_results": IndiaMartDiscoveryResult,
        "supplier_candidates": Supplier,
        "supplier_evidence": SupplierEvidence,
        "autonomous_evidence": AutonomousResearchEvidence,
        "changes": AutonomousResearchChange,
        "alerts": AutonomousResearchAlert,
        "recovery": AutonomousResearchRecovery,
        "reports": AutonomousResearchReport,
    }
    return {
        name: int(db.scalar(select(func.count()).select_from(model)) or 0)
        for name, model in models.items()
    }


def test_indiamart_storage_ledger_and_replay_have_zero_delta(client: TestClient) -> None:
    context = setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        before = _counts(db)
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_DISCOVERY",
            "goal": "Canonical IndiaMART storage flow",
            "market": "IN",
            "category": "outdoors",
            "provider_mode": "LOCAL_DETERMINISTIC",
            "idempotency_key": "storage-ledger-mission",
        },
        headers=ORIGIN,
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    plan = client.get(f"/api/v1/intelligence/autonomous/missions/{mission_id}/plan", headers=ORIGIN)
    assert plan.status_code == 200
    task_id = plan.json()["tasks"][0]["id"]
    payload = {
        "query": "storage ledger",
        "product_id": context["product"]["id"],
        "mission_id": mission_id,
        "task_id": task_id,
        "idempotency_key": "storage-ledger-discovery",
    }
    first = client.post("/api/v1/intelligence/indiamart/discover", json=payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    first_ids = {row["id"] for row in first.json()["results"]}
    for result in first.json()["results"]:
        handoff = client.post(
            f"/api/v1/intelligence/indiamart/discoveries/{result['id']}/evidence",
            json={"mission_id": mission_id, "task_id": task_id},
            headers=ORIGIN,
        )
        assert handoff.status_code == 200, handoff.text
    with test_ai_integration.factory() as db:
        after = _counts(db)
    replay = client.post("/api/v1/intelligence/indiamart/discover", json=payload, headers=ORIGIN)
    assert replay.status_code == 200
    assert {row["id"] for row in replay.json()["results"]} == first_ids
    with test_ai_integration.factory() as db:
        after_replay = _counts(db)
    assert all(after[name] >= before[name] for name in before)
    assert after_replay == after


def test_indiamart_integrity_exposes_zero_duplicate_orphan_lineage_owner_counters(
    client: TestClient,
) -> None:
    context = setup_context(client)
    discovery = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "integrity counters", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert discovery.status_code == 200, discovery.text
    response = client.get("/api/v1/intelligence/indiamart/integrity", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classification"] == "PASS"
    assert all(value == 0 for value in body["duplicates"].values())
    assert all(value == 0 for value in body["orphans"].values())
    assert all(value == 0 for value in body["broken_lineage"].values())
    assert all(value == 0 for value in body["cross_owner"].values())
