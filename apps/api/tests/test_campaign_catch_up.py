"""Guarded PostgreSQL acceptance tests for one durable Campaign catch-up."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_campaign_activity_rescheduling import ORIGIN, create_reschedule_scenario

from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import (
    CampaignActivity,
    CampaignActivityDependency,
    CampaignMissedActivityResolution,
    CampaignScheduleLink,
)
from vayujit_api.campaigns.schedule_service import project_activity_states
from vayujit_api.publishing.job_queue import claim_jobs
from vayujit_api.publishing.models import PublishingExecution, PublishingJob, PublishingSchedule
from vayujit_api.publishing.worker import execute_job

pytestmark = pytest.mark.integration
pytest_plugins = ("test_scheduler_integration",)


@pytest.fixture
def reschedule_harness(harness):
    return harness


def preview(client, scenario, **overrides: object):
    payload: dict[str, object] = {
        "activity_id": str(scenario.activity_id),
        "proposed_local_datetime": (datetime.now(UTC) + timedelta(minutes=2))
        .replace(microsecond=0, tzinfo=None)
        .isoformat(),
        "proposed_timezone": "UTC",
        "reason": "Catch-up acceptance.",
        "expected_activity_row_version": scenario.expected_row_version,
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/campaigns/{scenario.campaign_id}/recovery/create-one-catch-up/preview",
        json=payload,
        headers=ORIGIN,
    )


def confirm(client, scenario, body: dict[str, object], **overrides: object):
    payload: dict[str, object] = {
        "action": "create_one_catch_up",
        "campaign_id": str(scenario.campaign_id),
        "activity_id": str(scenario.activity_id),
        "expected_activity_row_version": scenario.expected_row_version,
        "proposed_local_datetime": body["proposed_local_datetime"],
        "proposed_timezone": body["timezone"],
        "reason": "Catch-up acceptance.",
        "preview_fingerprint": body["preview_fingerprint"],
        "confirm": True,
    }
    if body.get("fold") is not None:
        payload["fold"] = body["fold"]
    payload.update(overrides)
    return client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)


def test_catch_up_preview_is_non_mutating(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    with sessions() as db:
        before = (
            db.scalar(select(func.count()).select_from(CampaignActivity)),
            db.scalar(select(func.count()).select_from(CampaignScheduleLink)),
            db.scalar(select(func.count()).select_from(PublishingSchedule)),
            db.scalar(select(func.count()).select_from(PublishingJob)),
        )
    response = preview(client, scenario)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["original_activity_status"] == "missed"
    assert body["artifact_version"] == scenario.artifact_version
    with sessions() as db:
        after = (
            db.scalar(select(func.count()).select_from(CampaignActivity)),
            db.scalar(select(func.count()).select_from(CampaignScheduleLink)),
            db.scalar(select(func.count()).select_from(PublishingSchedule)),
            db.scalar(select(func.count()).select_from(PublishingJob)),
        )
    assert after == before


def test_successful_catch_up_preserves_original_and_creates_one_durable_occurrence(
    reschedule_harness,
) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    with sessions() as db:
        original = db.get(CampaignActivity, scenario.activity_id)
        assert original is not None
        original_snapshot = (original.id, original.status, original.row_version, original.job_id)
    body = preview(client, scenario).json()
    response = confirm(client, scenario, body)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["outcome"] == "succeeded"
    with sessions() as db:
        original = db.get(CampaignActivity, scenario.activity_id)
        replacements = list(
            db.scalars(
                select(CampaignActivity).where(
                    CampaignActivity.replaces_activity_id == scenario.activity_id
                )
            )
        )
        assert original is not None
        assert (
            original.id,
            original.status,
            original.row_version,
            original.job_id,
        ) == original_snapshot
        assert len(replacements) == 1
        replacement = replacements[0]
        assert replacement.product_id == scenario.product_id
        assert replacement.artifact_id == scenario.artifact_id
        assert replacement.artifact_version == scenario.artifact_version
        assert replacement.schedule_id is not None
        assert replacement.job_id is not None
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 0
        assert db.scalar(select(func.count()).select_from(CampaignMissedActivityResolution)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "campaign.catch_up_created")
            )
            == 1
        )


def test_repeated_catch_up_confirmation_reuses_existing_result(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    first = confirm(client, scenario, body)
    second = confirm(client, scenario, body)
    assert first.status_code == second.status_code == 200
    assert second.json()["result"]["idempotent_reuse"] is True
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CampaignActivity)
                .where(CampaignActivity.replaces_activity_id == scenario.activity_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "campaign.catch_up_created")
            )
            == 1
        )


def test_catch_up_job_executes_once_without_duplicate_execution(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    response = confirm(client, scenario, body)
    assert response.status_code == 200, response.text
    catch_up_id = response.json()["result"]["resource_ids"]["activity_id"]
    with sessions() as db:
        replacement = db.get(CampaignActivity, catch_up_id)
        assert replacement and replacement.job_id
        job = db.get(PublishingJob, replacement.job_id)
        assert job
        original_job = db.get(PublishingJob, scenario.original_job_id)
        assert original_job
        original_job.available_at_utc = datetime.now(UTC) + timedelta(days=1)
        original_job.scheduled_at_utc = original_job.available_at_utc
        job.available_at_utc = datetime.now(UTC) - timedelta(seconds=1)
        job.scheduled_at_utc = job.available_at_utc
        db.commit()
        claimed = claim_jobs(db, "catch-up-worker", 1, 60)
        assert claimed == [job.id]
    execute_job(claimed[0], "catch-up-worker")
    execute_job(claimed[0], "catch-up-worker")
    with sessions() as db:
        replacement = db.get(CampaignActivity, catch_up_id)
        assert replacement
        assert project_activity_states(db, scenario.campaign_id) >= 1
        db.refresh(replacement)
        assert replacement.status == "succeeded"
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 1
        job = db.get(PublishingJob, claimed[0])
        assert job and job.state == "succeeded"


@pytest.mark.parametrize("status", ["scheduled", "succeeded", "cancelled"])
def test_non_missed_activity_is_rejected(reschedule_harness, status: str) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions, activity_status=status)
    response = preview(client, scenario)
    assert response.status_code == 409


def test_catch_up_rejects_stale_fingerprint_without_mutation(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    response = confirm(client, scenario, body, preview_fingerprint="stale")
    assert response.status_code == 409
    assert "stale" in response.text.lower()
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CampaignActivity)
                .where(CampaignActivity.replaces_activity_id == scenario.activity_id)
            )
            == 0
        )


def test_catch_up_preserves_dependency_intent(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    with sessions() as db:
        predecessor = db.get(CampaignActivity, scenario.activity_id)
        assert predecessor is not None
        successor = db.scalar(
            select(CampaignActivity).where(CampaignActivity.id != scenario.activity_id)
        )
        if successor is None:
            pytest.skip("Fixture has no successor Activity.")
        db.add(
            CampaignActivityDependency(
                owner_id=predecessor.owner_id,
                campaign_id=predecessor.campaign_id,
                predecessor_activity_id=predecessor.id,
                successor_activity_id=successor.id,
                dependency_type="success_required",
                released_at=None,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    body = preview(client, scenario).json()
    assert confirm(client, scenario, body).status_code == 200
    with sessions() as db:
        replacement_id = db.scalar(
            select(CampaignActivity.id).where(
                CampaignActivity.replaces_activity_id == scenario.activity_id
            )
        )
        assert replacement_id is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(CampaignActivityDependency)
                .where(
                    CampaignActivityDependency.predecessor_activity_id == replacement_id,
                    CampaignActivityDependency.successor_activity_id == successor.id,
                )
            )
            == 1
        )
