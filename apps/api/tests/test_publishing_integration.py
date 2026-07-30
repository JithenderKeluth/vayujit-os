import base64
import json
import os
import struct
import uuid
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.ai.models import PromptTemplate
from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.config import get_settings
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.router import attempts
from vayujit_api.identity.service import now
from vayujit_api.main import create_app
from vayujit_api.publishing.connector import ConnectorResult, WordPressConnector
from vayujit_api.publishing.models import ShopifyConnectorConfiguration
from vayujit_api.publishing.shopify_connector import ShopifyThrottle

URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
test_factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    global test_factory
    assert URL and URL.startswith("postgresql")
    engine = create_engine(URL)
    reset_test_schema(engine, Base.metadata, database_url=URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    test_factory = factory
    with factory() as db:
        stamp = now()
        db.add(
            PromptTemplate(
                id=uuid.uuid4(),
                key="product-content",
                name="Product content",
                description="Default",
                version=1,
                template_type="product_content",
                system_instructions="Structured.",
                user_template="Generate.",
                output_schema={},
                status="enabled",
                is_default=True,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()

    def session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=URL)
    engine.dispose()


def setup(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Owner",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    brand = client.post("/api/v1/brands", json={"name": "Publish Brand"}, headers=ORIGIN).json()
    product = client.post(
        "/api/v1/products",
        json={
            "name": "Publish Product",
            "product_type": "physical",
            "description": "Ready product",
            "short_description": "Ready",
            "price_amount": "20.00",
            "price_currency": "USD",
        },
        headers=ORIGIN,
    ).json()
    client.post(f"/api/v1/products/{product['id']}/activate", headers=ORIGIN)
    generation = client.post(
        "/api/v1/ai/generations", json={"product_id": product["id"]}, headers=ORIGIN
    ).json()
    artifact = client.post(
        f"/api/v1/ai/artifacts/{generation['artifact_id']}/approve", headers=ORIGIN
    ).json()
    return brand, artifact


def test_complete_publish_idempotency_failure_and_retry(client: TestClient) -> None:
    assert client.get("/api/v1/publishing/connectors").status_code == 401
    brand, artifact = setup(client)
    assert client.get("/api/v1/publishing/connectors").json()[0]["local"] is True
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Local Channel",
            "brand_id": brand["id"],
            "connector_key": "mock_publisher_v1",
            "configuration": {
                "channel_name": "Demo",
                "publication_prefix": "DEMO",
                "simulate_failure": False,
                "failure_type": "non_retryable",
            },
        },
        headers=ORIGIN,
    )
    assert destination.status_code == 201
    key = "publish-test-key-001"
    first = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": destination.json()["id"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert first.status_code == 201 and first.json()["status"] == "succeeded"
    assert first.json()["attempt_count"] == 1
    repeated = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": destination.json()["id"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert repeated.json()["id"] == first.json()["id"]
    assert repeated.json()["attempt_count"] == 1
    assert first.json()["content_snapshot"]["product_name"] == "Publish Product"
    assert first.json()["external_url"].startswith("https://example.invalid/")

    failure = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Retry Channel",
            "configuration": {
                "channel_name": "Retry",
                "publication_prefix": "TRY",
                "simulate_failure": True,
                "failure_type": "retryable",
            },
        },
        headers=ORIGIN,
    ).json()
    failed = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": failure["id"],
            "idempotency_key": "retry-test-key-001",
        },
        headers=ORIGIN,
    ).json()
    assert failed["status"] == "failed" and failed["retryable"] is True
    client.patch(
        f"/api/v1/publishing/destinations/{failure['id']}",
        json={
            "configuration": {
                "channel_name": "Retry",
                "publication_prefix": "TRY",
                "simulate_failure": False,
                "failure_type": "retryable",
            }
        },
        headers=ORIGIN,
    )
    retried = client.post(
        f"/api/v1/publishing/executions/{failed['id']}/retry", headers=ORIGIN
    ).json()
    assert retried["status"] == "succeeded" and retried["attempt_count"] == 2
    assert [item["status"] for item in retried["attempts"]] == ["failed", "succeeded"]
    history = client.get("/api/v1/publishing/executions?status=succeeded").json()
    assert history["total"] == 2
    assert test_factory is not None
    with test_factory() as db:
        actions = set(db.scalars(select(AuditEvent.action)).all())
        assert {
            "publishing.destination_created",
            "publishing.destination_updated",
            "publishing.execution_requested",
            "publishing.execution_succeeded",
            "publishing.execution_failed",
            "publishing.execution_retried",
        } <= actions


