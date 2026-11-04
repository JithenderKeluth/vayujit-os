"""Offline regressions for category scope, source review, and truthful counters."""

from __future__ import annotations

import uuid
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from vayujit_api.core.config import Settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence import product_research as research
from vayujit_api.intelligence.external_schemas import (
    ExternalFetchRequestBody,
    ExternalSearchRequestBody,
)


@pytest.fixture
def discovery(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, User]:
    settings = Settings().model_copy(
        update={
            "intelligence_external_provider_mode": "LIVE_READ_ONLY",
            "intelligence_product_search_max_requests": 3,
        }
    )
    monkeypatch.setattr(research, "get_settings", lambda: settings)
    monkeypatch.setattr(research, "approved_source_profiles", lambda *_: {})
    db = MagicMock(spec=Session)
    return db, User(id=uuid.uuid4())


def search_row(domain: str = "sports.example.org") -> SimpleNamespace:
    url = f"https://{domain}/product/sports-band"
    return SimpleNamespace(
        id=uuid.uuid4(),
        url=url,
        canonical_url=url,
        domain=domain,
        title="Sports resistance band",
        snippet="Synthetic test product",
        provider="fixture",
    )


def test_missing_approval_has_actionable_status_and_zero_successful_fetches(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = discovery
    row = search_row()
    queries: list[str] = []

    def search(
        _db: object, _owner: object, request: ExternalSearchRequestBody
    ) -> dict[str, object]:
        queries.append(request.query)
        return {"status": "COMPLETED", "results": [row]}

    def blocked(*_: object) -> dict[str, object]:
        raise HTTPException(403, "External source approval is required before fetching.")

    monkeypatch.setattr(research, "external_search", search)
    monkeypatch.setattr(research, "approved_fetch", blocked)
    result = research.run_live_product_discovery(
        db,
        owner,
        raw_goal="Find 3 products in the sports and outdoor fitness category.",
        structured_goal={"category": "Home & Kitchen"},
    )
    assert result["status"] == "SOURCE_APPROVAL_REQUIRED"
    assert result["source_approvals_required"] == [row.domain]
    assert len(queries) == 1  # wait for HUMAN review instead of spending the remaining budget
    assert all("sports and outdoor fitness" in query for query in queries)
    assert all("container" not in query and "wardrobe" not in query for query in queries)
    assert result["observability"]["fetch_attempts"] == 1
    assert result["observability"]["urls_fetched"] == 0
    assert result["observability"]["successful_fetches"] == 0
    assert result["observability"]["blocked_fetches"] == 1
    assert result["fetch_count"] == 0
    assert result["candidate_ids"] == []
    db.add.assert_not_called()


@pytest.mark.parametrize("reused", [False, True])
def test_successful_fetch_counters_do_not_promote_editorial_pages(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
    reused: bool,
) -> None:
    db, owner = discovery
    row = search_row()
    row.url = row.canonical_url = "https://sports.example.org/pages/fitness-guide"
    monkeypatch.setattr(research, "external_search", lambda *_: {"results": [row]})
    monkeypatch.setattr(
        research,
        "approved_fetch",
        lambda *_: {
            "status": "COMPLETED",
            "reuse": reused,
            "extracted": {"title": "Best fitness products guide", "text": "Editorial test content"},
        },
    )
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    assert result["status"] == "NO_USEFUL_PRODUCT_CANDIDATES"
    assert result["observability"]["fetch_attempts"] == 1
    assert result["observability"]["successful_fetches"] == 1
    assert result["observability"]["urls_fetched"] == int(not reused)
    assert result["observability"]["fetches_reused"] == int(reused)
    assert result["candidate_ids"] == []
    db.add.assert_not_called()


def test_discovery_uses_most_specific_approved_owner_profile(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = discovery
    monkeypatch.setattr(
        research,
        "approved_source_profiles",
        lambda *_: {
            "example.org": "parent-profile",
            "sports.example.org": "specific-profile",
        },
    )
    monkeypatch.setattr(research, "external_search", lambda *_: {"results": [search_row()]})
    profiles: list[str] = []

    def fetch(_db: object, _owner: object, request: ExternalFetchRequestBody) -> dict[str, object]:
        profiles.append(request.source_profile)
        raise HTTPException(502, "Approved fetch failed safely.")

    monkeypatch.setattr(research, "approved_fetch", fetch)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    assert profiles == ["specific-profile"]
    assert result["status"] == "NO_USEFUL_PRODUCT_CANDIDATES"
    assert result["source_approvals_required"] == []
    assert result["observability"]["urls_fetched"] == 0


def test_other_security_rejections_are_not_misreported_as_approval_requests(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = discovery
    monkeypatch.setattr(research, "external_search", lambda *_: {"results": [search_row()]})

    def blocked(*_: object) -> dict[str, object]:
        raise HTTPException(403, "External source requires manual review.")

    monkeypatch.setattr(research, "approved_fetch", blocked)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    assert result["status"] == "NO_USEFUL_PRODUCT_CANDIDATES"
    assert result["source_approvals_required"] == []
    assert result["rejected_results"][0]["reason"] == "External source requires manual review."


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.in/foldable-wardrobe/s?k=wardrobe",
        "https://www.amazon.in/s?k=fitness",
        "https://www.amazon.in/b?node=123",
        "https://www.amazon.in/",
        "https://example.org/search?q=band",
        "https://example.org/manufacturers/bands.html",
        "https://example.org/suppliers/bands",
        "https://example.org/collections/fitness",
        "https://example.org/category/fitness",
        "https://example.org/policies/shipping-policy",
    ],
)
def test_obvious_nonproduct_urls_do_not_request_fetch_or_approval(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    db, owner = discovery
    row = search_row()
    row.url = row.canonical_url = url
    monkeypatch.setattr(research, "external_search", lambda *_: {"results": [row]})
    fetch = MagicMock(side_effect=AssertionError("Non-product URL must not be fetched"))
    monkeypatch.setattr(research, "approved_fetch", fetch)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    fetch.assert_not_called()
    assert result["source_approvals_required"] == []
    assert result["observability"]["fetch_attempts"] == 0
    assert result["observability"]["non_product_pages_skipped"] == 1
    assert result["rejected_results"][0]["reason_code"] == "NON_PRODUCT_PAGE"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/collections/fitness/products/resistance-band",
        "https://www.amazon.in/example/dp/B123456789?node=123",
        "https://example.org/product/band",
        "https://example.org/band-specifications.html",
    ],
)
def test_possible_product_pages_still_require_fetched_identity(url: str) -> None:
    assert research.non_product_discovery_url(url) is None


