from typing import Any

import pytest
import test_ai_integration as ai_fixture
from sqlalchemy import select

from vayujit_api.social.models import SocialPost

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _make_post(client: Any, platform: str = "instagram") -> dict[str, Any]:
    context = ai_fixture.setup_context(client)
    from test_social_integration import _account, _artifact

    artifact = _artifact(client, context["product"]["id"], f"recovery-{platform}")
    account = _account(client, platform)
    content_type = "youtube_video" if platform == "youtube" else f"{platform}_post"
    created = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "account_id": account["id"],
            "platform": platform,
            "content_type": content_type,
            "content_artifact_id": artifact["id"],
            "content_artifact_version": artifact["version_number"],
            "caption": "Recovery test",
            "idempotency_key": f"recovery-{platform}",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    return created.json()


def _mark_failed(post_id: str) -> None:
    assert ai_fixture.factory is not None
    with ai_fixture.factory() as db:
        row = db.scalar(select(SocialPost).where(SocialPost.id == post_id))
        assert row is not None
        row.lifecycle_status = "failed"
        row.failure_code = "social.provider_unavailable"
        row.safe_failure_message = "The local social connector is unavailable."
        db.commit()


def test_social_recovery_projection_actions_and_idempotency(client: Any) -> None:
    post = _make_post(client)
    _mark_failed(post["id"])
    projection = client.get("/api/v1/social/recovery", headers=ORIGIN)
    assert projection.status_code == 200
    assert projection.json()[0]["post_id"] == post["id"]
    first = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "retry", "confirm": True},
        headers=ORIGIN,
    )
    assert first.status_code == 200, first.text
    assert first.json()["result"]["status"] == "approved"
    repeated = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "retry", "confirm": True},
        headers=ORIGIN,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["result"]["idempotent_reuse"] is True
    history = client.get(f"/api/v1/social/posts/{post['id']}/history", headers=ORIGIN)
    assert history.status_code == 200
    assert any(item["action"] == "social.post_retry" for item in history.json())


def test_social_ambiguous_reconcile_does_not_resubmit(client: Any) -> None:
    post = _make_post(client, "facebook")
    _mark_failed(post["id"])
    response = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "reconcile", "confirm": True},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["status"] == "published"
    remote_id = result["remote_publication_id"]
    repeated = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "reconcile", "confirm": True},
        headers=ORIGIN,
    )
    assert repeated.status_code == 200
    assert repeated.json()["result"]["remote_publication_id"] == remote_id


def test_social_account_credential_replacement_and_archive(client: Any) -> None:
    post = _make_post(client, "youtube")
    account_id = post["account_id"]
    replaced = client.patch(
        f"/api/v1/social/accounts/{account_id}",
        json={"credentials": {"token": "new-secret"}},
        headers=ORIGIN,
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["credential_configured"] is True
    assert "new-secret" not in replaced.text
    assert replaced.json()["validation_status"] == "unknown"
    archived = client.post(f"/api/v1/social/accounts/{account_id}/archive", headers=ORIGIN)
    assert archived.status_code == 200
    assert archived.json()["enabled"] is False


def test_social_repurpose_preserves_exact_source_lineage(client: Any) -> None:
    source = _make_post(client, "instagram")
    from test_social_integration import _account

    facebook = _account(client, "facebook")
    youtube = _account(client, "youtube")
    for account, content_type in ((facebook, "facebook_post"), (youtube, "youtube_video")):
        response = client.post(
            f"/api/v1/social/posts/{source['id']}/repurpose",
            json={
                "account_id": account["id"],
                "content_type": content_type,
                "idempotency_key": f"repurpose-{content_type}",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["content_artifact_id"] == source["content_artifact_id"]
        assert result["content_artifact_version"] == source["content_artifact_version"]
        assert result["platform"] == account["platform"]


def test_social_remote_missing_reconcile_is_safe_and_retryable(client: Any) -> None:
    post = _make_post(client, "instagram")
    account = client.patch(
        f"/api/v1/social/accounts/{post['account_id']}",
        json={"capabilities": {"scenario": "remote_missing"}},
        headers=ORIGIN,
    )
    assert account.status_code == 200, account.text
    _mark_failed(post["id"])
    response = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "reconcile", "confirm": True},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["status"] == "failed"
    assert result["remote_publication_id"] is None
    assert "retry" in result["safe_message"].lower()
    projection = client.get("/api/v1/social/recovery", headers=ORIGIN)
    item = next(value for value in projection.json() if value["post_id"] == post["id"])
    assert item["failure_code"] == "social.remote_missing"
    assert "retry" in item["available_actions"]
