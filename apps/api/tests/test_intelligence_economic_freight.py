from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_freight_service import create_snapshot
from vayujit_api.intelligence.economic_schemas import FreightSnapshotCreate

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _economic_context(client: Any, key: str, currency: str = "USD") -> dict[str, Any]:
    fixture = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": key,
            "product_id": fixture["product"]["id"],
            "origin_country": "IN",
            "destination_country": "US",
            "target_quantity": "10",
            "quantity_unit": "unit",
            "base_currency": currency,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["context"]


def _logistics(client: Any, context: dict[str, Any], key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/logistics/contexts",
        json={
            "economic_context_id": context["id"],
            "idempotency_key": key,
            "origin_country": "IN",
            "origin_location": "Mumbai",
            "destination_country": "US",
            "destination_location": "New York",
            "transport_mode": "AIR",
            "target_quantity": "10",
            "quantity_unit": "unit",
            "total_weight": "12.5",
            "weight_unit": "KG",
            "total_volume": "0.4",
            "volume_unit": "CBM",
            "package_count": 2,
            "incoterm": "dap",
            "status": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["context"]


def _freight(
    client: Any,
    logistics: dict[str, Any],
    key: str,
    *,
    amount: str | None = "25",
    currency: str | None = "USD",
    basis: str = "PER_SHIPMENT",
    provenance: str = "QUOTED",
    freshness: str = "CURRENT",
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "logistics_context_id": logistics["id"],
        "idempotency_key": key,
        "amount": amount,
        "currency": currency,
        "basis": basis,
        "provider": "local-fixture-freight",
        "mode": "LOCAL_FIXTURE",
        "provenance": provenance,
        "freshness": freshness,
        "metadata_json": {"fixture": "13d"},
        "quoted_at": "2026-01-01T00:00:00Z",
        "valid_until": "2026-01-02T00:00:00Z",
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/freight/observations",
        json=payload,
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["observation"]


def _freight_snapshot(
    client: Any, observation: dict[str, Any], version: str = "freight-v1"
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/freight/snapshots",
        json={"observation_id": observation["id"], "version": version},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["snapshot"]


def _economic_snapshot(client: Any, context: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["snapshot"]


def _component(
    client: Any, context: dict[str, Any], category: str, amount: str, currency: str
) -> None:
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": category,
            "amount": amount,
            "currency": currency,
            "unit_basis": "PER_UNIT" if category == "PRODUCT_COST" else "ONE_TIME",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _calculate(client: Any, snapshot: dict[str, Any], **payload: Any) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot['id']}/calculate",
        json=payload,
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_13d_preserves_route_zero_unknown_stale_and_snapshot_idempotency(client: Any) -> None:
    context = _economic_context(client, "freight-preservation")
    logistics = _logistics(client, context, "logistics-preservation")
    assert logistics["transport_mode"] == "AIR"
    assert logistics["incoterm"] == "DAP"
    assert logistics["total_weight"] == 12.5

    zero = _freight(
        client,
        logistics,
        "freight-zero",
        amount="0",
        provenance="CONFIGURED",
        freshness="CURRENT",
    )
    assert zero["amount"] == 0
    assert zero["origin_location"] == "Mumbai"
    assert zero["destination_location"] == "New York"

    stale = _freight(
        client,
        logistics,
        "freight-stale",
        quoted_at="2025-01-01T00:00:00Z",
        valid_until="2025-01-02T00:00:00Z",
    )
    assert stale["freshness"] == "STALE"

    unknown = _freight(
        client,
        logistics,
        "freight-unknown",
        amount=None,
        currency=None,
        basis="UNKNOWN",
        provenance="UNKNOWN",
        freshness="UNKNOWN",
    )
    assert unknown["amount"] is None
    assert unknown["currency"] is None
    snapshot = _freight_snapshot(client, zero)
    repeated = client.post(
        "/api/v1/intelligence/sourcing-economics/freight/snapshots",
        json={"observation_id": zero["id"], "version": "freight-v1"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    assert repeated.json()["idempotent_reuse"] is True
    assert repeated.json()["snapshot"]["id"] == snapshot["id"]


def test_13d_freight_is_included_once_and_unknown_is_not_zero(client: Any) -> None:
    context = _economic_context(client, "freight-calculation")
    _component(client, context, "PRODUCT_COST", "10", "USD")
    logistics = _logistics(client, context, "logistics-calculation")
    observation = _freight(client, logistics, "freight-calculation-observation", amount="25")
    freight = _freight_snapshot(client, observation)
    snapshot = _economic_snapshot(client, context)

    result = _calculate(
        client,
        snapshot,
        freight_snapshot_id=freight["id"],
        calculation_version="landed-cost-v3",
        policy_version="known-cost-freight-v1",
    )
    assert float(result["calculation"]["total_included_cost"]) == 125.0
    freight_lines = [line for line in result["breakdown"] if line["category"] == "FREIGHT"]
    assert len(freight_lines) == 1
    assert freight_lines[0]["freight_snapshot_id"] == freight["id"]


def test_13d_different_currency_requires_explicit_13c_fx(client: Any) -> None:
    context = _economic_context(client, "freight-fx", currency="INR")
    _component(client, context, "PRODUCT_COST", "10", "INR")
    logistics = _logistics(client, context, "logistics-fx")
    observation = _freight(
        client,
        logistics,
        "freight-usd",
        amount="25",
        currency="USD",
    )
    freight = _freight_snapshot(client, observation)
    snapshot = _economic_snapshot(client, context)
    without_fx = _calculate(
        client,
        snapshot,
        freight_snapshot_id=freight["id"],
        calculation_version="landed-cost-v3",
        policy_version="known-cost-freight-v1",
    )
    assert float(without_fx["calculation"]["total_included_cost"]) == 100.0
    assert "FREIGHT:NO_COMPATIBLE_FX_SNAPSHOT" in without_fx["calculation"]["missing_inputs"]

    fx_observation = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/observations",
        json={
            "idempotency_key": "freight-fx-rate",
            "base_currency": "USD",
            "quote_currency": "INR",
            "rate": "83.125",
            "observed_at": "2026-01-01T00:00:00Z",
            "provider": "local-fixture",
            "mode": "LOCAL_FIXTURE",
            "provenance": "LOCAL_FIXTURE",
            "freshness": "CURRENT",
        },
        headers=ORIGIN,
    )
    assert fx_observation.status_code == 201, fx_observation.text
    fx_snapshot = client.post(
        "/api/v1/intelligence/sourcing-economics/fx/snapshots",
        json={
            "observation_id": fx_observation.json()["observation"]["id"],
            "base_currency": "USD",
            "quote_currency": "INR",
        },
        headers=ORIGIN,
    )
    assert fx_snapshot.status_code == 201, fx_snapshot.text
    with_fx = _calculate(
        client,
        snapshot,
        freight_snapshot_id=freight["id"],
        fx_snapshot_id=fx_snapshot.json()["snapshot"]["id"],
        calculation_version="landed-cost-v3",
        policy_version="known-cost-freight-v1",
    )
    assert float(with_fx["calculation"]["total_included_cost"]) == 2178.125


def test_13d_owner_scope_and_metadata_safety(client: Any) -> None:
    context = _economic_context(client, "freight-safety")
    foreign = client.post(
        "/api/v1/intelligence/sourcing-economics/logistics/contexts",
        json={
            "economic_context_id": "00000000-0000-4000-8000-000000000001",
            "idempotency_key": "foreign",
        },
        headers=ORIGIN,
    )
    assert foreign.status_code == 404
    logistics = _logistics(client, context, "logistics-safety")
    blocked = client.post(
        "/api/v1/intelligence/sourcing-economics/freight/observations",
        json={
            "logistics_context_id": logistics["id"],
            "idempotency_key": "freight-secret",
            "amount": "1",
            "currency": "USD",
            "provider": "local",
            "provenance": "QUOTED",
            "metadata_json": {"token": "must-not-persist"},
        },
        headers=ORIGIN,
    )
    assert blocked.status_code == 422
    assert "must-not-persist" not in blocked.text


def test_13d_concurrent_snapshot_creation_converges(client: Any) -> None:
    context = _economic_context(client, "freight-concurrency")
    logistics = _logistics(client, context, "logistics-concurrency")
    observation = _freight(client, logistics, "freight-concurrency-observation")
    factory = integration_helpers.factory
    assert factory is not None
    observation_id = observation["id"]

    def create() -> tuple[str, bool]:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            row, reused = create_snapshot(
                db,
                owner,
                FreightSnapshotCreate(observation_id=observation_id, version="concurrent-v1"),
            )
            return str(row.id), reused

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=30) for future in [pool.submit(create), pool.submit(create)]
        ]
    assert len({item[0] for item in results}) == 1
    assert {item[1] for item in results} == {False, True}
