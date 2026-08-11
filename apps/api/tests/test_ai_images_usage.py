from __future__ import annotations

import pytest
import test_ai_images_bulk
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_image_usage_separates_modality_and_counts_attempts(client) -> None:
    context = setup_context(client)
    payload = test_ai_images_bulk.image_payload([context["product"]["id"]], "image-usage")
    payload["channels"] = ["amazon", "flipkart"]
    queued = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    assert test_ai_images_bulk.run_worker("usage-worker") == 2
    usage = client.get("/api/v1/ai/images/usage", headers=ORIGIN)
    assert usage.status_code == 200, usage.text
    body = usage.json()
    assert body["modality"] == "image"
    assert body["total_generations"] == 2
    assert body["provider_calls"] == 2
    assert body["generated_images"] == 2
    assert body["generated_bytes"] > 0
    assert body["cost_status"] == "unavailable"
    assert body["cost"] is None
    assert body["token_totals"] is None
    assert "amazon" in body["channels"]
