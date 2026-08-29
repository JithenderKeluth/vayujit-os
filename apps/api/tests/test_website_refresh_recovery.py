from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from website_postgres_fixture import ORIGIN

from vayujit_api.intelligence.website_models import WebsiteRefreshJob, WebsiteSourceProfile

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_disabled_source_is_skipped_without_mission(client, db_session, owner):
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "disabled.example", "display_name": "Disabled", "enabled": False},
        headers=ORIGIN,
    ).json()
    row = db_session.scalar(
        select(WebsiteSourceProfile).where(WebsiteSourceProfile.id == profile["id"])
    )
    assert row is not None
    row.enabled = False
    job = WebsiteRefreshJob(
        owner_id=owner.id,
        source_profile_id=row.id,
        scheduled_for=datetime.now(UTC),
        idempotency_key="disabled-refresh",
        status="QUEUED",
    )
    db_session.add(job)
    db_session.commit()
    response = client.post(
        f"/api/v1/intelligence/websites/refresh/jobs/{job.id}/run", json={}, headers=ORIGIN
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SKIPPED"
    assert response.json()["failure_code"] == "source_disabled"
