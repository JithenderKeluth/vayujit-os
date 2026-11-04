"""Readiness is authoritative at HUMAN review, not just a browser button guard."""

import uuid

import pytest
from test_pr_sos_02_amazon_controls import ORIGIN, _seed_listing, _session_factory
from test_pr_sos_02_amazon_controls import client as client

from vayujit_api.commerce.models import MarketplacePrice

pytestmark = pytest.mark.integration


def test_amazon_incomplete_listing_cannot_receive_human_review(client):
    _, listing_id = _seed_listing(client, complete=False)
    endpoint = f"/api/v1/marketplaces/amazon/listings/{listing_id}"
    readiness = client.get(endpoint + "/readiness").json()
    assert readiness["ready"] is False
    assert "media_missing" in {item["code"] for item in readiness["blocking"]}
    review = client.post(
        endpoint + "/review", json={"confirm": True, "product_type": "Kids"}, headers=ORIGIN
    )
    assert review.status_code == 409
    assert review.json()["detail"]["code"] == "amazon_listing_not_ready"
    assert client.get(endpoint + "/review").json()["status"] == "review_required"


def test_amazon_review_still_requires_explicit_human_confirmation(client):
    _, listing_id = _seed_listing(client, complete=False)
    response = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/review",
        json={"confirm": False, "product_type": "Kids"},
        headers=ORIGIN,
    )
    assert response.status_code == 400


def test_amazon_authorization_rechecks_prerequisites_after_review(client):
    _, listing_id = _seed_listing(client)
    endpoint = f"/api/v1/marketplaces/amazon/listings/{listing_id}"
    review = client.post(
        endpoint + "/review", json={"confirm": True, "product_type": "Kids"}, headers=ORIGIN
    )
    assert review.status_code == 200
    with _session_factory()() as db:
        for price in db.query(MarketplacePrice).filter_by(listing_id=uuid.UUID(listing_id)):
            db.delete(price)
        db.commit()
    assert client.get(endpoint + "/readiness").json()["ready"] is False
    authorization = client.post(
        endpoint + "/execution-authorizations",
        json={
            "confirm": True,
            "review_id": review.json()["id"],
            "idempotency_key": "qa6-price-removed",
        },
        headers=ORIGIN,
    )
    assert authorization.status_code == 409
    assert (
        client.get(endpoint + "/execution-authorizations/latest").json()["status"]
        == "authorization_required"
    )
