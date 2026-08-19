from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from helpers.ads_acceptance import create_campaign, setup_ads_context
from test_ai_integration import ORIGIN

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_concurrent_pause_requests_share_one_logical_job(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="concurrent-pause")

    def request() -> tuple[int, str]:
        response = client.post(
            f"/api/v1/ads/campaigns/{campaign['id']}/action",
            json={"action": "pause", "confirm": True, "idempotency_key": "pause-concurrent"},
            headers=ORIGIN,
        )
        return response.status_code, response.json().get("job_id", "")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert {status for status, _ in results} == {200}
    assert len({job_id for _, job_id in results}) == 1


def test_concurrent_recovery_requests_share_one_record(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="concurrent-recovery")
    payload = {
        "action": "reconcile",
        "entity_type": "campaign",
        "entity_id": campaign["id"],
        "failure_code": "ads.ambiguous_result",
        "confirm": True,
        "idempotency_key": "recovery-concurrent",
    }

    def request() -> dict[str, object]:
        response = client.post("/api/v1/ads/recovery", json=payload, headers=ORIGIN)
        assert response.status_code == 200, response.text
        return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert len({str(result["recovery_id"]) for result in results}) == 1
    assert any(result["idempotent_reuse"] is True for result in results)
