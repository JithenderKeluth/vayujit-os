from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import website_postgres_fixture as fixture
from sqlalchemy import func, select

from vayujit_api.audit.models import AuditEvent
from vayujit_api.intelligence.autonomous_models import (
    AutonomousResearchAlert,
    AutonomousResearchChange,
    AutonomousResearchEvidence,
    AutonomousResearchMission,
    AutonomousResearchReport,
)
from vayujit_api.intelligence.external_projection import (
    website_storage_counts,
    website_table_inventory,
)
from vayujit_api.intelligence.website_models import (
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteClaim,
    WebsiteObservation,
    WebsiteOffering,
    WebsiteRefreshJob,
    WebsiteRefreshRecovery,
    WebsiteSourceProfile,
    WebsiteSourceProfileVersion,
)
from vayujit_api.intelligence.website_refresh import (
    claim_refresh_jobs,
    recover_expired_refresh_leases,
    run_refresh_jobs_once,
)

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


WEBSITE_MODELS = (
    WebsiteSourceProfile,
    WebsiteSourceProfileVersion,
    ManufacturerCandidate,
    SupplierWebsiteCandidate,
    WebsiteObservation,
    WebsiteOffering,
    WebsiteClaim,
    WebsiteRefreshJob,
    WebsiteRefreshRecovery,
    AutonomousResearchMission,
    AutonomousResearchEvidence,
    AutonomousResearchChange,
    AutonomousResearchAlert,
    AutonomousResearchReport,
)


def _count(db: Any, model: Any, owner_id: Any) -> int:
    column = getattr(model, "owner_id", getattr(model, "actor_id", None))
    return int(db.scalar(select(func.count()).select_from(model).where(column == owner_id)) or 0)


def _create_refresh_job(client: Any, db: Any, owner: Any, domain: str) -> WebsiteRefreshJob:
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": domain, "display_name": domain, "enabled": True},
        headers=fixture.ORIGIN,
    )
    assert profile.status_code == 201, profile.text
    row = db.scalar(
        select(WebsiteSourceProfile).where(WebsiteSourceProfile.id == profile.json()["id"])
    )
    assert row is not None
    job = WebsiteRefreshJob(
        owner_id=owner.id,
        source_profile_id=row.id,
        scheduled_for=datetime.now(UTC),
        target_type="WEBSITE_SOURCE",
        timezone="UTC",
        policy_version=row.version,
        correlation_id="final-crash-correlation",
        idempotency_key="final-crash-refresh",
        status="QUEUED",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_crash_before_fetch_recovers_one_terminal_website_execution(client, db_session, owner):
    job = _create_refresh_job(client, db_session, owner, "example.org")
    assert claim_refresh_jobs(db_session, "crash-worker", limit=1) == [job.id]
    claimed = db_session.get(WebsiteRefreshJob, job.id)
    assert claimed is not None
    claimed.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert recover_expired_refresh_leases(db_session) == 1
    assert run_refresh_jobs_once(db_session, "recovery-worker") == 1
    db_session.expire_all()
    terminal = db_session.get(WebsiteRefreshJob, job.id)
    assert terminal is not None and terminal.status == "SUCCEEDED"
    assert _count(db_session, AutonomousResearchMission, owner.id) == 1
    assert _count(db_session, WebsiteSourceProfile, owner.id) == 1
    assert _count(db_session, ManufacturerCandidate, owner.id) == 1
    assert _count(db_session, WebsiteObservation, owner.id) > 0


def test_crash_after_fetch_replay_does_not_duplicate_website_ledger(client, db_session, owner):
    content = "Company Name: Replay Supplier. Product: Tray. Factory in Pune. ISO certificate."
    first = fixture.run_website_research(client, content=content, key="final-replay-key")
    before = website_storage_counts(db_session, owner)
    replay = fixture.run_website_research(client, content=content, key="final-replay-key")
    after = website_storage_counts(db_session, owner)
    assert replay["mission_id"] == first["mission_id"]
    assert after == before
    assert _count(db_session, WebsiteObservation, owner.id) > 0


def test_crash_checkpoint_replay_has_one_evidence_set(client, db_session, owner):
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_WEBSITE_RESEARCH",
            "goal": "Bounded crash checkpoint certification",
            "scope": {"url": "https://example.org", "single_page": True},
            "idempotency_key": "final-checkpoint-mission",
        },
        headers=fixture.ORIGIN,
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    first = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
        json={"crash_stage": "after_evidence"},
        headers=fixture.ORIGIN,
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
        json={},
        headers=fixture.ORIGIN,
    )
    assert second.status_code == 200, second.text
    mission = db_session.get(AutonomousResearchMission, mission_id)
    assert mission is not None and mission.status in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}
    evidences = list(
        db_session.scalars(
            select(AutonomousResearchEvidence).where(
                AutonomousResearchEvidence.owner_id == owner.id,
                AutonomousResearchEvidence.mission_id == mission.id,
            )
        )
    )
    assert evidences
    assert len({row.retrieval_identity for row in evidences}) == len(evidences)


