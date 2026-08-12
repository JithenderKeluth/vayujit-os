from datetime import UTC, datetime
from typing import Any, cast

import pytest
import test_ai_integration as ai_fixture
from fastapi.testclient import TestClient
from sqlalchemy import select

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _artifact(client: TestClient, product_id: str, key: str) -> dict[str, Any]:
    queued = client.post(
        "/api/v1/ai/studio/generate",
        json={
            "product_ids": [product_id],
            "channels": ["canonical"],
            "content_types": ["product_title"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    assert ai_fixture.factory is not None
    with ai_fixture.factory() as db:
        run_ai_jobs_once(db, f"social-{key}", limit=10)
    generation = client.get(f"/api/v1/ai/studio/generations/{queued.json()['id']}", headers=ORIGIN)
    assert generation.status_code == 200, generation.text
    artifact_id = generation.json()["outputs"][0]["artifact_id"]
    approved = client.post(f"/api/v1/ai/studio/artifacts/{artifact_id}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    return cast(
        dict[str, Any],
        client.get(f"/api/v1/ai/studio/artifacts/{artifact_id}", headers=ORIGIN).json(),
    )


def _account(client: TestClient, platform: str) -> dict[str, Any]:
    created = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": platform,
            "display_name": f"{platform.title()} Local",
            "remote_account_id": f"{platform}-local",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    account = created.json()
    validated = client.post(f"/api/v1/social/accounts/{account['id']}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text
    return validated.json()


def test_social_three_platform_publish_reconcile_metrics(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "social-three-platform")
    posts: list[tuple[dict[str, Any], str]] = []
    for platform, content_type in (
        ("instagram", "instagram_post"),
        ("facebook", "facebook_post"),
        ("youtube", "youtube_video"),
    ):
        account = _account(client, platform)
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
                "caption": f"{platform} caption",
                "title": "Video title" if platform == "youtube" else None,
                "idempotency_key": f"social-{platform}-1",
            },
            headers=ORIGIN,
        )
        assert created.status_code == 201, created.text
        post = created.json()
        preview = client.get(f"/api/v1/social/posts/{post['id']}/preview", headers=ORIGIN)
        assert preview.status_code == 200, preview.text
        assert preview.json()["readiness"]["ready"] is True
        assert (
            client.post(f"/api/v1/social/posts/{post['id']}/approve", headers=ORIGIN).status_code
            == 200
        )
        posts.append((post, preview.json()["fingerprint"]))
    now = datetime.now(UTC).replace(microsecond=0)
    for post, fingerprint in posts:
        response = client.post(
            f"/api/v1/social/posts/{post['id']}/publish-now",
            json={
                "preview_fingerprint": fingerprint,
                "local_scheduled_at": now.isoformat(),
                "timezone_name": "UTC",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    with ai_fixture.factory() as db:
        assert materialize_due_schedules(db) == 3
        claimed = claim_jobs(db, "social-integration-worker", 3, 60)
        jobs = list(db.scalars(select(PublishingJob).where(PublishingJob.id.in_(claimed))))
    for job in jobs:
        execute_job(job.id, "social-integration-worker")
    results = [
        client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json() for post, _ in posts
    ]
    assert {value["lifecycle_status"] for value in results} == {"published"}
    assert len({value["remote_publication_id"] for value in results}) == 3
    for post, _ in posts:
        metrics = client.get(f"/api/v1/social/posts/{post['id']}/metrics", headers=ORIGIN)
        assert metrics.status_code == 200
        assert any(item["source"] == "synthetic_test_data" for item in metrics.json())

    with ai_fixture.factory() as db:
        actions = set(db.scalars(select(AuditEvent.action)))
        required_actions = {
            "social.account_created",
            "social.account_validated",
            "social.post_created",
            "social.post_approved",
            "social.post_scheduled",
            "social.post_published",
        }
        assert required_actions.issubset(actions), sorted(actions)


def test_social_stale_preview_and_disabled_account_are_blocked(client: TestClient) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "social-stale-preview")
    account = _account(client, "instagram")
    created = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "account_id": account["id"],
            "platform": "instagram",
            "content_type": "instagram_post",
            "content_artifact_id": artifact["id"],
            "content_artifact_version": artifact["version_number"],
            "caption": "old",
            "idempotency_key": "social-stale",
        },
        headers=ORIGIN,
    )
    post = created.json()
    fingerprint = client.get(f"/api/v1/social/posts/{post['id']}/preview", headers=ORIGIN).json()[
        "fingerprint"
    ]
    assert (
        client.patch(
            f"/api/v1/social/posts/{post['id']}", json={"caption": "new"}, headers=ORIGIN
        ).status_code
        == 200
    )
    stale = client.post(
        f"/api/v1/social/posts/{post['id']}/publish-now",
        json={
            "preview_fingerprint": fingerprint,
            "local_scheduled_at": datetime.now(UTC).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_preview"
    assert (
        client.post(f"/api/v1/social/posts/{post['id']}/approve", headers=ORIGIN).status_code == 200
    )
    assert (
        client.post(f"/api/v1/social/accounts/{account['id']}/disable", headers=ORIGIN).status_code
        == 200
    )
