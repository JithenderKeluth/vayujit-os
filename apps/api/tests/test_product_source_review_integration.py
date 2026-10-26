"""Canonical API replay in disposable PostgreSQL, with offline provider transports."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
import test_ai_integration as integration
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.core.config import get_settings
from vayujit_api.intelligence import business_agent_service, external_service, product_research
from vayujit_api.intelligence.external_models import (
    ExternalExecution,
    ExternalFetch,
    ExternalSearchResult,
    ExternalSourceProfile,
)
from vayujit_api.intelligence.external_provider import SearchProvider, SearchResult
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


class FixtureSearch(SearchProvider):
    name = "offline-source-review-fixture"
    calls = 0
    queries: list[str]

    def __init__(self) -> None:
        self.queries = []

    def search(self, **kwargs: Any) -> list[SearchResult]:
        self.calls += 1
        self.queries.append(str(kwargs["query"]))
        return [
            SearchResult(
                title="Synthetic sports resistance band",
                url="https://example.org/product/sports-band",
                domain="example.org",
                snippet="Synthetic sports and outdoor fitness test fixture.",
                published_at=None,
                retrieved_at=datetime.now(UTC),
                provider=self.name,
                provider_result_id="synthetic-band",
                rank=1,
                metadata={},
                raw_payload_reference=None,
            )
        ]


class FixtureFetcher:
    calls = 0

    def __init__(self, _settings: object) -> None:
        pass

    def fetch(self, url: str, **kwargs: object) -> dict[str, object]:
        assert url == "https://example.org/product/sports-band"
        assert kwargs["allowed_domains"] == ("example.org",)
        type(self).calls += 1
        return {
            "requested_url": url,
            "final_url": url,
            "domain": "example.org",
            "status": "COMPLETED",
            "http_status": 200,
            "content_type": "text/html",
            "content_length": 400,
            "content_hash": "synthetic-source-review-content",
            "redirect_count": 0,
            "classification": "UNTRUSTED_EXTERNAL_DATA",
            "extracted": {
                "title": "Synthetic sports resistance band",
                "product_metadata": {
                    "json_ld": {
                        "@type": "Product",
                        "name": "Synthetic sports resistance band",
                        "brand": "Synthetic fixture brand",
                        "category": "Sports and outdoor fitness",
                        "description": (
                            "Synthetic fabric resistance band used only for offline tests."
                        ),
                    }
                },
            },
        }


def test_business_agent_source_review_retry_persists_real_authorities_without_live_calls(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_context(client)
    settings = get_settings().model_copy(
        update={
            "intelligence_external_provider_mode": "LIVE_READ_ONLY",
            "intelligence_enabled": True,
            "intelligence_execution_enabled": True,
            "intelligence_external_research_enabled": True,
            "intelligence_search_provider_enabled": True,
            "intelligence_web_fetch_enabled": True,
            "intelligence_external_require_source_approval": True,
            "intelligence_external_approved_domains": "",
            "intelligence_external_blocked_domains": "",
            "intelligence_external_review_required_domains": "",
            "intelligence_external_kill_switch": False,
            "external_mutations_emergency_stop": False,
            "intelligence_product_search_max_requests": 3,
        }
    )
    for module in (business_agent_service, product_research):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    provider = FixtureSearch()
    FixtureFetcher.calls = 0
    monkeypatch.setattr(external_service, "_provider", lambda _: provider)
    monkeypatch.setattr(external_service, "ApprovedWebFetcher", FixtureFetcher)
    previous = client.post(
        "/api/v1/intelligence/product-opportunities",
        json={"name": "Unrelated historical household fixture", "category": "Home & Kitchen"},
        headers=ORIGIN,
    )
    assert previous.status_code == 201, previous.text
    goal = client.post(
        "/api/v1/intelligence/business-agent/goals",
        json={
            "raw_goal": (
                "Find 1 product in the sports and outdoor fitness category for Amazon India."
            ),
            "idempotency_key": str(uuid.uuid4()),
        },
        headers=ORIGIN,
    )
    assert goal.status_code == 201, goal.text
    goal_id = goal.json()["id"]
    assert (
        client.post(
            f"/api/v1/intelligence/business-agent/goals/{goal_id}/plan", headers=ORIGIN
        ).status_code
        == 200
    )
    run = client.post(
        f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "max_steps": 1,
        },
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]
    first = client.post(f"/api/v1/intelligence/business-agent/runs/{run_id}/start", headers=ORIGIN)
    assert first.status_code == 200, first.text
    assert first.json()["failure"]["code"] == "SOURCE_APPROVAL_REQUIRED"
    assert "source" in first.json()["failure"]["message"].lower()
    assert FixtureFetcher.calls == 0
    assert 0 < provider.calls <= 3
    assert all("sports and outdoor fitness" in query for query in provider.queries)
    assert all("container" not in query and "wardrobe" not in query for query in provider.queries)
    assert integration.factory is not None
    with integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductOpportunity)) == 1
    assert first.json()["candidates"] == []  # unrelated owner history is not this goal's result

    payload = {
        "domain": "example.org",
        "reason": "Synthetic HUMAN policy review for offline test only.",
        "approval_authority": "HUMAN",
    }
    for _ in range(2):
        approved = client.post(
            "/api/v1/intelligence/external/source-profiles/admit", json=payload, headers=ORIGIN
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["approval"]["external_write"] is False
    with integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(ExternalSourceProfile)) == 1
        profile = db.scalar(select(ExternalSourceProfile))
        assert profile is not None
        profile.enabled = False  # disposable revoked-profile fixture, never live state
        db.commit()
    revoked = client.post(
        f"/api/v1/intelligence/business-agent/runs/{run_id}/resume", headers=ORIGIN
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["failure"]["code"] == "SOURCE_APPROVAL_REQUIRED"
    assert FixtureFetcher.calls == 0
    # Only the canonical explicit admission can restore this test profile.
    assert (
        client.post(
            "/api/v1/intelligence/external/source-profiles/admit", json=payload, headers=ORIGIN
        ).status_code
        == 200
    )
    calls_before_retry = provider.calls
    retry = client.post(f"/api/v1/intelligence/business-agent/runs/{run_id}/resume", headers=ORIGIN)
    assert retry.status_code == 200, retry.text
    assert retry.json()["candidates"], retry.json()
    assert len(retry.json()["candidates"]) == 1
    assert retry.json()["candidates"][0]["name"] == "Synthetic sports resistance band"
    assert retry.json()["failure"].get("code") != "SOURCE_APPROVAL_REQUIRED", retry.json()
    assert retry.json()["status"] != "RUNNING"
    assert provider.calls == calls_before_retry  # normal search reuse, no extra provider spend
    assert FixtureFetcher.calls == 1
    with integration.factory() as db:
        product = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.name == "Synthetic sports resistance band"
            )
        )
        assert product is not None
        assert product.name == "Synthetic sports resistance band"
        assert product.intelligence_profile["business_agent_run_id"] == run_id
        constraint = product.intelligence_profile["category_constraint"]
        assert isinstance(constraint, dict) and constraint["matched"] is True
        fetch = db.scalar(select(ExternalFetch))
        assert fetch is not None and fetch.source_profile.startswith("dynamic-")
        assert fetch.search_result_id is not None
        assert fetch.provider_mode == "LIVE_READ_ONLY"
    # An unauthenticated client cannot admit a source or see the owner-scoped registry.
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/intelligence/external/source-profiles/admit", json=payload, headers=ORIGIN
        ).status_code
        == 401
    )
    assert (
        client.get("/api/v1/intelligence/external/source-profiles", headers=ORIGIN).status_code
        == 401
    )


def test_cross_query_cache_reconstructs_shared_results_from_execution_lineage(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_context(client)
    settings = get_settings().model_copy(
        update={
            "intelligence_external_provider_mode": "LOCAL_FIXTURE",
            "intelligence_external_approved_domains": "example.org",
            "intelligence_external_blocked_domains": "",
            "intelligence_external_kill_switch": False,
            "external_mutations_emergency_stop": False,
        }
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)
    provider = FixtureSearch()
    monkeypatch.setattr(external_service, "_provider", lambda _: provider)
    payloads = [{"query": f"shared result query {index}", "market": "IN"} for index in range(2)]
    fresh = [
        client.post("/api/v1/intelligence/external/search", json=payload, headers=ORIGIN)
        for payload in payloads
    ]
    assert all(response.status_code == 200 for response in fresh)
    assert provider.calls == 2
    assert fresh[0].json()["results"][0]["id"] == fresh[1].json()["results"][0]["id"]
    assert integration.factory is not None
    with integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(ExternalSearchResult)) == 1
        executions = list(
            db.scalars(select(ExternalExecution).where(ExternalExecution.kind == "search"))
        )
        assert len(executions) == 2 and all(len(item.result_ids) == 1 for item in executions)
    for payload in payloads:
        replay = client.post("/api/v1/intelligence/external/search", json=payload, headers=ORIGIN)
        assert replay.status_code == 200, replay.text
        assert len(replay.json()["results"]) == 1
        assert replay.json()["new_result_count"] == 0
    assert provider.calls == 2


@pytest.mark.parametrize("failure_code", ["dns_rebinding_blocked", "untrusted-provider-output"])
def test_fetch_api_exposes_only_allowlisted_safe_failure_codes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    failure_code: str,
) -> None:
    setup_context(client)
    settings = get_settings().model_copy(
        update={
            "intelligence_external_provider_mode": "LIVE_READ_ONLY",
            "intelligence_enabled": True,
            "intelligence_external_research_enabled": True,
            "intelligence_search_provider_enabled": True,
            "intelligence_web_fetch_enabled": True,
            "intelligence_external_require_source_approval": True,
            "intelligence_external_approved_domains": "",
            "intelligence_external_blocked_domains": "",
            "intelligence_external_review_required_domains": "",
            "intelligence_external_kill_switch": False,
            "external_mutations_emergency_stop": False,
        }
    )
    monkeypatch.setattr(external_service, "_settings", lambda: settings)

    class DeniedFixtureFetcher:
        def __init__(self, _settings: object) -> None:
            pass

        def fetch(self, *_: object, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError(failure_code)

    monkeypatch.setattr(external_service, "ApprovedWebFetcher", DeniedFixtureFetcher)
    approved = client.post(
        "/api/v1/intelligence/external/source-profiles/admit",
        json={
            "domain": "example.org",
            "reason": "Synthetic read-only policy review",
            "approval_authority": "HUMAN",
        },
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    response = client.post(
        "/api/v1/intelligence/external/fetch",
        json={
            "url": "https://example.org/product/synthetic-band",
            "source_profile": approved.json()["name"],
            "allowed_domains": ["example.org"],
        },
        headers=ORIGIN,
    )
    assert response.status_code == 502, response.text
    assert response.json()["detail"] == "Approved fetch failed safely."
    if failure_code == "dns_rebinding_blocked":
        assert response.headers["X-External-Failure-Code"] == failure_code
    else:
        assert "X-External-Failure-Code" not in response.headers
        assert failure_code not in response.text
