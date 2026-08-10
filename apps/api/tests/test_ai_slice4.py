import pytest
import test_ai_integration
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def run_worker(worker_id: str) -> None:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        from vayujit_api.ai.studio_worker import run_ai_jobs_once

        run_ai_jobs_once(db, worker_id, limit=10)


def test_artifact_edit_is_immutable_and_comparable(client) -> None:
    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [context["product"]["id"]],
            "channels": ["amazon"],
            "content_types": ["product_title"],
            "idempotency_key": "slice4-edit",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    run_worker("slice4-edit-worker")
    generation = client.get(
        f"/api/v1/ai/studio/generations/{queued.json()['id']}", headers=ORIGIN
    ).json()
    old_id = generation["outputs"][0]["artifact_id"]
    old = client.get(f"/api/v1/ai/studio/artifacts/{old_id}", headers=ORIGIN).json()
    editable_key = next(key for key, value in old["content"].items() if isinstance(value, str))
    edited_content = {**old["content"], editable_key: "Human edited title"}
    edited_response = client.patch(
        f"/api/v1/ai/studio/artifacts/{old_id}", json={"content": edited_content}, headers=ORIGIN
    )
    assert edited_response.status_code == 200, edited_response.text
    edited = edited_response.json()
    assert edited["id"] != old_id
    assert edited["version_number"] > old["version_number"]
    assert edited["source"] == "ai_human_edited"
    assert (
        client.get(f"/api/v1/ai/studio/artifacts/{old_id}", headers=ORIGIN).json()["content"]
        == old["content"]
    )
    comparison = client.get(
        f"/api/v1/ai/studio/artifacts/{old_id}/compare",
        params={"against_id": edited["id"]},
        headers=ORIGIN,
    )
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["fields"][editable_key]["status"] == "changed"
