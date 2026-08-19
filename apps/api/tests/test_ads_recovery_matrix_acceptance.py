from __future__ import annotations

from typing import Any, cast

import pytest
from helpers.ads_acceptance import create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

from vayujit_api.ads.failure import ADS_FAILURE_TAXONOMY

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_every_advertised_recovery_action_executes_through_router(client: Any) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="recovery-executor-matrix")
    observed = client.get("/api/v1/ads/recovery", headers=ORIGIN)
    assert observed.status_code == 200
    assert {row["failure_code"] for row in observed.json()} == set(ADS_FAILURE_TAXONOMY)
    action_count = 0
    for failure_code, spec in ADS_FAILURE_TAXONOMY.items():
        for action in cast(list[str], spec["recovery_actions"]):
            action_count += 1
            response = client.post(
                "/api/v1/ads/recovery",
                json={
                    "action": action,
                    "entity_type": "campaign",
                    "entity_id": campaign["id"],
                    "failure_code": failure_code,
                    "confirm": True,
                    "idempotency_key": f"matrix:{failure_code}:{action}",
                    "correlation_id": f"matrix-{action_count}",
                },
                headers=ORIGIN,
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["action"] == action
            assert body["failure_code"] == failure_code
            assert body["safe_message"]
            assert body["correlation_id"] == f"matrix-{action_count}"
            assert all(
                marker not in response.text.lower()
                for marker in (
                    "token",
                    "cookie",
                    "password",
                    "traceback",
                    "postgresql://",
                    "c:\\users\\",
                    "database_url",
                    "sql",
                )
            )
    assert action_count >= 16


def test_recovery_action_matrix_repeats_idempotently(client: Any) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="recovery-repeat")
    payload = {
        "action": "retry",
        "entity_type": "campaign",
        "entity_id": campaign["id"],
        "failure_code": "ads.throttled",
        "confirm": True,
        "idempotency_key": "recovery-repeat-once",
    }
    first = client.post("/api/v1/ads/recovery", json=payload, headers=ORIGIN)
    repeated = client.post("/api/v1/ads/recovery", json=payload, headers=ORIGIN)
    assert first.status_code == repeated.status_code == 200
    assert repeated.json()["idempotent_reuse"] is True
    assert repeated.json()["recovery_id"] == first.json()["recovery_id"]
