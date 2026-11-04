"""Canonical SEO revisions and owned read boundaries; no live provider operations."""

import uuid

import pytest
from test_ai_integration import ORIGIN, setup_context
from test_ai_integration import client as client

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_scoped_keyword_revision_and_conflict_preserve_saved_data(client):
    context = setup_context(client)
    product_id = context["product"]["id"]
    endpoint = "/api/v1/ai/seo/keywords"
    initial = {
        "name": "[QA SYNTHETIC] scoped keywords",
        "product_id": product_id,
        "primary": ["one"],
        "secondary": ["two"],
        "locale": "en-IN",
    }
    response = client.post(endpoint, json=initial, headers=ORIGIN)
    assert response.status_code == 201
    first = response.json()
    assert first["product_id"] == product_id
    changed = client.put(
        endpoint + "/" + first["id"], json={**initial, "secondary": ["three"]}, headers=ORIGIN
    )
    assert changed.status_code == 200
    assert changed.json()["id"] == first["id"]
    assert changed.json()["version"] == first["version"] + 1
    conflict = client.put(
        endpoint + "/" + first["id"], json={**initial, "negative": ["ONE"]}, headers=ORIGIN
    )
    assert conflict.status_code == 422
    saved = client.get(endpoint + "/" + first["id"]).json()
    assert saved["secondary"] == ["three"]
    assert saved["version"] == changed.json()["version"]


def test_tag_update_normalization_and_archive_do_not_mutate_product_tags(client):
    context = setup_context(client)
    product = context["product"]
    before = client.get("/api/v1/products/" + product["id"]).json()
    endpoint = "/api/v1/ai/seo/tags"
    payload = {
        "name": "[QA SYNTHETIC] saved tags",
        "product_id": product["id"],
        "tags": ["#fixture", "Fixture"],
    }
    first = client.post(endpoint, json=payload, headers=ORIGIN)
    assert first.status_code == 201
    assert first.json()["tags"] == ["fixture"]
    duplicate = client.post(endpoint, json=payload, headers=ORIGIN)
    assert duplicate.status_code == 409
    assert len(client.get(endpoint).json()) == 1
    tag_id = first.json()["id"]
    updated = client.put(
        endpoint + "/" + tag_id, json={**payload, "tags": ["updated"]}, headers=ORIGIN
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == tag_id
    assert client.post(endpoint + "/" + tag_id + "/archive", headers=ORIGIN).status_code == 200
    assert all(item["id"] != tag_id for item in client.get(endpoint).json())
    assert client.get("/api/v1/products/" + product["id"]).json()["tags"] == before["tags"]


def test_video_draft_confirmation_returns_exact_durable_identity_without_dispatch(client):
    import test_ai_integration
    import test_ai_video_slice3_channels as channels_fixture
    from sqlalchemy import func, select

    from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
    from vayujit_api.social.models import SocialPost

    context = setup_context(client)
    generation = channels_fixture._video(client, context, key="wp7a5-draft-identity")
    account = channels_fixture._account(client, "youtube", "wp7a5")
    prepared = client.post(
        "/api/v1/ai/video/channels/prepare",
        json={
            "video_generation_id": generation,
            "channel": "youtube",
            "target_id": account,
            "idempotency_key": "wp7a5-exact-draft",
        },
        headers=ORIGIN,
    )
    assert prepared.status_code == 200
    value = prepared.json()
    endpoint = f"/api/v1/ai/video/channels/{value['id']}/confirm"
    assert (
        client.post(
            endpoint, json={"fingerprint": value["fingerprint"], "confirm": False}, headers=ORIGIN
        ).status_code
        == 422
    )
    assert (
        client.post(
            endpoint, json={"fingerprint": "f" * 64, "confirm": True}, headers=ORIGIN
        ).status_code
        == 409
    )
    saved = client.post(
        endpoint, json={"fingerprint": value["fingerprint"], "confirm": True}, headers=ORIGIN
    )
    assert saved.status_code == 200
    assert saved.json()["social_post_id"]
    replay = client.post(
        endpoint, json={"fingerprint": value["fingerprint"], "confirm": True}, headers=ORIGIN
    )
    assert replay.status_code == 200
    assert replay.json()["social_post_id"] == saved.json()["social_post_id"]
    assert replay.json()["idempotent_reuse"] is True
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(SocialPost)) == 1
        post = db.get(SocialPost, uuid.UUID(saved.json()["social_post_id"]))
        assert post and str(post.video_generation_id) == generation
        assert post.lifecycle_status == "draft" and post.remote_publication_id is None
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 0


