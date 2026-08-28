from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_external_calendar_is_informational_and_replacement_safe(client: Any) -> None:
    integration.setup_context(client)
    response = client.get("/api/v1/intelligence/external/calendar", headers=ORIGIN)
    assert response.status_code == 200, response.text
    events = response.json()
    assert isinstance(events, list)
    assert all(item["informational"] is True and item["actions"] == [] for item in events)
    assert not any(
        marker in response.text.lower() for marker in ("purchase", "contact_supplier", "fetch now")
    )
    repeated = client.get("/api/v1/intelligence/external/calendar", headers=ORIGIN)
    assert repeated.status_code == 200
    assert repeated.json() == events
