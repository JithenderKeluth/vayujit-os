"""Unpublished preparation and exact image review; disposable PostgreSQL only."""

import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from helpers.ads_acceptance import create_account
from PIL import Image
from test_pr_sos_02_amazon_controls import ORIGIN, _seed_listing, _session_factory
from test_pr_sos_02_amazon_controls import client as client

from vayujit_api.commerce.models import (
    AmazonListingExecutionAuthorization,
    MarketplaceListing,
    MarketplacePrice,
)
from vayujit_api.identity.service import now

pytestmark = pytest.mark.integration


def _ads_draft(client):
    _, context = _context(client)
    artifact = client.get("/api/v1/ai/artifacts/" + context["artifact_id"], headers=ORIGIN).json()
    account = create_account(client, "meta", "qa7-exact")
    creative = dict(
        creative_type="content",
        product_id=context["product_id"],
        artifact_id=artifact["id"],
        artifact_version=artifact["version_number"],
        destination_url="https://example.invalid/qa7",
        idempotency_key="qa7-exact-creative",
    )
    return dict(
        provider="meta",
        account_id=account["id"],
        product_id=context["product_id"],
        name="[QA SYNTHETIC] QA7 exact",
        objective="awareness",
        budget=dict(daily_amount="100", currency="INR"),
        creative=creative,
        idempotency_key="qa7-exact-campaign",
    )


def test_ads_prospective_readiness_does_not_create_or_approve_campaign(client):
    data = _ads_draft(client)
    before = client.get("/api/v1/ads/campaigns", headers=ORIGIN).json()
    response = client.post(
        "/api/v1/ads/creatives/readiness",
        json={
            **data["creative"],
            "campaign_id": str(uuid.UUID(int=0)),
            "account_id": data["account_id"],
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["prospective"] is True
    assert response.json()["approval_granted"] is False
    assert client.get("/api/v1/ads/campaigns", headers=ORIGIN).json() == before


def test_ads_confirmation_binds_creative_and_rejects_stale_or_conflicting_replay(client):
    data = _ads_draft(client)
    preview = client.post("/api/v1/ads/campaigns/preview", json=data, headers=ORIGIN)
    assert preview.status_code == 200
    payload = dict(
        campaign=data,
        confirm=True,
        preview_fingerprint=preview.json()["fingerprint"],
        idempotency_key="qa7-confirm",
    )
    changed = {**data, "creative": {**data["creative"], "headline": "Changed after review"}}
    stale = client.post(
        "/api/v1/ads/campaigns/confirm", json={**payload, "campaign": changed}, headers=ORIGIN
    )
    assert stale.status_code == 409
    assert not client.get("/api/v1/ads/campaigns", headers=ORIGIN).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: client.post(
                    "/api/v1/ads/campaigns/confirm", json=payload, headers=ORIGIN
                ),
                range(2),
            )
        )
    assert {r.status_code for r in results} == {200}
    assert len({r.json()["campaign"]["id"] for r in results}) == 1
    assert len({r.json()["job"]["id"] for r in results}) == 1
    campaign_id = results[0].json()["campaign"]["id"]
    detail = client.get("/api/v1/ads/campaigns/" + campaign_id, headers=ORIGIN).json()
    assert len(detail["creatives"]) == 1
    assert detail["creatives"][0]["lineage"]["artifact_id"] == data["creative"]["artifact_id"]
    assert (
        detail["creatives"][0]["lineage"]["artifact_version"]
        == data["creative"]["artifact_version"]
    )
    assert detail["campaign"]["remote_campaign_id"] is None
    changed_preview = client.post(
        "/api/v1/ads/campaigns/preview", json=changed, headers=ORIGIN
    ).json()
    conflict = client.post(
        "/api/v1/ads/campaigns/confirm",
        json={
            **payload,
            "campaign": changed,
            "preview_fingerprint": changed_preview["fingerprint"],
        },
        headers=ORIGIN,
    )
    assert conflict.status_code == 409