def test_image_failure_and_same_job_retry_preserve_output_history(client, monkeypatch):
    from datetime import UTC, datetime

    import test_ai_integration
    from sqlalchemy import select

    from vayujit_api.ai import studio_worker
    from vayujit_api.ai.failures import StudioProviderFailure
    from vayujit_api.ai.image_provider import image_provider
    from vayujit_api.ai.studio_models import AIStudioJob, AIStudioJobAttempt

    context = setup_context(client)
    queued = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": context["brand"]["id"],
            "product_id": context["product"]["id"],
            "operation": "generate_product_image",
            "width": 64,
            "height": 64,
            "output_count": 1,
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202
    output = queued.json()["outputs"][0]
    assert test_ai_integration.factory is not None

    def run(failure):
        with test_ai_integration.factory() as db:
            job = db.get(AIStudioJob, uuid.UUID(output["job_id"]))
            assert job
            with monkeypatch.context() as patch:
                patch.setattr(
                    studio_worker, "utcnow", lambda: max(datetime.now(UTC), job.available_at)
                )
                if failure:

                    def unavailable(**kwargs):
                        raise StudioProviderFailure("provider_unavailable")

                    patch.setattr(image_provider, "generate", unavailable)
                studio_worker.run_ai_jobs_once(db, "wp7a5-image-recovery", limit=1)

    for _ in range(4):
        run(True)
    failed = client.get("/api/v1/ai/images/outputs/" + output["id"]).json()
    assert failed["status"] == "failed" and failed["media_id"] is None
    generation = client.get(
        "/api/v1/ai/images/generations/" + queued.json()["generation_id"]
    ).json()
    assert generation["failed_outputs"] == 1
    recovered = client.post(
        "/api/v1/ai/studio/recovery/actions",
        json={"action": "retry_generation", "job_id": output["job_id"]},
        headers=ORIGIN,
    )
    assert recovered.status_code == 200
    run(False)
    saved = client.get("/api/v1/ai/images/outputs/" + output["id"]).json()
    assert saved["id"] == output["id"] and saved["job_id"] == output["job_id"]
    assert saved["media_id"] and saved["status"] != "approved"
    with test_ai_integration.factory() as db:
        attempts = db.scalars(
            select(AIStudioJobAttempt).where(
                AIStudioJobAttempt.job_id == uuid.UUID(output["job_id"])
            )
        ).all()
        assert any(a.state == "failed" for a in attempts)
        assert any(a.state == "succeeded" for a in attempts)


def test_bulk_polling_and_concurrent_retry_share_parent_lock_order(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import UTC, datetime
    from threading import Barrier

    import test_ai_integration
    from sqlalchemy import select

    from vayujit_api.ai import studio_worker
    from vayujit_api.ai.failures import StudioProviderFailure
    from vayujit_api.ai.studio_models import AIStudioJob

    context = setup_context(client)
    created = client.post(
        "/api/v1/ai/studio/bulk",
        json={
            "product_ids": [context["product"]["id"]],
            "channels": ["canonical"],
            "content_types": ["product_title", "product_description"],
            "idempotency_key": "wp7a5-concurrent-poll",
        },
        headers=ORIGIN,
    )
    assert created.status_code == 202
    bulk_id = created.json()["id"]
    assert test_ai_integration.factory is not None
    for _ in range(4):
        with test_ai_integration.factory() as db:
            jobs = db.scalars(select(AIStudioJob)).all()
            with monkeypatch.context() as patch:
                patch.setattr(
                    studio_worker,
                    "utcnow",
                    lambda jobs=jobs: max([datetime.now(UTC), *[job.available_at for job in jobs]]),
                )

                def unavailable(*args, **kwargs):
                    raise StudioProviderFailure("provider_unavailable")

                patch.setattr(studio_worker, "_provider_call", unavailable)
                studio_worker.run_ai_jobs_once(db, "wp7a5-bulk-fault", limit=2)
    barrier = Barrier(8)
    endpoint = "/api/v1/ai/studio/bulk/" + bulk_id

    def request(index):
        barrier.wait(timeout=10)
        return (
            client.post(endpoint + "/retry-failed", json={}, headers=ORIGIN)
            if index % 2
            else client.get(endpoint)
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(request, range(8)))
    assert all(response.status_code == 200 for response in results)
    assert sum(response.json().get("retried_count", 0) for response in results) == 2
    with test_ai_integration.factory() as db:
        studio_worker.run_ai_jobs_once(db, "wp7a5-bulk-recovered", limit=2)
    saved = client.get(endpoint).json()
    assert len(saved["outputs"]) == 2
    assert len({item["job_id"] for item in saved["outputs"]}) == 2
    assert all(item["artifact_id"] for item in saved["outputs"])


@pytest.mark.parametrize("path", ["ai/video/bulk/", "ai/seo/analyses/", "social/posts/"])
def test_missing_owned_resource_does_not_fall_back_to_another_record(client, path):
    setup_context(client)
    response = client.get("/api/v1/" + path + str(uuid.uuid4()))
    assert response.status_code == 404
