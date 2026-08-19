from __future__ import annotations

import uuid
from typing import Any

from test_ai_integration import ORIGIN, setup_context


def create_account(client: Any, provider: str, suffix: str = "acceptance") -> dict[str, Any]:
    response = client.post(
        "/api/v1/ads/accounts",
        json={
            "provider": provider,
            "external_account_id": f"{provider}-{suffix}-{uuid.uuid4().hex[:8]}",
            "display_name": f"{provider} acceptance",
            "credentials": {"opaque": "never-returned"},
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    account = response.json()
    account_id = account["id"]
    assert (
        client.post(f"/api/v1/ads/accounts/{account_id}/validate", headers=ORIGIN).status_code
        == 200
    )
    enabled = client.post(f"/api/v1/ads/accounts/{account_id}/enable", headers=ORIGIN)
    assert enabled.status_code == 200
    return client.get(f"/api/v1/ads/accounts/{account_id}", headers=ORIGIN).json()


def create_campaign(
    client: Any,
    context: dict[str, Any],
    provider: str = "meta",
    suffix: str = "campaign",
    **overrides: Any,
) -> dict[str, Any]:
    account = create_account(client, provider, suffix)
    payload: dict[str, Any] = {
        "provider": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "name": f"{provider} {suffix}",
        "objective": "awareness" if provider == "meta" else "traffic",
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"{provider}-{suffix}-{uuid.uuid4().hex}",
    }
    payload.update(overrides)
    response = client.post("/api/v1/ads/campaigns", json=payload, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


def setup_ads_context(client: Any) -> dict[str, Any]:
    return setup_context(client)
