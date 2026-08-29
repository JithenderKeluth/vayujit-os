from __future__ import annotations

import pytest
from website_postgres_fixture import ORIGIN

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_system_doctor_reports_refresh_worker_registration(client):
    response = client.get("/api/v1/intelligence/system-doctor", headers=ORIGIN)
    assert response.status_code == 200, response.text
    checks = response.json()["checks"]
    assert checks["website_intelligence"]["worker_registered"] is True
    assert checks["website_intelligence"]["scheduler_registered"] is True
    assert checks["website_intelligence"]["recovery"]["registered"] is True
