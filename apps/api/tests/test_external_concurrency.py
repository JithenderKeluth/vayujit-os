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

import vayujit_api.intelligence.external_service as external_service
from vayujit_api.intelligence.external_models import ExternalSearchResult
from vayujit_api.intelligence.external_provider import SearchResult

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


class _OverlappingProvider:
    name = "overlap-provider"

    def search(self, **kwargs):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        shared = SearchResult(
            "Shared canonical result",
            "https://example.org/shared?utm_source=search",
            "example.org",
            "Shared result",
            None,
            now,
            self.name,
            "shared-result",
            1,
            {},
            None,
        )
        unique = SearchResult(
            f"Unique {kwargs['query']}",
            f"https://example.org/{kwargs['query'].replace(' ', '-')}",
            "example.org",
            "Unique result",
            None,
            now,
            self.name,
            f"unique-{kwargs['query']}",
            2,
            {},
            None,
        )
        if kwargs["query"] == "first overlap":
            return [shared, shared, unique]
        return [shared, unique]


def test_cross_query_duplicate_results_reuse_without_poisoning_session(client, monkeypatch) -> None:
    setup_context(client)
    monkeypatch.setattr(external_service, "_provider", lambda _settings: _OverlappingProvider())
    first = client.post(
        "/api/v1/intelligence/external/search",
        json={"query": "first overlap", "allowed_domains": ["example.org"], "max_results": 3},
        headers=ORIGIN,
    )
    assert first.status_code == 200, first.text
    assert first.json()["result_count"] == 3
    assert first.json()["new_result_count"] == 2
    assert first.json()["duplicate_result_count"] == 1

    second = client.post(
        "/api/v1/intelligence/external/search",
        json={"query": "second overlap", "allowed_domains": ["example.org"], "max_results": 2},
        headers=ORIGIN,
    )
    assert second.status_code == 200, second.text
    assert second.json()["result_count"] == 2
    assert second.json()["new_result_count"] == 1
    assert second.json()["reused_result_count"] == 1

    assert integration.factory is not None
    with integration.factory() as db:
        rows = list(db.scalars(select(ExternalSearchResult).order_by(ExternalSearchResult.rank)))
        assert len(rows) == 3
        shared = next(row for row in rows if row.provider_result_id == "shared-result")
        assert shared.title == "Shared canonical result"
        assert db.execute(select(ExternalSearchResult.id)).all()
