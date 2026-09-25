from __future__ import annotations

from typing import Any

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _baseline(client: Any, key: str, product_id: str) -> dict[str, Any]:
    context_response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": key,
            "product_id": product_id,
            "origin_country": "IN",
            "destination_country": "US",
            "target_quantity": "10",
            "quantity_unit": "unit",
            "base_currency": "USD",
        },
        headers=ORIGIN,
    )
    assert context_response.status_code == 201, context_response.text
    context = context_response.json()["context"]
    for category, amount, basis in (
        ("PRODUCT_COST", "10", "PER_UNIT"),
        ("FREIGHT", "5", "ONE_TIME"),
    ):
        response = client.post(
            "/api/v1/intelligence/sourcing-economics/components",
            json={
                "context_id": context["id"],
                "category": category,
                "amount": amount,
                "currency": "USD",
                "unit_basis": basis,
                "provenance": "CONFIGURED",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    snapshot = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    calculation = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot.json()['snapshot']['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert calculation.status_code == 201, calculation.text
    return {"context": context, "calculation": calculation.json()["calculation"]}


def _opportunity(client: Any, product_id: str, key: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "Disposable cost evidence opportunity",
            "product_id": product_id,
            "category": "Outdoors",
            "origin": "manual",
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_product_opportunity_projects_existing_economics_without_scoring(client: Any) -> None:
    fixture = setup_context(client)
    baseline = _baseline(client, "13g-context", fixture["product"]["id"])
    opportunity = _opportunity(client, fixture["product"]["id"], "13g-opportunity")

    response = client.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity['id']}/sourcing-economics",
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["readiness"] == "AVAILABLE"
    assert body["economic_context_id"] == baseline["context"]["id"]
    assert body["calculation"]["total_included_cost"] == "105.00000000"
    assert body["calculation"]["per_unit_cost"] == "10.50000000"
    assert body["external_writes"] == []
    assert "winner" not in body
    assert "ranking" not in body


def test_product_opportunity_missing_economics_is_a_research_gap(client: Any) -> None:
    fixture = setup_context(client)
    opportunity = _opportunity(client, fixture["product"]["id"], "13g-gap-opportunity")
    response = client.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity['id']}/sourcing-economics",
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["readiness"] == "NOT_EVALUATED"
    assert "calculation" not in body
    assert body["research_gaps"]
    assert body["external_writes"] == []


def test_product_opportunity_rejects_mismatched_context(client: Any) -> None:
    fixture = setup_context(client)
    other_product = client.post(
        "/api/v1/products",
        json={
            "name": "Other bottle",
            "product_type": "physical",
            "short_description": "Other",
            "description": "Other",
            "category": "Outdoors",
            "price_amount": "20.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    ).json()
    baseline = _baseline(client, "13g-mismatch-context", other_product["id"])
    opportunity = _opportunity(client, fixture["product"]["id"], "13g-mismatch-opportunity")
    response = client.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity['id']}/sourcing-economics"
        f"?economic_context_id={baseline['context']['id']}",
        headers=ORIGIN,
    )
    assert response.status_code == 409, response.text
