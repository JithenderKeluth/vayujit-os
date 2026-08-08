"""Guarded local end-to-end release-candidate journey using the mock publisher."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_scheduler_integration import ORIGIN, business

from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignMissedActivityResolution,
)
from vayujit_api.campaigns.schedule_service import project_activity_states
from vayujit_api.campaigns.workflow_service import project_campaign_state
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingExecution, PublishingJob
from vayujit_api.publishing.scheduler_service import materialize_due_schedules
from vayujit_api.publishing.worker import execute_job

pytestmark = pytest.mark.integration
pytest_plugins = ("test_scheduler_integration",)


def workflow_action(client, payload: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json={"correlation_id": f"release-{uuid.uuid4().hex[:12]}", **payload},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_release_candidate_campaign_journey(harness) -> None:
    client, sessions = harness
    product, artifact, destination = business(client)

    assert client.get("/api/v1/auth/me").status_code == 200
    brand_activation = client.post(f"/api/v1/brands/{product['brand_id']}/activate", headers=ORIGIN)
    assert brand_activation.status_code == 200, brand_activation.text
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "scheduler@example.com", "password": "correct horse battery staple"},
        headers=ORIGIN,
    )
    assert login.status_code == 200, login.text

    stamp = datetime.now(UTC).replace(microsecond=0)
    campaign = workflow_action(
        client,
        {
            "action": "create_campaign",
            "campaign": {
                "brand_id": product["brand_id"],
                "name": "Release candidate journey",
                "timezone_name": "UTC",
                "local_start_at": (stamp - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
                "local_end_at": (stamp + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            },
        },
    )
    campaign_id = str(campaign["campaign_id"])
    activity_ids: list[str] = []
    for sequence, required in ((1, True), (2, False)):
        activity = workflow_action(
            client,
            {
                "action": "add_campaign_activity",
                "campaign_id": campaign_id,
                "activity": {
                    "product_id": product["id"],
                    "artifact_id": artifact["id"],
                    "destination_id": destination["id"],
                    "activity_type": "mock_publish",
                    "name": f"Release activity {sequence}",
                    "sequence": sequence,
                    "scheduled_local_date": (stamp - timedelta(minutes=1)).date().isoformat(),
                    "scheduled_local_time": (stamp - timedelta(minutes=1)).time().isoformat(),
                    "timezone_name": "UTC",
                    "required": required,
                },
            },
        )
        activity_ids.append(str(activity["activity_id"]))

    workflow_action(client, {"action": "validate_campaign", "campaign_id": campaign_id})
    workflow_action(
        client,
        {"action": "release_campaign", "campaign_id": campaign_id, "confirm": True},
    )
    workflow_action(
        client,
        {
            "action": "schedule_campaign",
            "campaign_id": campaign_id,
            "request": {
                "activity_ids": activity_ids,
                "behavior": "require_all_ready",
                "confirm": True,
            },
        },
    )

    with sessions() as db:
        assert materialize_due_schedules(db) == 2
        project_activity_states(db, uuid.UUID(campaign_id))
        jobs = list(db.scalars(select(PublishingJob).order_by(PublishingJob.created_at)))
        assert len(jobs) == 2
        optional_activity = db.get(CampaignActivity, uuid.UUID(activity_ids[1]))
        assert optional_activity and optional_activity.job_id
        optional_job = db.get(PublishingJob, optional_activity.job_id)
        assert optional_job and optional_job.state == "pending"
        optional_job.available_at_utc = now() + timedelta(days=1)
        optional_job.scheduled_at_utc = optional_job.available_at_utc
        optional_activity.status = "missed"
        db.commit()
        first_job = claim_jobs(db, "release-worker", 1, 60)[0]

    execute_job(first_job, "release-worker")
    with sessions() as db:
        assert project_activity_states(db, uuid.UUID(campaign_id)) >= 1
        first = db.get(CampaignActivity, uuid.UUID(activity_ids[0]))
        optional = db.get(CampaignActivity, uuid.UUID(activity_ids[1]))
        assert first and first.status == "succeeded"
        assert optional and optional.status == "missed"
        expected_row_version = optional.row_version

    proposed = (datetime.now(UTC) + timedelta(minutes=2)).replace(microsecond=0)
    preview = client.post(
        f"/api/v1/campaigns/{campaign_id}/recovery/create-one-catch-up/preview",
        json={
            "activity_id": activity_ids[1],
            "proposed_local_datetime": proposed.replace(tzinfo=None).isoformat(),
            "proposed_timezone": "UTC",
            "reason": "Release candidate catch-up journey.",
            "expected_activity_row_version": expected_row_version,
        },
        headers=ORIGIN,
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    confirmed = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "create_one_catch_up",
            "campaign_id": campaign_id,
            "activity_id": activity_ids[1],
            "expected_activity_row_version": expected_row_version,
            "proposed_local_datetime": preview_body["proposed_local_datetime"],
            "proposed_timezone": preview_body["timezone"],
            "reason": "Release candidate catch-up journey.",
            "preview_fingerprint": preview_body["preview_fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    catch_up_id = uuid.UUID(confirmed.json()["result"]["activity_id"])

    with sessions() as db:
        catch_up = db.get(CampaignActivity, catch_up_id)
        assert catch_up and catch_up.job_id
        catch_up_job = db.get(PublishingJob, catch_up.job_id)
        assert catch_up_job
        catch_up_job.available_at_utc = now() - timedelta(seconds=1)
        catch_up_job.scheduled_at_utc = catch_up_job.available_at_utc
        db.commit()
        claimed = claim_jobs(db, "catch-up-worker", 1, 60)
        assert claimed == [catch_up_job.id]

    execute_job(claimed[0], "catch-up-worker")
    with sessions() as db:
        assert project_activity_states(db, uuid.UUID(campaign_id)) >= 1
        original = db.get(CampaignActivity, uuid.UUID(activity_ids[1]))
        replacement = db.get(CampaignActivity, catch_up_id)
        assert original and original.status == "missed"
        assert replacement and replacement.status == "succeeded"
        campaign_value = db.get(Campaign, uuid.UUID(campaign_id))
        assert campaign_value and project_campaign_state(db, campaign_value) == "completed"
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 2
        assert db.scalar(select(func.count()).select_from(CampaignMissedActivityResolution)) == 1
        actions = set(db.scalars(select(AuditEvent.action)))
        assert "campaign.catch_up_created" in actions
        assert "publishing.execution_succeeded" in actions
        assert db.scalar(select(User.id)) is not None
    operations = client.get("/api/v1/operations/history")
    assert operations.status_code == 200, operations.text
