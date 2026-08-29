from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from website_postgres_fixture import ORIGIN

from vayujit_api.intelligence.website_models import WebsiteRefreshJob

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_refresh_storage_ledger_has_single_owner_scoped_job(client, db_session, owner):
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "storage.example", "display_name": "Storage", "enabled": True},
        headers=ORIGIN,
    ).json()
    client.post(
        f"/api/v1/intelligence/websites/profiles/{profile['id']}/refresh/schedule",
        json={
            "policy": "DAILY",
            "timezone": "UTC",
            "next_refresh_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
        headers=ORIGIN,
    )
    client.post("/api/v1/intelligence/websites/refresh/materialize-due", headers=ORIGIN)
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(WebsiteRefreshJob)
            .where(WebsiteRefreshJob.owner_id == owner.id)
        )
        == 1
    )
    job = db_session.scalar(select(WebsiteRefreshJob).where(WebsiteRefreshJob.owner_id == owner.id))
    assert job is not None and job.idempotency_key.startswith("website-refresh:")
