from __future__ import annotations

import os

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_WEB_FETCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS"] = "example.org"


import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_system_doctor_reports_external_execution_without_credentials(client) -> None:
    setup_context(client)
    response = client.get("/api/v1/intelligence/system-doctor", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    external = body["checks"]["autonomous_research"]
    assert "recovery_registered" in external
    assert "budget_configuration" in external
    assert "kill_switches" in external
    assert "api_key" not in response.text.lower()


def test_global_external_kill_switch_fails_closed(client, monkeypatch: pytest.MonkeyPatch) -> None:
    setup_context(client)
    monkeypatch.setenv("VAYUJIT_INTELLIGENCE_EXTERNAL_KILL_SWITCH", "true")
    from vayujit_api.core.config import get_settings

    get_settings.cache_clear()
    response = client.post(
        "/api/v1/intelligence/external/search", json={"query": "blocked"}, headers=ORIGIN
    )
    assert response.status_code == 409
    assert "disabled" in response.text.lower()
    get_settings.cache_clear()
