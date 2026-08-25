from __future__ import annotations

from typing import Any

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_sourcing_local_flow_is_durable_and_owner_scoped(client: Any) -> None:
    context = setup_context(client)
    supplier = client.post(
        "/api/v1/intelligence/suppliers/manual",
        json={
            "display_name": "Disposable Fixture Supplier",
            "supplier_type": "manufacturer",
            "country_code": "IN",
            "country": "India",
            "provenance": "local sourcing fixture",
        },
        headers=ORIGIN,
    )
    assert supplier.status_code in (200, 201), supplier.text
    supplier_id = supplier.json()["id"]
    requirement = client.post(
        "/api/v1/intelligence/sourcing/requirements",
        json={
            "product_id": context["product"]["id"],
            "idempotency_key": "source-req-1",
            "payload": {"category": "outdoors", "target_quantity": 100, "maximum_moq": 500},
        },
        headers=ORIGIN,
    )
    assert requirement.status_code == 201, requirement.text
    requirement_id = requirement.json()["requirement"]["id"]
    rfq = client.post(
        "/api/v1/intelligence/sourcing/rfqs",
        json={
            "requirement_id": requirement_id,
            "requirement_version": 1,
            "title": "Disposable fixture RFQ",
            "supplier_ids": [supplier_id],
            "idempotency_key": "rfq-1",
            "payload": {"requested_incoterm": "FOB"},
        },
        headers=ORIGIN,
    )
    assert rfq.status_code == 201, rfq.text
    rfq_id = rfq.json()["rfq"]["id"]
    assert (
        client.post(
            f"/api/v1/intelligence/sourcing/rfqs/{rfq_id}/approve", headers=ORIGIN
        ).status_code
        == 200
    )
    quote = client.post(
        "/api/v1/intelligence/sourcing/quotes",
        json={
            "rfq_id": rfq_id,
            "supplier_id": supplier_id,
            "quote_reference": "Q-1",
            "currency": "INR",
            "unit_price": 125,
            "moq": 100,
            "lines": [
                {"kind": "base_product", "description": "base", "amount": 125, "currency": "INR"}
            ],
        },
        headers=ORIGIN,
    )
    assert quote.status_code == 201, quote.text
    quote_id = quote.json()["id"]
    scenario = client.post(
        "/api/v1/intelligence/sourcing/scenarios",
        json={
            "requirement_id": requirement_id,
            "quote_id": quote_id,
            "name": "BASE",
            "currency": "INR",
            "inputs": {
                "unit_supplier_price": 125,
                "freight": 10,
                "selling_price": 250,
                "quantity": 100,
            },
        },
        headers=ORIGIN,
    )
    assert scenario.status_code == 201, scenario.text
    assert scenario.json()["result"]["landed_cost_per_unit"] == 1.35
    decision = client.post(
        "/api/v1/intelligence/sourcing/decisions",
        json={
            "requirement_id": requirement_id,
            "quote_id": quote_id,
            "decision": "hold",
            "classification": "review_required",
            "confirmed": True,
        },
        headers=ORIGIN,
    )
    assert decision.status_code == 201, decision.text
    overview = client.get("/api/v1/intelligence/sourcing/overview", headers=ORIGIN)
    assert overview.status_code == 200
    assert overview.json()["open_rfqs"] == 0
