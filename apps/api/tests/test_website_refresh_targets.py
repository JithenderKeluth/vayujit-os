from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from website_postgres_fixture import ORIGIN

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration

TARGETS = (
    "WEBSITE_SOURCE",
    "MANUFACTURER_CANDIDATE",
    "SUPPLIER_WEBSITE_CANDIDATE",
    "CERTIFICATION_REVIEW",
    "PRICE_RECHECK",
    "MOQ_RECHECK",
    "LEAD_TIME_RECHECK",
    "AVAILABILITY_RECHECK",
)


def test_all_refresh_target_types_are_persisted_and_materialized(client):
    for index, target in enumerate(TARGETS):
        profile = client.post(
            "/api/v1/intelligence/websites/profiles",
            json={
                "domain": f"target-{index}.example",
                "display_name": f"Target {target}",
                "enabled": True,
            },
            headers=ORIGIN,
        )
        assert profile.status_code == 201, profile.text
        scheduled = client.post(
            f"/api/v1/intelligence/websites/profiles/{profile.json()['id']}/refresh/schedule",
            json={
                "policy": "DAILY",
                "timezone": "UTC",
                "target_type": target,
                "next_refresh_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            },
            headers=ORIGIN,
        )
        assert scheduled.status_code == 200, scheduled.text
    materialized = client.post(
        "/api/v1/intelligence/websites/refresh/materialize-due", headers=ORIGIN
    )
    assert materialized.status_code == 200, materialized.text
    jobs = client.get("/api/v1/intelligence/websites/refresh/jobs", headers=ORIGIN).json()
    assert {job["target_type"] for job in jobs} == set(TARGETS)
    calendar = client.get("/api/v1/intelligence/websites/calendar", headers=ORIGIN)
    assert calendar.status_code == 200, calendar.text
    assert {event["target_type"] for event in calendar.json()} == set(TARGETS)
    assert {event["type"] for event in calendar.json()} == {
        "WEBSITE_SOURCE_REFRESH_DUE",
        "MANUFACTURER_CANDIDATE_DUE",
        "SUPPLIER_WEBSITE_CANDIDATE_DUE",
        "CERTIFICATION_REVIEW_DUE",
        "PRICE_RECHECK_DUE",
        "MOQ_RECHECK_DUE",
        "LEAD_TIME_RECHECK_DUE",
        "AVAILABILITY_RECHECK_DUE",
    }
