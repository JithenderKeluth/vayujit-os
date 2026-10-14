"""Focused PR-8B comparison, idempotency, stale, and HUMAN-shortlist coverage."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare
from test_pr7a_supplier_engagement import _engagement, _seed_current_proceed

from vayujit_api.audit.models import AuditEvent
from vayujit_api.intelligence.shortlisting_models import SupplierShortlistDecision
from vayujit_api.intelligence.supplier_comparison_models import SupplierComparisonSnapshot
from vayujit_api.intelligence.supplier_models import SupplierCommercialTerm, SupplierProduct

pytestmark = pytest.mark.integration
pytest_plugins = ["test_pr5b_landed_cost"]
TEST_DATABASE_URL = os.environ.get("VAYUJIT_TEST_DATABASE_URL")


def _set_term_current(term_id: str, value: bool) -> None:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        term = db.get(SupplierCommercialTerm, uuid.UUID(term_id))
        assert term is not None
        term.is_current = value
        db.commit()
    engine.dispose()


def _set_term_price(term_id: str, value: str) -> None:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        term = db.get(SupplierCommercialTerm, uuid.UUID(term_id))
        assert term is not None
        term.unit_price = Decimal(value)
        db.commit()
    engine.dispose()


def _supplier_and_contact(api: TestClient, name: str, domain: str) -> tuple[str, str]:
    supplier = _ok(
        api.post(
            "/api/v1/intelligence/suppliers/manual",
            json={
                "display_name": name,
                "supplier_type": "manufacturer",
                "country_code": "IN",
                "country": "India",
                "website": f"https://{domain}",
                "source_type": "manual_entry",
                "provenance": "DETERMINISTIC_TEST",
            },
            headers=ORIGIN,
        )
    )
    contact = _ok(
        api.post(
            f"/api/v1/intelligence/suppliers/{supplier['id']}/contacts",
            json={
                "name": f"{name} Contact",
                "role": "Sales",
                "business_email": f"sales@{domain}",
                "preferred_method": "email",
                "source": "DETERMINISTIC_TEST",
                "verification": "unverified",
            },
            headers=ORIGIN,
        )
    )
    return str(supplier["id"]), str(contact["id"])


def _reassessment(
    api: TestClient,
    opportunity_id: str,
    assessment_id: str,
    promotion_id: str,
    key: str,
    *,
    quantity: int = 500,
    include_freight: bool = True,
    selling_price: int = 250,
) -> dict[str, Any]:
    assumptions: list[dict[str, object]] = []
    if include_freight:
        assumptions.extend(
            [
                {
                    "key": "freight_cost",
                    "value": "2500",
                    "unit": "per_shipment",
                    "currency": "INR",
                    "reason": "Explicit deterministic scenario",
                },
                {
                    "key": "freight_currency",
                    "value": "INR",
                    "reason": "Explicit deterministic scenario",
                },
            ]
        )
    assumptions.extend(
        [
            {"key": "origin", "value": "IN", "reason": "Explicit deterministic scenario"},
            {
                "key": "destination",
                "value": "IN",
                "reason": "Explicit deterministic scenario",
            },
        ]
    )
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/commercial-reassessments"
    )
    return _ok(
        api.post(
            url,
            json={
                "idempotency_key": key,
                "promotion_id": promotion_id,
                "assumptions": assumptions,
                "landed_cost": {
                    "idempotency_key": f"{key}-landed",
                    "base_currency": "INR",
                    "target_quantity": str(quantity),
                    "quantity_unit": "unit",
                },
                "unit_economics": {
                    "idempotency_key": f"{key}-unit",
                    "selling_price": str(selling_price),
                    "selling_price_currency": "INR",
                    "selling_price_provenance": "DETERMINISTIC_TEST",
                    "quantity": str(quantity),
                    "selling_cost_components": [
                        {
                            "key": "selling_cost",
                            "basis": "PER_UNIT",
                            "amount": "25.10",
                            "currency": "INR",
                            "required": True,
                            "provenance": "DETERMINISTIC_TEST",
                            "marker": "DETERMINISTIC_TEST",
                            "reason": "Explicit deterministic scenario",
                        }
                    ],
                },
            },
            headers=ORIGIN,
        )
    )


def _promotion(
    api: TestClient,
    opportunity_id: str,
    supplier_id: str,
    contact_id: str,
    key: str,
    *,
    engagement_id: str | None = None,
    product_name: str = "Reusable kids lunch box",
    price: str = "INR 112.50",
    moq: int = 500,
) -> str:
    engagement = (
        {"id": engagement_id}
        if engagement_id is not None
        else _engagement(api, opportunity_id, supplier_id, contact_id, key)
    )
    response = _ok(
        api.post(
            "/api/v1/intelligence/supplier-responses",
            json={
                "supplier_id": supplier_id,
                "opportunity_id": opportunity_id,
                "engagement_id": engagement["id"],
                "channel": "EMAIL",
                "sender_identity": f"sales-{key}@example.test",
                "recipient_identity": "buyer@example.test",
                "provider_message_id": key,
                "raw_content": (
                    f"Product: {product_name}\n"
                    "SKU: KLB-500\n"
                    f"Price: {price} per unit\n"
                    f"MOQ: {moq} units\n"
                    "Lead time: 21 days"
                ),
                "trust_environment": "DETERMINISTIC_TEST",
                "evidence_environment": "DETERMINISTIC_TEST",
                "idempotency_key": f"{key}-response",
            },
            headers=ORIGIN,
        )
    )
    _ok(
        api.post(
            f"/api/v1/intelligence/supplier-responses/{response['id']}/review",
            json={
                "decision": "ACCEPT_EXTRACTION",
                "provenance": "HUMAN",
                "idempotency_key": f"{key}-review",
            },
            headers=ORIGIN,
        )
    )
    promoted = _ok(
        api.post(
            f"/api/v1/intelligence/supplier-responses/{response['id']}/promote",
            headers=ORIGIN,
        )
    )
    return str(promoted["promotion"]["id"])


def _comparison_fixture(
    api: TestClient,
    key: str,
    *,
    quantity_a: int = 500,
    quantity_b: int = 500,
    freight_a: bool = True,
    freight_b: bool = True,
    selling_price_a: int = 250,
    selling_price_b: int = 250,
    product_a_specs: dict[str, object] | None = None,
    product_b_specs: dict[str, object] | None = None,
    quote_b_price: str = "INR 112.50",
    quote_b_moq: int = 500,
) -> tuple[str, str, dict[str, Any], dict[str, Any], str]:
    opportunity_id, assessment_id = _prepare(api)
    supplier_a, contact_a = _supplier_and_contact(api, f"{key} Supplier A", f"{key}-a.example")
    supplier_b, contact_b = _supplier_and_contact(api, f"{key} Supplier B", f"{key}-b.example")
    _seed_current_proceed(opportunity_id, supplier_a)
    _seed_current_proceed(opportunity_id, supplier_b)
    promotion_a = _promotion(api, opportunity_id, supplier_a, contact_a, f"{key}-a-quote")
    promotion_b = _promotion(
        api,
        opportunity_id,
        supplier_b,
        contact_b,
        f"{key}-b-quote",
        price=quote_b_price,
        moq=quote_b_moq,
    )
    reassessment_a = _reassessment(
        api,
        opportunity_id,
        assessment_id,
        promotion_a,
        f"{key}-ra",
        quantity=quantity_a,
        include_freight=freight_a,
        selling_price=selling_price_a,
    )
    reassessment_b = _reassessment(
        api,
        opportunity_id,
        assessment_id,
        promotion_b,
        f"{key}-rb",
        quantity=quantity_b,
        include_freight=freight_b,
        selling_price=selling_price_b,
    )
    if product_a_specs is not None or product_b_specs is not None:
        assert TEST_DATABASE_URL
        engine = create_engine(TEST_DATABASE_URL)
        with Session(engine) as db:
            if product_a_specs is not None:
                product_a = db.get(
                    SupplierProduct, uuid.UUID(reassessment_a["supplier_product_id"])
                )
                assert product_a is not None
                product_a.specifications = product_a_specs
            if product_b_specs is not None:
                product_b = db.get(
                    SupplierProduct, uuid.UUID(reassessment_b["supplier_product_id"])
                )
                assert product_b is not None
                product_b.specifications = product_b_specs
            db.commit()
        engine.dispose()
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/supplier-comparisons"
    )
    return opportunity_id, assessment_id, reassessment_a, reassessment_b, url


def test_pr8b_comparison_reuses_pr4_human_shortlist_and_blocks_stale(client: TestClient) -> None:
    opportunity_id, assessment_id = _prepare(client)
    supplier_a, contact_a = _supplier_and_contact(client, "PR-8B Supplier A", "pr8b-a.example")
    supplier_b, contact_b = _supplier_and_contact(client, "PR-8B Supplier B", "pr8b-b.example")
    _seed_current_proceed(opportunity_id, supplier_a)
    _seed_current_proceed(opportunity_id, supplier_b)
    promotion_a = _promotion(client, opportunity_id, supplier_a, contact_a, "pr8b-a-quote")
    promotion_b = _promotion(client, opportunity_id, supplier_b, contact_b, "pr8b-b-quote")
    reassessment_a = _reassessment(client, opportunity_id, assessment_id, promotion_a, "pr8b-ra")
    reassessment_b = _reassessment(client, opportunity_id, assessment_id, promotion_b, "pr8b-rb")
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/supplier-comparisons"
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-comparison-one",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    assert comparison["status"] in {"COMPARABLE", "PARTIALLY_COMPARABLE", "NEEDS_EVIDENCE"}
    assert len(comparison["suppliers"]) == 2
    assert comparison["provenance"]["automatic_winner"] is None
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        snapshot = db.get(SupplierComparisonSnapshot, uuid.UUID(comparison["id"]))
        assert snapshot is not None
        snapshot.notes = "tamper attempt"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
    engine.dispose()
    assert comparison["shortlist_context_id"]
    assert comparison["shortlist_version_id"]
    replay = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-comparison-different-ui-key",
                "reassessment_ids": [reassessment_b["id"], reassessment_a["id"]],
            },
            headers=ORIGIN,
        )
    )
    assert replay["id"] == comparison["id"]
    assert replay["input_fingerprint"] == comparison["input_fingerprint"]
    canonical_id = comparison["canonical_supplier_ids"][0]
    shortlist_url = f"{url}/{comparison['id']}/shortlist"
    _set_term_price(reassessment_a["commercial_term_id"], "113.25")
    stale_quote = client.post(
        shortlist_url,
        json={
            "canonical_supplier_id": canonical_id,
            "decision": "KEEP_UNDER_REVIEW",
            "reason": "Human is retaining this supplier for evidence review.",
            "decision_key": "pr8b-stale-quote-review",
        },
        headers=ORIGIN,
    )
    assert stale_quote.status_code == 409
    _set_term_price(reassessment_a["commercial_term_id"], "112.50")
    _set_term_current(reassessment_a["commercial_term_id"], False)
    stale = client.post(
        shortlist_url,
        json={
            "canonical_supplier_id": canonical_id,
            "decision": "KEEP_UNDER_REVIEW",
            "reason": "Human is retaining this supplier for evidence review.",
            "decision_key": "pr8b-stale-review",
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    _set_term_current(reassessment_a["commercial_term_id"], True)
    decision = _ok(
        client.post(
            shortlist_url,
            json={
                "canonical_supplier_id": canonical_id,
                "decision": "KEEP_UNDER_REVIEW",
                "reason": "Human is retaining this supplier for evidence review.",
                "decision_key": "pr8b-human-review",
            },
            headers=ORIGIN,
        )
    )
    assert decision["human_provenance"] == "HUMAN"
    assert decision["comparison_id"] == comparison["id"]
    assert decision["decision"] == "KEEP_UNDER_REVIEW"
    replay_decision = _ok(
        client.post(
            shortlist_url,
            json={
                "canonical_supplier_id": canonical_id,
                "decision": "KEEP_UNDER_REVIEW",
                "reason": "Human is retaining this supplier for evidence review.",
                "decision_key": "pr8b-human-review",
            },
            headers=ORIGIN,
        )
    )
    assert replay_decision["id"] == decision["id"]
    assert replay_decision["idempotent_reuse"] is True


def test_pr8b_requires_two_distinct_suppliers_and_owner_scope(client: TestClient) -> None:
    opportunity_id, assessment_id = _prepare(client)
    response = client.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/supplier-comparisons",
        json={"idempotency_key": "pr8b-too-few", "reassessment_ids": []},
        headers=ORIGIN,
    )
    assert response.status_code == 422
    foreign = client.get(
        "/api/v1/intelligence/product-opportunities/00000000-0000-0000-0000-000000000001/assessments/00000000-0000-0000-0000-000000000002/supplier-comparisons",
        headers=ORIGIN,
    )
    assert foreign.status_code == 404


def test_pr8b_certifies_incomplete_supplier_without_zero_or_winner(client: TestClient) -> None:
    _, _, reassessment_a, reassessment_b, url = _comparison_fixture(
        client, "pr8b-incomplete", freight_b=False
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-incomplete-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    assert comparison["status"] == "NEEDS_EVIDENCE"
    assert len(comparison["suppliers"]) == 2
    incomplete = next(
        item for item in comparison["suppliers"] if item["reassessment_id"] == reassessment_b["id"]
    )
    assert incomplete["status"] == "BLOCKED"
    assert incomplete["metrics"]["landed_cost_per_unit"]["state"] == "UNKNOWN"
    assert comparison["provenance"]["automatic_winner"] is None
    landed = next(
        item for item in comparison["metrics"] if item["metric"] == "landed_cost_per_unit"
    )
    assert landed["delta"] is None
    assert landed["state"] in {"UNKNOWN", "NOT_DIRECTLY_COMPARABLE"}


def test_pr8b_certifies_quantity_mismatch_without_silent_normalization(client: TestClient) -> None:
    _, _, reassessment_a, reassessment_b, url = _comparison_fixture(
        client, "pr8b-quantity", quantity_b=1000, quote_b_moq=1000
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-quantity-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    rows = {item["reassessment_id"]: item for item in comparison["suppliers"]}
    assert Decimal(rows[reassessment_a["id"]]["metrics"]["order_quantity"]["value"]) == 500
    assert Decimal(rows[reassessment_b["id"]]["metrics"]["order_quantity"]["value"]) == 1000
    total = next(item for item in comparison["metrics"] if item["metric"] == "total_landed_cost")
    capital = next(item for item in comparison["metrics"] if item["metric"] == "capital_required")
    assert total["state"] == "NOT_DIRECTLY_COMPARABLE"
    assert capital["state"] == "NOT_DIRECTLY_COMPARABLE"
    assert total["delta"] is None and capital["delta"] is None
    assert comparison["provenance"]["automatic_winner"] is None


def test_pr8b_certifies_product_mismatch_as_not_comparable(client: TestClient) -> None:
    _, _, reassessment_a, reassessment_b, url = _comparison_fixture(
        client,
        "pr8b-product-mismatch",
        product_a_specs={
            "product_type": "reusable lunch box",
            "material": "food-grade plastic",
            "capacity": "800ml",
            "intended_use": "school lunch",
        },
        product_b_specs={
            "product_type": "stainless steel water bottle",
            "material": "steel",
            "capacity": "750ml",
            "intended_use": "hydration",
        },
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-product-mismatch-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    assert comparison["status"] == "NOT_COMPARABLE"
    assert len(comparison["suppliers"]) == 2
    assert all(item["delta"] is None for item in comparison["metrics"])
    assert all(item["state"] == "NOT_DIRECTLY_COMPARABLE" for item in comparison["metrics"])
    assert comparison["provenance"]["automatic_winner"] is None


def test_pr8b_certifies_contradictory_quote_as_unresolved(client: TestClient) -> None:
    opportunity_id, assessment_id = _prepare(client)
    supplier_a, contact_a = _supplier_and_contact(
        client, "PR-8B Contradiction A", "pr8b-ca.example"
    )
    supplier_b, contact_b = _supplier_and_contact(
        client, "PR-8B Contradiction B", "pr8b-cb.example"
    )
    _seed_current_proceed(opportunity_id, supplier_a)
    _seed_current_proceed(opportunity_id, supplier_b)
    promotion_a = _promotion(client, opportunity_id, supplier_a, contact_a, "pr8b-contradiction-a")
    engagement_b = _engagement(
        client,
        opportunity_id,
        supplier_b,
        contact_b,
        "pr8b-contradiction-b-engagement",
    )
    _promotion(
        client,
        opportunity_id,
        supplier_b,
        contact_b,
        "pr8b-contradiction-b-v1",
        engagement_id=engagement_b["id"],
        moq=500,
    )
    promotion_b = _promotion(
        client,
        opportunity_id,
        supplier_b,
        contact_b,
        "pr8b-contradiction-b-v2",
        engagement_id=engagement_b["id"],
        moq=1000,
    )
    reassessment_a = _reassessment(
        client, opportunity_id, assessment_id, promotion_a, "pr8b-contradiction-ra"
    )
    reassessment_b = _reassessment(
        client, opportunity_id, assessment_id, promotion_b, "pr8b-contradiction-rb"
    )
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/supplier-comparisons"
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-contradiction-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    contradiction = next(
        item
        for item in comparison["contradictions"]
        if any(entry["field"] == "moq" for entry in item["items"])
    )
    assert contradiction["canonical_supplier_id"] in comparison["canonical_supplier_ids"]
    assert any(item["field"] == "moq" for item in contradiction["items"])
    supplier_b_row = next(
        item for item in comparison["suppliers"] if item["reassessment_id"] == reassessment_b["id"]
    )
    assert supplier_b_row["contradictions"]
    assert comparison["provenance"]["automatic_winner"] is None


def test_pr8b_certifies_capital_shortfall_without_auto_exclusion(client: TestClient) -> None:
    _, _, reassessment_a, reassessment_b, url = _comparison_fixture(
        client, "pr8b-capital-shortfall", quantity_b=50000
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-capital-shortfall-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    rows = {item["reassessment_id"]: item for item in comparison["suppliers"]}
    capital = rows[reassessment_b["id"]]["metrics"]["capital_required"]
    headroom = rows[reassessment_b["id"]]["metrics"]["capital_headroom"]
    assert Decimal(str(capital["value"])) > Decimal("300000")
    assert Decimal(str(headroom["value"])) < 0
    assert comparison["provenance"]["automatic_winner"] is None
    assert len(comparison["suppliers"]) == 2


def test_pr8b_certifies_negative_contribution_without_auto_rejection(client: TestClient) -> None:
    _, _, reassessment_a, reassessment_b, url = _comparison_fixture(
        client, "pr8b-negative-contribution", selling_price_b=50
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-negative-contribution-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    rows = {item["reassessment_id"]: item for item in comparison["suppliers"]}
    contribution = rows[reassessment_b["id"]]["metrics"]["contribution_per_unit"]
    assert Decimal(str(contribution["value"])) < 0
    assert rows[reassessment_b["id"]]["status"] == "READY"
    assert comparison["provenance"]["automatic_winner"] is None


def test_pr8b_rejects_human_impersonation_and_records_authenticated_actor(
    client: TestClient,
) -> None:
    _, _, reassessment_a, reassessment_b, url = _comparison_fixture(client, "pr8b-human-boundary")
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-human-boundary-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    canonical_id = comparison["canonical_supplier_ids"][0]
    shortlist_url = f"{url}/{comparison['id']}/shortlist"
    base = {
        "canonical_supplier_id": canonical_id,
        "decision": "KEEP_UNDER_REVIEW",
        "reason": "Explicit HUMAN review boundary certification.",
        "decision_key": "pr8b-human-boundary-decision",
    }
    for actor in ("SYSTEM", "AI", "BUSINESS_AGENT"):
        response = client.post(
            shortlist_url,
            json={**base, "provenance": actor},
            headers=ORIGIN,
        )
        assert response.status_code == 422

    decision = _ok(client.post(shortlist_url, json=base, headers=ORIGIN))
    assert decision["human_provenance"] == "HUMAN"
    assert decision["comparison_id"] == comparison["id"]
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        row = db.get(SupplierShortlistDecision, uuid.UUID(decision["id"]))
        assert row is not None
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "intelligence.supplier_shortlist_decision_created",
                    AuditEvent.entity_id == row.id,
                )
            )
        )
        assert len(events) == 1
        assert events[0].actor_id == row.owner_id
        assert events[0].metadata_json["provenance"] == "HUMAN"
    engine.dispose()

    client.cookies.clear()
    unauthenticated = client.post(shortlist_url, json={**base, "decision_key": "pr8b-unauth"})
    # The app's auth middleware rejects a missing session as 403 (rather than
    # 401); either is an unauthenticated response and must not be accepted.
    assert unauthenticated.status_code in {401, 403}


def test_pr8b_fresh_process_reconstructs_comparison_and_human_decision(
    client: TestClient,
) -> None:
    """Gate 72: the persisted canonical state survives an app-process restart."""

    opportunity_id, assessment_id, reassessment_a, reassessment_b, url = _comparison_fixture(
        client, "pr8b-fresh-process"
    )
    comparison = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8b-fresh-process-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    shortlist_url = f"{url}/{comparison['id']}/shortlist"
    decision = _ok(
        client.post(
            shortlist_url,
            json={
                "canonical_supplier_id": comparison["canonical_supplier_ids"][0],
                "decision": "KEEP_UNDER_REVIEW",
                "reason": "Fresh-process reconstruction certification.",
                "decision_key": "pr8b-fresh-process-decision",
            },
            headers=ORIGIN,
        )
    )
    live = _ok(client.get(f"{url}/{comparison['id']}", headers=ORIGIN))
    for field in (
        "id",
        "opportunity_id",
        "assessment_id",
        "input_fingerprint",
        "canonical_supplier_ids",
        "supplier_product_ids",
        "reassessment_ids",
        "quote_versions",
        "calculation_versions",
        "metrics",
        "unknowns",
        "blockers",
        "contradictions",
        "lineage",
        "shortlist_context_id",
        "shortlist_version_id",
    ):
        assert live[field] == comparison[field], field
    assert live["human_decisions"][0]["id"] == decision["id"]
    assert live["human_decisions"][0]["decision"] == "KEEP_UNDER_REVIEW"

    assert TEST_DATABASE_URL
    child_env = os.environ.copy()
    child_env.update(
        {
            "PR8B_FRESH_URL": f"{url}/{comparison['id']}",
            "PR8B_FRESH_COMPARISON_ID": comparison["id"],
            "PR8B_FRESH_FINGERPRINT": comparison["input_fingerprint"],
            "PR8B_FRESH_DECISION_ID": decision["id"],
        }
    )
    child_script = r"""
