# mypy: ignore-errors
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.autonomous_service import record_change
from vayujit_api.intelligence.external_intelligence import record_external_alert
from vayujit_api.intelligence.website_models import ManufacturerCandidate, WebsiteSourceProfile

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_production_change_alerts_retain_nine_row_lineage(client, db_session, owner) -> None:
    result = run_website_research(
        client,
        content="Company Name: Alert Lineage Fixture. Product: Tray. OEM. ISO certificate.",
        key="alert-lineage-final",
    )
    mission = db_session.get(AutonomousResearchMission, result["mission_id"])
    task = db_session.scalar(
        select(AutonomousResearchTask).where(AutonomousResearchTask.mission_id == mission.id)
    )
    profile = db_session.scalar(select(WebsiteSourceProfile))
    candidate = db_session.scalar(select(ManufacturerCandidate))
    assert (
        mission is not None and task is not None and profile is not None and candidate is not None
    )
    evidence = AutonomousResearchEvidence(
        owner_id=owner.id,
        mission_id=mission.id,
        task_id=task.id,
        source_class="WEBSITE",
        source_reference="https://example.org",
        retrieval_identity="alert-lineage-evidence",
        normalized_value={"candidate_id": str(candidate.id)},
        content_hash=str(uuid.uuid4()),
        verification_status="SUPPORTED",
        freshness_status="FRESH",
        evidence_class="GENERAL",
        lineage={"source_profile_id": str(profile.id), "candidate_id": str(candidate.id)},
    )
    db_session.add(evidence)
    db_session.flush()
    change_ids = []
    for index in range(9):
        row = record_change(
            db_session,
            owner,
            mission,
            change_type="supplier_verification",
            previous={"value": index},
            current={"value": index + 1},
            evidence_ids=[str(evidence.id)],
        )
        assert row is not None
        change_ids.append(str(row.id))
    db_session.expire_all()
    alerts = list(
        db_session.scalars(
            select(AutonomousResearchAlert).where(AutonomousResearchAlert.mission_id == mission.id)
        )
    )
    assert len(alerts) == 9
    assert {item.lineage.get("change_id") for item in alerts} == set(change_ids)
    assert all(item.owner_id == owner.id for item in alerts)
    assert all(item.lineage.get("correlation_id") == mission.correlation_id for item in alerts)
    assert all(item.lineage.get("evidence_ids") == [str(evidence.id)] for item in alerts)
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AutonomousResearchAlert)
            .where(
                AutonomousResearchAlert.mission_id == mission.id,
                AutonomousResearchAlert.lineage["source_profile_id"].as_string().is_not(None),
            )
        )
        == 9
    )


def test_nine_distinct_alert_types_replay_without_duplicates(client, db_session) -> None:
    result = run_website_research(
        client,
        content="Company Name: Alert Types Fixture. Product: Tray. OEM.",
        key="alert-types-final",
    )
    mission = db_session.get(AutonomousResearchMission, result["mission_id"])
    assert mission is not None
    event_types = [
        "MATERIAL_MOQ_INCREASE",
        "MATERIAL_LEAD_TIME_INCREASE",
        "CERTIFICATION_REMOVED",
        "CERTIFICATION_EXPIRED",
        "BUSINESS_IDENTITY_CHANGED",
        "CRITICAL_CAPABILITY_REMOVED",
        "MATERIAL_FACILITY_CHANGED",
        "CRITICAL_PRODUCT_UNAVAILABLE",
        "HIGH_RISK_CONTRADICTION",
    ]

    def emit(event_type: str, identity: str, detail: str) -> AutonomousResearchAlert:
        return record_external_alert(
            db_session,
            mission,
            alert_type=event_type,
            title=event_type,
            detail=detail,
            identity=identity,
            lineage={"correlation_id": mission.correlation_id},
        )

    created = [
        emit(event_type, event_type, "Deterministic website event.") for event_type in event_types
    ]
    db_session.commit()
    before = db_session.scalar(
        select(func.count())
        .select_from(AutonomousResearchAlert)
        .where(AutonomousResearchAlert.mission_id == mission.id)
    )
    replayed = [
        emit(event_type, event_type, "Deterministic website event.") for event_type in event_types
    ]
    later = emit(
        "MATERIAL_MOQ_INCREASE", "MATERIAL_MOQ_INCREASE-later", "Later deterministic website event."
    )
    db_session.commit()
    after = db_session.scalar(
        select(func.count())
        .select_from(AutonomousResearchAlert)
        .where(AutonomousResearchAlert.mission_id == mission.id)
    )
    assert len(created) == len(replayed) == 9
    assert all(first.id == second.id for first, second in zip(created, replayed, strict=True))
    assert after == before + 1
    assert later.alert_type == "MATERIAL_MOQ_INCREASE"
