from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.economic_calculation_service import calculate_from_snapshot
from vayujit_api.intelligence.economic_schemas import EconomicCalculationRequest

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _economic_context(client: Any, *, key: str, currency: str = "USD") -> dict[str, Any]:
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


def _snapshot(client: Any, context_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context_id}",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()["snapshot"]


def test_13b_calculates_from_immutable_snapshot_without_fx_or_unknown_zero(
    client: Any,
) -> None:
    context = _economic_context(client, key="economic-calculation-context")
    product = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "PRODUCT_COST",
            "amount": "12",
            "currency": "USD",
            "unit_basis": "PER_UNIT",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert product.status_code == 201, product.text
    packaging = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "PACKAGING",
            "amount": "2",
            "currency": "USD",
            "unit_basis": "ONE_TIME",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert packaging.status_code == 201, packaging.text
    unknown_freight = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "FREIGHT",
            "provenance": "UNKNOWN",
        },
        headers=ORIGIN,
    )
    assert unknown_freight.status_code == 201, unknown_freight.text
    snapshot = _snapshot(client, context["id"])

    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["calculation"]
    assert result["status"] == "PARTIAL"
    assert result["currency"] == "USD"
    assert float(result["total_included_cost"]) == 122.0
    assert float(result["per_unit_cost"]) == 12.2
    assert "FREIGHT" in result["missing_inputs"]
    assert len(body["breakdown"]) == 3
    assert any(
        line["category"] == "FREIGHT" and line["exclusion_reason"] == "UNKNOWN_AMOUNT"
        for line in body["breakdown"]
    )

    repeated = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["idempotent_reuse"] is True
    assert repeated.json()["calculation"]["id"] == result["id"]


def test_13b_rejects_implicit_currency_conversion_and_preserves_zero(client: Any) -> None:
    context = _economic_context(client, key="economic-currency-context")
    for payload in (
        {
            "context_id": context["id"],
            "category": "PRODUCT_COST",
            "amount": "10",
            "currency": "USD",
            "unit_basis": "PER_UNIT",
            "provenance": "CONFIGURED",
        },
        {
            "context_id": context["id"],
            "category": "PACKAGING",
            "amount": "0",
            "currency": "USD",
            "unit_basis": "ONE_TIME",
            "provenance": "CONFIGURED",
        },
        {
            "context_id": context["id"],
            "category": "FREIGHT",
            "amount": "4",
            "currency": "EUR",
            "unit_basis": "ONE_TIME",
            "provenance": "CONFIGURED",
        },
    ):
        response = client.post(
            "/api/v1/intelligence/sourcing-economics/components",
            json=payload,
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    snapshot = _snapshot(client, context["id"])
    response = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    result = response.json()["calculation"]
    assert result["status"] == "PARTIAL"
    assert float(result["total_included_cost"]) == 100.0
    assert any("CURRENCY_MISMATCH" in value for value in result["missing_inputs"])
    detail = client.get(
        f"/api/v1/intelligence/sourcing-economics/calculations/{result['id']}",
        headers=ORIGIN,
    )
    assert detail.status_code == 200, detail.text
    assert any(
        line["category"] == "PACKAGING" and line["included_amount"] == 0
        for line in detail.json()["breakdown"]
    )


def test_13b_concurrent_same_snapshot_converges_to_one_result(client: Any) -> None:
    context = _economic_context(client, key="economic-concurrent-context")
    component = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context["id"],
            "category": "PRODUCT_COST",
            "amount": "8",
            "currency": "USD",
            "unit_basis": "PER_UNIT",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert component.status_code == 201, component.text
    snapshot = _snapshot(client, context["id"])
    factory = integration_helpers.factory
    assert factory is not None

    def calculate() -> tuple[str, bool]:
        with factory() as db:
            owner = db.scalar(select(User).where(User.email == "owner@example.com"))
            assert owner is not None
            row, reused = calculate_from_snapshot(
                db,
                owner,
                snapshot["id"],
                EconomicCalculationRequest(),
            )
            return str(row.id), reused

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(calculate) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert len({result[0] for result in results}) == 1
    assert {result[1] for result in results} == {False, True}
