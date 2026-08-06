"""Focused successful Artifact replacement characterization."""

import pytest
from helpers.campaign_replacement_fixture import (
    assert_replacement_side_effects_unchanged,
    assert_safe_replacement_error,
    create_campaign_replacement_scenario,
    create_pending_artifact,
    create_rejected_artifact,
    create_superseded_artifact,
    invoke_successful_replacement,
    snapshot_replacement_side_effects,
)
from test_scheduler_integration import ORIGIN

from vayujit_api.campaigns.models import CampaignActivity

pytest_plugins = ("test_scheduler_integration",)


@pytest.mark.parametrize("version", ["one", 0, -1, 1.5, None, 10**30])
def test_malformed_artifact_version_has_no_side_effects(harness, version):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        before = snapshot_replacement_side_effects(db)
    payload = {
        "action": "replace_with_new_approved_activity",
        "campaign_id": str(scenario.campaign_id),
        "activity_id": str(scenario.original_activity_id),
        "replacement_artifact_id": str(scenario.replacement_artifact_id),
        "replacement_artifact_version": version,
        "expected_activity_row_version": scenario.expected_activity_row_version,
        "reason": "Malformed version characterization.",
        "confirm": True,
    }
    response = client.post("/api/v1/campaigns/recovery/actions", json=payload, headers=ORIGIN)
    assert response.status_code in {400, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


def test_artifact_replacement_characterization(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client, db)
    response = invoke_successful_replacement(client, scenario)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["status"] == "succeeded"
    assert result["replacement_activity_id"]


def test_pending_artifact_replacement_is_rejected_without_side_effects(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        pending = create_pending_artifact(client=client, db_session=db, scenario=scenario)
        original = db.get(CampaignActivity, scenario.original_activity_id)
        assert original is not None
        original_state = (
            original.product_id,
            original.artifact_id,
            original.artifact_version,
            original.row_version,
        )
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(pending.id),
            "replacement_artifact_version": pending.version_number,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Pending Artifact characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        current = db.get(CampaignActivity, scenario.original_activity_id)
        assert current is not None
        assert (
            current.product_id,
            current.artifact_id,
            current.artifact_version,
            current.row_version,
        ) == original_state
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


def test_superseded_artifact_replacement_is_rejected_without_side_effects(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        artifact = create_superseded_artifact(client=client, db_session=db, scenario=scenario)
        original = db.get(CampaignActivity, scenario.original_activity_id)
        assert original is not None
        state = (
            original.product_id,
            original.artifact_id,
            original.artifact_version,
            original.row_version,
        )
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(artifact.id),
            "replacement_artifact_version": artifact.version_number,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Superseded characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        current = db.get(CampaignActivity, scenario.original_activity_id)
        assert current is not None
        assert (
            current.product_id,
            current.artifact_id,
            current.artifact_version,
            current.row_version,
        ) == state
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


def test_artifact_version_mismatch_is_rejected_without_side_effects(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(scenario.replacement_artifact_id),
            "replacement_artifact_version": scenario.replacement_artifact_version + 99,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Version mismatch characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


@pytest.mark.parametrize("status", ["succeeded", "running", "cancelled"])
def test_replacement_characterizes_activity_lifecycle_status(harness, status):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        activity = db.get(CampaignActivity, scenario.original_activity_id)
        assert activity is not None
        activity.status = status
        db.commit()
        before = snapshot_replacement_side_effects(db)
    response = invoke_successful_replacement(client=client, scenario=scenario)
    assert response.status_code in {200, 404, 409, 422}
    if response.status_code != 200:
        assert_safe_replacement_error(response)
    with sessions() as db:
        current = db.get(CampaignActivity, scenario.original_activity_id)
        assert current is not None
        assert current.status == status
        if response.status_code != 200:
            assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


def test_replacement_rejects_activity_from_different_campaign(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        response = client.post(
            "/api/v1/campaigns/workflow-actions",
            json={
                "action": "create_campaign",
                "campaign": {
                    "brand_id": str(scenario.brand_id),
                    "name": "Wrong campaign",
                    "timezone_name": "UTC",
                    "local_start_at": "2025-01-01T00:00:00",
                    "local_end_at": "2025-01-02T00:00:00",
                },
            },
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
        wrong_campaign_id = response.json()["campaign_id"]
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": wrong_campaign_id,
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(scenario.replacement_artifact_id),
            "replacement_artifact_version": scenario.replacement_artifact_version,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Wrong campaign characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


def test_replacement_rejects_stale_activity_row_version(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        activity = db.get(CampaignActivity, scenario.original_activity_id)
        assert activity is not None
        activity.failure_code = "advanced_fixture_state"
        activity.row_version += 1
        db.commit()
        before = snapshot_replacement_side_effects(db)
    response = invoke_successful_replacement(client=client, scenario=scenario)
    assert response.status_code in {409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))


def test_rejected_artifact_replacement_is_rejected_without_side_effects(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        rejected = create_rejected_artifact(client=client, db_session=db, scenario=scenario)
        original = db.get(CampaignActivity, scenario.original_activity_id)
        assert original is not None
        original_state = (
            original.product_id,
            original.artifact_id,
            original.artifact_version,
            original.status,
            original.row_version,
        )
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(rejected.id),
            "replacement_artifact_version": rejected.version_number,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Rejected Artifact characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        current = db.get(CampaignActivity, scenario.original_activity_id)
        assert current is not None
        assert (
            current.product_id,
            current.artifact_id,
            current.artifact_version,
            current.status,
            current.row_version,
        ) == original_state
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))