def test_ads_invalid_creative_cannot_leave_campaign_budget_or_job(client):
    data = _ads_draft(client)
    data["creative"]["artifact_version"] = 999999
    response = client.post("/api/v1/ads/campaigns/preview", json=data, headers=ORIGIN)
    assert response.status_code == 422
    assert not client.get("/api/v1/ads/campaigns", headers=ORIGIN).json()


def _context(client):
    account_id, listing_id = _seed_listing(client, complete=False)
    with _session_factory()() as db:
        row = db.get(MarketplaceListing, uuid.UUID(listing_id))
        return account_id, {
            "brand_id": str(row.brand_id),
            "product_id": str(row.product_id),
            "artifact_id": str(row.content_artifact_id),
            "title": "[QA SYNTHETIC] unpublished preparation",
            "marketplace_sku": "QA7-LOCAL",
            "category": "Kids",
        }


def test_amazon_local_creation_does_not_invoke_connector(client, monkeypatch):
    account, payload = _context(client)

    def forbidden(*args, **kwargs):
        pytest.fail("Local draft preparation invoked a connector")

    monkeypatch.setattr("vayujit_api.commerce.router.connector_for", forbidden)
    response = client.post(
        "/api/v1/marketplaces/listings",
        json={**payload, "account_id": account, "prepare_only": True, "idempotency_key": "qa7"},
        headers=ORIGIN,
    )
    assert response.status_code == 201
    draft = response.json()
    assert draft["remote_listing_id"] is None
    assert draft["status"] == draft["publication_state"] == "draft"
    repeated = client.post(
        "/api/v1/marketplaces/listings",
        json={**payload, "account_id": account, "prepare_only": True, "idempotency_key": "qa7"},
        headers=ORIGIN,
    )
    assert repeated.json()["id"] == draft["id"]


def test_meesho_unpublished_price_can_satisfy_canonical_prerequisite(client, monkeypatch):
    _, payload = _context(client)
    account = client.post(
        "/api/v1/marketplaces/meesho/accounts",
        json={"display_name": "[QA SYNTHETIC] QA7", "seller_account_id": "qa7-meesho"},
        headers=ORIGIN,
    )
    assert account.status_code == 201
    account_id = account.json()["id"]
    client.post(f"/api/v1/marketplaces/meesho/accounts/{account_id}/validate", headers=ORIGIN)
    client.post(
        f"/api/v1/marketplaces/meesho/accounts/{account_id}/enable",
        json={"confirm": True},
        headers=ORIGIN,
    )
    draft = client.post(
        "/api/v1/marketplaces/meesho/listings",
        json={**payload, "account_id": account_id},
        headers=ORIGIN,
    )
    assert draft.status_code == 201
    listing_id = draft.json()["id"]

    def forbidden(*args, **kwargs):
        pytest.fail("Local preparation invoked a provider")

    monkeypatch.setattr("vayujit_api.commerce.meesho_router._connector", forbidden)
    endpoint = f"/api/v1/marketplaces/meesho/listings/{listing_id}/pricing"
    price = {
        "selling_price": "100.25",
        "list_price": "150.00",
        "currency": "INR",
        "confirm": True,
        "idempotency_key": "qa7-price",
    }
    saved = client.put(endpoint, json=price, headers=ORIGIN)
    assert saved.status_code == 200
    assert saved.json()["draft"] is True
    assert client.put(endpoint, json={**price, "confirm": False}, headers=ORIGIN).status_code == 409
    assert (
        client.put(endpoint, json={**price, "selling_price": "200"}, headers=ORIGIN).status_code
        == 422
    )
    with _session_factory()() as db:
        persisted = db.query(MarketplacePrice).filter_by(listing_id=uuid.UUID(listing_id)).one()
        assert persisted.amount == Decimal("100.25")
        assert db.get(MarketplaceListing, uuid.UUID(listing_id)).remote_listing_id is None


