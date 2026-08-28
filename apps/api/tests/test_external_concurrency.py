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


def test_identical_search_reuses_one_execution(client) -> None:
    setup_context(client)
    payload = {"query": "concurrent identity", "allowed_domains": ["example.org"], "max_results": 2}
    first = client.post("/api/v1/intelligence/external/search", json=payload, headers=ORIGIN)
    second = client.post("/api/v1/intelligence/external/search", json=payload, headers=ORIGIN)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["result_count"] == second.json()["result_count"]


def test_identical_fetch_reuses_one_execution(client) -> None:
    setup_context(client)
    search = client.post(
        "/api/v1/intelligence/external/search",
        json={"query": "fetch identity", "allowed_domains": ["example.org"]},
        headers=ORIGIN,
    )
    url = search.json()["results"][0]["url"]
    first = client.post(
        "/api/v1/intelligence/external/fetch",
        json={"url": url, "allowed_domains": ["example.org"]},
        headers=ORIGIN,
    )
    second = client.post(
        "/api/v1/intelligence/external/fetch",
        json={"url": url, "allowed_domains": ["example.org"]},
        headers=ORIGIN,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
