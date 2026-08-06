from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_scheduler_integration import ORIGIN, business

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.models import AuditEvent
from vayujit_api.campaigns.models import CampaignActivity
from vayujit_api.publishing.models import (
    PublishingDestination,
    PublishingExecution,
    PublishingJob,
    PublishingJobAttempt,
    PublishingSchedule,
)


@dataclass(frozen=True)
class CampaignReplacementScenario:
    owner_id: UUID
    brand_id: UUID
    product_id: UUID
    campaign_id: UUID
    original_activity_id: UUID
    original_artifact_id: UUID
    original_artifact_version: int
    replacement_artifact_id: UUID
    replacement_artifact_version: int
    destination_id: UUID
    expected_activity_row_version: int


@dataclass(frozen=True)
class ReplacementSideEffectSnapshot:
    activities: int
    replacement_links: int
    schedules: int
    jobs: int
    attempts: int
    executions: int
    replacement_audits: int


def snapshot_replacement_side_effects(db_session: Session) -> ReplacementSideEffectSnapshot:
    return ReplacementSideEffectSnapshot(
        activities=db_session.query(CampaignActivity).count(),
        replacement_links=db_session.query(CampaignActivity)
        .filter(CampaignActivity.replaces_activity_id.is_not(None))
        .count(),
        schedules=db_session.query(PublishingSchedule).count(),
        jobs=db_session.query(PublishingJob).count(),
        attempts=db_session.query(PublishingJobAttempt).count(),
        executions=db_session.query(PublishingExecution).count(),
        replacement_audits=db_session.query(AuditEvent)
        .filter(AuditEvent.action == "campaign.artifact_version_replaced")
        .count(),
    )


def assert_replacement_side_effects_unchanged(
    before: ReplacementSideEffectSnapshot,
    after: ReplacementSideEffectSnapshot,
) -> None:
    assert after == before


def assert_safe_replacement_error(response) -> None:
    body = response.text.lower()
    for forbidden in (
        "artifact content",
        "prompt",
        "provider",
        "credential",
        "token",
        "cookie",
        "database_url",
        "traceback",
        "select ",
        "c:\\users",
    ):
        assert forbidden not in body


