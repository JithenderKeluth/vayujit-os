from __future__ import annotations

import pytest

from vayujit_api.intelligence.external_projection import performance_projection

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_refresh_performance_projection_has_bounded_samples(client, db_session, owner):
    del client
    result = performance_projection(db_session, owner, samples=2)
    measurements = result["measurements"]
    refresh_routes = {row["route"] for row in measurements if "website-refresh" in row["route"]}
    assert {
        "/website-refresh/jobs",
        "/website-refresh/calendar",
        "/website-refresh/integrity",
    } <= refresh_routes
    assert all(row["samples"] == 2 for row in measurements)
