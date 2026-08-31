import uuid

import pytest
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import Settings
from vayujit_api.intelligence.indiamart import provider_preflight
from vayujit_api.intelligence.indiamart_models import (
    IndiaMartDiscoveryRequest,
    IndiaMartDiscoveryResult,
)
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_preflight_is_truthful_and_network_free() -> None:
    disabled = provider_preflight(Settings(indiamart_mode="DISABLED", indiamart_enabled=False))
    assert disabled["status"] == "DISABLED"
    assert disabled["network_call"] is False
    ready = provider_preflight(Settings(indiamart_mode="LOCAL_FIXTURE", indiamart_enabled=True))
    assert ready["status"] == "READY"
    live = provider_preflight(
        Settings(
            indiamart_mode="LIVE_READ_ONLY",
            indiamart_enabled=True,
            indiamart_base_url="https://official.example.invalid",
        )
    )
    assert live["status"] == "NOT_CONFIGURED"
    assert live["read_only"] is True


def test_local_discovery_normalizes_and_is_idempotent(client) -> None:
    context = setup_context(client)
    payload = {
        "query": "insulated bottle",
        "product_id": context["product"]["id"],
        "country_code": "IN",
        "region": "Maharashtra",
        "result_limit": 2,
        "correlation_id": "indiamart-test-correlation",
        "idempotency_key": "indiamart-test-replay-001",
    }
    first = client.post("/api/v1/intelligence/indiamart/discover", json=payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["results"]) == 2
    assert {row["classification"] for row in body["results"]} == {"DISCOVERY_ONLY"}
    assert all(row["provider"] == "INDIAMART" for row in body["results"])
    assert all("raw" not in row and "payload" not in row for row in body["results"])
    assert body["results"][0]["identity_match"] == "MATCH"
    assert body["results"][0]["product_match"] == "MATCH"
    assert body["results"][1]["price_claim"] is None
    replay = client.post("/api/v1/intelligence/indiamart/discover", json=payload, headers=ORIGIN)
    assert replay.status_code == 200, replay.text
    assert replay.json() == body

    history = client.get("/api/v1/intelligence/indiamart/discoveries", headers=ORIGIN)
    assert history.status_code == 200
    assert len(history.json()) == 1
    detail = client.get(
        f"/api/v1/intelligence/indiamart/discoveries/{body['request']['id']}", headers=ORIGIN
    )
    assert detail.status_code == 200

    operations = client.get("/api/v1/intelligence/indiamart/operations", headers=ORIGIN).json()
    assert operations["read_only"] is True
    assert "payment" in operations["prohibited_actions"]
    assert operations["result_count"] == 2
    assert operations["failure_count"] == 0


def test_owner_scope_and_operational_projections(client) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "steel bottle", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    product_id = context["product"]["id"]
    channel = client.get(
        f"/api/v1/intelligence/indiamart/product-channel/{product_id}", headers=ORIGIN
    )
    assert channel.status_code == 200
    assert channel.json()["listing_count"] == 2
    integrity = client.get("/api/v1/intelligence/indiamart/integrity", headers=ORIGIN)
    assert integrity.status_code == 200
    assert integrity.json()["classification"] == "PASS"
    assert integrity.json()["orphans"]["results_without_request"] == 0
    assert client.get("/api/v1/intelligence/indiamart/calendar", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/intelligence/indiamart/report", headers=ORIGIN).status_code == 200
    projection = client.get("/api/v1/operations/intelligence/projection", headers=ORIGIN)
    assert projection.status_code == 200
    assert projection.json()["indiamart"]["provider"] == "INDIAMART"
    doctor = client.get("/api/v1/intelligence/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["checks"]["indiamart"]["preflight"]["live_validation"] == "NOT_RUN"

    assert (
        client.get(
            f"/api/v1/intelligence/indiamart/product-channel/{uuid.uuid4()}", headers=ORIGIN
        ).status_code
        == 404
    )

    from test_ai_integration import factory

    assert factory is not None
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(IndiaMartDiscoveryRequest)) == 1
        assert db.scalar(select(func.count()).select_from(IndiaMartDiscoveryResult)) == 2
        assert db.scalar(select(func.count()).select_from(Supplier)) == 2
        assert db.scalar(select(func.count()).select_from(SupplierEvidence)) == 2
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert {"indiamart.discovery.requested", "indiamart.discovery.completed"} <= actions
