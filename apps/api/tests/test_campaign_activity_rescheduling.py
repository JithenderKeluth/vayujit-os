"""Guarded PostgreSQL acceptance tests for durable Campaign Activity rescheduling."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from helpers.campaign_replacement_fixture import assert_safe_replacement_error
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_scheduler_integration import ORIGIN, business

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityReschedule,
    CampaignScheduleLink,
)
from vayujit_api.campaigns.recovery_service import RECOVERY_ACTION_REGISTRY
from vayujit_api.identity.service import now
from vayujit_api.publishing.job_queue import claim_jobs, recover_expired_leases
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
    PublishingJob,
    PublishingJobAttempt,
    PublishingSchedule,
)
from vayujit_api.publishing.scheduler_service import materialize_due_schedules

pytestmark = pytest.mark.integration
pytest_plugins = ("test_scheduler_integration",)


@dataclass(frozen=True)
class RescheduleScenario:
    campaign_id: uuid.UUID
    activity_id: uuid.UUID
    owner_id: uuid.UUID
    product_id: uuid.UUID
    artifact_id: uuid.UUID
    artifact_version: int
    destination_id: uuid.UUID
    expected_row_version: int
    original_schedule_id: uuid.UUID
    original_job_id: uuid.UUID
    proposed_local_datetime: datetime


@pytest.fixture
def reschedule_harness(harness):
    return harness


def create_reschedule_scenario(
    client: TestClient,
    sessions: sessionmaker[Session],
    *,
    activity_status: str = "missed",
    due: bool = True,
) -> RescheduleScenario:
    product, artifact, destination = business(client)
    stamp = datetime.now(UTC).replace(microsecond=0)
    campaign_response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json={
            "action": "create_campaign",
            "campaign": {
                "brand_id": destination["brand_id"],
                "name": "Durable rescheduling campaign",
                "timezone_name": "UTC",
                "local_start_at": (stamp - timedelta(days=2)).replace(tzinfo=None).isoformat(),
                "local_end_at": (stamp + timedelta(days=2)).replace(tzinfo=None).isoformat(),
            },
        },
        headers=ORIGIN,
    )
    assert campaign_response.status_code == 200, campaign_response.text
    campaign_id = uuid.UUID(str(campaign_response.json()["campaign_id"]))
    scheduled = stamp - timedelta(minutes=1) if due else stamp + timedelta(hours=1)
    activity_response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json={
            "action": "add_campaign_activity",
            "campaign_id": str(campaign_id),
            "activity": {
                "product_id": product["id"],
                "artifact_id": artifact["id"],
                "destination_id": destination["id"],
                "activity_type": "wordpress_create_draft",
                "name": "Durable rescheduling activity",
                "sequence": 1,
                "scheduled_local_date": scheduled.date().isoformat(),
                "scheduled_local_time": scheduled.time().isoformat(),
                "timezone_name": "UTC",
            },
        },
        headers=ORIGIN,
    )
    assert activity_response.status_code == 200, activity_response.text
    activity_id = uuid.UUID(str(activity_response.json()["activity_id"]))
    assert (
        client.post(f"/api/v1/campaigns/{campaign_id}/validate", headers=ORIGIN).status_code == 200
    )
    schedule_response = client.post(
        f"/api/v1/campaigns/{campaign_id}/activities/{activity_id}/schedule", headers=ORIGIN
    )
    assert schedule_response.status_code == 200, schedule_response.text
    with sessions() as db:
        materialize_due_schedules(db)
        activity = db.get(CampaignActivity, activity_id)
        assert activity is not None and activity.schedule_id is not None
        from vayujit_api.campaigns.schedule_service import project_activity_states

        project_activity_states(db, campaign_id)
        db.refresh(activity)
        assert activity.job_id is not None
        activity.status = activity_status
        activity.updated_at = now()
        db.commit()
        return RescheduleScenario(
            campaign_id=campaign_id,
            activity_id=activity_id,
            owner_id=activity.owner_id,
            product_id=uuid.UUID(str(product["id"])),
            artifact_id=uuid.UUID(str(artifact["id"])),
            artifact_version=int(artifact["version_number"]),
            destination_id=uuid.UUID(str(destination["id"])),
            expected_row_version=activity.row_version,
            original_schedule_id=activity.schedule_id,
            original_job_id=activity.job_id,
            proposed_local_datetime=stamp + timedelta(minutes=1),
        )


def preview(client: TestClient, scenario: RescheduleScenario, **overrides: object):
    payload: dict[str, object] = {
        "activity_id": str(scenario.activity_id),
        "proposed_local_datetime": scenario.proposed_local_datetime.isoformat(),
        "proposed_timezone": "UTC",
        "reason": "Durable rescheduling acceptance.",
        "expected_activity_row_version": scenario.expected_row_version,
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/campaigns/{scenario.campaign_id}/recovery/reschedule-activity/preview",
        json=payload,
        headers=ORIGIN,
    )


def confirm(
    client: TestClient,
    scenario: RescheduleScenario,
    preview_body: dict[str, object],
    **overrides: object,
):
    payload: dict[str, object] = {
        "action": "reschedule_activity",
        "campaign_id": str(scenario.campaign_id),
        "activity_id": str(scenario.activity_id),
        "expected_activity_row_version": scenario.expected_row_version,
        "proposed_local_datetime": preview_body["proposed_local_datetime"],
        "proposed_timezone": preview_body["timezone"],
        "preview_fingerprint": preview_body["preview_fingerprint"],
        "reason": "Durable rescheduling acceptance.",
        "confirm": True,
    }
    if preview_body.get("fold") is not None:
        payload["fold"] = preview_body["fold"]
    payload.update(overrides)
    return client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)


def counts(db: Session) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        db.scalar(select(func.count()).select_from(CampaignActivity)) or 0,
        db.scalar(select(func.count()).select_from(CampaignActivityReschedule)) or 0,
        db.scalar(select(func.count()).select_from(CampaignScheduleLink)) or 0,
        db.scalar(select(func.count()).select_from(PublishingSchedule)) or 0,
        db.scalar(select(func.count()).select_from(PublishingJob)) or 0,
        db.scalar(select(func.count()).select_from(PublishingJobAttempt)) or 0,
        db.scalar(select(func.count()).select_from(PublishingExecution)) or 0,
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "campaign.activity_rescheduled")
        )
        or 0,
    )


def test_rescheduling_happy_path_is_durable_and_non_publishing(
    reschedule_harness,
) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    with sessions() as db:
        before = counts(db)
    preview_response = preview(client, scenario)
    assert preview_response.status_code == 200, preview_response.text
    preview_body = preview_response.json()
    with sessions() as db:
        assert counts(db) == before
    response = confirm(client, scenario, preview_body)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["outcome"] == "succeeded"
    with sessions() as db:
        activity = db.get(CampaignActivity, scenario.activity_id)
        original_schedule = db.get(PublishingSchedule, scenario.original_schedule_id)
        original_job = db.get(PublishingJob, scenario.original_job_id)
        record = db.scalar(select(CampaignActivityReschedule))
        replacement = db.get(PublishingSchedule, activity.schedule_id) if activity else None
        replacement_job = (
            db.scalar(select(PublishingJob).where(PublishingJob.schedule_id == replacement.id))
            if replacement
            else None
        )
        assert activity and replacement and replacement_job and record
        assert activity.product_id == scenario.product_id
        assert activity.artifact_id == scenario.artifact_id
        assert activity.artifact_version == scenario.artifact_version
        assert replacement.destination_id == scenario.destination_id
        assert replacement.artifact_id == scenario.artifact_id
        assert original_schedule and original_schedule.archived is True
        assert original_job and original_job.state == "cancelled"
        assert record.original_schedule_id == scenario.original_schedule_id
        assert record.replacement_schedule_id == replacement.id
        assert record.original_job_id == scenario.original_job_id
        assert record.replacement_job_id == replacement_job.id
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 0
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "campaign.activity_rescheduled")
        )
        assert event and str(event.metadata_json["campaign_id"]) == str(scenario.campaign_id)
        assert "artifact" not in str(event.metadata_json).lower()
        assert materialize_due_schedules(db) == 0


def test_repeated_confirmation_reuses_one_durable_result(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    first = confirm(client, scenario, body)
    second = confirm(client, scenario, body)
    assert first.status_code == second.status_code == 200
    assert second.json()["result"]["idempotent_reuse"] is True
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(CampaignActivityReschedule)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 2
        assert db.scalar(select(func.count()).select_from(CampaignScheduleLink)) == 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "campaign.activity_rescheduled")
            )
            == 1
        )


def test_readiness_and_successor_timing_are_recomputed_without_auto_reschedule(
    reschedule_harness,
) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    successor_time = scenario.proposed_local_datetime + timedelta(hours=1)
    successor_response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json={
            "action": "add_campaign_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity": {
                "product_id": str(scenario.product_id),
                "artifact_id": str(scenario.artifact_id),
                "destination_id": str(scenario.destination_id),
                "activity_type": "wordpress_create_draft",
                "name": "Rescheduling successor",
                "sequence": 2,
                "scheduled_local_date": successor_time.date().isoformat(),
                "scheduled_local_time": successor_time.time().isoformat(),
                "timezone_name": "UTC",
            },
        },
        headers=ORIGIN,
    )
    assert successor_response.status_code == 200, successor_response.text
    successor_id = uuid.UUID(str(successor_response.json()["activity_id"]))
    dependency_response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json={
            "action": "add_campaign_dependency",
            "campaign_id": str(scenario.campaign_id),
            "dependency": {
                "predecessor_activity_id": str(scenario.activity_id),
                "successor_activity_id": str(successor_id),
                "dependency_type": "success_required",
            },
        },
        headers=ORIGIN,
    )
    assert dependency_response.status_code == 200, dependency_response.text
    body = preview(client, scenario).json()
    assert confirm(client, scenario, body).status_code == 200
    with sessions() as db:
        successor = db.get(CampaignActivity, successor_id)
        assert successor is not None
        assert successor.scheduled_local_date == successor_time.date()
        assert successor.scheduled_local_time == successor_time.time()
    validated = client.post(f"/api/v1/campaigns/{scenario.campaign_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200, validated.text


def test_campaign_wait_projection_does_not_complete_on_reschedule(reschedule_harness) -> None:
    from vayujit_api.campaigns.workflow_service import (
        project_campaign_state,
        restore_campaign_waits,
    )

    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    assert confirm(client, scenario, body).status_code == 200
    with sessions() as db:
        campaign = db.get(Campaign, scenario.campaign_id)
        assert campaign is not None
        assert project_campaign_state(db, campaign) not in {"completed", "partially_completed"}
        assert restore_campaign_waits(db, owner_id=scenario.owner_id) == 0


def test_concurrent_confirmation_is_serialized_by_postgres_row_lock(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()

    def request(_: int):
        return confirm(client, scenario, body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(request, [1, 2]))
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]
    assert {response.json()["result"]["outcome"] for response in responses} == {
        "succeeded",
        "reused",
    }
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(CampaignActivityReschedule)) == 1
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 2
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 2


def test_dst_normal_gap_fold_and_invalid_timezone(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    normal = preview(
        client,
        scenario,
        proposed_local_datetime="2026-01-15T09:00:00",
        proposed_timezone="America/New_York",
    )
    assert normal.status_code == 200
    assert normal.json()["dst_classification"] == "normal"
    gap = preview(
        client,
        scenario,
        proposed_local_datetime="2026-03-08T02:30:00",
        proposed_timezone="America/New_York",
    )
    assert gap.status_code == 422
    fold = preview(
        client,
        scenario,
        proposed_local_datetime="2026-11-01T01:30:00",
        proposed_timezone="America/New_York",
    )
    assert fold.status_code == 200
    assert fold.json()["dst_classification"] == "ambiguous_local_time"
    assert fold.json()["confirmation_required"] is False
    fold_zero = preview(
        client,
        scenario,
        proposed_local_datetime="2026-11-01T01:30:00",
        proposed_timezone="America/New_York",
        fold=0,
    )
    fold_one = preview(
        client,
        scenario,
        proposed_local_datetime="2026-11-01T01:30:00",
        proposed_timezone="America/New_York",
        fold=1,
    )
    assert fold_zero.status_code == fold_one.status_code == 200
    assert (
        fold_zero.json()["proposed_scheduled_at_utc"]
        != fold_one.json()["proposed_scheduled_at_utc"]
    )
    assert fold_zero.json()["preview_fingerprint"] != fold_one.json()["preview_fingerprint"]
    invalid = preview(client, scenario, proposed_timezone="Not/A_Timezone")
    assert invalid.status_code == 422
    with sessions() as db:
        assert counts(db)[1:] == (0, 1, 1, 1, 0, 0, 0)


@pytest.mark.parametrize(
    "mutate",
    [
        "row_version",
        "status",
        "schedule",
        "job",
        "destination",
        "artifact",
        "campaign",
    ],
)
def test_stale_preview_matrix_has_no_mutation(reschedule_harness, mutate: str) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    with sessions() as db:
        activity = db.get(CampaignActivity, scenario.activity_id)
        assert activity is not None
        if mutate == "row_version":
            activity.row_version += 1
        elif mutate == "status":
            activity.status = "succeeded"
        elif mutate == "schedule":
            schedule = db.get(PublishingSchedule, scenario.original_schedule_id)
            assert schedule is not None
            schedule.archived = True
        elif mutate == "job":
            job = db.get(PublishingJob, scenario.original_job_id)
            assert job is not None
            job.state = "failed"
        elif mutate == "destination":
            destination = db.get(PublishingDestination, scenario.destination_id)
            assert destination is not None
            destination.status = "disabled"
        elif mutate == "artifact":
            artifact = db.get(GeneratedArtifact, scenario.artifact_id)
            assert artifact is not None
            artifact.status = "rejected"
        else:
            campaign = db.get(Campaign, scenario.campaign_id)
            assert campaign is not None
            campaign.status = "cancelled"
        db.commit()
        before = counts(db)
    response = confirm(client, scenario, body)
    assert response.status_code in {409, 422, 503}
    assert_safe_replacement_error(response)
    with sessions() as db:
        assert counts(db) == before
        assert db.scalar(select(func.count()).select_from(CampaignActivityReschedule)) == 0


def test_active_lease_blocks_rescheduling_and_expired_lease_recovers(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    with sessions() as db:
        job = db.get(PublishingJob, scenario.original_job_id)
        assert job is not None
        job.state = "claimed"
        job.lease_owner = "active-worker"
        job.lease_expires_at = now() + timedelta(minutes=5)
        db.commit()
    blocked = confirm(client, scenario, body)
    assert blocked.status_code == 409
    assert_safe_replacement_error(blocked)
    with sessions() as db:
        job = db.get(PublishingJob, scenario.original_job_id)
        assert job and job.lease_owner == "active-worker"
        job.lease_expires_at = now() - timedelta(minutes=1)
        db.commit()
        assert recover_expired_leases(db) >= 1


def test_confirmation_preserves_authentication_and_exact_origin(reschedule_harness) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    missing_origin = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "reschedule_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.activity_id),
            "expected_activity_row_version": scenario.expected_row_version,
            "proposed_local_datetime": body["proposed_local_datetime"],
            "proposed_timezone": body["timezone"],
            "preview_fingerprint": body["preview_fingerprint"],
            "confirm": True,
        },
    )
    assert missing_origin.status_code == 403
    invalid_origin = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "reschedule_activity",
            "campaign_id": str(scenario.campaign_id),
            "confirm": True,
        },
        headers={"Origin": "http://localhost:4200"},
    )
    assert invalid_origin.status_code == 403
    client.cookies.clear()
    unauthenticated = client.post(
        f"/api/v1/campaigns/{scenario.campaign_id}/recovery/reschedule-activity/preview",
        json={
            "activity_id": str(scenario.activity_id),
            "proposed_local_datetime": scenario.proposed_local_datetime.isoformat(),
            "proposed_timezone": "UTC",
            "expected_activity_row_version": scenario.expected_row_version,
        },
        headers=ORIGIN,
    )
    assert unauthenticated.status_code == 401


def test_maintenance_blocks_confirmation_but_not_preview(reschedule_harness, monkeypatch) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    monkeypatch.setattr("vayujit_api.campaigns.router.maintenance_enabled", lambda: True)
    read_only = preview(client, scenario)
    assert read_only.status_code == 200
    blocked = confirm(client, scenario, body)
    assert blocked.status_code == 503
    assert_safe_replacement_error(blocked)
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(CampaignActivityReschedule)) == 0


def test_replacement_job_is_claimable_once_and_recovery_does_not_revive_original(
    reschedule_harness,
) -> None:
    client, sessions = reschedule_harness
    scenario = create_reschedule_scenario(client, sessions)
    body = preview(client, scenario).json()
    assert confirm(client, scenario, body).status_code == 200
    with sessions() as db:
        assert claim_jobs(db, "reschedule-worker", 10, 60)
        assert claim_jobs(db, "reschedule-worker-2", 10, 60) == []
        old = db.get(PublishingJob, scenario.original_job_id)
        assert old and old.state == "cancelled"
        assert materialize_due_schedules(db) == 0


def test_registry_has_twenty_implemented_and_one_unsupported() -> None:
    unsupported = {
        key
        for key, spec in RECOVERY_ACTION_REGISTRY.items()
        if spec.implementation_status == "unsupported"
    }
    implemented = {
        key
        for key, spec in RECOVERY_ACTION_REGISTRY.items()
        if spec.implementation_status == "implemented"
    }
    assert len(implemented) == 20
    assert unsupported == {"create_one_catch_up"}
    spec = RECOVERY_ACTION_REGISTRY["reschedule_activity"]
    assert spec.classification == "mutating"
    assert callable(spec.executor)
    assert spec.confirmation_required
