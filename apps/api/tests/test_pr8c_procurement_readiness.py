"""Focused PR-8C procurement-readiness, HUMAN-boundary, and stale-context tests."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare
from test_pr8b_supplier_comparison import (
    _comparison_fixture,
    _engagement,
    _promotion,
    _reassessment,
    _seed_current_proceed,
    _set_term_price,
    _supplier_and_contact,
)

from vayujit_api.identity.models import User
from vayujit_api.intelligence.procurement_readiness_models import (
    SupplierProcurementReadinessAssessment,
)
from vayujit_api.intelligence.supplier_models import (
    SupplierCertificationClaim,
)

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.environ.get("VAYUJIT_TEST_DATABASE_URL")


def _comparison_with_human_shortlist(
    api: TestClient,
    key: str,
    *,
    canonical_supplier_id: str | None = None,
    select_second_supplier: bool = False,
    **fixture_options: Any,
) -> tuple[str, str, dict[str, Any], str, dict[str, Any]]:
    opportunity_id, assessment_id, reassessment_a, reassessment_b, comparison_url = (
        _comparison_fixture(api, key, **fixture_options)
    )
    comparison = _ok(
        api.post(
            comparison_url,
            json={
                "idempotency_key": f"{key}-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    selected_id = canonical_supplier_id
    if selected_id is None and select_second_supplier:
        selected_id = next(
            item["canonical_supplier_id"]
            for item in comparison["suppliers"]
            if item["reassessment_id"] == reassessment_b["id"]
        )
    if selected_id is None:
        selected_id = comparison["canonical_supplier_ids"][0]
    selected = next(
        item for item in comparison["suppliers"] if item["canonical_supplier_id"] == selected_id
    )
    decision = _ok(
        api.post(
            f"{comparison_url}/{comparison['id']}/shortlist",
            json={
                "canonical_supplier_id": selected_id,
                "decision": "KEEP_UNDER_REVIEW",
                "reason": "Bounded PR-8C.1 HUMAN review scenario.",
                "decision_key": f"{key}-shortlist",
            },
            headers=ORIGIN,
        )
    )
    return opportunity_id, assessment_id, comparison, str(decision["id"]), selected


def _readiness_for_selected(
    api: TestClient,
    key: str,
    context: tuple[str, str, dict[str, Any], str, dict[str, Any]],
    *,
    goal_id: str | None = None,
    latest_shortlist: bool = False,
) -> dict[str, Any]:
    opportunity_id, assessment_id, comparison, decision_id, selected = context
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/procurement-readiness"
    )
    payload: dict[str, Any] = {
        "idempotency_key": f"{key}-assessment",
        "canonical_supplier_id": selected["canonical_supplier_id"],
        "supplier_product_id": selected["supplier_product_id"],
        "shortlist_context_id": comparison["shortlist_context_id"],
        "reassessment_id": selected["reassessment_id"],
        "comparison_id": comparison["id"],
    }
    if not latest_shortlist:
        payload["shortlist_decision_id"] = decision_id
    if goal_id is not None:
        payload["goal_id"] = goal_id
    return _ok(api.post(url, json=payload, headers=ORIGIN))


def _pr8c_fixture(api: TestClient) -> tuple[str, str, dict[str, Any], str, str]:
    opportunity_id, assessment_id, reassessment_a, reassessment_b, comparison_url = (
        _comparison_fixture(api, "pr8c")
    )
    comparison = _ok(
        api.post(
            comparison_url,
            json={
                "idempotency_key": "pr8c-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    # PR-8B's comparison bridge is intentionally used as the canonical HUMAN
    # shortlist context for the one supplier selected below.
    if len(comparison["canonical_supplier_ids"]) < 1:
        raise AssertionError("PR-8B did not retain a canonical supplier")
    canonical_id = comparison["canonical_supplier_ids"][0]
    shortlist = _ok(
        api.post(
            f"{comparison_url}/{comparison['id']}/shortlist",
            json={
                "canonical_supplier_id": canonical_id,
                "decision": "KEEP_UNDER_REVIEW",
                "reason": "Human review before procurement readiness.",
                "decision_key": "pr8c-human-shortlist",
            },
            headers=ORIGIN,
        )
    )
    selected = next(
        item for item in comparison["suppliers"] if item["canonical_supplier_id"] == canonical_id
    )
    return (
        opportunity_id,
        assessment_id,
        comparison,
        shortlist["id"],
        selected["supplier_product_id"],
    )


def test_pr8c_assessment_is_explainable_idempotent_and_human_only(client: TestClient) -> None:
    opportunity_id, assessment_id, comparison, decision_id, product_id = _pr8c_fixture(client)
    canonical_id = comparison["canonical_supplier_ids"][0]
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/procurement-readiness"
    )
    payload = {
        "idempotency_key": "pr8c-assessment-ui-one",
        "canonical_supplier_id": canonical_id,
        "supplier_product_id": product_id,
        "shortlist_context_id": comparison["shortlist_context_id"],
        "shortlist_decision_id": decision_id,
        "comparison_id": comparison["id"],
    }
    assessment = _ok(client.post(url, json=payload, headers=ORIGIN))
    assert assessment["status"] == "BLOCKED"
    assert set(assessment["dimensions"]) == {
        "identity",
        "contact",
        "due_diligence",
        "product_capability",
        "quote_commercial",
        "economics",
        "capital_fit",
        "compliance",
        "human_shortlist",
    }
    assert assessment["dimensions"]["identity"]["provenance"] == "UNKNOWN"
    assert assessment["dimensions"]["human_shortlist"]["provenance"] == "HUMAN"
    assert assessment["provenance"]["supplier_claims_are_not_verification"] is True
    assert assessment["provenance"]["external_writes"] is False
    replay = _ok(
        client.post(
            url,
            json={**payload, "idempotency_key": "pr8c-assessment-ui-two"},
            headers=ORIGIN,
        )
    )
    assert replay["id"] == assessment["id"]
    assert replay["input_fingerprint"] == assessment["input_fingerprint"]
    assert replay["idempotent_reuse"] is True
    ack = _ok(
        client.post(
            f"/api/v1/intelligence/product-opportunities/procurement-readiness/{assessment['id']}/acknowledge",
            json={
                "idempotency_key": "pr8c-ack-one",
                "decision": "NEEDS_FURTHER_EVIDENCE",
                "provenance": "HUMAN",
                "reason": "Identity and contact verification remain unknown.",
            },
            headers=ORIGIN,
        )
    )
    assert ack["purchase_authorized"] is False
    assert ack["assessment"]["acknowledgements"][0]["provenance"] == "HUMAN"
    forged = client.post(
        f"/api/v1/intelligence/product-opportunities/procurement-readiness/{assessment['id']}/acknowledge",
        json={
            "idempotency_key": "pr8c-ack-ai",
            "decision": "REVIEWED",
            "provenance": "AI",
        },
        headers=ORIGIN,
    )
    assert forged.status_code == 422

    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        row = db.get(SupplierProcurementReadinessAssessment, uuid.UUID(assessment["id"]))
        assert row is not None
        original_notes = row.notes
        row.notes = "tamper"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        assert row.notes == original_notes
    engine.dispose()


def test_pr8c_stale_quote_blocks_ack_and_fresh_process_reconstructs(client: TestClient) -> None:
    opportunity_id, assessment_id, comparison, decision_id, product_id = _pr8c_fixture(client)
    canonical_id = comparison["canonical_supplier_ids"][0]
    # The comparison projection is the authority for the supplier ↔
    # reassessment relationship; its sorted snapshot list is not a supplier
    # ordering contract.
    reassessment = next(
        item["reassessment_id"]
        for item in comparison["suppliers"]
        if item["canonical_supplier_id"] == canonical_id
    )
    url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/procurement-readiness"
    )
    created = _ok(
        client.post(
            url,
            json={
                "idempotency_key": "pr8c-stale-assessment",
                "canonical_supplier_id": canonical_id,
                "supplier_product_id": product_id,
                "shortlist_context_id": comparison["shortlist_context_id"],
                "shortlist_decision_id": decision_id,
                "reassessment_id": reassessment,
                "comparison_id": comparison["id"],
            },
            headers=ORIGIN,
        )
    )
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        from vayujit_api.intelligence.commercial_reassessment_models import CommercialReassessment

        row = db.get(CommercialReassessment, uuid.UUID(reassessment))
        assert row is not None
        _set_term_price(str(row.commercial_term_id), "999.99")
    engine.dispose()
    stale = client.post(
        f"/api/v1/intelligence/product-opportunities/procurement-readiness/{created['id']}/acknowledge",
        json={
            "idempotency_key": "pr8c-stale-ack",
            "decision": "KEEP_UNDER_REVIEW",
            "provenance": "HUMAN",
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    assert "stale" in stale.text.casefold()
    fresh_process = """
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from vayujit_api.intelligence.procurement_readiness_models import (
    SupplierProcurementReadinessAssessment,
)
engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
with Session(engine) as db:
    row = db.scalar(
        select(SupplierProcurementReadinessAssessment).order_by(
            SupplierProcurementReadinessAssessment.created_at.desc()
        )
    )
    assert row is not None and row.input_fingerprint and row.dimensions["identity"]
