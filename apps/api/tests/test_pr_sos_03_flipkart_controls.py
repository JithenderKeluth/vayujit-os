"""PR-SOS-03 Flipkart HUMAN review and single-use execution controls."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from vayujit_api.ai.models import AIGenerationRequest, GeneratedArtifact, PromptTemplate
from vayujit_api.brands.models import Brand
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"


def _factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"], poolclass=NullPool),
        expire_on_commit=False,
    )


def _seed(client: TestClient) -> tuple[str, str, str]:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Flipkart Controls Owner",
            "email": "flipkart-controls@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    with _factory()() as db:
        owner = db.query(User).one()
        stamp = now()
        brand = Brand(
            owner_id=owner.id,
            name="Flipkart Controls Brand",
            normalized_name="flipkart-controls-brand",
            slug="flipkart-controls-brand",
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
            name="Flipkart Controls Product",
            normalized_name="flipkart-controls-product",
            slug="flipkart-controls-product",
            sku="FK-CTRL-001",
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
            key="flipkart-controls-template",
            name="Flipkart controls template",
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

        media = MediaAsset(
            owner_id=owner.id,
            original_filename="controls.png",
            safe_filename="controls.png",
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
        db.commit()
        media_id = str(media.id)

    account = client.post(
        "/api/v1/marketplaces/flipkart/accounts",
        json={
            "display_name": "Local Flipkart",
            "seller_account_id": "seller-flipkart-controls",
            "credentials": {"token": "local-fixture"},
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    assert (
        client.post(
            f"/api/v1/marketplaces/flipkart/accounts/{account_id}/validate", headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/marketplaces/flipkart/accounts/{account_id}/enable",
            json={"confirm": True},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    listing = client.post(
        "/api/v1/marketplaces/flipkart/listings",
        json={
            "account_id": account_id,
            "brand_id": str(brand_id),
            "product_id": str(product_id),
            "artifact_id": str(artifact_id),
            "title": "Flipkart Controls Product",
            "category": "Kids",
            "marketplace_sku": "FK-CTRL-001",
        },
        headers=ORIGIN,
    )
    assert listing.status_code == 201, listing.text
    listing_id = listing.json()["id"]
    assert (
        client.put(
            f"/api/v1/marketplaces/flipkart/listings/{listing_id}/variants",
            json={
                "variants": [
                    {
                        "stable_variant_key": "default",
                        "sku": "FK-CTRL-001",
                        "price": "199",
                        "options": {"variation_theme": "default"},
                    }
                ],
                "idempotency_key": "fk-variants-1",
            },
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/marketplaces/flipkart/listings/{listing_id}/media",
            json={
                "media": [{"media_id": media_id, "position": 0, "alt_text": "Controls"}],
                "idempotency_key": "fk-media-1",
            },
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/marketplaces/flipkart/listings/{listing_id}/pricing",
            json={
                "selling_price": "199",
                "list_price": "249",
                "currency": "INR",
                "confirm": True,
                "idempotency_key": "fk-price-1",
            },
            headers=ORIGIN,
        ).status_code
        == 200
    )
    return account_id, listing_id, media_id


@pytest.fixture
def client(pr56_client: TestClient) -> Generator[TestClient, None, None]:
    yield pr56_client


def _payload(media_id: str) -> dict[str, object]:
    return {
        "category_id": "Kids",
        "attributes": {"age_group": "children"},
        "media": [{"media_id": media_id, "position": 0}],
        "variants": [
            {
                "stable_variant_key": "default",
                "sku": "FK-CTRL-001",
                "price": "199",
                "options": {"variation_theme": "default"},
            }
        ],
        "price": {"selling_price": "199", "currency": "INR"},
    }


def test_flipkart_requires_human_review_and_single_use_authorization(client: TestClient) -> None:
    _, listing_id, media_id = _seed(client)
    payload = _payload(media_id)
    blocked = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/submit",
        json={**payload, "idempotency_key": "fk-submit-1"},
        headers=ORIGIN,
    )
    assert blocked.status_code == 422
    review = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/review",
        json={**payload, "confirm": True},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    review_id = review.json()["id"]
    auth = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/execution-authorizations",
        json={"review_id": review_id, "idempotency_key": "fk-submit-1", "confirm": True},
        headers=ORIGIN,
    )
    assert auth.status_code == 201, auth.text
    auth_id = auth.json()["id"]
    replay_auth = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/execution-authorizations",
        json={"review_id": review_id, "idempotency_key": "fk-submit-1", "confirm": True},
        headers=ORIGIN,
    )
    assert replay_auth.status_code == 201
    assert replay_auth.json()["id"] == auth_id
    submitted = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/submit",
        json={**payload, "idempotency_key": "fk-submit-1", "authorization_id": auth_id},
        headers=ORIGIN,
    )
    assert submitted.status_code == 200, submitted.text
    replay = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/submit",
        json={**payload, "idempotency_key": "fk-submit-1", "authorization_id": auth_id},
        headers=ORIGIN,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_reuse"] is True


def test_flipkart_authorization_is_stale_after_listing_change(client: TestClient) -> None:
    _, listing_id, media_id = _seed(client)
    payload = _payload(media_id)
    review = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/review",
        json={**payload, "confirm": True},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    auth = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/execution-authorizations",
        json={"review_id": review.json()["id"], "idempotency_key": "fk-stale-1", "confirm": True},
        headers=ORIGIN,
    )
    assert auth.status_code == 201, auth.text
    changed = client.patch(
        f"/api/v1/marketplaces/listings/{listing_id}",
        json={"title": "Changed after review", "idempotency_key": "fk-title-1"},
        headers=ORIGIN,
    )
    assert changed.status_code == 200, changed.text
    submit = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/submit",
        json={
            **payload,
            "idempotency_key": "fk-stale-1",
            "authorization_id": auth.json()["id"],
        },
        headers=ORIGIN,
    )
    assert submit.status_code == 409


def test_flipkart_provider_rejection_does_not_claim_existing_remote_listing(
    client: TestClient,
) -> None:
    account_id, listing_id, media_id = _seed(client)
    payload = _payload(media_id)
    review = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/review",
        json={**payload, "confirm": True},
        headers=ORIGIN,
    )
    assert review.status_code == 200, review.text
    auth = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/execution-authorizations",
        json={"review_id": review.json()["id"], "idempotency_key": "fk-reject-1", "confirm": True},
        headers=ORIGIN,
    )
    assert auth.status_code == 201, auth.text
    first = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{listing_id}/submit",
        json={**payload, "idempotency_key": "fk-reject-1", "authorization_id": auth.json()["id"]},
        headers=ORIGIN,
    )
    assert first.status_code == 200, first.text

    listing = client.get("/api/v1/marketplaces/flipkart/listings", headers=ORIGIN).json()[0]
    second = client.post(
        "/api/v1/marketplaces/flipkart/listings",
        json={
            "account_id": account_id,
            "brand_id": listing["brand_id"],
            "product_id": listing["product_id"],
            "artifact_id": listing["content_artifact_id"],
            "title": "Duplicate SKU fixture",
            "category": "Kids",
            "marketplace_sku": listing["marketplace_sku"],
        },
        headers=ORIGIN,
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    assert (
        client.put(
            f"/api/v1/marketplaces/flipkart/listings/{second_id}/variants",
            json={"variants": payload["variants"], "idempotency_key": "fk-reject-variants"},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/marketplaces/flipkart/listings/{second_id}/media",
            json={
                "media": [{"media_id": media_id, "position": 0}],
                "idempotency_key": "fk-reject-media",
            },
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/marketplaces/flipkart/listings/{second_id}/pricing",
            json={
                "selling_price": "199",
                "list_price": "249",
                "currency": "INR",
                "confirm": True,
                "idempotency_key": "fk-reject-price",
            },
            headers=ORIGIN,
        ).status_code
        == 200
    )
    second_review = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{second_id}/review",
        json={**payload, "confirm": True},
        headers=ORIGIN,
    )
    assert second_review.status_code == 200, second_review.text
    second_auth = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{second_id}/execution-authorizations",
        json={
            "review_id": second_review.json()["id"],
            "idempotency_key": "fk-reject-2",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert second_auth.status_code == 201, second_auth.text
    rejected = client.post(
        f"/api/v1/marketplaces/flipkart/listings/{second_id}/submit",
        json={
            **payload,
            "idempotency_key": "fk-reject-2",
            "authorization_id": second_auth.json()["id"],
        },
        headers=ORIGIN,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["remote_listing_id"] is not None
    persisted = client.get(f"/api/v1/marketplaces/listings/{second_id}", headers=ORIGIN)
    assert persisted.status_code == 200
    assert persisted.json()["remote_listing_id"] is None
