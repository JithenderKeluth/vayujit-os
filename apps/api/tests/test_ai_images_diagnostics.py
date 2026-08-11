from __future__ import annotations

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_image_diagnostics_are_safe_and_report_local_capabilities(client) -> None:
    setup_context(client)
    response = client.get("/api/v1/ai/images/diagnostics", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["image_studio"] == "healthy"
    assert body["local_provider"]["healthy"] is True
    assert body["local_provider"]["simulated"] is True
    assert body["live_provider"] == "not_configured"
    assert "marketplace_main_image" in body["supported_operations"]
    assert body["storage_ready"] is True
    assert body["storage_path_disclosed"] is False
    serialized = response.text.lower()
    assert "api_key" not in serialized
    assert "password" not in serialized
    assert "secret" not in serialized
    assert "127.0.0.1" not in serialized