def test_wordpress_draft_reconcile_and_move_to_draft(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(get_settings(), "media_storage_directory", str(tmp_path / "media"))
    brand, artifact = setup(client)
    posts: dict[int, dict[str, object]] = {}
    remote_media: dict[int, dict[str, object]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/users/me"):
            return httpx.Response(200, json={"id": 1, "name": "Owner"})
        if request.url.path.endswith("/categories"):
            return httpx.Response(
                200, json=[{"id": 3, "name": "Featured", "slug": "featured", "parent": 0}]
            )
        if request.url.path.endswith("/tags"):
            return httpx.Response(200, json=[{"id": 4, "name": "Launch", "slug": "launch"}])
        if request.url.path.endswith("/users"):
            return httpx.Response(200, json=[{"id": 1, "name": "Owner", "slug": "owner"}])
        if request.url.path.endswith("/media") and request.method == "POST":
            remote_media[61] = {
                "id": 61,
                "source_url": "http://127.0.0.1/media/61.png",
            }
            return httpx.Response(201, json=remote_media[61])
        if request.url.path.endswith("/media/61"):
            return httpx.Response(200, json=remote_media[61])
        if request.url.path.endswith("/posts") and request.method == "POST":
            body = json.loads(request.content)
            posts[81] = {
                "id": 81,
                "status": body["status"],
                "slug": body["slug"],
                "link": "http://127.0.0.1/?p=81",
                "title": {"rendered": body["title"]},
                "excerpt": {"rendered": body["excerpt"]},
                "categories": body.get("categories", []),
                "tags": body.get("tags", []),
                "author": body.get("author"),
                "featured_media": body.get("featured_media"),
                "modified_gmt": "2026-08-01T00:00:00",
            }
            return httpx.Response(201, json=posts[81])
        if request.url.path.endswith("/posts/81") and request.method == "GET":
            return httpx.Response(200, json=posts[81])
        if request.url.path.endswith("/posts/81"):
            posts[81]["status"] = json.loads(request.content)["status"]
            return httpx.Response(200, json=posts[81])
        raise AssertionError(request.url.path)

    fake = WordPressConnector(
        site_url="http://127.0.0.1",
        username="owner",
        application_password="not-a-real-secret",
        timeout_seconds=10,
        environment="development",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("vayujit_api.publishing.router.connector_for", lambda _value: fake)
    monkeypatch.setattr("vayujit_api.publishing.service.connector_for", lambda _value: fake)
    monkeypatch.setattr("vayujit_api.publishing.taxonomy.connector_for", lambda _value: fake)
    configuration = client.put(
        "/api/v1/publishing/connectors/wordpress",
        json={
            "site_url": "http://127.0.0.1",
            "username": "owner",
            "enabled": False,
            "default_post_status": "draft",
            "request_timeout_seconds": 10,
            "max_retry_attempts": 2,
        },
        headers=ORIGIN,
    )
    assert configuration.status_code == 200
    validated = client.post("/api/v1/publishing/connectors/wordpress/validate", headers=ORIGIN)
    assert validated.status_code == 200 and validated.json()["valid"] is True
    assert (
        client.post("/api/v1/publishing/connectors/wordpress/enable", headers=ORIGIN).status_code
        == 200
    )
    categories = client.get("/api/v1/publishing/connectors/wordpress/categories?search=feat")
    assert categories.status_code == 200 and categories.json()["items"][0]["id"] == 3
    assert client.get("/api/v1/publishing/connectors/wordpress/tags").json()["items"][0]["id"] == 4
    assert (
        client.get("/api/v1/publishing/connectors/wordpress/authors").json()["items"][0]["id"] == 1
    )
    local_png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", 2, 3)
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x00IEND\x00\x00\x00\x00"
    )
    local_media = client.post(
        "/api/v1/media",
        files={"file": ("featured.png", local_png, "image/png")},
        headers=ORIGIN,
    ).json()
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "WordPress Site",
            "brand_id": brand["id"],
            "connector_key": "wordpress",
            "configuration": {
                "post_status": "draft",
                "category_ids": [],
                "tag_ids": [],
                "author_id": None,
                "media_policy": "fail",
                "featured_image_policy": "required",
                "default_media_id": local_media["id"],
                "update_existing_remote_post": True,
                "content_mapping_version": 1,
            },
        },
        headers=ORIGIN,
    )
    assert destination.status_code == 201
    execution = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": destination.json()["id"],
            "idempotency_key": "wordpress-draft-001",
            "action": "create_draft",
        },
        headers=ORIGIN,
    )
    assert execution.status_code == 201
    assert execution.json()["remote_entity_id"] == "81"
    assert execution.json()["remote_status"] == "draft"
    assert posts[81]["featured_media"] == 61
    repeated = client.post(
        "/api/v1/publishing/executions",
        json={
            "artifact_id": artifact["id"],
            "destination_id": destination.json()["id"],
            "idempotency_key": "wordpress-draft-001",
            "action": "create_draft",
        },
        headers=ORIGIN,
    )
    assert repeated.json()["id"] == execution.json()["id"]
    assert len(remote_media) == 1
    reconciled = client.post(
        f"/api/v1/publishing/executions/{execution.json()['id']}/reconcile",
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["reconciliation_status"] == "in_sync"
    posts[81]["title"] = {"rendered": "Changed remotely"}
    drifted = client.post(
        f"/api/v1/publishing/executions/{execution.json()['id']}/reconcile",
        headers=ORIGIN,
    )
    assert "title" in drifted.json()["drift_fields"]
    remote_title = posts[81]["title"]
    assert isinstance(remote_title, dict)
    assert remote_title["rendered"] == "Changed remotely"
    moved = client.post(
        f"/api/v1/publishing/executions/{execution.json()['id']}/move-to-draft",
        headers=ORIGIN,
    )
    assert moved.status_code == 200 and moved.json()["remote_status"] == "draft"
    assert "application_password" not in configuration.text


def test_shopify_configuration_discovery_draft_idempotency_and_drift(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeShopify:
        last_throttle = ShopifyThrottle(currently_available=992, restore_rate=50.0)

        def validate(self) -> dict[str, object]:
            return {
                "shop": {
                    "id": "gid://shopify/Shop/1",
                    "name": "VAYUJIT Test Store",
                    "primaryDomain": {"host": "test-shop.myshopify.com"},
                }
            }

        def discover(
            self,
            kind: str,
            *,
            first: int,
            after: str | None,
            search: str = "",
        ) -> dict[str, object]:
            node = (
                {"id": "gid://shopify/Collection/1", "title": "Featured", "handle": "featured"}
                if kind == "collections"
                else {"id": "gid://shopify/Publication/1", "name": "Online Store"}
            )
            return {
                kind: {
                    "nodes": [node],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }

        def publish(
            self, destination: dict[str, object], snapshot: dict[str, object]
        ) -> ConnectorResult:
            return ConnectorResult(
                "gid://shopify/Product/42",
                "https://test-shop.myshopify.com/admin/products/42",
                {
                    "product": {
                        "id": "gid://shopify/Product/42",
                        "title": snapshot["product_name"],
                        "status": "DRAFT",
                    },
                    "throttle": self.last_throttle.__dict__,
                },
                remote_status="draft",
                remote_slug="publish-product",
            )

        def reconcile(self, remote_id: str) -> ConnectorResult:
            return ConnectorResult(
                remote_id,
                "https://test-shop.myshopify.com/admin/products/42",
                {
                    "id": remote_id,
                    "title": "Changed remotely",
                    "status": "DRAFT",
                    "vendor": "Publish Brand",
                    "productType": "",
                    "tags": [],
                    "seo": {"title": "", "description": ""},
                },
                remote_status="draft",
                remote_slug="publish-product",
            )

    fake = FakeShopify()
    monkeypatch.setattr(
        get_settings(),
        "credential_encryption_key",
        base64.urlsafe_b64encode(b"0" * 32).decode(),
    )
    monkeypatch.setattr("vayujit_api.publishing.shopify.validate_shop_domain", lambda value: value)
    monkeypatch.setattr("vayujit_api.publishing.router.shopify_connector_for", lambda _value: fake)
    monkeypatch.setattr("vayujit_api.publishing.service.shopify_connector_for", lambda _value: fake)
    monkeypatch.setattr(
        "vayujit_api.publishing.shopify_discovery.connector_for", lambda _value: fake
    )
    brand, artifact = setup(client)
    token = "shpat_test_token_never_returned"
    saved = client.put(
        "/api/v1/publishing/connectors/shopify",
        json={
            "shop_domain": "test-shop.myshopify.com",
            "access_token": token,
            "api_version": "2026-07",
            "default_product_status": "draft",
            "default_publication_ids": [],
            "inventory_policy": "no_inventory_write",
            "variant_policy": "default_variant",
            "media_policy": "fail",
            "request_timeout_seconds": 45,
            "max_retry_attempts": 3,
        },
        headers=ORIGIN,
    )
    assert saved.status_code == 200, saved.text
    assert token not in saved.text
    assert saved.json()["credential_source"] == "application"
    assert client.post("/api/v1/publishing/connectors/shopify/validate", headers=ORIGIN).json()[
        "valid"
    ]
    assert (
        client.post("/api/v1/publishing/connectors/shopify/enable", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.get("/api/v1/publishing/connectors/shopify/collections?search=feat").json()["items"][
            0
        ]["name"]
        == "Featured"
    )
    assert (
        client.get("/api/v1/publishing/connectors/shopify/publications").json()["items"][0]["name"]
        == "Online Store"
    )
    destination = client.post(
        "/api/v1/publishing/destinations",
        json={
            "name": "Shopify draft",
            "brand_id": brand["id"],
            "connector_key": "shopify",
            "configuration": {
                "default_product_status": "draft",
                "default_collection_ids": ["gid://shopify/Collection/1"],
                "default_publication_ids": [],
                "default_vendor": "",
                "default_product_type": "",
                "default_tags": [],
                "variant_policy": "default_variant",
                "inventory_policy": "no_inventory_write",
                "media_policy": "fail",
                "update_existing_remote_product": True,
                "content_mapping_version": 1,
            },
        },
        headers=ORIGIN,
    ).json()
    request = {
        "artifact_id": artifact["id"],
        "destination_id": destination["id"],
        "idempotency_key": "shopify-draft-integration",
        "action": "create_draft",
    }
    first = client.post("/api/v1/publishing/executions", json=request, headers=ORIGIN)
    assert first.status_code == 201
    assert first.json()["remote_status"] == "draft"
    second = client.post("/api/v1/publishing/executions", json=request, headers=ORIGIN)
    assert second.json()["id"] == first.json()["id"]
    reconciled = client.post(
        f"/api/v1/publishing/executions/{first.json()['id']}/reconcile",
        headers=ORIGIN,
    )
    assert reconciled.json()["reconciliation_status"] == "changed_remotely"
    assert "title" in reconciled.json()["drift_fields"]
    assert test_factory
    with test_factory() as db:
        configuration = db.scalar(select(ShopifyConnectorConfiguration))
        assert configuration and configuration.encrypted_access_token
        assert token not in configuration.encrypted_access_token