def _image_post(client):
    _, context = _context(client)
    account = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": "facebook",
            "display_name": "[QA SYNTHETIC] image",
            "remote_account_id": "qa7-image",
            "capabilities": {"supported_content_types": ["facebook_post"]},
        },
        headers=ORIGIN,
    ).json()
    for operation in ("validate", "enable"):
        assert (
            client.post(
                f"/api/v1/social/accounts/{account['id']}/{operation}", headers=ORIGIN
            ).status_code
            == 200
        )
    picture = io.BytesIO()
    Image.new("RGB", (600, 600), "white").save(picture, format="PNG")
    media = client.post(
        "/api/v1/media",
        files={"file": ("synthetic.png", picture.getvalue(), "image/png")},
        headers=ORIGIN,
    )
    assert media.status_code == 201
    post = client.post(
        "/api/v1/social/posts",
        json={
            "brand_id": context["brand_id"],
            "product_id": context["product_id"],
            "account_id": account["id"],
            "platform": "facebook",
            "content_type": "facebook_post",
            "content_artifact_id": context["artifact_id"],
            "content_artifact_version": 1,
            "media_ids": [media.json()["id"]],
            "caption": "[QA SYNTHETIC] original",
            "idempotency_key": "qa7-image",
        },
        headers=ORIGIN,
    )
    assert post.status_code == 201
    return post.json()


