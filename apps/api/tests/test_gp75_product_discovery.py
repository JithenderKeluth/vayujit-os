"""Focused GP-7.5 deterministic product discovery regressions."""

from types import SimpleNamespace

from vayujit_api.intelligence.product_discovery import discover_local_product_candidates
from vayujit_api.intelligence.product_opportunity_scoring_router import (
    _candidate_state,
    _meaningful_opportunity,
)


def test_local_discovery_returns_distinct_realistic_product_identities() -> None:
    candidates = discover_local_product_candidates(
        "Find lightweight non-fragile products for Amazon India.",
        {"marketplace": "AMAZON_IN", "country_region": "IN"},
    )

    assert len(candidates) == 5
    assert len({candidate["fingerprint"] for candidate in candidates}) == 5
    assert all(
        candidate["name"] != "Business Agent Product Opportunity" for candidate in candidates
    )
    for candidate in candidates:
        profile = candidate["profile"]
        assert profile["candidate_source"] == "LOCAL_DETERMINISTIC_RESEARCH_FIXTURE"
        assert profile["normalized_product_concept"]
        assert profile["goal_fit"]
        assert profile["image"]["available"] is False
        assert profile["price_evidence"]["status"] == "NOT_AVAILABLE"
        assert profile["customer_evidence"]["status"] == "NOT_AVAILABLE"
        assert profile["trend_evidence"]["status"] == "NOT_AVAILABLE"
        assert profile["candidate_readiness"] == "NEEDS_MORE_RESEARCH"


def test_legacy_generic_opportunity_cannot_advance_journey_or_comparison() -> None:
    generic = SimpleNamespace(
        name="Business Agent Product Opportunity",
        category="",
        description="Deterministic opportunity generated for owner review.",
        product_concept="Candidate product evaluation",
        intelligence_profile={},
    )
    meaningful = SimpleNamespace(
        name="Insulated Lunch Container",
        category="Home & Kitchen",
        description="A reusable insulated food container.",
        product_concept="Reusable insulated food container",
        intelligence_profile={"normalized_product_concept": "reusable insulated food container"},
    )

    assert _meaningful_opportunity(generic) is False
    assert _candidate_state(generic, None) == "INSUFFICIENT_EVIDENCE"
    assert _meaningful_opportunity(meaningful) is True
    assert _candidate_state(meaningful, None) == "NEEDS_MORE_RESEARCH"
