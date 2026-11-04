"""Offline query planning and final eligibility regressions; no database or providers."""

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
from vayujit_api.intelligence.product_discovery import discover_local_product_candidates
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("home and kitchen organization", ["Foldable Wardrobe Organizer"]),
        ("Home & Kitchen / Storage & Organization", ["Foldable Wardrobe Organizer"]),
        ("food storage", ["Insulated Lunch Container", "Reusable Food Storage Set"]),
        ("travel organization", ["Travel Toiletry Organizer"]),
        ("kids organization", []),
        ("and", []),
    ],
)
def test_hypotheses_require_all_explicit_category_qualifiers(
    category: str, expected: list[str]
) -> None:
    candidates = discover_local_product_candidates("", {"category": category})
    assert [row["name"] for row in candidates] == expected


def test_unknown_category_uses_scope_not_a_partially_matching_fixture() -> None:
    hypotheses = research._live_hypotheses("", {"category": "kids organization"})
    assert [row["product_concept"] for row in hypotheses] == ["kids organization"]
    assert hypotheses[0]["profile"]["candidate_provenance"]["authoritative"] is False


@pytest.mark.parametrize("category", ["", "Home & Kitchen"])
def test_plan_searches_every_hypothesis_before_refinement(category: str) -> None:
    hypotheses = research._live_hypotheses("", {"category": category})
    plan = research._live_product_query_plan(hypotheses, category)
    assert len(plan) == 9
    assert [row[0]["name"] for row in plan[:3]] == [row["name"] for row in hypotheses]
    assert [row[2] for row in plan[:3]] == ["PRIMARY_PRODUCT_QUERY"] * 3
    assert [row[2] for row in plan[3:6]] == ["REFINEMENT_AFTER_NO_PRODUCT_EVIDENCE"] * 3
    assert len({row[1] for row in plan}) == 9
    if category:
        assert all(category in row[1] for row in plan)


def setup_discovery(monkeypatch: pytest.MonkeyPatch, budget: int = 3) -> tuple[MagicMock, User]:
    settings = Settings().model_copy(
        update={
            "intelligence_external_provider_mode": "LIVE_READ_ONLY",
            "intelligence_product_search_max_requests": budget,
        }
    )
    monkeypatch.setattr(research, "get_settings", lambda: settings)
    monkeypatch.setattr(research, "approved_source_profiles", lambda *_: {})
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    monkeypatch.setattr(
        research, "approved_fetch", MagicMock(side_effect=AssertionError("Unexpected fetch"))
    )
    return db, User(id=uuid.uuid4())


@pytest.mark.parametrize("budget", [1, 2, 3, 5, 12])
def test_round_robin_keeps_the_existing_search_bound(
    monkeypatch: pytest.MonkeyPatch, budget: int
) -> None:
    db, owner = setup_discovery(monkeypatch, budget)
    search = MagicMock(return_value={"results": []})
    monkeypatch.setattr(research, "external_search", search)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "Home & Kitchen"}
    )
    assert search.call_count == min(budget, 9)
    queries = result["queries"]
    assert all(row["reason"] == "PRIMARY_PRODUCT_QUERY" for row in queries[: min(budget, 3)])
    assert len({row["hypothesis"] for row in queries[: min(budget, 3)]}) == min(budget, 3)
    assert result["candidate_ids"] == []
    db.add.assert_not_called()


