# mypy: ignore-errors
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchContradiction,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchTask,
)
from vayujit_api.intelligence.autonomous_service import record_change
from vayujit_api.intelligence.external_intelligence import record_external_contradiction
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteClaim,
    WebsiteObservation,
    WebsiteOffering,
    WebsiteSourceProfile,
)

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def _count(db, model, owner_id):
    return int(
        db.scalar(select(func.count()).select_from(model).where(model.owner_id == owner_id)) or 0
    )


def test_canonical_website_e2e_lineage_replay_and_duplicate_counters(
    client, db_session, owner
) -> None:
    first = run_website_research(
        client,
        content=(
            "Company Name: Canonical Supplier. Product: Tray. PRIVATE LABEL. "
            "Factory in Pune. ISO certificate."
        ),
        url="https://example.org",
        key="canonical-final-a",
    )
    second = run_website_research(
        client,
        content="Company Name: Canonical Supplier. Product: Tray. CUSTOM DESIGN. Factory in Pune.",
        url="https://example.org",
        key="canonical-final-b",
    )
    mission = db_session.get(AutonomousResearchMission, first["mission_id"])
    assert mission is not None and second["mission_id"]
    task = db_session.scalar(
        select(AutonomousResearchTask).where(AutonomousResearchTask.mission_id == mission.id)
    )
    profile = db_session.scalar(select(WebsiteSourceProfile))
    candidate = db_session.scalar(select(ManufacturerCandidate))
    supplier = db_session.scalar(select(SupplierWebsiteCandidate))
    assert (
        task is not None and profile is not None and candidate is not None and supplier is not None
    )

    observations = list(
        db_session.scalars(select(WebsiteObservation).order_by(WebsiteObservation.created_at))
    )
    capability = [row for row in observations if row.observation_type == "CAPABILITY"]
    history_response = client.get("/api/v1/intelligence/websites/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert {item["id"] for item in history} == {str(row.id) for row in observations}
    assert all(item["type"] for item in history)
    assert (
        client.get(f"/api/v1/intelligence/websites/history?candidate_id={uuid.uuid4()}").json()
        == []
    )
    assert len(capability) >= 2
    evidence_rows = []
    for index, observation in enumerate(capability[:2]):
        evidence = AutonomousResearchEvidence(
            owner_id=owner.id,
            mission_id=mission.id,
            task_id=task.id,
            source_class="WEBSITE_CAPABILITY",
            source_reference=observation.page_url,
            retrieval_identity=f"canonical-final-evidence-{index}",
            normalized_value={
                "capability": "PRIVATE_LABEL",
                "value": "SUPPORTED" if index == 0 else "NOT_SUPPORTED",
                "observation_id": str(observation.id),
            },
            content_hash=str(uuid.uuid4()),
            verification_status="SUPPORTED",
            freshness_status="FRESH",
            evidence_class="CAPABILITY",
            lineage={
                "source_profile_id": str(profile.id),
                "candidate_id": str(candidate.id),
                "correlation_id": mission.correlation_id,
            },
        )
        db_session.add(evidence)
        db_session.flush()
        evidence_rows.append(evidence)
    contradiction = record_external_contradiction(
        db_session, mission, evidence_rows[0], evidence_rows[1], claim_key="PRIVATE_LABEL"
    )
    change = record_change(
        db_session,
        owner,
        mission,
        change_type="supplier_verification",
        previous={"value": "SUPPORTED"},
        current={"value": "NOT_SUPPORTED"},
        evidence_ids=[str(evidence_rows[0].id)],
    )
    assert contradiction.owner_id == owner.id and change is not None
    db_session.commit()

    models = [
        WebsiteSourceProfile,
        ManufacturerCandidate,
        SupplierWebsiteCandidate,
        WebsiteObservation,
        WebsiteOffering,
        WebsiteClaim,
        AutonomousResearchContradiction,
        AutonomousResearchChange,
        AutonomousResearchAlert,
    ]
    before = {model.__tablename__: _count(db_session, model, owner.id) for model in models}
    replay = record_change(
        db_session,
        owner,
        mission,
        change_type="supplier_verification",
        previous={"value": "SUPPORTED"},
        current={"value": "NOT_SUPPORTED"},
        evidence_ids=[str(evidence_rows[0].id)],
    )
    assert replay is not None and replay.id == change.id
    db_session.expire_all()
    after = {model.__tablename__: _count(db_session, model, owner.id) for model in models}
    assert before == after

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AutonomousResearchContradiction)
            .where(AutonomousResearchContradiction.id == contradiction.id)
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(AutonomousResearchAlert)
            .where(AutonomousResearchAlert.lineage["change_id"].as_string() == str(change.id))
        )
        == 1
    )
    assert all(
        row.owner_id == owner.id for model in models for row in db_session.scalars(select(model))
    )
    assert all(
        row.owner_id == owner.id for row in db_session.scalars(select(AutonomousResearchEvidence))
    )
    assert all(
        row.owner_id == owner.id for row in db_session.scalars(select(AutonomousResearchMission))
    )

    for model in models:
        identity = getattr(model, "logical_identity", None) or getattr(model, "identity_key", None)
        if identity is None:
            continue
        duplicate_groups = db_session.execute(
            select(identity, func.count())
            .where(model.owner_id == owner.id)
            .group_by(identity)
            .having(func.count() > 1)
        ).all()
        assert duplicate_groups == []

    orphan_counters = {
        "orphan_observations": sum(
            row.candidate_id is None or row.source_profile_id is None
            for row in db_session.scalars(select(WebsiteObservation))
        ),
        "orphan_offerings": sum(
            row.candidate_id is None or row.source_profile_id is None
            for row in db_session.scalars(select(WebsiteOffering))
        ),
        "orphan_capabilities": sum(
            row.candidate_id is None
            for row in db_session.scalars(
                select(WebsiteClaim).where(WebsiteClaim.claim_type == "CAPABILITY")
            )
        ),
        "orphan_facilities": sum(
            row.candidate_id is None
            for row in db_session.scalars(
                select(WebsiteClaim).where(WebsiteClaim.claim_type == "FACILITY")
            )
        ),
        "orphan_certifications": sum(
            row.candidate_id is None
            for row in db_session.scalars(
                select(WebsiteClaim).where(WebsiteClaim.claim_type == "CERTIFICATION")
            )
        ),
        "orphan_risks": 0,
        "orphan_contradictions": sum(
            row.evidence_a_id is None or row.evidence_b_id is None
            for row in db_session.scalars(select(AutonomousResearchContradiction))
        ),
        "orphan_changes": sum(
            row.mission_id is None for row in db_session.scalars(select(AutonomousResearchChange))
        ),
        "orphan_alerts": sum(
            row.mission_id is None for row in db_session.scalars(select(AutonomousResearchAlert))
        ),
    }
    assert orphan_counters == {key: 0 for key in orphan_counters}
    assert all(
        row.owner_id == owner.id for model in models for row in db_session.scalars(select(model))
    )