def _action(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/api/v1/campaigns/workflow-actions",
        json=payload,
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_approved_artifact_for_other_product(
    *, client: TestClient, brand_id: UUID, origin: str = ORIGIN["Origin"]
) -> tuple[UUID, UUID, int]:
    product_response = client.post(
        "/api/v1/products",
        json={
            "brand_id": str(brand_id),
            "name": "Replacement fixture other product",
            "sku": "replacement-fixture-other",
            "product_type": "physical",
            "description": "Other product fixture.",
            "short_description": "Other product fixture.",
            "price_amount": "21.00",
            "price_currency": "USD",
        },
        headers={"Origin": origin},
    )
    assert product_response.status_code == 201, product_response.text
    product = product_response.json()
    activated = client.post(
        f"/api/v1/products/{product['id']}/activate", headers={"Origin": origin}
    )
    assert activated.status_code == 200, activated.text
    generation = client.post(
        "/api/v1/ai/generations", json={"product_id": product["id"]}, headers={"Origin": origin}
    )
    assert generation.status_code == 200, generation.text
    artifact_id = generation.json()["artifact_id"]
    approval = client.post(
        f"/api/v1/ai/artifacts/{artifact_id}/approve", headers={"Origin": origin}
    )
    assert approval.status_code == 200, approval.text
    artifact = approval.json()
    return UUID(str(product["id"])), UUID(str(artifact["id"])), int(artifact["version_number"])


def create_pending_artifact(
    *, client: TestClient, db_session: Session, scenario: CampaignReplacementScenario
) -> GeneratedArtifact:
    response = client.post(
        "/api/v1/ai/generations",
        json={"product_id": str(scenario.product_id)},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    artifact_id = UUID(str(response.json()["artifact_id"]))
    artifact = db_session.get(GeneratedArtifact, artifact_id)
    assert artifact is not None
    assert artifact.status == "pending_review"
    assert artifact.product_id == scenario.product_id
    return artifact


def create_rejected_artifact(
    *, client: TestClient, db_session: Session, scenario: CampaignReplacementScenario
) -> GeneratedArtifact:
    artifact = create_pending_artifact(client=client, db_session=db_session, scenario=scenario)
    response = client.post(
        f"/api/v1/ai/artifacts/{artifact.id}/reject",
        json={"reason": "Fixture rejection."},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    db_session.expire(artifact)
    db_session.refresh(artifact)
    assert artifact.status == "rejected"
    return artifact


def create_superseded_artifact(
    *, client: TestClient, db_session: Session, scenario: CampaignReplacementScenario
) -> GeneratedArtifact:
    first = create_pending_artifact(client=client, db_session=db_session, scenario=scenario)
    approved = client.post(f"/api/v1/ai/artifacts/{first.id}/approve", headers=ORIGIN)
    assert approved.status_code == 200, approved.text
    newer = client.post(
        "/api/v1/ai/generations", json={"product_id": str(scenario.product_id)}, headers=ORIGIN
    )
    assert newer.status_code == 200, newer.text
    newer_approved = client.post(
        f"/api/v1/ai/artifacts/{newer.json()['artifact_id']}/approve", headers=ORIGIN
    )
    assert newer_approved.status_code == 200, newer_approved.text
    db_session.expire(first)
    db_session.refresh(first)
    assert first.status == "superseded"
    return first


def create_campaign_replacement_scenario(
    *, client: TestClient, db_session: Session, origin: str = ORIGIN["Origin"]
) -> CampaignReplacementScenario:
    product, original_artifact, destination = business(client)
    destination_row = db_session.get(PublishingDestination, UUID(str(destination["id"])))
    assert destination_row is not None
    destination_row.connector_key = "wordpress"
    db_session.commit()
    replacement_generation = client.post(
        "/api/v1/ai/generations", json={"product_id": product["id"]}, headers={"Origin": origin}
    )
    replacement = client.post(
        f"/api/v1/ai/artifacts/{replacement_generation.json()['artifact_id']}/approve",
        headers={"Origin": origin},
    ).json()
    due = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)
    campaign = _action(
        client,
        {
            "action": "create_campaign",
            "campaign": {
                "brand_id": destination["brand_id"],
                "name": "Replacement fixture",
                "timezone_name": "UTC",
                "local_start_at": (due - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
                "local_end_at": (due + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            },
        },
    )
    activity = _action(
        client,
        {
            "action": "add_campaign_activity",
            "campaign_id": campaign["campaign_id"],
            "activity": {
                "product_id": product["id"],
                "artifact_id": original_artifact["id"],
                "destination_id": destination["id"],
                "activity_type": "wordpress_create_draft",
                "name": "Replacement fixture activity",
                "sequence": 1,
                "scheduled_local_date": due.date().isoformat(),
                "scheduled_local_time": due.time().isoformat(),
                "timezone_name": "UTC",
                "required": True,
            },
        },
    )
    value = db_session.get(CampaignActivity, UUID(str(activity["activity_id"])))
    assert value is not None
    value.status = "failed"
    value.failure_code = "fixture_failure"
    value.safe_failure_message = "Fixture failure."
    db_session.commit()
    return CampaignReplacementScenario(
        owner_id=value.owner_id,
        brand_id=UUID(str(destination["brand_id"])),
        product_id=UUID(str(product["id"])),
        campaign_id=UUID(str(campaign["campaign_id"])),
        original_activity_id=value.id,
        original_artifact_id=UUID(str(original_artifact["id"])),
        original_artifact_version=int(original_artifact["version_number"]),
        replacement_artifact_id=UUID(str(replacement["id"])),
        replacement_artifact_version=int(replacement["version_number"]),
        destination_id=UUID(str(destination["id"])),
        expected_activity_row_version=value.row_version,
    )


def invoke_successful_replacement(
    *, client: TestClient, scenario: CampaignReplacementScenario, origin: str = ORIGIN["Origin"]
):
    return client.post(
        "/api/v1/campaigns/recovery/actions",
        json={
            "action": "replace_with_new_approved_activity",
            "campaign_id": str(scenario.campaign_id),
            "activity_id": str(scenario.original_activity_id),
            "replacement_artifact_id": str(scenario.replacement_artifact_id),
            "replacement_artifact_version": scenario.replacement_artifact_version,
            "expected_activity_row_version": scenario.expected_activity_row_version,
            "reason": "Fixture replacement.",
            "confirm": True,
        },
        headers={"Origin": origin},
    )
