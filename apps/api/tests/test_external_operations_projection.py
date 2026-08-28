from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
SAFE_MARKERS = (
    "api_key",
    "access_token",
    "authorization",
    "cookie",
    "password",
    "postgresql://",
    "file://",
    "traceback",
)


def test_external_operations_and_system_doctor_projection(client: Any) -> None:
    integration.setup_context(client)
    projection = client.get("/api/v1/operations/intelligence/projection", headers=ORIGIN)
    assert projection.status_code == 200, projection.text
    body = projection.json()
    external = body["external_execution"]
    for key in (
        "provider_mode",
        "provider_health",
        "search_enabled",
        "fetch_enabled",
        "approved_domain_state",
        "rate_limit_count",
        "budget_exhaustion_count",
        "contradiction_count",
        "alert_count",
        "integrity_classification",
        "performance_classification",
        "recovery_registered",
    ):
        assert key in external
    assert body["external_integrity"]["classification"] in {"PASS", "REQUIRES_REVIEW"}
    doctor = client.get("/api/v1/intelligence/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200, doctor.text
    doctor_body = doctor.json()
    checks = doctor_body["checks"]["autonomous_research"]
    assert {
        "integrity_state",
        "performance_instrumentation",
        "live_search_validation",
        "live_fetch_validation",
    } <= checks.keys()
    for response in (projection, doctor):
        assert not any(marker in response.text.lower() for marker in SAFE_MARKERS)


def test_external_alert_projection_is_owner_scoped_and_safe(client: Any) -> None:
    integration.setup_context(client)
    response = client.get("/api/v1/intelligence/external/alerts", headers=ORIGIN)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)
    assert not any(marker in response.text.lower() for marker in SAFE_MARKERS)
