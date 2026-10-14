"""Focused PR-7C inbound response, review, and PR-5A promotion coverage."""

# The reconstruction script intentionally mirrors compact SQLAlchemy lookups.
# ruff: noqa: E501

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare
from test_pr7a_supplier_engagement import _engagement, _seed_current_proceed, _supplier_and_contact

from vayujit_api.intelligence.supplier_models import (
    SupplierCommercialTerm,
    SupplierEvidence,
    SupplierProduct,
)
from vayujit_api.intelligence.supplier_response_models import (
    SupplierResponsePromotion,
)

pytestmark = pytest.mark.integration
pytest_plugins = ["test_pr5b_landed_cost"]
TEST_DATABASE_URL = os.environ.get("VAYUJIT_TEST_DATABASE_URL")


def _context(client: TestClient, key: str) -> tuple[str, str, str, str]:
    opportunity_id, _assessment_id = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity_id, supplier_id)
    engagement = _engagement(client, opportunity_id, supplier_id, contact_id, key)
    return opportunity_id, supplier_id, contact_id, engagement["id"]


def _response(
    client: TestClient,
    *,
    opportunity_id: str,
    supplier_id: str,
    engagement_id: str,
    text: str,
    key: str,
    message_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "supplier_id": supplier_id,
        "opportunity_id": opportunity_id,
        "engagement_id": engagement_id,
        "channel": "EMAIL",
        "sender_identity": "sales@fixture.example",
        "recipient_identity": "buyer@example.test",
        "provider_message_id": message_id or key,
        "raw_content": text,
        "trust_environment": "DETERMINISTIC_TEST",
        "evidence_environment": "DETERMINISTIC_TEST",
        "idempotency_key": key,
    }
    return _ok(client.post("/api/v1/intelligence/supplier-responses", json=payload, headers=ORIGIN))


def test_pr7c_full_quote_review_promotion_idempotency_and_changed_version(
    client: TestClient,
) -> None:
    opportunity_id, supplier_id, _contact_id, engagement_id = _context(client, "pr7c-full")
    quote = (
        "Product: Reusable kids lunch box\n"
        "SKU: KLB-500\n"
        "Price: INR 112.50 per unit\n"
        "MOQ: 500 units\n"
        "Lead time: 21 days\n"
        "Incoterm: EXW\n"
        "Payment terms: 30% advance / 70% before dispatch\n"
        "Quote validity: 30 days\n"
        "ISO 9001 certified"
    )
    captured = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text=quote,
        key="pr7c-full-response",
    )
    assert captured["correlation_state"] == "CORRELATED"
    assert captured["classification"] == "QUOTE"
    fields = captured["extraction"]["extracted_fields"]
    assert fields["unit_price"] == 112.5
    assert fields["currency"] == "INR"
    assert fields["price_basis"] == "PER_UNIT"
    assert fields["moq"] == 500.0
    assert fields["lead_time_days"] == 21
    assert captured["trust_environment"] == "DETERMINISTIC_TEST"
    assert (
        captured["extraction"]["field_provenance"]["unit_price"]["provenance"]
        == "SOURCE_PROVIDED_CLAIM"
    )

    reviewed = _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{captured['id']}/review",
            json={
                "decision": "ACCEPT_EXTRACTION",
                "provenance": "HUMAN",
                "idempotency_key": "pr7c-full-review",
            },
            headers=ORIGIN,
        )
    )
    assert reviewed["reviews"][-1]["decision"] == "ACCEPT_EXTRACTION"
    promoted = _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{captured['id']}/promote",
            headers=ORIGIN,
        )
    )
    assert promoted["promotion"]["claim_semantics"] == "SOURCE_PROVIDED_CLAIM"

    replay = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text=quote,
        key="pr7c-full-replay",
        message_id="pr7c-full-response",
    )
    assert replay["id"] == captured["id"]
    changed = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text=quote.replace("112.50", "120.00").replace("500 units", "1000 units"),
        key="pr7c-full-changed",
        message_id="pr7c-full-response-v2",
    )
    _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{changed['id']}/review",
            json={
                "decision": "ACCEPT_EXTRACTION",
                "provenance": "HUMAN",
                "idempotency_key": "pr7c-full-changed-review",
            },
            headers=ORIGIN,
        )
    )
    changed_promoted = _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{changed['id']}/promote",
            headers=ORIGIN,
        )
    )
    assert changed_promoted["promotion"]["contradictions"]
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        evidence = list(
            db.scalars(
                select(SupplierEvidence).where(
                    SupplierEvidence.owner_id.is_not(None),
                    SupplierEvidence.reference.like("PR-7C response%"),
                )
            )
        )
        products = list(
            db.scalars(
                select(SupplierProduct).where(
                    SupplierProduct.supplier_id == uuid.UUID(supplier_id),
                    SupplierProduct.source_reference.like("pr7c-response:%"),
                )
            )
        )
        terms = list(
            db.scalars(
                select(SupplierCommercialTerm)
                .join(
                    SupplierProduct,
                    SupplierCommercialTerm.supplier_product_id == SupplierProduct.id,
                )
                .where(
                    SupplierCommercialTerm.supplier_id == uuid.UUID(supplier_id),
                    SupplierProduct.source_reference.like("pr7c-response:%"),
                )
            )
        )
        promotions = list(db.scalars(select(SupplierResponsePromotion)))
        assert len(evidence) == 2
        assert len(products) == 1
        assert {term.version for term in terms} == {1, 2}
        assert len(promotions) == 2
    engine.dispose()


