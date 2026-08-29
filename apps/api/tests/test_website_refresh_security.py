from __future__ import annotations

import uuid

import pytest
from website_postgres_fixture import ORIGIN

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_refresh_routes_are_owner_scoped_and_manual_is_safe(client):
    missing = uuid.uuid4()
    assert (
        client.post(
            f"/api/v1/intelligence/websites/profiles/{missing}/refresh/schedule",
            json={"policy": "DAILY"},
            headers=ORIGIN,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/intelligence/websites/refresh/jobs/{missing}/run", json={}, headers=ORIGIN
        ).status_code
        == 404
    )
    profile = client.post(
        "/api/v1/intelligence/websites/profiles",
        json={"domain": "safe.example", "display_name": "Safe", "enabled": True},
        headers=ORIGIN,
    ).json()
    response = client.post(
        f"/api/v1/intelligence/websites/profiles/{profile['id']}/refresh/schedule",
        json={"policy": "MANUAL"},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert (
        client.post("/api/v1/intelligence/websites/refresh/materialize-due", headers=ORIGIN).json()[
            "materialized"
        ]
        == 0
    )
