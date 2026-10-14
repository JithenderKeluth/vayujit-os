"""Focused PR-SOS-08 read-only connectivity and reconciliation certification."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"


def _account(client: TestClient, marketplace: str = "amazon") -> str:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "PR-SOS-08 Owner",
            "email": f"connectivity-{uuid.uuid4().hex}@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    response = client.post(
        "/api/v1/marketplaces/accounts",
        json={
            "marketplace": marketplace,
            "display_name": f"Local {marketplace}",
            "seller_account_id": f"seller-{marketplace}-{uuid.uuid4().hex[:8]}",
            "environment": "sandbox",
            "credentials": {},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["connection_state"] == "AUTHORIZATION_REQUIRED"
    assert body["transport_mode"] == "SYNTHETIC"
    assert "credentials" not in body
    return str(body["id"])


def test_capabilities_are_explicitly_read_only(client: TestClient) -> None:
    response = client.get("/api/v1/marketplaces/connectivity/capabilities", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["provider"] for item in body["providers"]} == {"amazon", "flipkart"}
    for provider in body["providers"]:
        assert provider["repo_supported"] is True
        assert provider["synthetic_fixture"] is True
        assert provider["live_read_only"] == "NOT_CONFIGURED"
        assert provider["live_write"] == "DENIED"
        assert provider["official_contract"] == "UNVERIFIED"
    assert body["external_writes"] is False


def test_synthetic_imports_reuse_canonical_authorities_and_are_idempotent(
    client: TestClient,
) -> None:
    account_id = _account(client)
    operations = ("catalog", "orders", "inventory", "financial")
    first: dict[str, dict[str, object]] = {}
    for operation in operations:
        response = client.post(
            f"/api/v1/marketplaces/accounts/{account_id}/imports",
            json={
                "operation": operation,
                "mode": "SYNTHETIC",
                "idempotency_key": f"run-{operation}",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["status"] == "SUCCEEDED"
        assert body["mode"] == "SYNTHETIC"
        assert body["provenance_json"]["external_writes"] is False
        assert body["checkpoint_json"]["complete"] is True
        first[operation] = body

    replay = client.post(
        f"/api/v1/marketplaces/accounts/{account_id}/imports",
        json={"operation": "orders", "mode": "SYNTHETIC", "idempotency_key": "run-orders"},
        headers=ORIGIN,
    )
    assert replay.status_code == 202, replay.text
    assert replay.json()["id"] == first["orders"]["id"]
    assert replay.json()["records_imported"] == first["orders"]["records_imported"]

    jobs = client.get(f"/api/v1/marketplaces/accounts/{account_id}/import-jobs", headers=ORIGIN)
    assert jobs.status_code == 200, jobs.text
    assert len(jobs.json()) == 4

    reconciliation = client.get(
        f"/api/v1/marketplaces/accounts/{account_id}/reconciliation", headers=ORIGIN
    )
    assert reconciliation.status_code == 200, reconciliation.text
    body = reconciliation.json()
    assert body["automatic_mutations"] is False
    assert body["stale_operations"] == []
    assert body["canonical_counts"]["orders"] == 1
    assert body["canonical_counts"]["settlements"] == 1


def test_external_modes_fail_closed_without_creating_jobs(client: TestClient) -> None:
    account_id = _account(client, "flipkart")
    seeded = client.post(
        f"/api/v1/marketplaces/accounts/{account_id}/imports",
        json={"operation": "catalog", "mode": "SYNTHETIC", "idempotency_key": "shared-key"},
        headers=ORIGIN,
    )
    assert seeded.status_code == 202
    for mode in ("SANDBOX", "LIVE_READ_ONLY"):
        response = client.post(
            f"/api/v1/marketplaces/accounts/{account_id}/imports",
            json={"operation": "catalog", "mode": mode, "idempotency_key": "shared-key"},
            headers=ORIGIN,
        )
        assert response.status_code == 409, response.text
        assert "authorization" in response.json()["detail"].lower()
        assert response.headers["X-VAYUJIT-External-Write"] == "denied"
    jobs = client.get(f"/api/v1/marketplaces/accounts/{account_id}/import-jobs", headers=ORIGIN)
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["id"] == seeded.json()["id"]


def test_owner_scope_and_job_detail_are_fail_closed(client: TestClient) -> None:
    account_id = _account(client)
    other_account = uuid.uuid4()
    assert (
        client.get(
            f"/api/v1/marketplaces/accounts/{other_account}/connectivity", headers=ORIGIN
        ).status_code
        == 404
    )
    created = client.post(
        f"/api/v1/marketplaces/accounts/{account_id}/imports",
        json={"operation": "catalog", "idempotency_key": "detail-1"},
        headers=ORIGIN,
    )
    assert created.status_code == 202
    job_id = created.json()["id"]
    detail = client.get(
        f"/api/v1/marketplaces/accounts/{account_id}/imports/{job_id}", headers=ORIGIN
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == job_id
    assert (
        client.get(
            f"/api/v1/marketplaces/accounts/{account_id}/imports/{uuid.uuid4()}",
            headers=ORIGIN,
        ).status_code
        == 404
    )


def test_completed_job_cannot_be_cancelled(client: TestClient) -> None:
    account_id = _account(client)
    created = client.post(
        f"/api/v1/marketplaces/accounts/{account_id}/imports",
        json={"operation": "catalog", "idempotency_key": "cancel-1"},
        headers=ORIGIN,
    )
    assert created.status_code == 202
    response = client.post(
        f"/api/v1/marketplaces/accounts/{account_id}/imports/{created.json()['id']}/cancel",
        headers=ORIGIN,
    )
    assert response.status_code == 409
