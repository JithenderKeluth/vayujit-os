from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_ai_integration as ai_fixture

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_social_bulk_approval_is_owner_scoped_and_bounded(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    from test_social_integration import _account, _artifact

    artifact = _artifact(client, context["product"]["id"], "social-bulk")
    account = _account(client, "instagram")
    post_ids: list[str] = []
    for index in range(2):
        response = client.post(
            "/api/v1/social/posts",
            json={
                "brand_id": context["brand"]["id"],
                "product_id": context["product"]["id"],
                "account_id": account["id"],
                "platform": "instagram",
                "content_type": "instagram_post",
                "content_artifact_id": artifact["id"],
                "content_artifact_version": artifact["version_number"],
                "caption": f"Bulk {index}",
                "idempotency_key": f"social-bulk-{index}",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        post_ids.append(response.json()["id"])
    approved = client.post(
        "/api/v1/social/bulk",
        json={"post_ids": post_ids, "action": "approve", "idempotency_key": "bulk-1"},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    assert {item["lifecycle_status"] for item in approved.json()} == {"approved"}
    repeated = client.post(
        "/api/v1/social/bulk",
        json={"post_ids": post_ids, "action": "approve", "idempotency_key": "bulk-1"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 200, repeated.text


def test_social_bulk_schedule_reuses_scheduler_without_connector_calls(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    from test_social_integration import _account, _artifact

    artifact = _artifact(client, context["product"]["id"], "social-bulk-schedule")
    account = _account(client, "facebook")
    created = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "account_id": account["id"],
            "platform": "facebook",
            "content_type": "facebook_post",
            "content_artifact_id": artifact["id"],
            "content_artifact_version": artifact["version_number"],
            "caption": "Bulk schedule",
            "idempotency_key": "bulk-schedule-post",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    post = created.json()
    preview = client.get(f"/api/v1/social/posts/{post['id']}/preview", headers=ORIGIN).json()
    assert (
        client.post(f"/api/v1/social/posts/{post['id']}/approve", headers=ORIGIN).status_code == 200
    )
    scheduled = client.post(
        "/api/v1/social/bulk/schedule",
        json={
            "items": [
                {
                    "post_id": post["id"],
                    "preview_fingerprint": preview["fingerprint"],
                    "local_scheduled_at": (datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
                    "timezone_name": "UTC",
                }
            ],
            "idempotency_key": "bulk-schedule-1",
        },
        headers=ORIGIN,
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()[0]["lifecycle_status"] == "scheduled"
