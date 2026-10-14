"""PR-SOS-02 controlled Amazon listing review and execution boundary tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from vayujit_api.ai.models import AIGenerationRequest, GeneratedArtifact, PromptTemplate
from vayujit_api.brands.models import Brand
from vayujit_api.commerce.models import (
    AmazonListingExecutionAuthorization,
    MarketplaceListing,
    MarketplaceMediaMapping,
)
from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"


def _session_factory() -> sessionmaker[Session]:
    url = os.environ["VAYUJIT_TEST_DATABASE_URL"]
    return sessionmaker(bind=create_engine(url, poolclass=NullPool), expire_on_commit=False)


def _seed_listing(client: TestClient) -> tuple[str, str]:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Amazon Controls Owner",
            "email": "amazon-controls@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    factory = _session_factory()
    with factory() as db:
        owner = db.query(User).one()
        stamp = now()
        brand = Brand(
            owner_id=owner.id,
            name="Controls Brand",
            normalized_name="controls-brand",
            slug="controls-brand",
            status="active",
            is_active_context=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(brand)
        db.flush()
        product = Product(
            owner_id=owner.id,
            brand_id=brand.id,
            name="Controls Product",
            normalized_name="controls-product",
            slug="controls-product",
            sku="CTRL-001",
            product_type="physical",
            status="active",
            category="Kids",
            inventory_quantity=0,
            low_stock_threshold=0,
            inventory_tracking_enabled=False,
            is_featured=False,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(product)
        db.flush()
        template = PromptTemplate(
            id=uuid.uuid4(),
            key="controls-template",
            name="Controls template",
            description="Test template",
            version=1,
            template_type="product",
            system_instructions="test",
            user_template="test",
            output_schema={},
            status="enabled",
            is_default=False,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(template)
        db.flush()
        request = AIGenerationRequest(
            owner_id=owner.id,
            brand_id=brand.id,
            product_id=product.id,
            prompt_template_id=template.id,
            provider_key="local_fixture",
            status="completed",
            additional_instructions=None,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(request)
        db.flush()
        artifact = GeneratedArtifact(
            owner_id=owner.id,
            brand_id=brand.id,
            product_id=product.id,
            generation_request_id=request.id,
            prompt_template_id=template.id,
            artifact_type="product_content",
            version_number=1,
            status="approved",
            content_json={"title": product.name},
            validation_result={"valid": True},
            provider_metadata={"provider": "local_fixture"},
            approved_at=stamp,
            approved_by=owner.id,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(artifact)
        db.commit()
        brand_id, product_id, artifact_id = brand.id, product.id, artifact.id
    account = client.post(
        "/api/v1/marketplaces/amazon/accounts",
        json={
            "display_name": "Local Amazon",
            "seller_account_id": "seller-controls",
            "credentials": {},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    listing = client.post(
        "/api/v1/marketplaces/listings",
        json={
            "account_id": account_id,
            "brand_id": str(brand_id),
            "product_id": str(product_id),
            "artifact_id": str(artifact_id),
            "title": "Controls Product",
            "marketplace_sku": "CTRL-001",
            "category": "Kids",
            "idempotency_key": "controls-listing-1",
        },
        headers=ORIGIN,
    )
    assert listing.status_code == 201, listing.text
    return account_id, listing.json()["id"]


@pytest.fixture
def client(pr56_client: TestClient) -> Generator[TestClient, None, None]:
    yield pr56_client


def test_listing_requires_review_then_single_use_authorization(client: TestClient) -> None:
    account_id, listing_id = _seed_listing(client)
    assert (
        client.post(
            f"/api/v1/marketplaces/amazon/accounts/{account_id}/validate", headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/marketplaces/amazon/accounts/{account_id}/enable",
            json={"confirm": True},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    blocked = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/submit",
        json={"product_type": "PRODUCT", "attributes": {}, "idempotency_key": "submit-1"},
        headers=ORIGIN,
    )
    assert blocked.status_code == 422
    review = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/review",
        json={
            "product_type": "PRODUCT",
            "attributes": {"item_name": "Controls Product"},
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    review_id = review.json()["id"]
    auth = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/execution-authorizations",
        json={"review_id": review_id, "idempotency_key": "submit-1", "confirm": True},
        headers=ORIGIN,
    )
    assert auth.status_code == 201, auth.text
    auth_id = auth.json()["id"]
    replay_auth = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/execution-authorizations",
        json={"review_id": review_id, "idempotency_key": "submit-1", "confirm": True},
        headers=ORIGIN,
    )
    assert replay_auth.status_code == 201
    assert replay_auth.json()["id"] == auth_id
    submitted = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/submit",
        json={
            "product_type": "PRODUCT",
            "attributes": {"item_name": "Controls Product"},
            "idempotency_key": "submit-1",
            "authorization_id": auth_id,
        },
        headers=ORIGIN,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["execution_mode"] == "LOCAL_FAKE"
    replay = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/submit",
        json={
            "product_type": "PRODUCT",
            "attributes": {"item_name": "Controls Product"},
            "idempotency_key": "submit-1",
            "authorization_id": auth_id,
        },
        headers=ORIGIN,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_reuse"] is True


def test_listing_authorization_is_stale_after_payload_change(client: TestClient) -> None:
    _, listing_id = _seed_listing(client)
    review = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/review",
        json={"product_type": "PRODUCT", "attributes": {}, "confirm": True},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    auth = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/execution-authorizations",
        json={"review_id": review.json()["id"], "idempotency_key": "stale-1", "confirm": True},
        headers=ORIGIN,
    )
    assert auth.status_code == 201
    update = client.patch(
        f"/api/v1/marketplaces/listings/{listing_id}",
        json={"title": "Changed after review", "idempotency_key": "listing-update-1"},
        headers=ORIGIN,
    )
    assert update.status_code == 200, update.text
    submit = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/submit",
        json={
            "product_type": "PRODUCT",
            "attributes": {},
            "idempotency_key": "stale-1",
            "authorization_id": auth.json()["id"],
        },
        headers=ORIGIN,
    )
    assert submit.status_code == 409


def test_amazon_drift_serializes_media_identifiers(client: TestClient) -> None:
    """The drift JSONB snapshot must contain strings, not UUID objects."""
    _, listing_id = _seed_listing(client)
    factory = _session_factory()
    with factory() as db:
        owner = db.query(User).one()
        listing = db.get(MarketplaceListing, uuid.UUID(listing_id))
        assert listing is not None
        listing.remote_listing_id = "fixture-remote"
        stamp = now()
        media = MediaAsset(
            owner_id=owner.id,
            original_filename="product.png",
            safe_filename="product.png",
            mime_type="image/png",
            size_bytes=4,
            width=600,
            height=600,
            checksum_sha256=uuid.uuid4().hex * 2,
            storage_key=f"fixture/{uuid.uuid4().hex}.png",
            status="ready",
            created_at=stamp,
            archived_at=None,
        )
        db.add(media)
        db.flush()
        db.add(
            MarketplaceMediaMapping(
                owner_id=owner.id,
                listing_id=listing.id,
                media_id=media.id,
                position=0,
                status="mapped",
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()

    response = client.get(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/drift", headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    media_field = next(field for field in response.json()["fields"] if field["path"] == "media")
    media_snapshot = media_field["local"]
    assert media_snapshot and isinstance(media_snapshot[0]["media_id"], str)


def test_keep_remote_clears_listing_readiness_drift_blocker(client: TestClient) -> None:
    """Resolving detected drift must unblock only the drift prerequisite."""
    _, listing_id = _seed_listing(client)
    reviewed = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/drift/review", headers=ORIGIN
    )
    assert reviewed.status_code == 200, reviewed.text
    before = client.get(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/readiness", headers=ORIGIN
    )
    assert before.status_code == 200, before.text
    assert any(item["code"] == "drift_review_required" for item in before.json()["blocking"])

    kept = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/drift/keep-remote",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert kept.status_code == 200, kept.text
    refreshed_drift = client.get(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/drift", headers=ORIGIN
    )
    assert refreshed_drift.status_code == 200, refreshed_drift.text
    assert refreshed_drift.json()["drift_state"] == "remote_kept"
    after = client.get(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/readiness", headers=ORIGIN
    )
    assert after.status_code == 200, after.text
    assert not any(item["code"] == "drift_review_required" for item in after.json()["blocking"])


def test_amazon_authorization_rejects_expired_revoked_and_kill_switch_states(
    client: TestClient,
) -> None:
    account_id, listing_id = _seed_listing(client)
    assert (
        client.post(
            f"/api/v1/marketplaces/amazon/accounts/{account_id}/validate", headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/marketplaces/amazon/accounts/{account_id}/enable",
            json={"confirm": True},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    review = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/review",
        json={"product_type": "PRODUCT", "attributes": {}, "confirm": True},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text

    def issue(key: str) -> str:
        response = client.post(
            f"/api/v1/marketplaces/amazon/listings/{listing_id}/execution-authorizations",
            json={
                "review_id": review.json()["id"],
                "idempotency_key": key,
                "confirm": True,
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def submit(auth_id: str, key: str) -> object:
        return client.post(
            f"/api/v1/marketplaces/amazon/listings/{listing_id}/submit",
            json={
                "product_type": "PRODUCT",
                "attributes": {},
                "idempotency_key": key,
                "authorization_id": auth_id,
            },
            headers=ORIGIN,
        )

    expired_id = issue("expired-1")
    factory = _session_factory()
    with factory() as db:
        expired = db.get(AmazonListingExecutionAuthorization, uuid.UUID(expired_id))
        assert expired is not None
        expired.expires_at = now() - timedelta(seconds=1)
        db.commit()
    expired_submit = submit(expired_id, "expired-1")
    assert expired_submit.status_code == 409

    revoked_id = issue("revoked-1")
    revoked = client.post(
        f"/api/v1/marketplaces/amazon/listings/{listing_id}/execution-authorizations/{revoked_id}/revoke",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert revoked.status_code == 200, revoked.text
    assert submit(revoked_id, "revoked-1").status_code == 409

    settings = get_settings()
    previous_stop = settings.external_mutations_emergency_stop
    previous_live = settings.live_marketplace_mutations_enabled
    try:
        stopped_id = issue("stop-1")
        settings.external_mutations_emergency_stop = True
        assert submit(stopped_id, "stop-1").status_code == 503

        live_id = issue("live-1")
        settings.external_mutations_emergency_stop = False
        settings.live_marketplace_mutations_enabled = True
        assert submit(live_id, "live-1").status_code == 409
    finally:
        settings.external_mutations_emergency_stop = previous_stop
        settings.live_marketplace_mutations_enabled = previous_live
