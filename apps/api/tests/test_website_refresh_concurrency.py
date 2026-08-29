from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from website_postgres_fixture import ORIGIN

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_repeated_materialization_is_idempotent_under_scheduler_replay(client):
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "concurrency.example", "display_name": "Concurrency", "enabled": True},
        headers=ORIGIN,
    ).json()
    client.post(
        f"/api/v1/intelligence/websites/profiles/{profile['id']}/refresh/schedule",
        json={
            "policy": "WEEKLY",
            "timezone": "UTC",
            "next_refresh_at": (datetime.now(UTC) - timedelta(seconds=2)).isoformat(),
        },
        headers=ORIGIN,
    )
    results = [
        client.post("/api/v1/intelligence/websites/refresh/materialize-due", headers=ORIGIN).json()
        for _ in range(2)
    ]
    assert [item["materialized"] for item in results] == [1, 0]
    assert len(client.get("/api/v1/intelligence/websites/refresh/jobs", headers=ORIGIN).json()) == 1
