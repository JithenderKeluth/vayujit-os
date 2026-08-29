from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from website_postgres_fixture import ORIGIN

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_calendar_projects_durable_refresh_lineage(client):
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "calendar.example", "display_name": "Calendar", "enabled": True},
        headers=ORIGIN,
    ).json()
    client.post(
        f"/api/v1/intelligence/websites/profiles/{profile['id']}/refresh/schedule",
        json={
            "policy": "MONTHLY",
            "timezone": "UTC",
            "next_refresh_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
        headers=ORIGIN,
    )
    events = client.get("/api/v1/intelligence/websites/calendar", headers=ORIGIN).json()
    event = next(item for item in events if item["source_profile_id"] == profile["id"])
    assert event["type"] == "WEBSITE_SOURCE_REFRESH_DUE"
    assert event["target_type"] == "WEBSITE_SOURCE"
    assert event["timezone"] == "UTC"