def test_legacy_review_projection_removes_useless_approval_prompt_without_changing_evidence() -> (
    None
):
    original: dict[str, object] = {
        "details": {
            "fetches": [
                {
                    "url": "https://example.org/manufacturers/bands.html",
                    "domain": "example.org",
                    "status": "BLOCKED",
                    "reason_code": "SOURCE_APPROVAL_REQUIRED",
                    "failure": "External source approval is required before fetching.",
                }
            ]
        }
    }
    preserved = deepcopy(original)
    projection = research.discovery_review_projection(original)
    assert original == preserved
    details = projection["details"]
    assert isinstance(details, dict)
    fetches = details["fetches"]
    assert isinstance(fetches, list)
    assert fetches[0]["source_review_eligible"] is False
    assert "No approval is needed" in details["review_guidance"]


def test_safe_dns_failure_is_actionable_and_cannot_be_approved_away(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = discovery
    monkeypatch.setattr(research, "external_search", lambda *_: {"results": [search_row()]})

    def blocked(*_: object) -> dict[str, object]:
        raise HTTPException(
            502,
            "Approved fetch failed safely.",
            headers={"X-External-Failure-Code": "dns_rebinding_blocked"},
        )

    monkeypatch.setattr(research, "approved_fetch", blocked)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    assert result["source_approvals_required"] == []
    assert result["fetches"][0]["reason_code"] == "dns_rebinding_blocked"
    assert "Source approval cannot override" in result["fetches"][0]["failure"]


def test_cached_nonproduct_results_trigger_one_bounded_product_page_refinement(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = discovery
    queries: list[str] = []
    directory = search_row()
    directory.url = directory.canonical_url = "https://example.org/manufacturers/bands.html"

    def search(
        _db: object, _owner: object, request: ExternalSearchRequestBody
    ) -> dict[str, object]:
        queries.append(request.query)
        return {
            "results": [directory] if len(queries) < 3 else [search_row()],
            "reuse": len(queries) < 3,
        }

    def needs_approval(*_: object) -> dict[str, object]:
        raise HTTPException(403, "External source approval is required before fetching.")

    monkeypatch.setattr(research, "external_search", search)
    monkeypatch.setattr(research, "approved_fetch", needs_approval)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    assert len(queries) == 3 and "buy online India product specifications" in queries[-1]
    assert result["status"] == "SOURCE_APPROVAL_REQUIRED"
    assert result["observability"]["executed_search_requests"] == 1
    assert result["observability"]["reused_search_requests"] == 2
    assert result["search_budget"]["provider_budget_remaining"] == 2
    assert result["observability"]["fetch_attempts"] == 1


def test_cached_empty_plan_never_loops_or_exceeds_budget(
    discovery: tuple[MagicMock, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = discovery
    search = MagicMock(return_value={"results": [], "reuse": True})
    monkeypatch.setattr(research, "external_search", search)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "fitness"}
    )
    assert search.call_count == 3
    assert result["observability"]["executed_search_requests"] == 0
    assert result["observability"]["stop_reason"] == "CACHED_QUERY_PLAN_EXHAUSTED"
