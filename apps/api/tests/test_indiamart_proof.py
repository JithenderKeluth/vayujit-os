from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_planner import RECOVERY_ACTIONS, RECOVERY_FAILURE_CODES
from vayujit_api.intelligence.autonomous_service import _materiality
from vayujit_api.intelligence.external_intelligence import (
    confidence_handoff,
    source_diversity_evaluation,
    verify_external_evidence,
)
from vayujit_api.intelligence.indiamart import IndiaMartListing
from vayujit_api.intelligence.indiamart_models import IndiaMartDiscoveryResult
from vayujit_api.intelligence.indiamart_service import (
    _append_observations,
    _identity_match,
    _offering_match,
    _product_match,
)
from vayujit_api.intelligence.supplier_models import Supplier, SupplierProduct
from vayujit_api.intelligence.website_models import ManufacturerCandidate, SupplierWebsiteCandidate

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _supplier(owner_id: uuid.UUID, name: str) -> Supplier:
    stamp = datetime.now(UTC)
    return Supplier(
        owner_id=owner_id,
        display_name=name,
        legal_name=name,
        supplier_type="manufacturer",
        country_code="IN",
        country="India",
        region="Maharashtra",
        city="Pune",
        address="",
        website=f"https://{name.casefold().replace(' ', '')}.example",
        normalized_domain=f"{name.casefold().replace(' ', '')}.example",
        business_identifier=None,
        source_identity="proof",
        normalized_identity=name.casefold().strip(),
        is_offline=False,
        verification_state="unverified",
        communication_status="not_contacted",
        created_at=stamp,
        updated_at=stamp,
    )


def test_persisted_identity_and_match_matrices_are_non_merging(client: TestClient) -> None:
    context = setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        exact = _supplier(owner.id, "Acme Exact Industries")
        ambiguous = _supplier(owner.id, "Acme Global Trading")
        unrelated = _supplier(owner.id, "Unrelated Metals")
        db.add_all([exact, ambiguous, unrelated])
        db.flush()
        manufacturer = ManufacturerCandidate(
            owner_id=owner.id,
            name="Acme Manufacturer Group",
            normalized_name="acme manufacturer group",
            website="https://acme-manufacturer.example",
            canonical_domain="acme-manufacturer.example",
            country="India",
            region="Maharashtra",
            logical_identity="proof:manufacturer:acme",
        )
        ambiguous_manufacturer = ManufacturerCandidate(
            owner_id=owner.id,
            name="Acme Global Trading",
            normalized_name="acme global trading",
            website="https://acme-global.example",
            canonical_domain="acme-global.example",
            country="India",
            region="Gujarat",
            logical_identity="proof:manufacturer:global",
        )
        website = SupplierWebsiteCandidate(
            owner_id=owner.id,
            supplier_id=exact.id,
            manufacturer_candidate_id=manufacturer.id,
            domain="acme-exact.example",
            identity_state="MATCH",
            match_state="MATCH",
            logical_identity="proof:website:acme",
        )
        db.add_all([manufacturer, ambiguous_manufacturer, website])
        db.flush()
        offering = SupplierProduct(
            owner_id=owner.id,
            supplier_id=exact.id,
            source_reference="proof:offering:exact",
            title="Trail Bottle",
            category="Outdoors",
            specifications={},
            observed_price=10,
            currency="USD",
            price_kind="displayed_price",
            moq=10,
            moq_unit="units",
            sample_available=True,
            sample_moq=1,
            sample_lead_days=2,
            production_lead_days=7,
            dispatch_lead_days=2,
            shipping_lead_days=5,
            private_label=False,
            customization=False,
            packaging=None,
            evidence_ids=[],
            observed_at=datetime.now(UTC),
            freshness_status="fresh",
            created_at=datetime.now(UTC),
        )
        db.add(offering)
        db.commit()

        identity_cases = {
            "exact_supplier": ("Acme Exact Industries", "MATCH"),
            "exact_website_link": ("Acme Exact Industries", "MATCH"),
            "exact_manufacturer": ("Acme Manufacturer Group", "MATCH"),
            "ambiguous": ("Acme Global Trading Services", "POSSIBLE_MATCH"),
            "unrelated": ("Ceramic House", "NO_MATCH"),
            "insufficient": ("", "UNKNOWN"),
        }
        assert {
            key: _identity_match(db, owner, value) for key, (value, _) in identity_cases.items()
        } == {key: expected for key, (_, expected) in identity_cases.items()}

        product_id = uuid.UUID(context["product"]["id"])
        product_cases = (
            (
                "MATCH",
                _product_match(
                    db, owner, product_id, "insulated bottle", "Insulated bottle supplier"
                ),
            ),
            (
                "POSSIBLE_MATCH",
                _product_match(db, owner, product_id, "outdoors accessories", "Accessories"),
            ),
            ("NO_MATCH", _product_match(db, owner, product_id, "ceramic mug", "Other item")),
            ("UNKNOWN", _product_match(db, owner, None, "insulated bottle", "Insulated bottle")),
        )
        assert [actual for _, actual in product_cases] == [
            expected for expected, _ in product_cases
        ]

        offering_cases = (
            ("MATCH", _offering_match(db, owner, exact.id, "Trail Bottle")),
            ("POSSIBLE_MATCH", _offering_match(db, owner, exact.id, "Trail Bottle Components")),
            ("NO_MATCH", _offering_match(db, owner, exact.id, "Ceramic Mug")),
            ("UNKNOWN", _offering_match(db, owner, unrelated.id, "Trail Bottle")),
        )
        assert [actual for _, actual in offering_cases] == [
            expected for expected, _ in offering_cases
        ]
        assert _identity_match(db, owner, "Acme Global Trading Services") != "MATCH"


