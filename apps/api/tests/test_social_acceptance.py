import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
import test_ai_integration as ai_fixture
from sqlalchemy import select

from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent
from vayujit_api.publishing.job_queue import (
    claim_jobs,
    finish_job,
    recover_expired_leases,
    start_attempt,
)
from vayujit_api.publishing.models import PublishingJob, PublishingJobAttempt
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.scheduler_time import utcnow
from vayujit_api.publishing.worker import execute_job
from vayujit_api.social.connectors import (
    FAKE_CONNECTOR_CALLS,
    FAKE_REMOTE_PUBLICATIONS,
    connector_for,
)
from vayujit_api.social.models import SocialPost

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _artifact(client: Any, product_id: str, key: str) -> dict[str, Any]:
    from test_social_integration import _artifact as create_artifact

    return create_artifact(client, product_id, key)


def _account(client: Any, platform: str, *, scenario: str | None = None) -> dict[str, Any]:
    from test_social_integration import _account as create_account

    value = create_account(client, platform)
    if scenario:
        response = client.patch(
            f"/api/v1/social/accounts/{value['id']}",
            json={"capabilities": {"scenario": scenario}},
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
        value = response.json()
    return value


def _campaign(client: Any, brand_id: str) -> dict[str, Any]:
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    response = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": brand_id,
            "name": "Social Acceptance Campaign",
            "timezone_name": "UTC",
            "local_start_at": (now - timedelta(hours=1)).isoformat(),
            "local_end_at": (now + timedelta(days=2)).isoformat(),
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _post(
    client: Any,
    context: dict[str, Any],
    artifact: dict[str, Any],
    account: dict[str, Any],
    key: str,
    *,
    campaign_id: str | None = None,
    media_ids: list[str] | None = None,
) -> dict[str, Any]:
    content_type = f"{account['platform']}_post"
    if account["platform"] == "youtube":
        content_type = "youtube_video"
    response = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "account_id": account["id"],
            "platform": account["platform"],
            "content_type": content_type,
            "content_artifact_id": artifact["id"],
            "content_artifact_version": artifact["version_number"],
            "caption": f"Acceptance {key}",
            "title": "Acceptance video" if account["platform"] == "youtube" else None,
            "media_ids": media_ids or [],
            "campaign_id": campaign_id,
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def _schedule(client: Any, post: dict[str, Any], *, when: datetime | None = None) -> dict[str, Any]:
    preview = client.get(f"/api/v1/social/posts/{post['id']}/preview", headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    approved = client.post(f"/api/v1/social/posts/{post['id']}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    scheduled = client.post(
        f"/api/v1/social/posts/{post['id']}/schedule",
        json={
            "preview_fingerprint": preview.json()["fingerprint"],
            "local_scheduled_at": (when or datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert scheduled.status_code == 200, scheduled.text
    return cast(dict[str, Any], scheduled.json())


def _due_job(factory: Any, *, worker_id: str = "acceptance-a", lease_seconds: int = 60) -> Any:
    with factory() as db:
        assert materialize_due_schedules(db) >= 1
        claimed = claim_jobs(db, worker_id, 1, lease_seconds)
        assert len(claimed) == 1
        return db.get(PublishingJob, claimed[0])


def test_social_crash_before_lease_recovery_publishes_once(client: Any, monkeypatch: Any) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-crash-before")
    account = _account(client, "instagram")
    post = _post(client, context, artifact, account, "acceptance-crash-before-post")
    _schedule(client, post)
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    job = _due_job(ai_fixture.factory, lease_seconds=1)
    with ai_fixture.factory() as db:
        row = db.get(PublishingJob, job.id)
        assert row is not None
        row.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_leases(db) == 1
        row.available_at_utc = utcnow() - timedelta(seconds=1)
        db.commit()
        claimed = claim_jobs(db, "acceptance-b", 1, 60)
        assert claimed == [job.id]
    execute_job(job.id, "acceptance-b")
    key = f"instagram:{post['idempotency_key']}"
    assert FAKE_CONNECTOR_CALLS[key] == 1
    published = client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()
    assert published["lifecycle_status"] == "published"
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    with ai_fixture.factory() as db:
        stored = db.get(PublishingJob, job.id)
        assert stored is not None and stored.state == "succeeded"
        assert db.scalar(select(PublishingJobAttempt).where(PublishingJobAttempt.job_id == job.id))
        assert db.scalar(
            select(AuditEvent.id).where(
                AuditEvent.action == "social.post_published",
                AuditEvent.entity_id == post["id"],
            )
        )
        assert finish_job(db, job.id, "acceptance-a", succeeded=True) == "lease_lost"


def test_social_crash_after_checkpoint_reuses_remote_identity(
    client: Any, monkeypatch: Any
) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-crash-after")
    account = _account(client, "facebook")
    post = _post(client, context, artifact, account, "acceptance-crash-after-post")
    _schedule(client, post)
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    FAKE_CONNECTOR_CALLS.clear()
    FAKE_REMOTE_PUBLICATIONS.clear()
    job = _due_job(ai_fixture.factory, worker_id="acceptance-a")
    with ai_fixture.factory() as db:
        attempt = start_attempt(db, job.id, "acceptance-a")
        assert attempt is not None
        row = db.get(SocialPost, post["id"])
        assert row is not None
        remote = connector_for("facebook", {"scenario": "success"}).publish_post(
            {"remote_account_id": account["remote_account_id"]},
            {"caption": row.caption, "artifact_id": str(row.content_artifact_id)},
            row.idempotency_key,
        )
        row.remote_publication_id = str(remote["remote_publication_id"])
        row.failure_code = "social.remote_checkpoint"
        db.commit()
        row_job = db.get(PublishingJob, job.id)
        assert row_job is not None
        row_job.lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_leases(db) == 1
        row_job.available_at_utc = utcnow() - timedelta(seconds=1)
        db.commit()
        assert claim_jobs(db, "acceptance-b", 1, 60) == [job.id]
    execute_job(job.id, "acceptance-b")
    assert FAKE_CONNECTOR_CALLS["facebook:" + post["idempotency_key"]] == 1
    assert len(FAKE_REMOTE_PUBLICATIONS) == 1
    assert (
        client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()["lifecycle_status"]
        == "published"
    )


def test_social_ambiguous_existing_and_missing_remote_are_safe(
    client: Any, monkeypatch: Any
) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-ambiguous")
    account = _account(client, "instagram", scenario="ambiguous_result")
    post = _post(client, context, artifact, account, "acceptance-ambiguous-post")
    _schedule(client, post)
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    job = _due_job(ai_fixture.factory)
    execute_job(job.id, "acceptance-a")
    failed = client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()
    assert failed["lifecycle_status"] == "failed"
    assert failed["remote_publication_id"]
    first_remote = failed["remote_publication_id"]
    account_response = client.patch(
        f"/api/v1/social/accounts/{account['id']}",
        json={"capabilities": {"scenario": "success"}},
        headers=ORIGIN,
    )
    assert account_response.status_code == 200
    reconciled = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "reconcile", "confirm": True},
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["result"]["remote_publication_id"] == first_remote

    missing_account = client.patch(
        f"/api/v1/social/accounts/{account['id']}",
        json={"capabilities": {"scenario": "remote_missing"}},
        headers=ORIGIN,
    )
    assert missing_account.status_code == 200
    missing = client.post(
        "/api/v1/social/recovery/actions",
        json={"post_id": post["id"], "action": "reconcile", "confirm": True},
        headers=ORIGIN,
    )
    assert missing.status_code == 200, missing.text
    assert missing.json()["result"]["status"] == "failed"
    assert missing.json()["result"]["remote_publication_id"] is None


def test_social_platform_isolation_and_campaign_identity(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-platforms")
    campaign = _campaign(client, context["brand"]["id"])
    posts: list[dict[str, Any]] = []
    for platform in ("instagram", "facebook", "youtube"):
        account = _account(client, platform)
        posts.append(
            _post(
                client,
                context,
                artifact,
                account,
                f"acceptance-{platform}",
                campaign_id=campaign["id"],
            )
        )
    assert ai_fixture.factory is not None
    with ai_fixture.factory() as db:
        from vayujit_api.campaigns.models import CampaignActivity

        activities = list(
            db.scalars(
                select(CampaignActivity).where(CampaignActivity.campaign_id == campaign["id"])
            )
        )
        assert len(activities) == 3
        assert {str(item.social_post_id) for item in activities} == {item["id"] for item in posts}
        assert {item.social_platform for item in activities} == {"instagram", "facebook", "youtube"}
        assert all(item.social_account_id for item in activities)
        assert all(item.social_content_type for item in activities)
        assert all(item.social_media_ids == [] for item in activities)
    updated = client.patch(
        f"/api/v1/social/posts/{posts[0]['id']}",
        json={"caption": "Instagram-only change"},
        headers=ORIGIN,
    )
    assert updated.status_code == 200
    for post in posts[1:]:
        assert (
            client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()["caption"]
            != "Instagram-only change"
        )


def test_social_campaign_exact_artifact_version_is_stable(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    first = _artifact(client, context["product"]["id"], "acceptance-version-one")
    second = _artifact(client, context["product"]["id"], "acceptance-version-two")
    campaign = _campaign(client, context["brand"]["id"])
    account = _account(client, "instagram")
    post = _post(
        client, context, first, account, "acceptance-version-post", campaign_id=campaign["id"]
    )
    assert ai_fixture.factory is not None
    with ai_fixture.factory() as db:
        from vayujit_api.campaigns.models import CampaignActivity

        activity = db.scalar(
            select(CampaignActivity).where(CampaignActivity.social_post_id == post["id"])
        )
        assert activity is not None
        assert str(activity.artifact_id) == first["id"]
        assert activity.artifact_version == first["version_number"]
        assert second["version_number"] != first["version_number"]
        assert activity.artifact_version != second["version_number"]


def test_social_account_disable_blocks_worker_and_preserves_history(
    client: Any, monkeypatch: Any
) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-disable")
    account = _account(client, "youtube")
    post = _post(client, context, artifact, account, "acceptance-disable-post")
    _schedule(client, post)
    disabled = client.post(f"/api/v1/social/accounts/{account['id']}/disable", headers=ORIGIN)
    assert disabled.status_code == 200
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    FAKE_CONNECTOR_CALLS.clear()
    job = _due_job(ai_fixture.factory)
    execute_job(job.id, "acceptance-a")
    assert not any(key.endswith(post["idempotency_key"]) for key in FAKE_CONNECTOR_CALLS)
    stored = client.get(f"/api/v1/social/posts/{post['id']}", headers=ORIGIN).json()
    assert stored["lifecycle_status"] == "failed"
    assert (
        client.get(f"/api/v1/social/posts/{post['id']}/history", headers=ORIGIN).status_code == 200
    )


def test_social_metrics_and_privacy_payload(client: Any, monkeypatch: Any) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-metrics")
    account = _account(client, "instagram")
    post = _post(client, context, artifact, account, "acceptance-metrics-post")
    _schedule(client, post)
    assert ai_fixture.factory is not None
    monkeypatch.setattr("vayujit_api.publishing.worker.SessionFactory", ai_fixture.factory)
    job = _due_job(ai_fixture.factory)
    captured: list[dict[str, object]] = []
    import vayujit_api.publishing.worker as publishing_worker

    original = publishing_worker.execute_social_job

    def spy(db: Any, queued: Any) -> Any:
        result = original(db, queued)
        captured.append({"safe": True})
        return result

    monkeypatch.setattr(publishing_worker, "execute_social_job", spy)
    execute_job(job.id, "acceptance-a")
    metrics = client.get(f"/api/v1/social/posts/{post['id']}/metrics", headers=ORIGIN)
    assert metrics.status_code == 200
    values = metrics.json()
    assert {item["availability"] for item in values} <= {
        "available",
        "not_supported",
        "not_synced",
        "unavailable",
    }
    assert any(item["source"] == "synthetic_test_data" for item in values)
    assert captured == [{"safe": True}]


def test_social_owner_scoped_bulk_and_url_matrix(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    artifact = _artifact(client, context["product"]["id"], "acceptance-bulk-owner")
    account = _account(client, "facebook")
    post = _post(client, context, artifact, account, "acceptance-bulk-owner-post")
    for value in (
        "javascript:alert(1)",
        "file:///tmp/a",
        "data:text/plain,hello",
        "http://localhost/a",
        "http://127.0.0.1/a",
        "http://[::1]/a",
        "C:\\secret\\file.txt",
        "/tmp/secret",
    ):
        response = client.patch(
            f"/api/v1/social/posts/{post['id']}",
            json={"destination_url": value},
            headers=ORIGIN,
        )
        assert response.status_code in {400, 422}
    missing = client.get(
        f"/api/v1/social/posts/{'00000000-0000-4000-8000-000000000001'}", headers=ORIGIN
    )
    assert missing.status_code == 404


def test_social_bulk_generation_reuses_durable_ai_bulk(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    product_ids = [context["product"]["id"]]
    for index in range(4):
        response = client.post(
            "/api/v1/products",
            json={
                "name": f"Bulk Social Product {index}",
                "product_type": "physical",
                "short_description": "Bulk social test product",
                "description": "A deterministic product for social bulk acceptance.",
                "category": "Outdoors",
                "tags": ["bulk"],
                "price_amount": "19.00",
                "price_currency": "USD",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        product_ids.append(response.json()["id"])
    payload = {
        "product_ids": product_ids,
        "channels": ["instagram", "facebook"],
        "content_types": ["social_caption"],
        "idempotency_key": "social-bulk-acceptance",
    }
    preview = client.post("/api/v1/ai/studio/bulk/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    assert preview.json()["total_outputs"] == 10
    first = client.post("/api/v1/ai/studio/bulk", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/ai/studio/bulk", json=payload, headers=ORIGIN)
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["id"] == second.json()["id"]
    assert ai_fixture.factory is not None
    with ai_fixture.factory() as db:
        processed = run_ai_jobs_once(db, "social-bulk-worker", limit=20)
    assert processed == 10
    bulk_id = first.json()["id"]
    status = client.get(f"/api/v1/ai/studio/bulk/{bulk_id}", headers=ORIGIN)
    assert status.status_code == 200, status.text
    assert status.json()["counts"].get("needs_review") == 10
    outputs = client.get(f"/api/v1/ai/studio/bulk/{bulk_id}/outputs", headers=ORIGIN)
    assert outputs.status_code == 200, outputs.text
    items = outputs.json()["items"]
    assert len(items) == 10
    assert {item["channel"] for item in items} == {"instagram", "facebook"}
    assert len({item["artifact_id"] for item in items}) == 10
    missing = client.get(f"/api/v1/ai/studio/bulk/{uuid.uuid4()}", headers=ORIGIN)
    assert missing.status_code == 404
