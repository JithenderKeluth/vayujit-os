from __future__ import annotations

import pytest
from helpers.ads_acceptance import create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

from vayujit_api.ads.connectors import CONNECTORS

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_account_disable_stops_queued_mutation_before_connector(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="disabled-worker")
    account_id = str(campaign["account_id"])
    disabled = client.post(f"/api/v1/ads/accounts/{account_id}/disable", headers=ORIGIN)
    assert disabled.status_code == 200, disabled.text
    queued = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/action",
        json={"action": "pause", "confirm": True, "idempotency_key": "disabled-pause"},
        headers=ORIGIN,
    )
    assert queued.status_code == 200, queued.text
    before = len(CONNECTORS["meta"].state.calls)
    result = client.post(f"/api/v1/ads/jobs/{queued.json()['job_id']}/run", headers=ORIGIN)
    assert result.status_code == 200
    assert result.json()["status"] == "failed"
    assert result.json()["result"] is None
    assert len(CONNECTORS["meta"].state.calls) == before
    assert "credential" not in result.text.lower()


def test_pause_resume_and_recovery_requests_are_idempotent(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="action-idempotency")
    pause = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/action",
        json={"action": "pause", "confirm": True, "idempotency_key": "pause-once"},
        headers=ORIGIN,
    )
    repeated = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/action",
        json={"action": "pause", "confirm": True, "idempotency_key": "pause-once"},
        headers=ORIGIN,
    )
    assert pause.status_code == repeated.status_code == 200
    assert pause.json()["job_id"] == repeated.json()["job_id"]
    recovery = {
        "action": "reconcile",
        "entity_type": "campaign",
        "entity_id": campaign["id"],
        "failure_code": "ads.ambiguous_result",
        "confirm": True,
        "idempotency_key": "recover-once",
    }
    first = client.post("/api/v1/ads/recovery", json=recovery, headers=ORIGIN)
    second = client.post("/api/v1/ads/recovery", json=recovery, headers=ORIGIN)
    assert first.status_code == second.status_code == 200
    assert second.json()["idempotent_reuse"] is True
    assert first.json()["recovery_id"] == second.json()["recovery_id"]
