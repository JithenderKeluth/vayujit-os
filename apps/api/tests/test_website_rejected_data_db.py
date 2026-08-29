# mypy: ignore-errors
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.autonomous_service import record_change

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_rejected_and_non_authoritative_evidence_cannot_create_changes(
    client, db_session, owner
) -> None:
    result = run_website_research(
        client, content="Company Name: Rejection Fixture. Product: Tray.", key="rejection-seed"
    )
    mission = db_session.get(AutonomousResearchMission, result["mission_id"])
    assert mission is not None
    task = db_session.scalar(
        select(AutonomousResearchTask).where(AutonomousResearchTask.mission_id == mission.id)
    )
    assert task is not None
    cases = [
        ("UNVERIFIED", "FRESH"),
        ("REJECTED", "FRESH"),
        ("SUPPORTED", "EXPIRED"),
        ("SUPPORTED", "STALE"),
    ]
    for index, (verification, freshness) in enumerate(cases):
        evidence = AutonomousResearchEvidence(
            owner_id=owner.id,
            mission_id=mission.id,
            task_id=task.id,
            source_class="WEBSITE",
            source_reference="https://example.org",
            retrieval_identity=f"rejection:{index}",
            normalized_value={"value": index},
            content_hash=str(uuid.uuid4()),
            verification_status=verification,
            freshness_status=freshness,
            evidence_class="GENERAL",
        )
        db_session.add(evidence)
        db_session.flush()
        assert (
            record_change(
                db_session,
                owner,
                mission,
                change_type=f"rejection_{index}",
                previous={"value": 1},
                current={"value": 2},
                evidence_ids=[str(evidence.id)],
            )
            is None
        )
    unknown_id = str(uuid.uuid4())
    assert (
        record_change(
            db_session,
            owner,
            mission,
            change_type="wrong_owner",
            previous={"value": 1},
            current={"value": 2},
            evidence_ids=[unknown_id],
        )
        is None
    )
    db_session.rollback()
