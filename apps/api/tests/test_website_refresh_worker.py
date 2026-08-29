from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from website_postgres_fixture import ORIGIN

from vayujit_api.intelligence.website_models import WebsiteRefreshJob, WebsiteSourceProfile
from vayujit_api.intelligence.website_refresh import (
    claim_refresh_jobs,
    recover_expired_refresh_leases,
)

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_refresh_worker_claim_is_single_and_stale_leases_recover(client, db_session, owner):
    profile_payload = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "worker.example", "display_name": "Worker", "enabled": True},
        headers=ORIGIN,
    )
    assert profile_payload.status_code == 201, profile_payload.text
    profile = db_session.scalar(
        select(WebsiteSourceProfile).where(WebsiteSourceProfile.id == profile_payload.json()["id"])
    )
    assert profile is not None
    job = WebsiteRefreshJob(
        owner_id=owner.id,
        source_profile_id=profile.id,
        scheduled_for=datetime.now(UTC),
        idempotency_key="worker-claim-1",
        status="QUEUED",
    )
    db_session.add(job)
    db_session.commit()
    assert len(claim_refresh_jobs(db_session, "worker-a", limit=1, lease_seconds=60)) == 1
    assert claim_refresh_jobs(db_session, "worker-b", limit=1, lease_seconds=60) == []
    job = db_session.get(WebsiteRefreshJob, job.id)
    assert job is not None
    job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert recover_expired_refresh_leases(db_session) == 1
    db_session.refresh(job)
    assert job.status == "QUEUED"
    assert job.lease_owner is None
