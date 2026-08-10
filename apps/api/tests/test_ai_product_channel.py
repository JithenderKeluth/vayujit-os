import pytest
import test_ai_integration
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def run_worker(worker_id: str) -> None:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        from vayujit_api.ai.studio_worker import run_ai_jobs_once

        run_ai_jobs_once(db, worker_id, limit=20)


def test_product_channel_intelligence_reports_all_cross_channel_states(client) -> None:
    context = setup_context(client)
    product_id = context["product"]["id"]
    channels = ("canonical", "wordpress", "shopify", "amazon", "flipkart", "meesho")
    for index, channel in enumerate(channels):
        queued = client.post(
            "/api/v1/ai/studio/generate",
            json={
                "product_ids": [product_id],
                "channels": [channel],
                "content_types": ["product_title"],
                "locale": "en-IN",
                "idempotency_key": f"channel-{channel}-{index}",
            },
            headers=ORIGIN,
        )
        assert queued.status_code == 202, queued.text
        run_worker(f"channel-{channel}-worker")
        generation = client.get(
            f"/api/v1/ai/studio/generations/{queued.json()['id']}", headers=ORIGIN
        ).json()
        artifact_id = generation["outputs"][0]["artifact_id"]
        approved = client.post(f"/api/v1/ai/studio/artifacts/{artifact_id}/approve", headers=ORIGIN)
        assert approved.status_code == 200, approved.text
        analysis = client.post(
            "/api/v1/ai/seo/analyze",
            json={
                "product_id": product_id,
                "artifact_id": artifact_id,
                "channel": channel,
                "locale": "en-IN",
                "primary_keyword": "trail bottle",
            },
            headers=ORIGIN,
        )
        assert analysis.status_code == 201, analysis.text
        assert analysis.json()["metrics"]["search_volume"] == "unavailable"

    response = client.get(f"/api/v1/ai/seo/products/{product_id}/channels", headers=ORIGIN)
    assert response.status_code == 200, response.text
    rows = {item["channel"]: item for item in response.json()}
    assert set(rows) == set(channels)
    for channel in channels:
        row = rows[channel]
        assert row["approved_artifact_id"]
        assert row["approved_version"]
        assert row["locale"] == "en-IN"
        assert row["content_quality_score"] is not None
        assert row["search_score"] is not None
        assert row["readiness"] in {"ready", "needs_review", "blocked", "update_available"}
        assert "search_volume" not in str(row).lower()