def test_image_approval_requires_explicit_exact_review_and_rejects_stale(client):
    post = _image_post(client)
    endpoint = f"/api/v1/social/posts/{post['id']}"
    preview = client.get(endpoint + "/preview").json()
    assert (
        client.post(
            endpoint + "/approve",
            json={"confirm": False, "preview_fingerprint": preview["fingerprint"]},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            endpoint, json={"caption": "[QA SYNTHETIC] changed"}, headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.post(
            endpoint + "/approve",
            json={"confirm": True, "preview_fingerprint": preview["fingerprint"]},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    current = client.get(endpoint + "/preview").json()
    for _ in range(2):
        approved = client.post(
            endpoint + "/approve",
            json={"confirm": True, "preview_fingerprint": current["fingerprint"]},
            headers=ORIGIN,
        )
        assert approved.status_code == 200
        assert approved.json()["lifecycle_status"] == "approved"
        assert approved.json()["schedule_id"] is None
        assert approved.json()["remote_publication_id"] is None


def test_amazon_local_price_and_variants_never_invoke_provider(client, monkeypatch):
    _, listing_id = _seed_listing(client)
    with _session_factory()() as db:
        listing = db.get(MarketplaceListing, uuid.UUID(listing_id))
        listing.remote_listing_id = None
        listing.status = listing.publication_state = "draft"
        # Exercise the actual first-price case, not only replacement of a seeded row.
        for price in db.query(MarketplacePrice).filter_by(listing_id=uuid.UUID(listing_id)):
            db.delete(price)
        db.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Local preparation invoked a provider")

    monkeypatch.setattr("vayujit_api.commerce.amazon_router._connector", forbidden)
    endpoint = f"/api/v1/marketplaces/amazon/listings/{listing_id}"
    variants = {
        "variants": [
            {
                "stable_variant_key": "default",
                "sku": "CTRL-001",
                "variation_theme": "Size",
                "options": {"Size": "M"},
                "price": "100.25",
                "currency": "INR",
            }
        ],
        "idempotency_key": "qa7-variants",
    }
    assert client.put(endpoint + "/variants", json=variants, headers=ORIGIN).status_code == 200
    for _ in range(2):
        price = client.put(
            endpoint + "/pricing",
            json={
                "selling_price": "100.25",
                "list_price": "150.00",
                "currency": "INR",
                "confirm": True,
                "idempotency_key": "qa7-price",
            },
            headers=ORIGIN,
        )
        assert price.status_code == 200
        assert price.json()["status"] == "prepared"
    assert client.get(endpoint + "/readiness").json()["ready"] is True
    assert client.get(endpoint + "/variants").json()[0]["variation_theme"] == "Size"
    with _session_factory()() as db:
        assert db.query(MarketplacePrice).filter_by(listing_id=uuid.UUID(listing_id)).count() == 1
        assert db.get(MarketplaceListing, uuid.UUID(listing_id)).remote_listing_id is None


def test_amazon_material_price_change_invalidates_review(client):
    _, listing_id = _seed_listing(client)
    endpoint = f"/api/v1/marketplaces/amazon/listings/{listing_id}"
    review = client.post(
        endpoint + "/review", json={"confirm": True, "product_type": "Kids"}, headers=ORIGIN
    )
    assert review.status_code == 200
    with _session_factory()() as db:
        price = db.query(MarketplacePrice).filter_by(listing_id=uuid.UUID(listing_id)).one()
        price.amount += 1
        db.commit()
    assert client.get(endpoint + "/readiness").json()["ready"] is True
    response = client.post(
        endpoint + "/execution-authorizations",
        json={
            "confirm": True,
            "review_id": review.json()["id"],
            "idempotency_key": "qa7-material-change",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 409


def test_amazon_expired_authorization_is_not_projected_as_issued(client):
    _, listing_id = _seed_listing(client)
    endpoint = f"/api/v1/marketplaces/amazon/listings/{listing_id}"
    review = client.post(
        endpoint + "/review", json={"confirm": True, "product_type": "Kids"}, headers=ORIGIN
    ).json()
    authorization = client.post(
        endpoint + "/execution-authorizations",
        json={"confirm": True, "review_id": review["id"], "idempotency_key": "qa7-expire"},
        headers=ORIGIN,
    )
    assert authorization.status_code == 201
    with _session_factory()() as db:
        row = db.get(AmazonListingExecutionAuthorization, uuid.UUID(authorization.json()["id"]))
        row.expires_at = now() - timedelta(seconds=1)
        db.commit()
    response = client.get(endpoint + "/execution-authorizations/latest")
    assert response.json()["status"] == "expired"
    with _session_factory()() as db:
        # Projection does not rewrite immutable issuance history.
        assert (
            db.get(
                AmazonListingExecutionAuthorization, uuid.UUID(authorization.json()["id"])
            ).status
            == "issued"
        )


def test_flipkart_late_account_disable_blocks_authorization(client):
    from test_pr_sos_03_flipkart_controls import _payload, _seed

    account_id, listing_id, media_id = _seed(client)
    endpoint = f"/api/v1/marketplaces/flipkart/listings/{listing_id}"
    review = client.post(
        endpoint + "/review", json={**_payload(media_id), "confirm": True}, headers=ORIGIN
    )
    assert review.status_code == 200
    assert (
        client.post(
            f"/api/v1/marketplaces/flipkart/accounts/{account_id}/disable",
            json={"confirm": True},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert client.get(endpoint + "/readiness").json()["ready"] is False
    response = client.post(
        endpoint + "/execution-authorizations",
        json={"confirm": True, "review_id": review.json()["id"], "idempotency_key": "qa7-disabled"},
        headers=ORIGIN,
    )
    assert response.status_code == 409


def test_concurrent_amazon_review_and_authorization_reuse_exact_identity(client):
    _, listing_id = _seed_listing(client)
    endpoint = f"/api/v1/marketplaces/amazon/listings/{listing_id}"

    def review_request(_):
        response = client.post(
            endpoint + "/review", json={"confirm": True, "product_type": "Kids"}, headers=ORIGIN
        )
        assert response.status_code == 200
        return response.json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(pool.map(review_request, range(2)))
    assert len(set(reviews)) == 1

    def authorization_request(_):
        response = client.post(
            endpoint + "/execution-authorizations",
            json={"confirm": True, "review_id": reviews[0], "idempotency_key": "qa7-concurrent"},
            headers=ORIGIN,
        )
        assert response.status_code == 201
        return response.json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        authorizations = list(pool.map(authorization_request, range(2)))
    assert len(set(authorizations)) == 1
