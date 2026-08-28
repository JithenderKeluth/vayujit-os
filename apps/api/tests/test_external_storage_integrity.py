from __future__ import annotations

import uuid
from typing import Any

import pytest
import test_ai_integration as integration
from sqlalchemy import func, select

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalFetch,
    ExternalSearchRequest,
    ExternalSearchResult,
)
from vayujit_api.intelligence.external_projection import storage_counts, table_inventory

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _mission_and_task(client: Any, product_id: str) -> tuple[str, str]:
    response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "PRODUCT_VALIDATION",
            "goal": "Validate external product evidence.",
            "product_id": product_id,
            "source_policy": {
                "external_research_enabled": True,
                "allowed_domains": ["example.org"],
            },
            "idempotency_key": f"storage-{uuid.uuid4()}",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    mission_id = response.json()["id"]
    plan = client.get(f"/api/v1/intelligence/autonomous/missions/{mission_id}/plan", headers=ORIGIN)
    assert plan.status_code == 200, plan.text
    task_id = plan.json()["tasks"][0]["id"]
    return mission_id, task_id


def test_external_storage_ledger_canonical_flow_and_replay(client: Any) -> None:
    context = integration.setup_context(client)
    mission_id, task_id = _mission_and_task(client, context["product"]["id"])
    tables = client.get("/api/v1/intelligence/external/tables", headers=ORIGIN)
    assert tables.status_code == 200, tables.text
    table_names = {row["table"] for row in tables.json()}
    assert table_names == {row["table"] for row in table_inventory()}
    assert len(table_names) == 18

    assert integration.factory is not None
    with integration.factory() as db:
        owner = db.scalar(
            select(integration.User).where(integration.User.email == "owner@example.com")
        )
        assert owner is not None
        before = storage_counts(db, owner)

    search_payload = {
        "query": f"storage-ledger-{uuid.uuid4()}",
        "allowed_domains": ["example.org"],
        "mission_id": mission_id,
        "task_id": task_id,
        "max_results": 2,
    }
    search = client.post(
        "/api/v1/intelligence/external/search", json=search_payload, headers=ORIGIN
    )
    assert search.status_code == 200, search.text
    result = search.json()["results"][0]
    fetch_payload = {
        "url": result["canonical_url"],
        "allowed_domains": ["example.org"],
        "mission_id": mission_id,
        "task_id": task_id,
        "search_result_id": result["id"],
    }
    fetch = client.post("/api/v1/intelligence/external/fetch", json=fetch_payload, headers=ORIGIN)
    assert fetch.status_code == 200, fetch.text

    with integration.factory() as db:
        owner = db.scalar(
            select(integration.User).where(integration.User.email == "owner@example.com")
        )
        assert owner is not None
        after = storage_counts(db, owner)
        assert (
            after["intelligence_external_search_requests"]
            == before["intelligence_external_search_requests"] + 1
        )
        assert (
            after["intelligence_external_search_results"]
            > before["intelligence_external_search_results"]
        )
        assert after["intelligence_external_fetches"] == before["intelligence_external_fetches"] + 1
        assert (
            after["intelligence_external_executions"]
            == before["intelligence_external_executions"] + 2
        )
        assert (
            after["intelligence_autonomous_evidence"]
            == before["intelligence_autonomous_evidence"] + 1
        )
        assert all(value >= before[name] for name, value in after.items())

    replay_search = client.post(
        "/api/v1/intelligence/external/search", json=search_payload, headers=ORIGIN
    )
    replay_fetch = client.post(
        "/api/v1/intelligence/external/fetch", json=fetch_payload, headers=ORIGIN
    )
    assert replay_search.status_code == replay_fetch.status_code == 200
    with integration.factory() as db:
        owner = db.scalar(
            select(integration.User).where(integration.User.email == "owner@example.com")
        )
        assert owner is not None
        replay = storage_counts(db, owner)
        assert replay == after
        assert (
            db.scalar(
                select(func.count())
                .select_from(ExternalSearchRequest)
                .where(ExternalSearchRequest.owner_id == owner.id)
            )
            == after["intelligence_external_search_requests"]
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ExternalSearchResult)
                .where(ExternalSearchResult.owner_id == owner.id)
            )
            == after["intelligence_external_search_results"]
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ExternalFetch)
                .where(ExternalFetch.owner_id == owner.id)
            )
            == after["intelligence_external_fetches"]
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ExternalExecution)
                .where(ExternalExecution.owner_id == owner.id)
            )
            == after["intelligence_external_executions"]
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchEvidence)
                .where(AutonomousResearchEvidence.owner_id == owner.id)
            )
            == after["intelligence_autonomous_evidence"]
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AutonomousResearchMission)
                .where(AutonomousResearchMission.owner_id == owner.id)
            )
            == 1
        )
        assert (
            int(
                db.scalar(
                    select(func.count())
                    .select_from(AutonomousResearchTask)
                    .where(AutonomousResearchTask.owner_id == owner.id)
                )
                or 0
            )
            >= 1
        )


def test_external_integrity_is_database_derived_and_owner_scoped(client: Any) -> None:
    integration.setup_context(client)
    response = client.get("/api/v1/intelligence/external/integrity", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classification"] == "PASS"
    assert body["cross_owner_leakage"] == 0
    assert all(value == 0 for value in body["duplicates"].values())
    assert all(value == 0 for value in body["orphans"].values())
    assert all(value == 0 for value in body["broken_lineage"].values())
    assert body["storage"]
    assert "password" not in response.text.lower()