"""
    subprocess.run(
        [sys.executable, "-c", fresh_process],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )


def test_pr8c1_gate106_attractive_unverified_supplier_preserves_human_boundary(
    client: TestClient,
) -> None:
    """Gate 106: attractive economics never imply verified identity or approval."""

    context = _comparison_with_human_shortlist(
        client,
        "pr8c1-g106",
        quote_b_price="INR 90.00",
        select_second_supplier=True,
    )
    comparison = context[2]
    landed = next(
        item for item in comparison["metrics"] if item["metric"] == "landed_cost_per_unit"
    )
    landed_values = [
        Decimal(str(item["value"])) for item in landed["values"] if item["value"] is not None
    ]
    assert len(landed_values) == 2
    assert min(landed_values) < max(landed_values)
    assessment = _readiness_for_selected(client, "pr8c1-g106", context)
    economics = assessment["dimensions"]["economics"]
    capital = assessment["dimensions"]["capital_fit"]
    assert Decimal(str(economics["values"]["unit_economics"]["per_unit_contribution"])) > 0
    assert capital["values"]["capital_fit_status"] == "FITS"
    assert assessment["dimensions"]["identity"]["provenance"] == "UNKNOWN"
    assert assessment["status"] == "BLOCKED"
    assert assessment["provenance"]["external_writes"] is False
    assert not assessment.get("purchase_authorized", False)


def test_pr8c1_gate107_contradictory_terms_remain_visible_and_blocked(
    client: TestClient,
) -> None:
    """Gate 107: conflicting MOQ versions remain evidence and block readiness."""

    opportunity_id, assessment_id = _prepare(client)
    supplier_a, contact_a = _supplier_and_contact(
        client, "PR-8C.1 Contradiction A", "pr8c1-ca.example"
    )
    supplier_b, contact_b = _supplier_and_contact(
        client, "PR-8C.1 Contradiction B", "pr8c1-cb.example"
    )
    _seed_current_proceed(opportunity_id, supplier_a)
    _seed_current_proceed(opportunity_id, supplier_b)
    promotion_a = _promotion(client, opportunity_id, supplier_a, contact_a, "pr8c1-g107-a")
    engagement_b = _engagement(
        client, opportunity_id, supplier_b, contact_b, "pr8c1-g107-engagement"
    )
    _promotion(
        client,
        opportunity_id,
        supplier_b,
        contact_b,
        "pr8c1-g107-v1",
        engagement_id=engagement_b["id"],
        moq=500,
    )
    promotion_b = _promotion(
        client,
        opportunity_id,
        supplier_b,
        contact_b,
        "pr8c1-g107-v2",
        engagement_id=engagement_b["id"],
        moq=1000,
    )
    reassessment_a = _reassessment(
        client, opportunity_id, assessment_id, promotion_a, "pr8c1-g107-ra"
    )
    reassessment_b = _reassessment(
        client, opportunity_id, assessment_id, promotion_b, "pr8c1-g107-rb"
    )
    comparison_url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/supplier-comparisons"
    )
    comparison = _ok(
        client.post(
            comparison_url,
            json={
                "idempotency_key": "pr8c1-g107-comparison",
                "reassessment_ids": [reassessment_a["id"], reassessment_b["id"]],
            },
            headers=ORIGIN,
        )
    )
    supplier_b_row = next(
        item for item in comparison["suppliers"] if item["reassessment_id"] == reassessment_b["id"]
    )
    decision = _ok(
        client.post(
            f"{comparison_url}/{comparison['id']}/shortlist",
            json={
                "canonical_supplier_id": supplier_b_row["canonical_supplier_id"],
                "decision": "KEEP_UNDER_REVIEW",
                "reason": "Conflicting terms require review.",
                "decision_key": "pr8c1-g107-shortlist",
            },
            headers=ORIGIN,
        )
    )
    assessment = _readiness_for_selected(
        client,
        "pr8c1-g107",
        (
            opportunity_id,
            assessment_id,
            comparison,
            str(decision["id"]),
            supplier_b_row,
        ),
    )
    commercial = assessment["dimensions"]["quote_commercial"]
    assert commercial["status"] == "BLOCKED"
    assert any(
        item.get("field") == "moq"
        for item in commercial["contradictions"]
        if isinstance(item, dict)
    )
    assert len(commercial["evidence_refs"]) >= 2
    assert assessment["status"] == "BLOCKED"


def test_pr8c1_gate114_negative_contribution_and_capital_shortfall_are_independent(
    client: TestClient,
) -> None:
    """Gate 114: negative contribution and capital shortfall stay explicit, not auto decisions."""

    negative_context = _comparison_with_human_shortlist(
        client,
        "pr8c1-g114-negative",
        selling_price_b=50,
        select_second_supplier=True,
    )
    negative = _readiness_for_selected(client, "pr8c1-g114-negative", negative_context)
    negative_unit = negative["dimensions"]["economics"]["values"]["unit_economics"]
    assert Decimal(str(negative_unit["per_unit_contribution"])) < 0
    assert negative["dimensions"]["capital_fit"]["values"]["capital_fit_status"] == "FITS"
    assert not negative.get("purchase_authorized", False)


def test_pr8c1_gate114_capital_shortfall_is_preserved_without_auto_rejection(
    client: TestClient,
) -> None:
    """Gate 114: a capital shortfall is independently visible without auto rejection."""

    shortfall_context = _comparison_with_human_shortlist(
        client,
        "pr8c1-g114-shortfall",
        quantity_b=50000,
        select_second_supplier=True,
    )
    shortfall = _readiness_for_selected(client, "pr8c1-g114-shortfall", shortfall_context)
    capital = shortfall["dimensions"]["capital_fit"]
    assert capital["status"] == "BLOCKED"
    assert Decimal(str(capital["values"]["capital_shortfall"])) > 0
    assert shortfall["dimensions"]["economics"]["status"] == "READY_FOR_HUMAN_REVIEW"
    assert not shortfall.get("purchase_authorized", False)


def test_pr8c1_gate115_source_claim_is_not_independent_compliance_verification(
    client: TestClient,
) -> None:
    """Gate 115: a supplier certification claim remains unverified evidence."""

    context = _comparison_with_human_shortlist(client, "pr8c1-g115")
    opportunity_id, _, _, _, selected = context
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        owner = db.scalar(select(User).where(User.email == "pr5b-owner@example.com"))
        assert owner is not None
        db.add(
            SupplierCertificationClaim(
                owner_id=owner.id,
                supplier_id=uuid.UUID(selected["supplier_id"]),
                claim="food_contact_compliance",
                version=1,
                is_current=True,
                source_reference="https://pr8c1-g115.example/certification",
                document_reference=None,
                observed_at=datetime.now(UTC),
                verification_state="unverified",
                expires_at=None,
                evidence_ids=[],
            )
        )
        db.commit()
    engine.dispose()
    assessment = _readiness_for_selected(client, "pr8c1-g115", context)
    compliance = assessment["dimensions"]["compliance"]
    assert compliance["provenance"] == "SOURCE_PROVIDED_CLAIM"
    assert compliance["status"] == "NEEDS_EVIDENCE"
    assert compliance["values"]["claims"][0]["verification_state"] == "unverified"
    assert "independent_compliance_verification" in compliance["missing_information"]
    _ok(
        client.post(
            f"/api/v1/intelligence/product-opportunities/procurement-readiness/{assessment['id']}/acknowledge",
            json={
                "idempotency_key": "pr8c1-g115-ack",
                "decision": "NEEDS_FURTHER_EVIDENCE",
                "provenance": "HUMAN",
                "reason": "Certification claim requires independent verification.",
            },
            headers=ORIGIN,
        )
    )
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        claim = db.scalar(
            select(SupplierCertificationClaim).where(
                SupplierCertificationClaim.supplier_id == uuid.UUID(selected["supplier_id"]),
                SupplierCertificationClaim.claim == "food_contact_compliance",
            )
        )
        assert claim is not None and claim.verification_state == "unverified"
    engine.dispose()
    assert opportunity_id


def test_pr8c1_gate116_superseding_human_withdrawal_stales_old_assessment(
    client: TestClient,
) -> None:
    """Gate 116: a later HUMAN withdrawal supersedes, but does not mutate, old snapshots."""

    context = _comparison_with_human_shortlist(client, "pr8c1-g116")
    old = _readiness_for_selected(client, "pr8c1-g116", context)
    opportunity_id, assessment_id, comparison, _, selected = context
    comparison_url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/supplier-comparisons"
    )
    withdrawn = _ok(
        client.post(
            f"{comparison_url}/{comparison['id']}/shortlist",
            json={
                "canonical_supplier_id": selected["canonical_supplier_id"],
                "decision": "REJECT",
                "reason": "Human withdrew this supplier after review.",
                "decision_key": "pr8c1-g116-withdrawal",
            },
            headers=ORIGIN,
        )
    )
    assert withdrawn["decision"] == "REJECT"
    stale = client.post(
        f"/api/v1/intelligence/product-opportunities/procurement-readiness/{old['id']}/acknowledge",
        json={
            "idempotency_key": "pr8c1-g116-old-ack",
            "decision": "KEEP_UNDER_REVIEW",
            "provenance": "HUMAN",
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    assert "shortlist" in stale.text.casefold()
    fresh = _readiness_for_selected(client, "pr8c1-g116-fresh", context, latest_shortlist=True)
    assert fresh["id"] != old["id"]
    assert fresh["shortlist_decision_id"] == withdrawn["id"]
    assert fresh["dimensions"]["human_shortlist"]["values"]["decision"] == "REJECT"
    assert old["shortlist_decision_id"] != fresh["shortlist_decision_id"]
    assert old["acknowledgements"] == []
