from __future__ import annotations

from datetime import UTC, datetime

import pytest
from website_postgres_fixture import ORIGIN

from vayujit_api.intelligence.website_models import WebsiteRefreshJob

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_refresh_recovery_catalog_and_idempotent_retry(client, db_session, owner):
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "recovery.example", "display_name": "Recovery", "enabled": True},
        headers=ORIGIN,
    ).json()
    job = WebsiteRefreshJob(
        owner_id=owner.id,
        source_profile_id=profile["id"],
        scheduled_for=datetime.now(UTC),
        idempotency_key="recovery-job-1",
        status="FAILED",
        failure_code="TIMEOUT",
        correlation_id="corr-recovery",
    )
    db_session.add(job)
    db_session.commit()
    catalog = client.get("/api/v1/intelligence/websites/refresh/recovery/catalog")
    assert catalog.status_code == 200
    assert "TIMEOUT" in catalog.json()["failure_codes"]
    payload = {"action": "retry", "failure_code": "TIMEOUT", "idempotency_key": "retry-1"}
    first = client.post(
        f"/api/v1/intelligence/websites/refresh/jobs/{job.id}/recover",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == 200, first.text
    assert first.json()["idempotent_reuse"] is False
    second = client.post(
        f"/api/v1/intelligence/websites/refresh/jobs/{job.id}/recover",
        json=payload,
        headers=ORIGIN,
    )
    assert second.status_code == 200, second.text
    assert second.json()["idempotent_reuse"] is True