def test_true_postgres_concurrency_reuses_one_website_identity(client, owner):
    del client
    assert fixture.factory is not None
    session_factory = fixture.factory

    def invoke(_: int) -> dict[str, object]:
        with session_factory() as db:
            current_owner = db.scalar(select(type(owner)).where(type(owner).id == owner.id))
            assert current_owner is not None
            from vayujit_api.intelligence.website_service import run_website_mission

            return run_website_mission(
                db,
                current_owner,
                url="https://example.org",
                content="Company Name: Concurrent Supplier. Product: Tray. Factory in Pune.",
                source_type="SUPPLIER_WEBSITE",
                idempotency_key="concurrent-final-key",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, range(2)))
    assert len({result["mission_id"] for result in results}) == 1
    with session_factory() as db:
        current_owner = db.scalar(select(type(owner)).where(type(owner).id == owner.id))
        assert current_owner is not None
        assert _count(db, AutonomousResearchMission, current_owner.id) == 1
        assert _count(db, WebsiteSourceProfile, current_owner.id) == 1
        assert _count(db, ManufacturerCandidate, current_owner.id) == 1
        assert _count(db, SupplierWebsiteCandidate, current_owner.id) == 1


def test_complete_website_integrity_projection_and_inventory(client, db_session, owner):
    fixture.run_website_research(
        client,
        content=(
            "Company Name: Integrity Supplier. Product: Tray. Factory in Pune. ISO certificate."
        ),
        key="final-integrity-key",
    )
    response = client.get("/api/v1/intelligence/websites/integrity", headers=fixture.ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    required = {
        "duplicate_source_profiles",
        "duplicate_manufacturer_candidates",
        "duplicate_supplier_website_candidates",
        "duplicate_offerings",
        "duplicate_observations",
        "duplicate_capabilities",
        "duplicate_facilities",
        "duplicate_certifications",
        "duplicate_risks",
        "duplicate_contradictions",
        "duplicate_changes",
        "duplicate_alerts",
        "duplicate_refresh_jobs",
        "duplicate_recovery",
        "duplicate_reports",
    }
    assert required <= body["duplicates"].keys()
    assert all(value == 0 for value in body["duplicates"].values())
    assert all(value == 0 for value in body["orphans"].values())
    assert all(value == 0 for value in body["broken_lineage"].values())
    assert body["cross_owner_leakage"] == 0
    assert body["filesystem"]["artifacts"] == "N/A"
    assert body["classification"] == "PASS"
    tables = client.get("/api/v1/intelligence/websites/tables", headers=fixture.ORIGIN)
    assert tables.status_code == 200, tables.text
    assert len(tables.json()) == len(website_table_inventory())
    assert all(
        {"identity", "unique_constraints", "foreign_keys", "semantics"} <= row.keys()
        for row in tables.json()
    )


def test_website_performance_projection_is_bounded_and_private(client, db_session, owner):
    del db_session
    del owner
    started = time.perf_counter()
    response = client.get("/api/v1/intelligence/external/performance", headers=fixture.ORIGIN)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classification"] == "PASS"
    assert all(row["samples"] == 10 for row in body["measurements"])
    assert elapsed_ms < 30000
    assert not any(
        marker in response.text.lower()
        for marker in (
            "password",
            "authorization",
            "cookie",
            "postgresql://",
            "traceback",
            "c:\\\\users",
        )
    )


def test_website_projection_privacy_and_report_xss_boundaries(client, db_session, owner):
    result = fixture.run_website_research(
        client,
        content="Company Name: <script>alert(1)</script>. Product: Tray.",
        key="final-privacy-key",
    )
    report = client.get(
        f"/api/v1/intelligence/websites/reports/mission/{result['mission_id']}?format=html",
        headers=fixture.ORIGIN,
    )
    assert report.status_code == 200, report.text
    payload = report.text.lower()
    assert "<script>" not in payload
    assert all(
        marker not in payload
        for marker in ("postgresql://", "authorization", "cookie", "password", "traceback")
    )
    integrity = client.get("/api/v1/operations/intelligence/projection", headers=fixture.ORIGIN)
    assert integrity.status_code == 200, integrity.text
    assert all(
        marker not in integrity.text.lower() for marker in ("postgresql://", "password", "cookie")
    )
    assert _count(db_session, AuditEvent, owner.id) > 0


@pytest.mark.parametrize(
    "stage",
    ["before_source", "after_evidence"],
)
def test_checkpoint_failure_stages_are_recoverable_without_duplicate_reports(client, stage):
    mission = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_WEBSITE_RESEARCH",
            "goal": f"Checkpoint stage {stage}",
            "scope": {"url": "https://example.org"},
            "idempotency_key": f"final-stage-{stage}",
        },
        headers=fixture.ORIGIN,
    )
    assert mission.status_code == 201, mission.text
    mission_id = mission.json()["id"]
    crashed = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
        json={"crash_stage": stage},
        headers=fixture.ORIGIN,
    )
    assert crashed.status_code == 200, crashed.text
    recovered = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
        json={},
        headers=fixture.ORIGIN,
    )
    assert recovered.status_code == 200, recovered.text
    reports = client.get("/api/v1/intelligence/websites/reports", headers=fixture.ORIGIN)
    assert reports.status_code == 200
    assert len({row["id"] for row in reports.json()}) == len(reports.json())
