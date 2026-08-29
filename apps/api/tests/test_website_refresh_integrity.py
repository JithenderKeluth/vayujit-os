from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from website_postgres_fixture import ORIGIN

from vayujit_api.intelligence.external_projection import integrity_projection
from vayujit_api.intelligence.website_models import WebsiteRefreshJob, WebsiteRefreshRecovery

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_refresh_integrity_and_recovery_storage_are_owner_scoped(client, db_session, owner):
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "integrity.example", "display_name": "Integrity"},
        headers=ORIGIN,
    ).json()
    job = WebsiteRefreshJob(
        owner_id=owner.id,
        source_profile_id=UUID(profile["id"]),
        scheduled_for=datetime.now(UTC),
        idempotency_key="integrity-job",
        status="FAILED",
        failure_code="TIMEOUT",
        correlation_id="integrity-correlation",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        WebsiteRefreshRecovery(
            owner_id=owner.id,
            job_id=job.id,
            action="retry",
            failure_code="TIMEOUT",
            status="COMPLETED",
            safe_reason_code="WEBSITE_REFRESH_TIMEOUT",
            correlation_id="integrity-correlation",
            idempotency_key="integrity-recovery",
        )
    )
    db_session.commit()
    value = integrity_projection(db_session, owner)
    refresh = value["refresh"]
    assert refresh["duplicate_refresh_recovery"] == 0
    assert refresh["orphan_refresh_recovery"] == 0
    storage = value["storage"]
    assert storage["intelligence_website_refresh_jobs"] == 1
    assert storage["intelligence_website_refresh_recovery"] == 1
