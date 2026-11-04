"""WP7A3 invariants, exercised only by the guarded disposable QA runner."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import test_ai_integration
from pydantic import ValidationError
from test_ai_integration import ORIGIN, setup_context
from test_ai_integration import client as client

from vayujit_api.ai.provider import DeterministicMockAIProvider, GenerationInput
from vayujit_api.ai.schemas import ProductContent

pytest_plugins = ("test_ai_integration",)


@pytest.mark.parametrize("name", ["[QA SYNTHETIC] A/B", "O'Reilly (IN)", "a" * 190, "₹", "बोतल"])
def test_local_provider_keywords_satisfy_output_contract(name):
    value = GenerationInput(
        "Brand",
        name,
        "physical",
        None,
        "Known product description",
        None,
        [],
        None,
        "product-content",
        1,
    )
    result = DeterministicMockAIProvider().generate(value)
    content = ProductContent.model_validate(result.content)
    assert result.metadata["deterministic"] is True
    assert all(1 <= len(k) <= 50 for k in content.keywords)


def test_invalid_remote_keywords_are_still_rejected():
    value = GenerationInput(
        "Brand", "Product", "physical", None, None, None, [], None, "product-content", 1
    )
    result = DeterministicMockAIProvider().generate(value)
    result.content["keywords"] = ["<script>unsafe</script>"]
    with pytest.raises(ValidationError):
        ProductContent.model_validate(result.content)


def test_bulk_images_with_real_application_no_autoflush_session(client):
    context = setup_context(client)
    assert test_ai_integration.factory is not None
    test_ai_integration.factory.configure(autoflush=False)
    payload = {
        "product_ids": [context["product"]["id"]],
        "channels": ["amazon"],
        "operation": "marketplace_main_image",
        "width": 64,
        "height": 64,
        "idempotency_key": "wp7a3-no-autoflush",
    }
    result = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    assert result.status_code == 202
    body = result.json()
    assert len(body["outputs"]) == 1
    assert body["outputs"][0]["image_output_id"]
    replay = client.post("/api/v1/ai/images/bulk", json=payload, headers=ORIGIN)
    assert replay.status_code == 202
    assert replay.json()["id"] == body["id"]


def test_concurrent_edit_preserves_one_revision_and_approval_boundary(client):
    context = setup_context(client)
    generated = client.post(
        "/api/v1/ai/generations",
        json={"product_id": context["product"]["id"], "provider_key": "deterministic_mock_v1"},
        headers=ORIGIN,
    )
    assert generated.status_code == 201
    source = generated.json()["artifact_id"]
    original = client.get(f"/api/v1/ai/artifacts/{source}").json()
    content = {**original["content"], "product_title": "A revised title"}
    barrier = Barrier(2)

    def edit():
        barrier.wait(timeout=10)
        try:
            return client.patch(
                f"/api/v1/ai/studio/artifacts/{source}",
                json={"content": content, "expected_source_version": original["version_number"]},
                headers=ORIGIN,
            ).status_code
        except Exception:
            return 500  # Never persist sensitive exception/SQL text in QA output.

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: edit(), range(2)))
    assert sorted(results) == [200, 409]
    assert client.get(f"/api/v1/ai/artifacts/{source}").json()["content"] == original["content"]
    assert (
        client.post(f"/api/v1/ai/artifacts/{source}/approve", json={}, headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/ai/studio/artifacts/{source}", json={"content": content}, headers=ORIGIN
        ).status_code
        == 409
    )


def test_duplicate_campaign_sequence_is_a_conflict_not_a_server_error(client):
    context = setup_context(client)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": context["brand"]["id"],
            "name": "[QA SYNTHETIC] WP7A3 checkpoints",
            "timezone_name": "Asia/Kolkata",
            "local_start_at": "2026-11-10T09:00:00",
            "local_end_at": "2026-11-15T18:00:00",
        },
        headers=ORIGIN,
    )
    assert campaign.status_code == 201
    url = f"/api/v1/campaigns/{campaign.json()['id']}/activities"
    payload = {
        "activity_type": "review_checkpoint",
        "name": "Synthetic review",
        "sequence": 1,
        "scheduled_local_date": "2026-11-11",
        "scheduled_local_time": "09:00:00",
    }
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=10)
        return client.post(url, json=payload, headers=ORIGIN).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: create(), range(2))) == [201, 409]
    assert client.post(url, json=payload, headers=ORIGIN).status_code == 409
    assert len(client.get(url).json()) == 1
