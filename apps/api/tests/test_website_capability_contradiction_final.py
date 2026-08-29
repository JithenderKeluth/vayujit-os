# mypy: ignore-errors
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.external_intelligence import record_external_contradiction
from vayujit_api.intelligence.website_models import WebsiteObservation

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_website_capability_contradiction_reverse_pair_is_idempotent(
    client, db_session, owner
) -> None:
    first = run_website_research(
        client,
        content="Company Name: Contradiction Fixture. Product: Tray. PRIVATE LABEL.",
        key="capability-source-a",
    )
    run_website_research(
        client,
        content="Company Name: Contradiction Fixture. Product: Tray. CUSTOM DESIGN.",
        key="capability-source-b",
    )
    mission = db_session.get(AutonomousResearchMission, first["mission_id"])
    assert mission is not None
    task = db_session.scalar(
        select(AutonomousResearchTask).where(AutonomousResearchTask.mission_id == mission.id)
    )
    assert task is not None
    observations = list(
        db_session.scalars(
            select(WebsiteObservation)
            .where(WebsiteObservation.observation_type == "CAPABILITY")
            .order_by(WebsiteObservation.created_at)
        )
    )
    assert len(observations) >= 2
    evidence = []
    for index, (observation, value) in enumerate(
        zip(observations[:2], ["SUPPORTED", "NOT_SUPPORTED"], strict=True)
    ):
        row = AutonomousResearchEvidence(
            owner_id=owner.id,
            mission_id=mission.id,
            task_id=task.id,
            source_class="WEBSITE_CAPABILITY",
            source_reference=str(observation.page_url),
            retrieval_identity=f"capability-contradiction:{index}",
            normalized_value={
                "capability": "PRIVATE_LABEL",
                "value": value,
                "observation_id": str(observation.id),
            },
            content_hash=str(uuid.uuid4()),
            verification_status="SUPPORTED",
            freshness_status="FRESH",
            evidence_class="CAPABILITY",
        )
        db_session.add(row)
        db_session.flush()
        evidence.append(row)
    contradiction = record_external_contradiction(
        db_session, mission, evidence[0], evidence[1], claim_key="PRIVATE_LABEL"
    )
    reverse = record_external_contradiction(
        db_session, mission, evidence[1], evidence[0], claim_key="PRIVATE_LABEL"
    )
    assert contradiction.id == reverse.id
    assert contradiction.status == "UNRESOLVED"
    assert contradiction.resolution_strategy == "REQUIRES_HUMAN_REVIEW"
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AutonomousResearchContradiction)
            .where(AutonomousResearchContradiction.mission_id == mission.id)
        )
        == 1
    )
