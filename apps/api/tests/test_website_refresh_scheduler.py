from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from website_postgres_fixture import ORIGIN

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def _profile(client, *, enabled=True):
    response = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={
            "domain": "refresh.example",
            "display_name": "Refresh Example",
            "source_type": "SUPPLIER_WEBSITE",
            "enabled": enabled,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_refresh_policies_materialize_once_and_advance(client):
    profile = _profile(client)
    scheduled = client.post(
        f"/api/v1/intelligence/websites/profiles/{profile['id']}/refresh/schedule",
        json={
            "policy": "DAILY",
            "timezone": "UTC",
            "next_refresh_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
        headers=ORIGIN,
    )
    assert scheduled.status_code == 200, scheduled.text
    first = client.post("/api/v1/intelligence/websites/refresh/materialize-due", headers=ORIGIN)
    assert first.status_code == 200, first.text
    assert first.json()["materialized"] == 1
    second = client.post("/api/v1/intelligence/websites/refresh/materialize-due", headers=ORIGIN)
    assert second.status_code == 200
    assert second.json()["materialized"] == 0
    jobs = client.get("/api/v1/intelligence/websites/refresh/jobs", headers=ORIGIN).json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "QUEUED"


def test_manual_policy_does_not_schedule(client):
    profile = _profile(client)
    response = client.post(
        f"/api/v1/intelligence/websites/profiles/{profile['id']}/refresh/schedule",
        json={"policy": "MANUAL", "timezone": "UTC"},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "manual"