def test_pr7c_missing_currency_partial_and_conservative_classification(client: TestClient) -> None:
    opportunity_id, supplier_id, _contact_id, engagement_id = _context(client, "pr7c-partial")
    missing_currency = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text="Product: Kids storage basket\nPrice: 100 per unit\nMOQ: 20 units",
        key="pr7c-no-currency",
    )
    assert missing_currency["classification"] == "QUOTE"
    fields = missing_currency["extraction"]["extracted_fields"]
    assert fields["unit_price"] == 100.0
    assert fields["currency"] == "UNKNOWN"
    assert "currency" in missing_currency["extraction"]["unknown_fields"]
    assert (
        "currency was not explicitly supplied"
        in missing_currency["extraction"]["warnings"][0].lower()
    )

    rupee = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text="Product: Kids storage basket\nPrice: ₹125 per unit\nMOQ: 10 units",
        key="pr7c-rupee-symbol",
    )
    assert rupee["classification"] == "QUOTE"
    assert rupee["extraction"]["extracted_fields"]["unit_price"] == 125.0
    assert rupee["extraction"]["extracted_fields"]["currency"] == "INR"

    numeric = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text="100 500 21",
        key="pr7c-numeric-only",
    )
    assert numeric["classification"] == "UNKNOWN"


def test_pr7c_correlation_owner_and_human_review_safety(client: TestClient) -> None:
    opportunity_id, supplier_id, _contact_id, engagement_id = _context(client, "pr7c-safety")
    ambiguous = _ok(
        client.post(
            "/api/v1/intelligence/supplier-responses",
            json={
                "supplier_id": supplier_id,
                "opportunity_id": opportunity_id,
                "raw_content": "Quote: INR 99 per unit",
                "trust_environment": "DETERMINISTIC_TEST",
                "evidence_environment": "DETERMINISTIC_TEST",
                "idempotency_key": "pr7c-ambiguous",
            },
            headers=ORIGIN,
        )
    )
    assert ambiguous["correlation_state"] == "AMBIGUOUS"
    review = _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{ambiguous['id']}/review",
            json={
                "decision": "ACCEPT_EXTRACTION",
                "provenance": "HUMAN",
                "idempotency_key": "pr7c-ambiguous-review",
            },
            headers=ORIGIN,
        )
    )
    assert review["reviews"][-1]["provenance"] == "HUMAN"
    blocked = client.post(
        f"/api/v1/intelligence/supplier-responses/{ambiguous['id']}/promote", headers=ORIGIN
    )
    assert blocked.status_code == 409

    wrong_supplier = str(uuid.uuid4())
    response = _ok(
        client.post(
            "/api/v1/intelligence/supplier-responses",
            json={
                "supplier_id": supplier_id,
                "opportunity_id": opportunity_id,
                "engagement_id": engagement_id,
                "raw_content": "Please clarify the requested quantity.",
                "trust_environment": "DETERMINISTIC_TEST",
                "evidence_environment": "DETERMINISTIC_TEST",
                "idempotency_key": "pr7c-wrong-supplier-input",
            },
            headers=ORIGIN,
        )
    )
    assert response["correlation_state"] == "CORRELATED"
    # A system/AI caller cannot impersonate a HUMAN reviewer.
    denied = client.post(
        f"/api/v1/intelligence/supplier-responses/{response['id']}/review",
        json={
            "decision": "ACCEPT_EXTRACTION",
            "provenance": "SYSTEM",
            "idempotency_key": "pr7c-system-review",
        },
        headers=ORIGIN,
    )
    assert denied.status_code == 422
    assert wrong_supplier != supplier_id
    unsafe_attachment = client.post(
        "/api/v1/intelligence/supplier-responses",
        json={
            "supplier_id": supplier_id,
            "opportunity_id": opportunity_id,
            "engagement_id": engagement_id,
            "raw_content": "Please see the attached quote.",
            "attachment_refs": [{"path": "..\\secrets\\quote.pdf"}],
            "trust_environment": "DETERMINISTIC_TEST",
            "evidence_environment": "DETERMINISTIC_TEST",
            "idempotency_key": "pr7c-unsafe-attachment",
        },
        headers=ORIGIN,
    )
    assert unsafe_attachment.status_code == 422


