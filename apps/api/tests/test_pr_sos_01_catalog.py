"""PR-SOS-01 Seller Catalog and listing-preparation contract coverage."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from test_product_opportunity_feasibility import ORIGIN, _assessment, _setup

from vayujit_api.identity.models import User
from vayujit_api.intelligence.supplier_models import Supplier
from vayujit_api.media.models import MediaAsset

pytestmark = pytest.mark.integration


def _factory() -> sessionmaker[Session]:
    url = os.environ["VAYUJIT_TEST_DATABASE_URL"]
    return sessionmaker(bind=create_engine(url), expire_on_commit=False)


def _selected_opportunity(api: TestClient) -> tuple[str, str, str]:
    """Create a canonical opportunity and record the normal HUMAN shortlist."""
    product_id = _setup(api, _factory())
    opportunity_id, assessment_id = _assessment(api, product_id)
    score_path = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{assessment_id}/score"
    )
    score = api.post(score_path, json={}, headers=ORIGIN)
    assert score.status_code == 201, score.text
    decision = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{assessment_id}/decision",
        json={"action": "shortlist", "rationale": "Human selected for catalog preparation."},
        headers=ORIGIN,
    )
    assert decision.status_code == 201, decision.text
    return product_id, opportunity_id, assessment_id


def test_catalog_conversion_requires_human_selection_and_is_replayable(
    pr56_client: TestClient,
) -> None:
    api = pr56_client
    product_id = _setup(api, _factory())
    opportunity_id, _assessment_id = _assessment(api, product_id)
    convert_path = f"/api/v1/catalog/opportunities/{opportunity_id}/convert"

    blocked = api.post(convert_path, json={}, headers=ORIGIN)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "PRODUCT_SELECTION_REQUIRED"

    # The selected product is already the canonical ProductOpportunity identity.
    # Conversion adds durable Seller Catalog lineage only after the HUMAN action.
    score_path = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{_assessment_id}/score"
    )
    assert api.post(score_path, json={}, headers=ORIGIN).status_code == 201
    decision = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{_assessment_id}/decision",
        json={"action": "shortlist", "rationale": "Ready for seller-owned preparation."},
        headers=ORIGIN,
    )
    assert decision.status_code == 201, decision.text

    converted = api.post(convert_path, json={}, headers=ORIGIN)
    assert converted.status_code == 201, converted.text
    body = converted.json()
    assert body["product"]["id"] == product_id
    assert body["lineage"]["source_kind"] == "opportunity"
    assert body["lineage"]["provenance_json"]["selection_action"] == "shortlist"
    repeated = api.post(convert_path, json={}, headers=ORIGIN)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json() == body


def test_catalog_variants_listing_readiness_and_human_review(pr56_client: TestClient) -> None:
    api = pr56_client
    product_id, _opportunity_id, _assessment_id = _selected_opportunity(api)

    variant = api.post(
        f"/api/v1/catalog/products/{product_id}/variants",
        json={"variant_key": "default", "title": "Default", "sku": "VAR-001"},
        headers=ORIGIN,
    )
    assert variant.status_code == 201, variant.text
    duplicate = api.post(
        f"/api/v1/catalog/products/{product_id}/variants",
        json={"variant_key": "default", "title": "Duplicate", "sku": "VAR-002"},
        headers=ORIGIN,
    )
    assert duplicate.status_code == 409, duplicate.text

    draft = api.post(
        f"/api/v1/catalog/products/{product_id}/listing-drafts",
        json={"channel": "amazon_in", "idempotency_key": "catalog-draft-1"},
        headers=ORIGIN,
    )
    assert draft.status_code == 201, draft.text
    draft_body = draft.json()
    assert draft_body["status"] == "incomplete"
    readiness = api.get(f"/api/v1/catalog/products/{product_id}/readiness", headers=ORIGIN)
    assert readiness.status_code == 200
    assert readiness.json()["readiness"] == "BLOCKED"
    assert "amazon_in:title" in readiness.json()["blockers"]
    review = api.post(
        f"/api/v1/catalog/listing-drafts/{draft_body['id']}/review",
        json={"version": draft_body["version"], "decision": "approve"},
        headers=ORIGIN,
    )
    assert review.status_code == 409
    assert review.json()["detail"]["code"] == "LISTING_DRAFT_INCOMPLETE"

    complete = api.patch(
        f"/api/v1/catalog/listing-drafts/{draft_body['id']}",
        json={
            "version": draft_body["version"],
            "title": "Disposable Feasibility Product",
            "description": "Seller-authored description pending final review.",
            "bullets": ["Evidence-backed draft"],
            "category": "Home",
            "image_refs": ["seller-upload://pending"],
            "intended_price_amount": "999.00",
            "intended_currency": "INR",
            "compliance": {"review_status": "pending_human_review"},
        },
        headers=ORIGIN,
    )
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "needs_review"
    approved = api.post(
        f"/api/v1/catalog/listing-drafts/{draft_body['id']}/review",
        json={"version": complete.json()["version"], "decision": "approve"},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["human_review_state"] == "approved"
    assert approved.json()["readiness_state"] == "APPROVED_FOR_FUTURE_SUBMISSION"
    ready = api.get(f"/api/v1/catalog/products/{product_id}/readiness", headers=ORIGIN)
    assert ready.json()["readiness"] == "READY_FOR_FUTURE_SUBMISSION"
    assert ready.json()["external_publication"] == "DISABLED_IN_PR_SOS_01"

    stale = api.patch(
        f"/api/v1/catalog/listing-drafts/{draft_body['id']}",
        json={"version": 1, "title": "stale"},
        headers=ORIGIN,
    )
    assert stale.status_code == 409


def test_supplier_association_is_review_required_and_owner_scoped(pr56_client: TestClient) -> None:
    api = pr56_client
    product_id, opportunity_id, _assessment_id = _selected_opportunity(api)
    # This is a disposable persisted supplier fixture, created through the
    # canonical Supplier model; no remote supplier or network operation occurs.
    with _factory()() as db:
        owner = db.scalar(select(User).where(User.email == "feasibility@example.com"))
        assert owner
        supplier = Supplier(
            owner_id=owner.id,
            display_name="Catalog Supplier Fixture",
            supplier_type="manufacturer",
            country_code="IN",
            country="India",
            source_identity="manual_fixture",
            normalized_identity="catalog-supplier-fixture",
            verification_state="unverified",
            communication_status="not_contacted",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(supplier)
        db.commit()
        supplier_id = str(supplier.id)

    associated = api.post(
        f"/api/v1/catalog/products/{product_id}/supplier-associations",
        json={
            "supplier_id": supplier_id,
            "opportunity_id": opportunity_id,
            "status": "review_required",
            "provenance_json": {"source": "canonical_supplier_discovery"},
        },
        headers=ORIGIN,
    )
    assert associated.status_code == 201, associated.text
    assert associated.json()["provenance_json"]["supplier_approval"] == "NOT_IMPLIED"
    repeated = api.post(
        f"/api/v1/catalog/products/{product_id}/supplier-associations",
        json={"supplier_id": supplier_id, "status": "review_required"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    accepted = api.post(
        f"/api/v1/catalog/products/{product_id}/supplier-associations",
        json={"supplier_id": supplier_id, "status": "accepted"},
        headers=ORIGIN,
    )
    assert accepted.status_code == 409


def test_catalog_guessed_ids_are_not_authorized(pr56_client: TestClient) -> None:
    api = pr56_client
    _setup(api, _factory())
    random_id = "00000000-0000-0000-0000-000000000000"
    assert api.get(f"/api/v1/catalog/products/{random_id}", headers=ORIGIN).status_code == 404
    assert (
        api.get(f"/api/v1/catalog/products/{random_id}/readiness", headers=ORIGIN).status_code
        == 404
    )
    assert api.get(f"/api/v1/catalog/listing-drafts/{random_id}", headers=ORIGIN).status_code == 404
    assert (
        api.patch(
            f"/api/v1/catalog/variants/{random_id}",
            json={"version": 1, "variant_key": "guess"},
            headers=ORIGIN,
        ).status_code
        == 404
    )


def test_catalog_variant_option_combinations_and_economics_state(
    pr56_client: TestClient,
) -> None:
    api = pr56_client
    product_id, _opportunity_id, _assessment_id = _selected_opportunity(api)
    first = api.post(
        f"/api/v1/catalog/products/{product_id}/variants",
        json={
            "variant_key": "blue-small",
            "title": "Blue / Small",
            "option_values": {"color": "Blue", "size": "Small"},
        },
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    duplicate_combination = api.post(
        f"/api/v1/catalog/products/{product_id}/variants",
        json={
            "variant_key": "blue-small-copy",
            "title": "Duplicate combination",
            "option_values": {"size": "Small", "color": "Blue"},
        },
        headers=ORIGIN,
    )
    assert duplicate_combination.status_code == 409, duplicate_combination.text
    invalid = api.post(
        f"/api/v1/catalog/products/{product_id}/variants",
        json={
            "variant_key": "missing-size",
            "option_values": {"size": ""},
        },
        headers=ORIGIN,
    )
    assert invalid.status_code == 422, invalid.text
    economics = api.get(f"/api/v1/catalog/products/{product_id}/economics", headers=ORIGIN)
    assert economics.status_code == 200, economics.text
    assert economics.json()["available"] is False
    assert economics.json()["projection"] is None
    assert "Product Opportunity lineage" in economics.json()["reason"]


def test_catalog_product_images_are_private_owner_scoped_and_optimistic(
    pr56_client: TestClient,
) -> None:
    api = pr56_client
    product_id, _opportunity_id, _assessment_id = _selected_opportunity(api)
    with _factory()() as db:
        owner = db.scalar(select(User).where(User.email == "feasibility@example.com"))
        assert owner
        media = MediaAsset(
            owner_id=owner.id,
            original_filename="kids-product.png",
            safe_filename="kids-product.png",
            mime_type="image/png",
            size_bytes=128,
            width=1200,
            height=1200,
            checksum_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            storage_key=f"{owner.id.hex[:12]}/" + ("a" * 64) + ".png",
            status="ready",
            created_at=datetime.now(UTC),
        )
        db.add(media)
        db.commit()
        media_id = str(media.id)

    attached = api.post(
        f"/api/v1/catalog/products/{product_id}/images",
        json={
            "media_id": media_id,
            "alt_text": "A reusable kids lunch container",
            "is_primary": True,
        },
        headers=ORIGIN,
    )
    assert attached.status_code == 201, attached.text
    body = attached.json()
    assert body["is_primary"] is True
    assert body["preview_url"].endswith(f"/media/{media_id}/preview")
    assert (
        api.get(f"/api/v1/catalog/products/{product_id}/images", headers=ORIGIN).json()[0][
            "media_id"
        ]
        == media_id
    )
    stale = api.patch(
        f"/api/v1/catalog/images/{body['id']}",
        json={"version": 1, "alt_text": "stale"},
        headers=ORIGIN,
    )
    assert stale.status_code == 200, stale.text
    stale_replay = api.patch(
        f"/api/v1/catalog/images/{body['id']}",
        json={"version": 1, "alt_text": "stale replay"},
        headers=ORIGIN,
    )
    assert stale_replay.status_code == 409, stale_replay.text
    missing_media = api.post(
        f"/api/v1/catalog/products/{product_id}/images",
        json={"media_id": str(uuid.uuid4())},
        headers=ORIGIN,
    )
    assert missing_media.status_code == 404, missing_media.text
