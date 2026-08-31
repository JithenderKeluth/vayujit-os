from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence import indiamart_service
from vayujit_api.intelligence.indiamart import provider_preflight
from vayujit_api.intelligence.indiamart_models import (
    IndiaMartDiscoveryRequest,
    IndiaMartDiscoveryResult,
)
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_provider_mode_matrix_is_network_free() -> None:
    cases = (
        (Settings(indiamart_mode="DISABLED", indiamart_enabled=False), "DISABLED"),
        (Settings(indiamart_mode="LOCAL_FIXTURE", indiamart_enabled=True), "READY"),
        (Settings(indiamart_mode="LIVE_READ_ONLY", indiamart_enabled=True), "NOT_CONFIGURED"),
        (
            Settings(
                indiamart_mode="LIVE_READ_ONLY",
                indiamart_enabled=True,
                indiamart_base_url="not-a-url",
            ),
            "NOT_CONFIGURED",
        ),
    )
    for settings, expected in cases:
        result = provider_preflight(settings)
        assert result["status"] == expected
        assert result["network_call"] is False
        assert result["read_only"] is True


def test_service_preflight_matrix_is_fail_closed() -> None:
    assert (
        indiamart_service.preflight(
            Settings(indiamart_mode="LOCAL_FIXTURE", indiamart_enabled=True)
        )["status"]
        == "READY"
    )
    assert (
        indiamart_service.preflight(Settings(indiamart_mode="DISABLED", indiamart_enabled=False))[
            "status"
        ]
        == "DISABLED"
    )
    assert (
        indiamart_service.preflight(
            Settings(indiamart_mode="LIVE_READ_ONLY", indiamart_enabled=True)
        )["status"]
        == "BLOCKED_BY_EXTERNAL_CONFIGURATION"
    )
    assert (
        indiamart_service.preflight(
            Settings(
                indiamart_mode="LOCAL_FIXTURE",
                indiamart_enabled=True,
                intelligence_external_kill_switch=True,
            )
        )["status"]
        == "KILL_SWITCHED"
    )
    assert (
        indiamart_service.preflight(
            Settings(
                indiamart_mode="LOCAL_FIXTURE",
                indiamart_enabled=True,
                external_mutations_emergency_stop=True,
            )
        )["status"]
        == "KILL_SWITCHED"
    )


def test_read_only_boundary_has_no_contact_or_purchase_routes(client: TestClient) -> None:
    setup_context(client)
    for action in (
        "contact",
        "message",
        "email",
        "phone",
        "whatsapp",
        "rfq",
        "order",
        "purchase",
        "payment",
    ):
        response = client.post(
            f"/api/v1/intelligence/indiamart/{action}",
            json={},
            headers=ORIGIN,
        )
        assert response.status_code in {404, 405}


def test_normalized_claims_are_null_safe_and_discovery_only(client: TestClient) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "insulated bottle", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert len(results) == 2
    assert {row["classification"] for row in results} == {"DISCOVERY_ONLY"}
    assert results[0]["price_claim"] is not None
    assert results[1]["price_claim"] is None
    assert results[1]["moq_claim"] is None
    assert results[1]["verification_claim"] is None
    assert all("raw" not in row and "payload" not in row for row in results)

    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        evidence = list(db.scalars(select(SupplierEvidence)))
        suppliers = list(db.scalars(select(Supplier)))
        assert len(evidence) == 2
        assert len(suppliers) == 2
        assert all(row.verification_status == "unverified" for row in evidence)
        assert all(row.source_url and "indiamart.com" in row.source_url for row in evidence)


def test_replay_and_storage_ledger_have_zero_duplicate_deltas(client: TestClient) -> None:
    context = setup_context(client)
    payload = {
        "query": "replay bottle",
        "product_id": context["product"]["id"],
        "idempotency_key": "indiamart-cert-replay",
    }
    first = client.post("/api/v1/intelligence/indiamart/discover", json=payload, headers=ORIGIN)
    assert first.status_code == 200
    second = client.post("/api/v1/intelligence/indiamart/discover", json=payload, headers=ORIGIN)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(IndiaMartDiscoveryRequest)) == 1
        assert db.scalar(select(func.count()).select_from(IndiaMartDiscoveryResult)) == 2
        assert db.scalar(select(func.count()).select_from(Supplier)) == 2
        assert db.scalar(select(func.count()).select_from(SupplierEvidence)) == 2


