import uuid

import pytest
from helpers.campaign_replacement_fixture import (
    assert_replacement_side_effects_unchanged,
    assert_safe_replacement_error,
    create_approved_artifact_for_other_product,
    create_campaign_replacement_scenario,
    invoke_successful_replacement,
    snapshot_replacement_side_effects,
)
from sqlalchemy import func, select
from test_scheduler_integration import ORIGIN

from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.publishing.models import PublishingExecution, PublishingJob, PublishingSchedule

pytestmark = pytest.mark.integration
pytest_plugins = ("test_scheduler_integration",)


def test_minimal_replacement_scenario_supports_real_recovery_api(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 0
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
        assert db.scalar(select(func.count()).select_from(PublishingExecution)) == 0
    response = invoke_successful_replacement(client=client, scenario=scenario)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    with sessions() as db:
        replacement = db.scalar(
            select(CampaignActivity).where(
                CampaignActivity.replaces_activity_id == scenario.original_activity_id
            )
        )
        assert replacement is not None
        assert replacement.artifact_id == scenario.replacement_artifact_id
        assert replacement.artifact_version == scenario.replacement_artifact_version
        assert replacement.schedule_id is None
        assert replacement.job_id is None
        assert replacement.publishing_execution_id is None
        assert str(replacement.id) == str(result["replacement_activity_id"])


def test_replacement_fixture_isolated_between_runs(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        assert scenario.campaign_id
        assert scenario.original_activity_id
        assert scenario.product_id
        assert db.scalar(select(func.count()).select_from(CampaignActivity)) == 1


def test_missing_replacement_artifact_has_no_side_effects(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        original = db.get(CampaignActivity, scenario.original_activity_id)
        assert original is not None
        original_snapshot = {
            field: getattr(original, field)
            for field in (
                "id",
                "campaign_id",
                "product_id",
                "artifact_id",
                "artifact_version",
                "destination_id",
                "status",
                "failure_code",
                "safe_failure_message",
                "schedule_id",
                "job_id",
                "publishing_execution_id",
                "completed_at",
            )
        }
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(uuid.uuid4()),
            "replacement_artifact_version": scenario.replacement_artifact_version,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Missing Artifact characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409}
    assert_safe_replacement_error(response)
    with sessions() as db:
        after = snapshot_replacement_side_effects(db)
        assert_replacement_side_effects_unchanged(before, after)
        current = db.get(CampaignActivity, scenario.original_activity_id)
        assert current is not None
        assert {field: getattr(current, field) for field in original_snapshot} == original_snapshot


def test_other_product_artifact_has_no_side_effects(harness):
    client, sessions = harness
    with sessions() as db:
        scenario = create_campaign_replacement_scenario(client=client, db_session=db)
        other_product_id, other_artifact_id, other_artifact_version = (
            create_approved_artifact_for_other_product(client=client, brand_id=scenario.brand_id)
        )
        original = db.get(CampaignActivity, scenario.original_activity_id)
        assert original is not None
        original_product_id = original.product_id
        original_artifact_id = original.artifact_id
        original_artifact_version = original.artifact_version
        original_row_version = original.row_version
        before = snapshot_replacement_side_effects(db)
    response = client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(other_artifact_id),
            "replacement_artifact_version": other_artifact_version,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Other Product characterization.",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code in {404, 409, 422}
    assert_safe_replacement_error(response)
    with sessions() as db:
        current = db.get(CampaignActivity, scenario.original_activity_id)
        assert current is not None
        assert current.product_id == original_product_id
        assert current.artifact_id == original_artifact_id
        assert current.artifact_version == original_artifact_version
        assert current.row_version == original_row_version
        assert other_product_id != scenario.product_id
        assert_replacement_side_effects_unchanged(before, snapshot_replacement_side_effects(db))