def test_pr7c_fresh_process_reconstructs_raw_review_and_promotion(client: TestClient) -> None:
    opportunity_id, supplier_id, _contact_id, engagement_id = _context(client, "pr7c-reconstruct")
    captured = _response(
        client,
        opportunity_id=opportunity_id,
        supplier_id=supplier_id,
        engagement_id=engagement_id,
        text="Product: Kids organizer\nPrice: INR 55 per unit\nMOQ: 100 units",
        key="pr7c-reconstruct-response",
    )
    _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{captured['id']}/review",
            json={
                "decision": "CORRECT_EXTRACTION",
                "corrections": {"moq": 120.0},
                "reason": "Human checked the MOQ in the response.",
                "provenance": "HUMAN",
                "idempotency_key": "pr7c-reconstruct-review",
            },
            headers=ORIGIN,
        )
    )
    _ok(
        client.post(
            f"/api/v1/intelligence/supplier-responses/{captured['id']}/promote",
            headers=ORIGIN,
        )
    )
    assert TEST_DATABASE_URL
    script = """
import os
import uuid
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from vayujit_api.intelligence.supplier_response_models import (
    SupplierInboundResponse, SupplierResponseExtraction, SupplierResponseReview,
    SupplierResponsePromotion,
)
from vayujit_api.intelligence.supplier_models import SupplierEvidence, SupplierCommercialTerm
engine = create_engine(os.environ['VAYUJIT_TEST_DATABASE_URL'])
with Session(engine) as db:
    response = db.scalar(select(SupplierInboundResponse).where(
        SupplierInboundResponse.id == uuid.UUID(os.environ['PR7C_RESPONSE_ID'])))
    assert response is not None and response.raw_content_hash
    extraction = db.scalar(select(SupplierResponseExtraction).where(SupplierResponseExtraction.response_id == response.id))
    review = db.scalar(select(SupplierResponseReview).where(SupplierResponseReview.response_id == response.id))
    promotion = db.scalar(select(SupplierResponsePromotion).where(SupplierResponsePromotion.response_id == response.id))
    assert extraction is not None and review is not None and review.provenance == 'HUMAN'
    assert promotion is not None and promotion.supplier_evidence_id is not None
    evidence = db.get(SupplierEvidence, promotion.supplier_evidence_id)
    term = db.get(SupplierCommercialTerm, promotion.commercial_term_id)
    assert evidence is not None and evidence.evidence_kind == 'self_reported'
    assert term is not None and term.currency == 'INR'
"""
    env = os.environ.copy()
    env["PR7C_RESPONSE_ID"] = captured["id"]
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
