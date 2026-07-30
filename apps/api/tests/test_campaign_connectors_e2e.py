import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_scheduler_integration import ORIGIN, business

from vayujit_api.campaigns.models import CampaignActivity, CampaignScheduleLink
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingExecution, PublishingJob
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job

pytestmark = pytest.mark.integration
pytest_plugins = ("test_scheduler_integration",)


def action(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json={"correlation_id": f"campaign-{uuid.uuid4().hex[:12]}", **payload},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_campaign_fake_connectors_two_workers_and_duplicate_prevention(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, sessions = harness
    product, artifact, _ = business(client)
    brand_id = client.get(f"/api/v1/products/{product['id']}").json()["brand_id"]
    client.put(
        "/api/v1/publishing/connectors/wordpress",
        json={
            "site_url": "http://127.0.0.1",
            "username": "owner",
            "enabled": False,
            "default_post_status": "draft",
            "request_timeout_seconds": 10,
            "max_retry_attempts": 2,
        },
        headers=ORIGIN,
    )
    client.post("/api/v1/publishing/connectors/wordpress/validate", headers=ORIGIN)
    client.post("/api/v1/publishing/connectors/wordpress/enable", headers=ORIGIN)
    wordpress_response = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Campaign WordPress",
            "brand_id": brand_id,
            "connector_key": "wordpress",
            "configuration": {
                "post_status": "draft",
                "category_ids": [],
                "tag_ids": [],
                "media_policy": "fail",
                "featured_image_policy": "none",
                "update_existing_remote_post": True,
                "content_mapping_version": 1,
            },
        },
        headers=ORIGIN,
    )
    assert wordpress_response.status_code == 201, wordpress_response.text
    wordpress = wordpress_response.json()
    client.put(
        "/api/v1/publishing/connectors/shopify",
        json={
            "shop_domain": "test-shop.myshopify.com",
            "access_token": "shpat_campaign_fake_only",
            "api_version": "2026-07",
            "default_product_status": "draft",
            "default_publication_ids": [],
            "inventory_policy": "no_inventory_write",
            "variant_policy": "default_variant",
            "media_policy": "fail",
            "request_timeout_seconds": 45,
            "max_retry_attempts": 3,
        },
        headers=ORIGIN,
    )
    client.post("/api/v1/publishing/connectors/shopify/validate", headers=ORIGIN)
    client.post("/api/v1/publishing/connectors/shopify/enable", headers=ORIGIN)
    shopify_response = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Campaign Shopify",
            "brand_id": brand_id,
            "connector_key": "shopify",
            "configuration": {
                "default_product_status": "draft",
                "default_collection_ids": [],
                "default_publication_ids": [],
                "default_vendor": "",
                "default_product_type": "",
                "default_tags": [],
                "variant_policy": "default_variant",
                "inventory_policy": "no_inventory_write",
                "media_policy": "fail",
                "update_existing_remote_product": True,
                "content_mapping_version": 1,
            },
        },
        headers=ORIGIN,
    )
    assert shopify_response.status_code == 201, shopify_response.text
    shopify = shopify_response.json()
    due = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)
    created = action(
        client,
        {
            "action": "create_campaign",
            "campaign": {
                "brand_id": brand_id,
                "name": "Connector acceptance",
                "timezone_name": "UTC",
                "local_start_at": (due - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
                "local_end_at": (due + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            },
        },
    )
    campaign_id = created["campaign_id"]
    activities: list[str] = []
    for sequence, activity_type, destination in (
        (1, "wordpress_create_draft", wordpress),
        (2, "shopify_create_draft", shopify),
    ):
        result = action(
            client,
            {
                "action": "add_campaign_activity",
                "campaign_id": campaign_id,
                "activity": {
                    "product_id": product["id"],
                    "artifact_id": artifact["id"],
                    "destination_id": destination["id"],
                    "activity_type": activity_type,
                    "name": activity_type,
                    "sequence": sequence,
                    "scheduled_local_date": due.date().isoformat(),
                    "scheduled_local_time": due.time().isoformat(),
                    "timezone_name": "UTC",
                    "required": True,
                },
            },
        )
        activities.append(str(result["activity_id"]))
    action(client, {"action": "validate_campaign", "campaign_id": campaign_id})
    action(
        client,
        {"action": "release_campaign", "campaign_id": campaign_id, "confirm": True},
    )
    action(
        client,
        {
            "action": "schedule_campaign",
            "campaign_id": campaign_id,
            "request": {
                "activity_ids": activities,
                "behavior": "require_all_ready",
                "confirm": True,
            },
        },
    )
    with sessions() as db:
        materialize_due_schedules(db)
        first = claim_jobs(db, "campaign-worker-a", 1, 60)
        second = claim_jobs(db, "campaign-worker-b", 1, 60)
        assert len(first) == len(second) == 1 and first[0] != second[0]
    execute_job(first[0], "campaign-worker-a")
    execute_job(second[0], "campaign-worker-b")
    execute_job(first[0], "campaign-worker-a")
    execute_job(second[0], "campaign-worker-b")
    with sessions() as db:
        jobs = list(db.scalars(select(PublishingJob).order_by(PublishingJob.id)))
        assert all(job.state == "succeeded" for job in jobs)
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 2
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 2
        projected = list(db.scalars(select(CampaignActivity)))
        assert {value.artifact_version for value in projected} == {artifact["version_number"]}
