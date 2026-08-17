import pytest
from test_ai_integration import ORIGIN, setup_context

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def test_bulk_preview_confirmation_and_stale_fingerprint_are_safe(client):
    context = setup_context(client)
    payload = {
        "product_ids": [context["product"]["id"]],
        "video_types": ["youtube_video"],
        "targets": ["youtube"],
        "duration_seconds": 2,
        "resolution": "320x240",
        "idempotency_key": "bulk-acceptance-strict",
    }
    preview = client.post("/api/v1/ai/video/bulk/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    plan = preview.json()
    assert plan["ready"] is True
    assert plan["plan_fingerprint"]
    queued = client.post(
        "/api/v1/ai/video/bulk",
        json={**payload, "preview_fingerprint": plan["plan_fingerprint"], "confirm": True},
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    stale = client.post(
        "/api/v1/ai/video/bulk",
        json={
            **payload,
            "idempotency_key": "bulk-acceptance-stale",
            "preview_fingerprint": "0" * 64,
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409, stale.text
    status = client.get(f"/api/v1/ai/video/bulk/{queued.json()['id']}", headers=ORIGIN)
    assert status.status_code == 200
    assert status.json()["child_count"] == 1
