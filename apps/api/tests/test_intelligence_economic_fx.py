from __future__ import annotations

from typing import Any

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _context(client: Any, key: str, currency: str = "INR") -> dict[str, Any]:
    fixture = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": key,
            "product_id": fixture["product"]["id"],
            "target_quantity": "10",
            "quantity_unit": "unit",
            "base_currency": currency,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["context"]


def _observation(client: Any, key: str = "fx-usd-inr") -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/observations",
        json={
            "idempotency_key": key,
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": "83.125",
            "observed_at": "2026-01-01T00:00:00Z",
            "provider": "local-fixture",
            "mode": "LOCAL_FIXTURE",
            "provenance": "LOCAL_FIXTURE",
            "freshness": "CURRENT",
            "metadata_json": {"fixture": "13c"},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["observation"]


def test_fx_observation_direct_inverse_and_idempotency(client: Any) -> None:
    setup_context(client)
    observation = _observation(client)
    repeated = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/observations",
        json={
            "idempotency_key": "fx-usd-inr",
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": "83.125",
            "observed_at": "2026-01-01T00:00:00Z",
            "provider": "local-fixture",
            "mode": "LOCAL_FIXTURE",
            "provenance": "LOCAL_FIXTURE",
            "freshness": "CURRENT",
            "metadata_json": {"fixture": "13c"},
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 201 and repeated.json()["idempotent_reuse"] is True
    direct = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/snapshots",
        json={"observation_id": observation["id"], "base_currency": "USD", "quote_currency": "INR"},
        headers=ORIGIN,
    )
    assert direct.status_code == 201, direct.text
    inverse = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/snapshots",
        json={"observation_id": observation["id"], "base_currency": "INR", "quote_currency": "USD"},
        headers=ORIGIN,
    )
    assert inverse.status_code == 201, inverse.text
    assert inverse.json()["snapshot"]["inverted"] is True
    unsupported = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/snapshots",
        json={"observation_id": observation["id"], "base_currency": "EUR", "quote_currency": "INR"},
        headers=ORIGIN,
    )
    assert unsupported.status_code == 422


def test_fx_calculation_converts_and_reuses_immutable_snapshot(client: Any) -> None:
    context = _context(client, "fx-calc-context")
    component = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "PRODUCT_COST",
            "amount": "10",
            "currency": "USD",
            "unit_basis": "PER_UNIT",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert component.status_code == 201, component.text
    observation = _observation(client, "fx-calc-usd-inr")
    snapshot_fx = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/snapshots",
        json={"observation_id": observation["id"], "base_currency": "USD", "quote_currency": "INR"},
        headers=ORIGIN,
    )
    assert snapshot_fx.status_code == 201, snapshot_fx.text
    snapshot = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot.json()['snapshot']['id']}/calculate",
        json={
            "fx_snapshot_id": snapshot_fx.json()["snapshot"]["id"],
            "calculation_version": "landed-cost-v2",
            "policy_version": "known-cost-fx-v1",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    result = response.json()["calculation"]
    assert result["reporting_currency"] == "INR"
    assert float(result["total_included_cost"]) == 8312.5
    assert response.json()["breakdown"][0]["converted_amount"] == 8312.5
    repeated = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot.json()['snapshot']['id']}/calculate",
        json={
            "fx_snapshot_id": snapshot_fx.json()["snapshot"]["id"],
            "calculation_version": "landed-cost-v2",
            "policy_version": "known-cost-fx-v1",
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 201 and repeated.json()["idempotent_reuse"] is True


def test_fx_validation_and_missing_rate_are_safe(client: Any) -> None:
    context = _context(client, "fx-missing-context")
    bad = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/observations",
        json={
            "idempotency_key": "fx-bad",
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": "0",
            "observed_at": "2026-01-01T00:00:00Z",
            "provider": "local",
            "metadata_json": {"token": "blocked"},
        },
        headers=ORIGIN,
    )
    assert bad.status_code == 422
    component = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "PRODUCT_COST",
            "amount": "10",
            "currency": "USD",
            "unit_basis": "PER_UNIT",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert component.status_code == 201
    snapshot = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context['id']}",
        json={},
        headers=ORIGIN,
    )
    result = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot.json()['snapshot']['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert result.status_code == 201
    assert "CURRENCY_MISMATCH" in str(result.json()["calculation"]["missing_inputs"])