import os
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import get_session
from vayujit_api.main import create_app

origin = {"Origin": "http://127.0.0.1:4200"}
engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
factory = sessionmaker(bind=engine, expire_on_commit=False)

def test_session() -> Generator[Session, None, None]:
    with factory() as db:
        yield db

app = create_app()
app.dependency_overrides[get_session] = test_session
with TestClient(app) as api:
    login = api.post(
        "/api/v1/auth/login",
        json={
            "email": "pr5b-owner@example.com",
            "password": "correct horse battery staple",
        },
        headers=origin,
    )
    assert login.status_code == 200, login.text
    response = api.get(os.environ["PR8B_FRESH_URL"], headers=origin)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == os.environ["PR8B_FRESH_COMPARISON_ID"]
    assert payload["input_fingerprint"] == os.environ["PR8B_FRESH_FINGERPRINT"]
    assert payload["human_decisions"][0]["id"] == os.environ["PR8B_FRESH_DECISION_ID"]
    assert payload["canonical_supplier_ids"]
    assert payload["supplier_product_ids"]
    assert payload["reassessment_ids"]
    assert payload["quote_versions"]
    assert payload["calculation_versions"]
    assert payload["lineage"]
    assert payload["shortlist_context_id"]
    assert payload["shortlist_version_id"]
engine.dispose()
"""
    completed = subprocess.run(
        [sys.executable, "-c", child_script],
        cwd=os.getcwd(),
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        "fresh-process reconstruction failed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
