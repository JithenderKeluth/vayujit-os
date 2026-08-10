import pytest
import test_ai_integration
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_ai_studio_three_marketplace_e2e(client) -> None:
    context = setup_context(client)
    response = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [context["product"]["id"]],
            "channels": ["amazon", "flipkart", "meesho"],
            "content_types": ["marketplace_listing"],
            "idempotency_key": "studio-e2e-three-market-001",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 202, response.text
    queued = response.json()
    assert queued["status"] == "queued"
    assert all(output["artifact_id"] is None for output in queued["outputs"])

    assert test_ai_integration.factory is not None
    from vayujit_api.ai.studio_worker import run_ai_jobs_once

    with test_ai_integration.factory() as db:
        assert run_ai_jobs_once(db, "ai-studio-e2e-worker", limit=10) == 3

    result = client.get(f"/api/v1/ai/studio/generations/{queued['id']}", headers=ORIGIN)
    assert result.status_code == 200, result.text
    outputs = result.json()["outputs"]
    assert len(outputs) == 3
    assert {output["channel"] for output in outputs} == {"amazon", "flipkart", "meesho"}
    for output in outputs:
        artifact = client.get(
            f"/api/v1/ai/studio/artifacts/{output['artifact_id']}", headers=ORIGIN
        )
        assert artifact.status_code == 200
        assert artifact.json()["status"] == "pending_review"
