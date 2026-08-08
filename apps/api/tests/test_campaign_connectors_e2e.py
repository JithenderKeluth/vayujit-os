import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_scheduler_integration import ORIGIN, business, connector_state

from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import CampaignActivity, CampaignScheduleLink
from vayujit_api.campaigns.schedule_service import project_activity_states
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.publishing.job_queue import (
    claim_jobs,
    finish_job,
    recover_expired_leases,
    start_attempt,
)
from vayujit_api.publishing.models import (
    PublishingExecution,
    PublishingJob,
    PublishingRecoveryRecord,
)
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.schemas import CreateExecution
from vayujit_api.publishing.service import create_execution
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


@pytest.mark.parametrize(
    "activity_order",
    [
        ("wordpress", "shopify"),
        ("shopify", "wordpress"),
    ],
)
def test_campaign_fake_connectors_two_workers_and_duplicate_prevention(
    harness: tuple[TestClient, sessionmaker[Session]],
    activity_order: tuple[str, str],
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
    destinations = {"wordpress": wordpress, "shopify": shopify}
    for sequence, connector_key in enumerate(activity_order, start=1):
        activity_type = f"{connector_key}_create_draft"
        destination = destinations[connector_key]
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
    assert len(connector_state.wordpress_posts) == 0
    assert len(connector_state.shopify_products) == 0
    with sessions() as db:
        assert start_attempt(db, first[0], "campaign-worker-a")
        crashed_job = db.get(PublishingJob, first[0])
        assert crashed_job
        crashed_job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_leases(db) == 1
        db.refresh(crashed_job)
        assert crashed_job.state == "retry_wait"
        assert crashed_job.lease_owner is None
        assert finish_job(db, first[0], "campaign-worker-a", succeeded=True) == "lease_lost"
        crashed_job.available_at_utc = now() - timedelta(seconds=1)
        db.commit()
        recovered = claim_jobs(db, "campaign-worker-recovery", 1, 60)
        assert recovered == first
    assert len(connector_state.wordpress_posts) == 0
    assert len(connector_state.shopify_products) == 0
    execute_job(first[0], "campaign-worker-recovery")
    with sessions() as db:
        assert start_attempt(db, second[0], "campaign-worker-b")
        remote_success_job = db.get(PublishingJob, second[0])
        owner = db.scalar(select(User))
        assert remote_success_job and owner
        assert remote_success_job.destination_id == uuid.UUID(
            str(destinations[activity_order[1]]["id"])
        )
        remote_success = create_execution(
            db,
            owner,
            CreateExecution(
                artifact_id=remote_success_job.artifact_id,
                destination_id=remote_success_job.destination_id,
                idempotency_key=f"job:{remote_success_job.id}",
                action=cast(Any, remote_success_job.requested_action),
            ),
        )
        assert remote_success.status == "succeeded"
        db.refresh(remote_success_job)
        assert remote_success_job.state == "running"
        remote_success_job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
        assert recover_expired_leases(db) == 1
        db.refresh(remote_success_job)
        assert remote_success_job.state == "succeeded"
        assert remote_success_job.publishing_execution_id == remote_success.id
        assert finish_job(db, second[0], "campaign-worker-b", succeeded=True) == "lease_lost"
    wordpress_post_count = len(connector_state.wordpress_posts)
    shopify_product_count = len(connector_state.shopify_products)
    wordpress_request_count = len(connector_state.wordpress_requests)
    shopify_request_count = len(connector_state.shopify_requests)
    with sessions() as db:
        assert materialize_due_schedules(db) == 0
    execute_job(first[0], "campaign-worker-a")
    execute_job(second[0], "campaign-worker-b")
    assert len(connector_state.wordpress_posts) == wordpress_post_count == 1
    assert len(connector_state.shopify_products) == shopify_product_count == 1
    assert len(connector_state.wordpress_requests) == wordpress_request_count
    assert len(connector_state.shopify_requests) == shopify_request_count
    wordpress_post = connector_state.wordpress_posts[81]
    shopify_product = connector_state.shopify_products["gid://shopify/Product/42"]
    assert wordpress_post["status"] == "draft"
    assert shopify_product["status"] == "DRAFT"
    assert len(cast(list[object], shopify_product["variants"])) == 1
    assert shopify_product["media"] == []
    assert shopify_product["collections"] == []
    assert shopify_product["publications"] == []
    with sessions() as db:
        jobs = list(db.scalars(select(PublishingJob).order_by(PublishingJob.id)))
        executions = list(
            db.scalars(select(PublishingExecution).order_by(PublishingExecution.connector_key))
        )
        assert all(job.state == "succeeded" for job in jobs)
        assert len(executions) == 2
        assert {execution.remote_entity_id for execution in executions} == {
            "81",
            "gid://shopify/Product/42",
        }
        assert {execution.idempotency_key for execution in executions} == {
            f"job:{job.id}" for job in jobs
        }
        assert {str(execution.artifact_id) for execution in executions} == {str(artifact["id"])}
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingRecoveryRecord)) == 2
        recovery_results = set(db.scalars(select(PublishingRecoveryRecord.result)))
        assert recovery_results == {"retry_wait", "remote_succeeded"}
        assert project_activity_states(db, uuid.UUID(str(campaign_id))) == 2
        projected = list(db.scalars(select(CampaignActivity)))
        assert all(value.status == "succeeded" for value in projected)
        assert {value.artifact_version for value in projected} == {artifact["version_number"]}
        for value in projected:
            value.status = "reconciliation_required"
        db.commit()

    remote_counts = (
        len(connector_state.wordpress_posts),
        len(connector_state.shopify_products),
    )
    execution_ids: set[str] = set()
    for activity_id in activities:
        payload = {
            "action": "reconcile_activity",
            "campaign_id": campaign_id,
            "activity_id": activity_id,
            "reason": "Guarded Campaign connector reconciliation.",
            "confirm": True,
        }
        response = client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["status"] == "succeeded"
        repeated = client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["result"]["idempotent_reuse"] is True
        execution_ids.add(str(repeated.json()["result"]["publishing_execution_id"]))
    assert (
        remote_counts
        == (
            len(connector_state.wordpress_posts),
            len(connector_state.shopify_products),
        )
        == (1, 1)
    )
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingRecoveryRecord)) == 4
        assert len(execution_ids) == 2
        assert all(value.status == "succeeded" for value in db.scalars(select(CampaignActivity)))
        audit_actions = set(db.scalars(select(AuditEvent.action)))
        assert "campaign.activity_reconciled" in audit_actions

    rejected = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "reconcile_activity",
            "campaign_id": campaign_id,
            "activity_id": activities[0],
            "confirm": True,
        },
    )
    assert rejected.status_code == 403

    replacement_generation = client.post(
        "/api/v1/ai/generations", json={"product_id": product["id"]}, headers=ORIGIN
    )
    assert replacement_generation.status_code == 201, replacement_generation.text
    replacement_artifact = client.post(
        f"/api/v1/ai/artifacts/{replacement_generation.json()['artifact_id']}/approve",
        headers=ORIGIN,
    )
    assert replacement_artifact.status_code == 200, replacement_artifact.text
    with sessions() as db:
        original = db.get(CampaignActivity, uuid.UUID(activities[0]))
        assert original
        original.status = "failed"
        original.failure_code = "approval_revoked"
        original.safe_failure_message = "The approved version was revoked."
        db.commit()
        expected_row_version = original.row_version
    replacement_payload = {
        "action": "replace_with_new_approved_activity",
        "campaign_id": campaign_id,
        "activity_id": activities[0],
        "replacement_artifact_id": replacement_artifact.json()["id"],
        "replacement_artifact_version": replacement_artifact.json()["version_number"],
        "expected_activity_row_version": expected_row_version,
        "reason": "Use the newly approved exact Artifact version.",
        "confirm": True,
    }
    replacement_response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json=replacement_payload,
        headers=ORIGIN,
    )
    assert replacement_response.status_code == 200, replacement_response.text
    replacement_result = replacement_response.json()["result"]
    assert replacement_result["scheduled"] is False
    assert replacement_result["idempotent_reuse"] is False
    repeated_replacement = client.post(
        "/api/v1/campaigns/recovery/actions",
        json=replacement_payload,
        headers=ORIGIN,
    )
    assert repeated_replacement.status_code == 200, repeated_replacement.text
    assert repeated_replacement.json()["result"]["idempotent_reuse"] is True
    assert (
        repeated_replacement.json()["result"]["replacement_activity_id"]
        == replacement_result["replacement_activity_id"]
    )
    with sessions() as db:
        original = db.get(CampaignActivity, uuid.UUID(activities[0]))
        replacement = db.get(
            CampaignActivity, uuid.UUID(replacement_result["replacement_activity_id"])
        )
        assert original and replacement
        assert original.status == "failed"
        assert original.schedule_id is not None and original.job_id is not None
        assert original.replaced_by_activity_id == replacement.id
        assert replacement.replaces_activity_id == original.id
        assert replacement.status == "draft"
        assert replacement.schedule_id is None and replacement.job_id is None
        assert replacement.publishing_execution_id is None
        assert replacement.artifact_id == uuid.UUID(str(replacement_artifact.json()["id"]))
        assert replacement.artifact_version == replacement_artifact.json()["version_number"]
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 2
        assert "campaign.artifact_version_replaced" in set(db.scalars(select(AuditEvent.action)))
