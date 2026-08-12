from datetime import UTC, datetime
from typing import Any

import pytest
import test_ai_integration as ai_fixture
from fastapi.testclient import TestClient
from sqlalchemy import select

from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingJob
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


@pytest.mark.parametrize(
    ("platform", "content_type"),
    [("instagram", "instagram_post"), ("facebook", "facebook_post"), ("youtube", "youtube_video")],
)
def test_social_platform_publish_reconcile_metrics(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, platform: str, content_type: str
) -> None:
    context = ai_fixture.setup_context(client)
    from test_social_integration import _account, _artifact

    artifact = _artifact(client, context["product"]["id"], f"dedicated-{platform}")
    account = _account(client, platform)
    payload: dict[str, Any] = {
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "account_id": account["id"],
        "platform": platform,
        "content_type": content_type,
        "content_artifact_id": artifact["id"],
        "content_artifact_version": artifact["version_number"],
        "media_ids": [],
        "caption": f"{platform} acceptance",
        "idempotency_key": f"dedicated-{platform}",
    }
    if platform == "youtube":
        payload["title"] = "Dedicated YouTube acceptance"
    created = client.post("/api/v1/social/posts", json=payload, headers=ORIGIN)
    assert created.status_code == 201, created.text
    post = created.json()
    preview = client.get(f"/api/v1/social/posts/{post['id']}/preview", headers=ORIGIN)
    assert preview.status_code == 200
    assert preview.json()["readiness"]["ready"] is True
    assert preview.json()["media_ids"] == []
    approved = client.post(f"/api/v1/social/posts/{post['id']}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    scheduled = client.post(
        f"/api/v1/social/posts/{post['id']}/publish-now",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "local_scheduled_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert scheduled.status_code == 200, scheduled.text
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    with ai_fixture.factory() as db:
        assert materialize_due_schedules(db) == 1
        claimed = claim_jobs(db, f"dedicated-{platform}", 1, 60)
        job = db.scalar(select(PublishingJob).where(PublishingJob.id == claimed[0]))
        assert job is not None
        job_id = job.id
    execute_job(job_id, f"dedicated-{platform}")
    published = client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()
    assert published["lifecycle_status"] == "published"
    assert published["content_artifact_id"] == artifact["id"]
    assert published["content_artifact_version"] == artifact["version_number"]
    assert published["remote_publication_id"]
    reconciled = client.post(f"/api/v1/social/posts/{post['id']}/reconcile", headers=ORIGIN)
    assert reconciled.status_code == 200
    metric_response = client.get(f"/api/v1/social/posts/{post['id']}/metrics", headers=ORIGIN)
    assert metric_response.status_code == 200
    assert any(item["source"] == "synthetic_test_data" for item in metric_response.json())
