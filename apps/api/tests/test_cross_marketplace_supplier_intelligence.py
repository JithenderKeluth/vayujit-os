# ruff: noqa: E501
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from vayujit_api.intelligence.cross_marketplace_service import (
    _commercial,
    _confidence,
    _freshness,
    _match_state,
    _tokens,
)
from vayujit_api.intelligence.supplier_models import Supplier


def _supplier(name: str, *, domain: str | None = None, country: str = "IN") -> Supplier:
    row = Supplier(
        id=uuid.uuid4(),
        display_name=name,
        country_code=country,
        normalized_domain=domain,
        normalized_identity=name.casefold(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return row


def test_identity_matching_is_provider_independent_and_possible_matches_are_review_only() -> None:
    first = _supplier("Acme Home Goods", domain="acme.example")
    same_domain = _supplier("Acme Home Goods Pvt Ltd", domain="acme.example")
    similar = _supplier("Acme Home Goods Trading", country="IN")
    unrelated = _supplier("Different Manufacturing", country="CN")
    assert _match_state(first, same_domain) == ("MATCH", "same normalized website domain")
    assert _match_state(first, similar)[0] == "POSSIBLE_MATCH"
    assert _match_state(first, unrelated)[0] == "NO_MATCH"
    assert "acme" in _tokens(first.display_name)


def test_commercial_consolidation_preserves_currency_and_disagreement() -> None:
    claims = [
        {
            "source_supplier_id": "a",
            "price": 10,
            "currency": "USD",
            "moq": 50,
            "unit": "units",
            "lead_time_days": 10,
            "freshness": "fresh",
            "observed_at": None,
            "availability": "AVAILABLE",
        },
        {
            "source_supplier_id": "b",
            "price": 900,
            "currency": "INR",
            "moq": 100,
            "unit": "units",
            "lead_time_days": 20,
            "freshness": "fresh",
            "observed_at": None,
            "availability": "LIMITED",
        },
    ]
    value = _commercial(claims)
    assert value["currency_safety"]["status"] == "NOT_DIRECTLY_COMPARABLE"
    assert value["price"]["minimum"] is None
    assert value["moq"]["agreement"] == "CONFLICTS"
    assert value["availability"]["state"] == "CONFLICTING"
    assert len(value["price"]["source_lineage"]) == 2


def test_confidence_requires_diversity_and_explains_dimensions() -> None:
    sources = [
        {"source_type": "indiamart", "freshness": "fresh"},
        {"source_type": "alibaba", "freshness": "fresh"},
        {"source_type": "tradeindia", "freshness": "stale"},
    ]
    claims = [{"price": 10, "moq": 10, "lead_time_days": 10}]
    value = _confidence(sources, claims, {"dimensions": []}, [_supplier("Verified")])
    assert value["score"] < 100
    assert {item["dimension"] for item in value["dimensions"]} >= {
        "verification",
        "freshness",
        "source_diversity",
        "completeness",
        "contradictions",
    }


def test_freshness_is_bounded_and_deterministic() -> None:
    now = datetime.now(UTC)
    assert _freshness(now) == "fresh"
    assert _freshness(now - timedelta(days=31)) == "aging"
    assert _freshness(now - timedelta(days=91)) == "stale"
    assert _freshness(None) == "unknown"
