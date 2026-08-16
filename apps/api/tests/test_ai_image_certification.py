from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_ai_image_acceptance import (
    ORIGIN,
    _listing,
    _studio_artifact,
    _upload_source,
)
from test_ai_image_acceptance import acceptance_context as _acceptance_context  # noqa: F401

from vayujit_api.ai.image_models import AIImageOutput
from vayujit_api.ai.studio_worker import run_ai_jobs_once
from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_image_acceptance",)

pytestmark = pytest.mark.integration


def test_full_image_product_lifecycle_preserves_exact_lineage_and_handoffs(
    _acceptance_context: tuple[TestClient, sessionmaker[Session], dict[str, str]],  # noqa: F811
) -> None:
    """Exercise the guarded local workflow from source Media through downstream projections."""
    client, factory, ids = _acceptance_context
    source_id = _upload_source(client)
    source_before = client.get(f"/api/v1/media/{source_id}", headers=ORIGIN)
    source_bytes_before = client.get(f"/api/v1/media/{source_id}/preview", headers=ORIGIN)
    assert source_before.status_code == source_bytes_before.status_code == 200
    source_checksum = source_before.json()["checksum_sha256"]
    assert hashlib.sha256(source_bytes_before.content).hexdigest() == source_checksum

    style = client.post(
        "/api/v1/ai/images/styles",
        json={
            "brand_id": ids["brand_id"],
            "name": "Lifecycle style",
            "background_preference": "white",
            "photography_style": "clean",
            "guidance": "Use neutral lighting.",
        },
        headers=ORIGIN,
    )
    assert style.status_code == 201, style.text
    style_data = style.json()
    preset = client.post(
        "/api/v1/ai/images/presets",
        json={
            "name": "Lifecycle preset",
            "operation": "generate_product_image",
            "channel": "canonical",
            "rules": {"background": "white"},
        },
        headers=ORIGIN,
    )
    assert preset.status_code == 201, preset.text
    preset_data = preset.json()
    artifact = _studio_artifact(client, factory, ids, "lifecycle-artifact-v2")

    queued = client.post(
        "/api/v1/ai/images/generate",
        json={
            "brand_id": ids["brand_id"],
            "product_id": ids["product_id"],
            "source_media_ids": [source_id],
            "operation": "generate_product_image",
            "channel": "canonical",
            "style_id": style_data["id"],
            "preset_id": preset_data["id"],
            "content_artifact_id": artifact["id"],
            "content_artifact_version": artifact["version_number"],
            "width": 64,
            "height": 64,
            "idempotency_key": "full-image-lifecycle",
        },
        headers=ORIGIN,
    )
    assert queued.status_code == 202, queued.text
    with factory() as db:
        assert run_ai_jobs_once(db, "full-image-lifecycle-worker") == 1
    generation = client.get(
        f"/api/v1/ai/images/generations/{queued.json()['generation_id']}", headers=ORIGIN
    )
    assert generation.status_code == 200, generation.text
    output = generation.json()["outputs"][0]
    output_id = output["id"]
    detail = client.get(f"/api/v1/ai/images/outputs/{output_id}", headers=ORIGIN)
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()
    assert detail_data["status"] == "needs_review"
    assert detail_data["style_version"] == style_data["version"]
    assert detail_data["preset_version"] == preset_data["version"]
    assert detail_data["content_artifact_id"] == artifact["id"]
    assert detail_data["content_artifact_version"] == artifact["version_number"]

    generated_media_id = detail_data["media_id"]
    generated_media = client.get(f"/api/v1/media/{generated_media_id}", headers=ORIGIN)
    generated_bytes = client.get(f"/api/v1/media/{generated_media_id}/preview", headers=ORIGIN)
    assert generated_media.status_code == generated_bytes.status_code == 200
    assert (
        hashlib.sha256(generated_bytes.content).hexdigest()
        == generated_media.json()["checksum_sha256"]
    )
    comparison = client.get(f"/api/v1/ai/images/outputs/{output_id}/compare", headers=ORIGIN)
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["mode"] == "source_generated"

    for action, payload in (
        ("suggest", {"action": "suggest"}),
        ("edit", {"action": "edit", "text": "Clean product image on a white background."}),
        ("approve", {"action": "approve"}),
    ):
        alt_text = client.post(
            f"/api/v1/ai/images/outputs/{output_id}/alt-text",
            json=payload,
            headers=ORIGIN,
        )
        assert alt_text.status_code == 200, f"{action}: {alt_text.text}"
    approved = client.post(
        f"/api/v1/ai/images/outputs/{output_id}/approve", json={}, headers=ORIGIN
    )
    assert approved.status_code == 200, approved.text

    listing_id = _listing(factory, ids, "amazon")
    handoff_payload = {
        "marketplace": "amazon",
        "listing_id": listing_id,
        "position": 0,
        "role": "main",
        "idempotency_key": "full-image-amazon-handoff",
    }
    preview = client.post(
        f"/api/v1/ai/images/outputs/{output_id}/handoff/preview",
        json=handoff_payload,
        headers=ORIGIN,
    )
    assert preview.status_code == 200 and preview.json()["ready"] is True, preview.text
    handoff = client.post(
        f"/api/v1/ai/images/outputs/{output_id}/handoff",
        json={**handoff_payload, "fingerprint": preview.json()["fingerprint"]},
        headers=ORIGIN,
    )
    assert handoff.status_code == 200, handoff.text

    start = datetime.now().replace(microsecond=0)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "brand_id": ids["brand_id"],
            "name": "Full image campaign",
            "timezone_name": "UTC",
            "local_start_at": start.isoformat(),
            "local_end_at": (start + timedelta(hours=2)).isoformat(),
        },
        headers=ORIGIN,
    )
    assert campaign.status_code == 201, campaign.text
    activity = client.post(
        f"/api/v1/campaigns/{campaign.json()['id']}/activities",
        json={
            "product_id": ids["product_id"],
            "activity_type": "review_checkpoint",
            "name": "Full image campaign activity",
            "sequence": 1,
            "scheduled_local_date": start.date().isoformat(),
            "scheduled_local_time": start.time().isoformat(),
            "timezone_name": "UTC",
        },
        headers=ORIGIN,
    )
    assert activity.status_code == 201, activity.text
    campaign_handoff = client.post(
        f"/api/v1/ai/images/outputs/{output_id}/campaign-handoff",
        json={
            "campaign_id": campaign.json()["id"],
            "activity_id": activity.json()["id"],
            "expected_row_version": activity.json()["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert campaign_handoff.status_code == 200, campaign_handoff.text
    assert campaign_handoff.json()["output_id"] == output_id

    media_projection = client.get(
        f"/api/v1/ai/images/products/{ids['product_id']}/media", headers=ORIGIN
    )
    assert media_projection.status_code == 200, media_projection.text
    projected = next(
        item for item in media_projection.json() if item["media_id"] == generated_media_id
    )
    assert projected["image_output_id"] == output_id
    assert projected["marketplace_usage"]
    assert projected["campaign_usage"]
    channel_projection = client.get(
        f"/api/v1/ai/seo/products/{ids['product_id']}/channels", headers=ORIGIN
    )
    assert channel_projection.status_code == 200, channel_projection.text

    style_update = client.put(
        f"/api/v1/ai/images/styles/{style_data['id']}",
        json={
            "brand_id": ids["brand_id"],
            "name": "Lifecycle style updated",
            "background_preference": "white",
            "photography_style": "clean editorial",
            "guidance": "Updated only for future generations.",
        },
        headers=ORIGIN,
    )
    assert style_update.status_code == 200, style_update.text
    after_style = client.get(f"/api/v1/ai/images/outputs/{output_id}", headers=ORIGIN)
    after_bytes = client.get(f"/api/v1/media/{generated_media_id}/preview", headers=ORIGIN)
    assert after_style.status_code == after_bytes.status_code == 200
    assert after_style.json()["style_version"] == style_data["version"]
    assert after_bytes.content == generated_bytes.content

    third_artifact = _studio_artifact(client, factory, ids, "lifecycle-artifact-v3")
    artifact_version = artifact["version_number"]
    assert isinstance(artifact_version, int)
    assert third_artifact["version_number"] == artifact_version + 1
    after_artifact = client.get(f"/api/v1/ai/images/outputs/{output_id}", headers=ORIGIN)
    assert after_artifact.json()["content_artifact_version"] == artifact["version_number"]

    bulk = client.post(
        "/api/v1/ai/images/bulk",
        json={
            "product_ids": [ids["product_id"]],
            "channels": ["amazon", "flipkart", "meesho"],
            "operation": "generate_product_image",
            "source_media_by_product": {ids["product_id"]: [source_id]},
            "source_media_strategy": "selected",
            "width": 64,
            "height": 64,
            "idempotency_key": "full-image-bulk-source-immutability",
        },
        headers=ORIGIN,
    )
    assert bulk.status_code == 202, bulk.text
    with factory() as db:
        assert run_ai_jobs_once(db, "full-image-bulk-worker") == 3
    source_after = client.get(f"/api/v1/media/{source_id}", headers=ORIGIN)
    source_bytes_after = client.get(f"/api/v1/media/{source_id}/preview", headers=ORIGIN)
    assert source_after.json()["checksum_sha256"] == source_checksum
    assert source_bytes_after.content == source_bytes_before.content

    usage = client.get("/api/v1/ai/images/usage", headers=ORIGIN)
    diagnostics = client.get("/api/v1/ai/images/diagnostics", headers=ORIGIN)
    assert usage.status_code == diagnostics.status_code == 200
    assert usage.json()["modality"] == "image"
    assert diagnostics.json()["image_studio"] == "healthy"
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ai.image_campaign_handoff_completed")
            )
            == 1
        )
        assert db.scalar(select(func.count()).select_from(AIImageOutput)) == 4
