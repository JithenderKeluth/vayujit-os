from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from vayujit_api.intelligence.supplier_models import (
    SUPPLIER_ACCESS_MODES,
    SUPPLIER_EVIDENCE_KINDS,
    SUPPLIER_PRICE_KINDS,
    SUPPLIER_SOURCE_TYPES,
    SUPPLIER_TYPES,
    SUPPLIER_VERIFICATION_STATES,
)
from vayujit_api.intelligence.supplier_schemas import (
    SupplierManualCreate,
    SupplierSearchCreate,
    SupplierVerificationRequest,
)
from vayujit_api.intelligence.supplier_service import _fixtures, _score_dimensions


def test_supplier_fixture_provider_is_local_and_diverse() -> None:
    fixtures = _fixtures()
    assert len(fixtures) >= 5
    assert {item["source"] for item in fixtures} >= {
        "alibaba",
        "manufacturer_website",
        "offline_market",
        "trade_fair",
        "referral",
    }
    assert any(item["private_label"] for item in fixtures)
    assert any(item["price"] is None for item in fixtures)
    assert any(item["moq"] > 1000 for item in fixtures)
    assert any(item["verification"] == "unverified" for item in fixtures)


@pytest.mark.parametrize("source_type", SUPPLIER_SOURCE_TYPES)
def test_supplier_source_type_contract(source_type: str) -> None:
    assert source_type == source_type.lower()
    assert source_type.replace("_", "").isalnum()


@pytest.mark.parametrize("access_mode", SUPPLIER_ACCESS_MODES)
def test_supplier_access_mode_contract(access_mode: str) -> None:
    assert access_mode in {
        "api",
        "provider_connector",
        "approved_web_fetch",
        "manual_import",
        "manual_entry",
        "offline",
        "internal",
    }


@pytest.mark.parametrize("supplier_type", SUPPLIER_TYPES)
def test_supplier_type_contract(supplier_type: str) -> None:
    assert supplier_type == supplier_type.lower()


@pytest.mark.parametrize("state", SUPPLIER_VERIFICATION_STATES)
def test_supplier_verification_states_are_explicit(state: str) -> None:
    request = SupplierVerificationRequest(state=cast(Any, state))
    assert request.state == state


@pytest.mark.parametrize("kind", SUPPLIER_PRICE_KINDS)
def test_supplier_price_kinds_preserve_observation_semantics(kind: str) -> None:
    assert kind in {
        "observed_quote",
        "displayed_price",
        "estimated_range",
        "manual_quote",
        "unknown",
    }


@pytest.mark.parametrize("kind", SUPPLIER_EVIDENCE_KINDS)
def test_supplier_evidence_labels_are_bounded(kind: str) -> None:
    assert kind in {"observed", "manual", "self_reported", "verified", "assumed", "derived"}


@pytest.mark.parametrize(
    ("fixture_index", "requirements"),
    [
        (0, {"moq_max": 100, "lead_time_max_days": 30, "private_label": True}),
        (1, {"moq_max": 100, "lead_time_max_days": 30, "private_label": True}),
        (2, {"moq_max": 50, "lead_time_max_days": 30, "private_label": False}),
        (3, {"moq_max": 200, "lead_time_max_days": 45, "private_label": True}),
        (4, {"moq_max": 10, "lead_time_max_days": 15, "private_label": False}),
    ],
)
def test_supplier_score_is_explainable(fixture_index: int, requirements: dict[str, object]) -> None:
    dimensions, score, recommendation = _score_dimensions(_fixtures()[fixture_index], requirements)
    assert 0 <= score <= 100
    assert dimensions
    assert sum(item["weight"] for item in dimensions.values()) == 100
    assert recommendation in {
        "strong_match",
        "promising",
        "review_required",
        "blocked",
        "insufficient_evidence",
    }
    for value in dimensions.values():
        assert {"score", "weight", "reason"} <= set(value)


def test_supplier_manual_entry_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        SupplierManualCreate(
            display_name="Offline Co", country_code="IN", country="India", provenance=""
        )


def test_supplier_manual_entry_is_offline_ready() -> None:
    request = SupplierManualCreate(
        display_name="Local Fixture Supplier",
        country_code="IN",
        country="India",
        source_type="factory_visit",
        provenance="factory visit note",
    )
    assert request.source_type == "factory_visit"
    assert request.country_code == "IN"


def test_supplier_search_bounds_requirements() -> None:
    with pytest.raises(ValidationError):
        SupplierSearchCreate(requirements={str(index): index for index in range(41)})


def test_supplier_search_preserves_currency_and_requirements() -> None:
    request = SupplierSearchCreate(requirements={"target_unit_cost": 3.2, "currency": "USD"})
    assert request.requirements["currency"] == "USD"
