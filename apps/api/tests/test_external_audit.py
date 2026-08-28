from __future__ import annotations

import os

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_RESEARCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_WEB_FETCH_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_PROVIDER_MODE"] = "LOCAL_FIXTURE"
os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_APPROVED_DOMAINS"] = "example.org"


import pytest
import test_ai_integration as integration
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.audit.models import AuditEvent

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_search_fetch_audit_lifecycle_is_safe_and_idempotent(client) -> None:
    setup_context(client)
    search_payload = {
        "query": "audit lifecycle",
        "allowed_domains": ["example.org"],
        "max_results": 2,
    }
    first = client.post("/api/v1/intelligence/external/search", json=search_payload, headers=ORIGIN)
    assert first.status_code == 200, first.text
    url = first.json()["results"][0]["url"]
    fetched = client.post(
        "/api/v1/intelligence/external/fetch",
        json={"url": url, "allowed_domains": ["example.org"]},
        headers=ORIGIN,
    )
    assert fetched.status_code == 200, fetched.text
    replay = client.post(
        "/api/v1/intelligence/external/search", json=search_payload, headers=ORIGIN
    )
    assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    assert integration.factory is not None
    with integration.factory() as db:
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.action.like("external.%"))))
        actions = {event.action for event in events}
        assert "external.search.requested" in actions
        assert "external.search.completed" in actions
        assert "external.fetch.requested" in actions
        assert "external.fetch.completed" in actions
        for event in events:
            text = str(event.metadata_json).lower()
            assert all(
                secret not in text
                for secret in ("authorization", "api_key", "cookie", "password", "token")
            )
            assert "<html" not in text
        search_completed = [
            event for event in events if event.action == "external.search.completed"
        ]
        assert len(search_completed) == 1