def test_observation_versions_replay_without_duplicate_rows(client: TestClient) -> None:
    context = setup_context(client)
    discovery = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "proof observation", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert discovery.status_code == 200, discovery.text
    result_id = uuid.UUID(discovery.json()["results"][0]["id"])
    listing = IndiaMartListing(
        provider_result_id="proof-observation",
        supplier_name="Proof Supplier",
        listing_name="Proof Listing",
        source_url="https://www.indiamart.com/proof",
        location="Pune",
        category="Outdoors",
        price=100,
        currency="INR",
        moq=10,
        moq_unit="units",
        lead_time="10 days",
        availability="in_stock",
        verification_claim="provider_claimed",
        metadata={},
    )
    history: list[dict[str, object]] = []
    first_history: list[dict[str, object]] = []
    before_replay = 0
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        row = db.get(IndiaMartDiscoveryResult, result_id)
        assert row is not None
        row.metadata_json = {}
        stamp = datetime.now(UTC)
        _append_observations(row, listing, stamp)
        db.commit()
        first = dict(row.metadata_json)
        first_value = first.get("observation_history")
        assert isinstance(first_value, list)
        first_history = first_value
        changed = IndiaMartListing(
            **{
                **listing.__dict__,
                "price": 125,
                "moq": 20,
                "lead_time": "14 days",
                "availability": "limited",
                "verification_claim": "updated_claim",
            }
        )
        _append_observations(row, changed, stamp)
        db.commit()
        replay_value = row.metadata_json.get("observation_history")
        assert isinstance(replay_value, list)
        before_replay = len(replay_value)
        _append_observations(row, changed, stamp)
        db.commit()
        history_value = row.metadata_json.get("observation_history")
        assert isinstance(history_value, list)
        history = history_value
    assert len(history) == before_replay == 10
    for field in ("PRICE", "MOQ", "LEAD_TIME", "VERIFICATION_CLAIM", "AVAILABILITY"):
        values = [item["value"] for item in history if item["field"] == field]
        assert len(values) == 2
        assert (
            values[0]
            == first_history[[item["field"] for item in first_history].index(field)]["value"]
        )
        attribute = "verification_claim" if field == "VERIFICATION_CLAIM" else field.lower()
        assert values[1] == getattr(changed, attribute)


def test_evidence_rejection_materiality_confidence_and_diversity_are_fail_closed() -> None:
    base = {
        "owner_id": "owner",
        "source_profile": "profile",
        "fetch_id": "fetch",
        "search_result_id": "result",
        "requested_url": "https://indiamart.example/item",
        "final_url": "https://indiamart.example/item",
        "content_hash": "hash",
        "correlation_id": "corr",
        "provider": "INDIAMART",
        "content": "normalized claim",
        "freshness_status": "FRESH",
    }
    for status in ("UNVERIFIED", "REJECTED", "STALE", "EXPIRED"):
        freshness = status if status in {"STALE", "EXPIRED"} else "FRESH"
        candidate = {**base, "verification_status": status, "freshness_status": freshness}
        result = verify_external_evidence(candidate, expected_owner_id="owner")
        if status in {"STALE", "EXPIRED"}:
            assert result["verification_state"] == "REJECTED"
        else:
            assert result["verification_state"] == "SUPPORTED"
    assert _materiality("price", {"value": 100}, {"value": 105})[0] == "NON_MATERIAL"
    assert _materiality("price", {"value": 100}, {"value": 125})[0] == "MATERIAL"
    assert (
        _materiality("supplier_verification", {"value": "verified"}, {"value": "conflict"})[0]
        == "REQUIRES_REVIEW"
    )
    india_only = [
        {
            "url": "https://www.indiamart.com/a",
            "provider": "INDIAMART",
            "content_hash": "same",
            "verification_status": "SUPPORTED",
        },
        {
            "url": "https://www.indiamart.com/b",
            "provider": "INDIAMART",
            "content_hash": "same",
            "verification_status": "SUPPORTED",
        },
    ]
    before = source_diversity_evaluation(india_only)
    after = source_diversity_evaluation(
        india_only
        + [
            {
                "url": "https://supplier.example/a",
                "provider": "WEBSITE",
                "content_hash": "website",
                "verification_status": "VERIFIED",
            },
            {
                "url": "offline://manual/1",
                "provider": "MANUAL",
                "content_hash": "manual",
                "verification_status": "SUPPORTED",
            },
        ]
    )
    assert before["provider_count"] == 1
    assert before["domain_count"] == 1
    assert after["provider_count"] == 3
    confidence = confidence_handoff(india_only)
    assert float(cast(float, confidence["overall_confidence"])) < 0.85


def test_recovery_catalog_and_idempotency_are_explicit(client: TestClient) -> None:
    setup_context(client)
    mission = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "SUPPLIER_DISCOVERY",
            "goal": "IndiaMART proof recovery",
            "market": "IN",
            "category": "outdoors",
            "provider_mode": "LOCAL_DETERMINISTIC",
            "idempotency_key": "indiamart-proof-recovery",
        },
        headers=ORIGIN,
    )
    assert mission.status_code == 201, mission.text
    mission_id = mission.json()["id"]
    catalog = client.get("/api/v1/intelligence/autonomous/recovery/catalog", headers=ORIGIN)
    assert catalog.status_code == 200
    assert set(catalog.json()["failure_codes"]) == set(RECOVERY_FAILURE_CODES)
    assert set(catalog.json()["actions"]) == set(RECOVERY_ACTIONS)
    payload = {"failure_code": "timeout", "action": "retry", "idempotency_key": "proof-retry-1"}
    first = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    second = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["idempotent_reuse"] is False
    assert second.json()["idempotent_reuse"] is True
