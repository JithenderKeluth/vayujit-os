"""Focused contract and safety coverage for the Operations Control Center."""

from __future__ import annotations

import contextlib
import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from test_ai_integration import ORIGIN, setup_context
from test_ai_integration import client as integration_client

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> object:
    generator = cast(Any, integration_client).__wrapped__()
    value = next(generator)
    try:
        yield value
    finally:
        with contextlib.suppress(StopIteration):
            next(generator)


SAFE_RESPONSE_MARKERS = (
    "database_url",
    "credential_encryption_key",
    "session_secret",
    "access_token",
    "authorization",
    "password",
    "traceback",
    "private_key",
    "dsn",
    "local_path",
    "pgpassword",
)


def test_operations_control_center_requires_owner_authentication() -> None:
    from vayujit_api.main import create_app

    unauthenticated = TestClient(create_app())
    response = unauthenticated.get("/api/v1/operations/overview", headers=ORIGIN)
    assert response.status_code == 401


def test_operations_control_center_safe_endpoint_matrix(client: TestClient) -> None:
    setup_context(client)
    invalid_id = str(uuid.uuid4())
    requests = [
        ("GET", "/api/v1/operations/overview", None),
        ("GET", "/api/v1/operations/health", None),
        ("GET", "/api/v1/operations/workers", None),
        ("GET", "/api/v1/operations/workers/worker-missing", None),
        ("GET", "/api/v1/operations/scheduler", None),
        ("GET", "/api/v1/operations/jobs", None),
        ("GET", "/api/v1/operations/jobs?state=failed&page=1&page_size=10", None),
        ("GET", "/api/v1/operations/jobs/not-a-uuid", None),
        ("GET", "/api/v1/operations/providers", None),
        ("GET", "/api/v1/operations/providers/fake", None),
        ("GET", "/api/v1/operations/providers/not-configured", None),
        ("GET", "/api/v1/operations/configuration", None),
        ("GET", "/api/v1/operations/security", None),
        ("GET", "/api/v1/operations/storage", None),
        ("GET", "/api/v1/operations/alerts", None),
        ("GET", "/api/v1/operations/release-readiness", None),
        ("GET", "/api/v1/operations/backups/overview", None),
        ("GET", "/api/v1/operations/cleanup/preview", None),
        ("GET", "/api/v1/operations/audit?limit=10", None),
        ("GET", "/api/v1/operations/trace/correlation-missing", None),
        ("GET", "/api/v1/operations/metrics", None),
        ("POST", "/api/v1/operations/workers/worker-missing/pause", {}),
        ("POST", "/api/v1/operations/workers/worker-missing/resume", {}),
        ("POST", "/api/v1/operations/scheduler/run-due", {}),
        ("POST", f"/api/v1/operations/jobs/{invalid_id}/actions?action=inspect", {}),
        ("POST", f"/api/v1/operations/jobs/{invalid_id}/actions?action=unknown", {"confirm": True}),
        ("POST", "/api/v1/operations/providers/shopify/switch", {}),
        ("POST", "/api/v1/operations/backups/trigger", {}),
        ("POST", "/api/v1/operations/emergency-stop", {}),
        ("GET", "/api/v1/operations/jobs?connector=shopify&retryable=false", None),
        ("GET", "/api/v1/operations/audit?correlation_id=not-secret", None),
        ("GET", "/api/v1/operations/trace/not-secret", None),
        ("GET", "/api/v1/operations/providers/image", None),
        ("GET", "/api/v1/operations/providers/video", None),
        ("GET", "/api/v1/operations/providers/status", None),
    ]
    assert len(requests) >= 35
    allowed = {200, 401, 404, 409, 422, 503}
    for method, path, payload in requests:
        response = client.request(method, path, json=payload, headers=ORIGIN)
        assert response.status_code in allowed, (method, path, response.text)
        lowered = response.text.casefold()
        assert all(marker not in lowered for marker in SAFE_RESPONSE_MARKERS), (method, path)


SECURITY_CASES = [
    ("GET", "/api/v1/operations/overview", None),
    ("GET", "/api/v1/operations/health", None),
    ("GET", "/api/v1/operations/workers", None),
    ("POST", "/api/v1/operations/workers/foreign/pause", {"confirm": True}),
    ("GET", "/api/v1/operations/scheduler", None),
    ("GET", "/api/v1/operations/jobs", None),
    ("GET", "/api/v1/operations/jobs/forged", None),
    ("GET", "/api/v1/operations/recovery", None),
    ("GET", "/api/v1/operations/recovery/history", None),
    ("POST", "/api/v1/operations/recovery/actions?action=retry", {"confirm": True}),
    ("GET", "/api/v1/operations/providers", None),
    ("GET", "/api/v1/operations/providers/shopify", None),
    ("POST", "/api/v1/operations/providers/shopify/switch", {"confirm": True}),
    ("GET", "/api/v1/operations/mutation-control", None),
    ("POST", "/api/v1/operations/mutation-control", {"confirm": True}),
    ("GET", "/api/v1/operations/emergency-stop", None),
    ("POST", "/api/v1/operations/emergency-stop", {"confirm": True}),
    ("GET", "/api/v1/operations/ads/safety", None),
    ("GET", "/api/v1/operations/backups", None),
    ("GET", "/api/v1/operations/backups/overview", None),
    ("POST", "/api/v1/operations/backups/trigger", {"confirm": True}),
    ("GET", "/api/v1/operations/restore/readiness", None),
    ("GET", "/api/v1/operations/storage", None),
    ("GET", "/api/v1/operations/cleanup/preview", None),
    ("POST", "/api/v1/operations/cleanup", {"confirm": True}),
    ("GET", "/api/v1/operations/migrations", None),
    ("POST", "/api/v1/operations/migrations/run", {"confirm": True}),
    ("GET", "/api/v1/operations/configuration", None),
    ("GET", "/api/v1/operations/security", None),
    ("GET", "/api/v1/operations/security/events", None),
    ("GET", "/api/v1/operations/audit", None),
    ("GET", "/api/v1/operations/history", None),
    ("GET", "/api/v1/operations/trace/foreign", None),
    ("GET", "/api/v1/operations/alerts", None),
    ("POST", "/api/v1/operations/alerts/acknowledge?alert_code=test", {"confirm": True}),
    ("GET", "/api/v1/operations/release-readiness", None),
    ("GET", "/api/v1/operations/staging-readiness", None),
    ("GET", "/api/v1/operations/production-readiness", None),
]


@pytest.mark.parametrize("method,path,payload", SECURITY_CASES)
def test_operations_security_matrix(
    method: str, path: str, payload: dict[str, object] | None
) -> None:
    from vayujit_api.main import create_app

    response = TestClient(create_app()).request(method, path, json=payload, headers=ORIGIN)
    assert response.status_code == 401
    body = response.text.lower()
    assert not any(marker in body for marker in SAFE_RESPONSE_MARKERS)
