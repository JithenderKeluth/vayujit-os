from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence, SupplierSearch

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_provider_neutral_supplier_research_local_fixture_is_bounded_and_replayable(
    client: Any,
) -> None:
    setup_context(client)
    operations = client.get("/api/v1/intelligence/suppliers/operations", headers=ORIGIN)
    assert operations.status_code == 200, operations.text
    assert operations.json()["provider_neutral_discovery"] == "LOCAL_FIXTURE"
    assert operations.json()["live_discovery"] == "PENDING_EXTERNAL_PROVIDER"
    payload = {
        "product_query": "stainless-steel insulated water bottles",
        "country": "India",
        "manufacturer_preferred": True,
        "max_candidates": 7,
        "idempotency_key": "14f-canonical-1",
    }
    first = client.post("/api/v1/intelligence/suppliers/research", json=payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "completed"
    result = body["result"]
    assert result["provider"] == "provider-neutral-local-fixture"
    assert result["budget"]["max_candidates"] == 7
    assert result["external_calls"] is False
    assert result["accepted_candidate_count"] >= 1
    assert result["possible_duplicates"] >= 1
    assert result["contradictions"] >= 1
    assert result["prompt_injection"]["instructions_executable"] is False
    assert result["failures"]

    replay = client.post("/api/v1/intelligence/suppliers/research", json=payload, headers=ORIGIN)
    assert replay.status_code == 200, replay.text
    assert replay.json()["request"]["id"] == body["request"]["id"]

    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert (
            db.scalar(select(SupplierSearch).where(SupplierSearch.id == body["request"]["id"]))
            is not None
        )
        supplier_count = int(db.scalar(select(func.count()).select_from(Supplier)))
        evidence_count = int(db.scalar(select(func.count()).select_from(SupplierEvidence)))
        assert supplier_count >= 1
        assert evidence_count >= 1


def test_provider_neutral_supplier_research_zero_result_is_successful(client: Any) -> None:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/suppliers/research",
        json={"product_query": "zero result supplier", "idempotency_key": "14f-zero-1"},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["status"] == "COMPLETED"
    assert result["candidate_count"] == 0
    assert result["accepted_candidate_count"] == 0
    assert result["failures"] == []