@pytest.mark.parametrize("reused", [False, True])
@pytest.mark.parametrize("compatible", [False, True])
def test_final_category_eligibility_is_authoritative_even_for_reused_product_details(
    monkeypatch: pytest.MonkeyPatch, reused: bool, compatible: bool
) -> None:
    db, owner = setup_discovery(monkeypatch)
    url = "https://example.org/product/synthetic-fixture"
    row = SimpleNamespace(
        id=uuid.uuid4(),
        url=url,
        canonical_url=url,
        domain="example.org",
        title="",
        snippet="",
        provider="synthetic-fixture",
    )
    monkeypatch.setattr(research, "external_search", lambda *_: {"results": [row], "reuse": reused})
    fetched = {
        "status": "COMPLETED",
        "reuse": reused,
        "extracted": {
            "product_metadata": {
                "json_ld": {
                    "@type": "Product",
                    "name": "Synthetic Wardrobe Organizer" if compatible else "Synthetic Food Box",
                    "category": "Home & Kitchen",
                    "description": (
                        "Household storage organization" if compatible else "Food storage"
                    ),
                    "brand": "Synthetic Test Brand",
                }
            }
        },
    }
    monkeypatch.setattr(research, "approved_fetch", lambda *_: deepcopy(fetched))

    def assign_id(candidate: ProductOpportunity) -> None:
        candidate.id = uuid.uuid4()

    db.add.side_effect = assign_id
    result = research.run_live_product_discovery(
        db,
        owner,
        raw_goal="Find products in the home and kitchen organization category.",
        structured_goal={"category": "Home & Kitchen"},
    )
    assert result["fetches"][0]["status"] == "COMPLETED"
    assert result["fetches"][0]["page_type"] == "PRODUCT_DETAIL"
    assert result["fetches"][0]["eligible"] is compatible
    assert result["observability"]["successful_fetches"] == 1
    if compatible:
        assert len(result["candidate_ids"]) == 1
        candidate = db.add.call_args.args[0]
        assert candidate.intelligence_profile["category_constraint"]["matched"]
    else:
        db.add.assert_not_called()
        assert result["candidate_ids"] == []
        assert result["fetches"][0]["reason_code"] == "CATEGORY_CONSTRAINT_NOT_ESTABLISHED"
        assert "not established" in result["rejected_results"][0]["reason"]


def test_cached_projection_is_actionable_without_mutating_history() -> None:
    original = {
        "details": {
            "fetches": [],
            "search_budget": {"stop_reason": "CACHED_QUERY_PLAN_EXHAUSTED"},
        }
    }
    saved = deepcopy(original)
    result = research.discovery_review_projection(original)
    assert original == saved
    assert "No new provider search was made" in result["details"]["review_guidance"]
    assert "may still be reused" in result["details"]["review_guidance"]


def test_all_cached_run_reports_no_product_without_forcing_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner = setup_discovery(monkeypatch)
    search = MagicMock(return_value={"results": [], "reuse": True})
    monkeypatch.setattr(research, "external_search", search)
    result = research.run_live_product_discovery(
        db, owner, raw_goal="", structured_goal={"category": "Home & Kitchen"}
    )
    assert result["status"] == "NO_USEFUL_PRODUCT_CANDIDATES"
    assert search.call_count == 3
    assert result["observability"]["executed_search_requests"] == 0
    assert "No new provider search was made" in result["review_guidance"]
    assert result["candidate_ids"] == []


@pytest.mark.parametrize("status", [403, 429])
def test_approval_and_quota_still_stop_before_remaining_hypotheses(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    db, owner = setup_discovery(monkeypatch)
    search = MagicMock()
    if status == 429:
        search.side_effect = HTTPException(429, "Search quota exceeded.")
    else:
        url = "https://example.org/product/fixture"
        search.return_value = {
            "results": [
                SimpleNamespace(
                    id=uuid.uuid4(), url=url, canonical_url=url, domain="example.org", title=""
                )
            ]
        }
        monkeypatch.setattr(
            research,
            "approved_fetch",
            MagicMock(
                side_effect=HTTPException(
                    403, "External source approval is required before fetching."
                )
            ),
        )
    monkeypatch.setattr(research, "external_search", search)
    result = research.run_live_product_discovery(db, owner, raw_goal="", structured_goal={})
    assert search.call_count == 1
    assert result["status"] == (
        "SOURCE_APPROVAL_REQUIRED" if status == 403 else "PROVIDER_QUOTA_EXHAUSTED"
    )
    db.add.assert_not_called()