def test_budget_and_kill_switches_reject_before_provider_execution(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_context(client)
    blocked = Settings(
        indiamart_mode="LOCAL_FIXTURE",
        indiamart_enabled=True,
        indiamart_kill_switch=True,
    )
    original_preflight = indiamart_service.preflight
    monkeypatch.setattr(indiamart_service, "preflight", lambda _: {"status": "KILL_SWITCHED"})
    monkeypatch.setattr(
        indiamart_service, "discover_local", lambda **_: pytest.fail("provider called")
    )
    monkeypatch.setattr("vayujit_api.intelligence.indiamart_router.get_settings", lambda: blocked)
    response = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "blocked", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 409
    assert "KILL_SWITCHED" in response.text

    bounded = Settings(
        indiamart_mode="LOCAL_FIXTURE",
        indiamart_enabled=True,
        indiamart_max_results=1,
    )
    monkeypatch.setattr(indiamart_service, "preflight", original_preflight)
    monkeypatch.setattr("vayujit_api.intelligence.indiamart_router.get_settings", lambda: bounded)
    response = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "too many", "result_limit": 2},
        headers=ORIGIN,
    )
    assert response.status_code == 422
    assert "safety bound" in response.text


def test_concurrent_replay_is_single_request_and_result_set(client: TestClient) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    factory = test_ai_integration.factory
    barrier = threading.Barrier(2)

    def invoke(_: int) -> dict[str, Any]:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            barrier.wait()
            return indiamart_service.discover(
                db,
                owner,
                Settings(indiamart_mode="LOCAL_FIXTURE", indiamart_enabled=True),
                query="concurrent bottle",
                product_id=None,
                country_code="IN",
                region=None,
                result_limit=2,
                correlation_id="concurrent-cert",
                idempotency_key="indiamart-concurrent-cert",
                mission_id=None,
                task_id=None,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, range(2)))
    assert len({value["request"]["id"] for value in results}) == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(IndiaMartDiscoveryRequest)) == 1
        assert db.scalar(select(func.count()).select_from(IndiaMartDiscoveryResult)) == 2


def test_projection_and_ux_are_safe_and_complete(client: TestClient) -> None:
    context = setup_context(client)
    client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "projection bottle", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    channel = client.get(
        f"/api/v1/intelligence/indiamart/product-channel/{context['product']['id']}",
        headers=ORIGIN,
    )
    assert channel.status_code == 200
    assert channel.json()["listing_count"] == 2
    operations = client.get("/api/v1/intelligence/indiamart/operations", headers=ORIGIN).json()
    assert operations["read_only"] is True
    assert operations["live_validation"] == "NOT_RUN"
    assert operations["recovery"]["registered"] is True
    assert operations["prohibited_actions"] == [
        "contact",
        "rfq",
        "order",
        "payment",
        "supplier_modification",
    ]
    assert (
        client.get("/api/v1/intelligence/indiamart/integrity", headers=ORIGIN).json()[
            "classification"
        ]
        == "PASS"
    )


def test_normalized_result_handoff_uses_autonomous_verifier(client: TestClient) -> None:
    context = setup_context(client)
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "FULL_OPPORTUNITY_RESEARCH",
            "goal": "Verify a bounded IndiaMART result",
            "market": "IN",
            "category": "home",
            "provider_mode": "LOCAL_DETERMINISTIC",
            "idempotency_key": "indiamart-evidence-mission",
        },
        headers=ORIGIN,
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    plan = client.get(f"/api/v1/intelligence/autonomous/missions/{mission_id}/plan", headers=ORIGIN)
    assert plan.status_code == 200 and plan.json()["tasks"]
    task_id = plan.json()["tasks"][0]["id"]
    discovery = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={
            "query": "insulated bottle",
            "product_id": context["product"]["id"],
            "mission_id": mission_id,
            "task_id": task_id,
            "idempotency_key": "indiamart-evidence-discovery",
        },
        headers=ORIGIN,
    )
    assert discovery.status_code == 200, discovery.text
    result_id = discovery.json()["results"][0]["id"]
    handoff = client.post(
        f"/api/v1/intelligence/indiamart/discoveries/{result_id}/evidence",
        json={"mission_id": mission_id, "task_id": task_id},
        headers=ORIGIN,
    )
    assert handoff.status_code == 200, handoff.text
    payload = handoff.json()
    assert payload["provider"] == "INDIAMART"
    assert payload["verification_status"] == "SUPPORTED"
    assert payload["lineage"]["result_id"] == result_id
    repeated = client.post(
        f"/api/v1/intelligence/indiamart/discoveries/{result_id}/evidence",
        json={"mission_id": mission_id, "task_id": task_id},
        headers=ORIGIN,
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == payload["id"]
    assert repeated.json()["idempotent_reuse"] is True
    assert "text" not in repeated.json()
