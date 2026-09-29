from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import test_ai_integration
from fastapi import HTTPException
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.intelligence import supplier_research
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
    # Test configuration enables the validated Brave read-only provider; this is no longer pending.
    assert operations.json()["live_discovery"] == "LIVE_READY"
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


def test_provider_neutral_supplier_research_live_mode_uses_existing_boundaries(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    result_id = uuid.uuid4()
    row = SimpleNamespace(
        id=result_id,
        canonical_url="https://example.org/suppliers/acme",
        url="https://example.org/suppliers/acme",
        domain="example.org",
        title="Acme Bottle Manufacturer",
        snippet="Manufacturer of stainless steel insulated water bottles in India.",
        provider="brave",
        provider_result_id="brave-acme-1",
        rank=1,
        retrieved_at=datetime.now(UTC),
    )
    calls: list[str] = []

    def fake_search(_db: Any, _owner: Any, request: Any) -> dict[str, object]:
        calls.append(request.query)
        return {"id": uuid.uuid4(), "results": [row]}

    def fake_fetch(_db: Any, _owner: Any, request: Any) -> dict[str, object]:
        assert request.url == row.canonical_url
        assert request.allowed_domains == ["example.org"]
        return {
            "extracted": {
                "text": (
                    "Company Name: Acme Bottle Works. Address: Pune, India. "
                    "Manufacturer of stainless steel insulated water bottles. OEM capability."
                ),
                "prompt_injection": {"instructions_executable": False},
            }
        }

    monkeypatch.setattr(supplier_research, "external_search", fake_search)
    monkeypatch.setattr(supplier_research, "external_fetch", fake_fetch)
    response = client.post(
        "/api/v1/intelligence/suppliers/research",
        json={
            "product_query": "stainless steel insulated bottle",
            "country": "India",
            "mode": "LIVE_READ_ONLY",
            "approved_domains": ["example.org"],
            "max_candidates": 2,
            "idempotency_key": "14f-live-boundary-1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["live_discovery"] == "LIVE_READY"
    assert body["external_calls"] is True
    assert body["result"]["mode"] == "LIVE_READ_ONLY"
    assert body["result"]["provider"] == "brave"
    assert body["result"]["researched_count"] == 1
    assert body["result"]["accepted_candidate_count"] == 1
    assert calls


def test_live_supplier_research_preserves_fetch_approval_required(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)
    row = SimpleNamespace(
        id=uuid.uuid4(),
        canonical_url="https://supplier.example/supplier",
        url="https://supplier.example/supplier",
        domain="supplier.example",
        title="Supplier Manufacturer",
        snippet="Manufacturer website",
        provider="brave",
        provider_result_id="brave-blocked-1",
        rank=1,
        retrieved_at=datetime.now(UTC),
    )
    fetch_called = False

    monkeypatch.setattr(
        supplier_research,
        "external_search",
        lambda *_args, **_kwargs: {"id": uuid.uuid4(), "results": [row]},
    )

    def forbidden_fetch(*_args: Any, **_kwargs: Any) -> dict[str, object]:
        nonlocal fetch_called
        fetch_called = True
        return {}

    monkeypatch.setattr(supplier_research, "external_fetch", forbidden_fetch)
    response = client.post(
        "/api/v1/intelligence/suppliers/research",
        json={
            "product_query": "bottle manufacturer",
            "mode": "LIVE_READ_ONLY",
            "approved_domains": ["example.org"],
            "idempotency_key": "14f-live-approval-1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["status"] == "COMPLETED"
    assert result["accepted_candidate_count"] == 0
    assert result["failures"][0]["failure_code"] == "FETCH_APPROVAL_REQUIRED"
    assert fetch_called is False


def test_live_supplier_research_provider_failure_is_safe_and_does_not_fallback(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_context(client)

    def unavailable_search(*_args: Any, **_kwargs: Any) -> dict[str, object]:
        raise HTTPException(502, "External search failed safely.")

    monkeypatch.setattr(supplier_research, "external_search", unavailable_search)
    response = client.post(
        "/api/v1/intelligence/suppliers/research",
        json={
            "product_query": "stainless steel bottle manufacturer",
            "mode": "LIVE_READ_ONLY",
            "approved_domains": ["example.org"],
            "idempotency_key": "14f-live-provider-failure-1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["live_discovery"] == "LIVE_CONFIGURATION_INCOMPLETE"
    assert body["external_calls"] is False
    assert body["result"]["failure_code"] == "DISCOVERY_PROVIDER_UNAVAILABLE"
    assert body["result"]["safe_error"] == (
        "Live supplier discovery is unavailable under the current configuration."
    )
    assert "External search failed safely." not in response.text
    assert "provider-neutral-local-fixture" not in response.text


def test_supplier_research_results_projection_is_bounded_and_read_only(client: Any) -> None:
    setup_context(client)
    response = client.post(
        "/api/v1/intelligence/suppliers/research",
        json={
            "product_query": "gp4 disposable bottle",
            "category": "drinkware",
            "mode": "LOCAL_FIXTURE",
            "idempotency_key": "gp4-results-projection-1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    projection = client.get("/api/v1/intelligence/suppliers/research-results", headers=ORIGIN)
    assert projection.status_code == 200, projection.text
    body = projection.json()
    assert body["research"]["mode"] == "LOCAL_FIXTURE"
    assert body["research"]["external_calls"] is False
    assert body["external_write"] is False
    assert len(body["suppliers"]) <= 20
    assert body["next_action"] in {"Review supplier candidates", "Review supplier research gaps"}
