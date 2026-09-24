from __future__ import annotations

from typing import Any

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_13a_inputs_preserve_unknown_zero_provenance_and_snapshot(client: Any) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": "economic-foundation-context",
            "product_id": context["product"]["id"],
            "target_quantity": "100",
            "quantity_unit": "unit",
            "base_currency": "USD",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    economic_context = response.json()["context"]
    assert economic_context["base_currency"] == "USD"

    unknown = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": economic_context["id"],
            "category": "FREIGHT",
            "provenance": "UNKNOWN",
        },
        headers=ORIGIN,
    )
    assert unknown.status_code == 201, unknown.text
    assert unknown.json()["component"]["amount"] is None

    zero = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": economic_context["id"],
            "category": "PACKAGING",
            "amount": "0",
            "currency": "USD",
            "provenance": "CONFIGURED",
        },
        headers=ORIGIN,
    )
    assert zero.status_code == 201, zero.text
    assert zero.json()["component"]["amount"] == 0.0

    assumed = client.post(
        "/api/v1/intelligence/sourcing-economics/assumptions",
        json={
            "context_id": economic_context["id"],
            "key": "freight_review",
            "value": {"state": "UNKNOWN"},
            "reason": "No supplier freight evidence was supplied.",
        },
        headers=ORIGIN,
    )
    assert assumed.status_code == 201, assumed.text

    snapshot = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={economic_context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    frozen = snapshot.json()["snapshot"]
    assert frozen["version"] == 1
    assert frozen["completeness"] == "PARTIAL"
    assert frozen["fingerprint"]
    repeated = client.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={economic_context['id']}",
        json={},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["idempotent_reuse"] is True
    detail = client.get(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{frozen['id']}",
        headers=ORIGIN,
    )
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["components"]) == 2


def test_13a_money_and_metadata_validation(client: Any) -> None:
    setup_context(client)
    created = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={"idempotency_key": "economic-validation-context", "base_currency": "USD"},
        headers=ORIGIN,
    )
    context_id = created.json()["context"]["id"]
    missing_currency = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={"context_id": context_id, "category": "FREIGHT", "amount": "1"},
        headers=ORIGIN,
    )
    assert missing_currency.status_code == 422
    secret_metadata = client.post(
        "/api/v1/intelligence/sourcing-economics/components",
        json={
            "context_id": context_id,
            "category": "FREIGHT",
            "metadata_json": {"token": "never-persist"},
        },
        headers=ORIGIN,
    )
    assert secret_metadata.status_code == 422
