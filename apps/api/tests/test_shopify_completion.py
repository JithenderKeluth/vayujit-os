from __future__ import annotations

import httpx
import pytest
from fake_shopify_server import FakeShopifyServer

from vayujit_api.publishing.connector import ConnectorFailure
from vayujit_api.publishing.service import retry_delay_seconds
from vayujit_api.publishing.shopify_connector import (
    OPERATIONS,
    ShopifyGraphQLClient,
    _validate_staged_target,
    shopify_variant_inputs,
)


def test_default_variant_maps_existing_product_commerce_values() -> None:
    result = shopify_variant_inputs(
        {
            "sku": "SKU-1",
            "price_amount": "19.95",
            "compare_at_price_amount": "24.95",
            "barcode": "123456789012",
            "weight_value": "0.5",
            "weight_unit": "kg",
            "inventory_tracking_enabled": True,
        },
        [],
    )
    assert result == [
        {
            "localKey": "default",
            "sku": "SKU-1",
            "price": "19.95",
            "compareAtPrice": "24.95",
            "barcode": "123456789012",
            "inventoryItem": {
                "measurement": {"weight": {"value": 0.5, "unit": "KG"}},
                "tracked": True,
            },
        }
    ]


def test_default_variant_requires_price_before_remote_call() -> None:
    with pytest.raises(ValueError, match="price is required"):
        shopify_variant_inputs({"sku": "SKU-1"}, [], require_price=True)


def test_structured_variants_are_bounded_and_unique() -> None:
    values = [
        {
            "local_key": "blue-small",
            "options": [{"name": "Color", "value": "Blue"}, {"name": "Size", "value": "S"}],
            "sku": "BLUE-S",
            "price": "12.50",
        },
        {
            "local_key": "blue-large",
            "options": [{"name": "Color", "value": "Blue"}, {"name": "Size", "value": "L"}],
            "sku": "BLUE-L",
            "price": "14.50",
        },
    ]
    result = shopify_variant_inputs({}, values)
    assert [item["localKey"] for item in result] == ["blue-small", "blue-large"]
    assert result[0]["optionValues"][0] == {"optionName": "Color", "name": "Blue"}  # type: ignore[index]


def test_duplicate_structured_variant_is_rejected() -> None:
    value = {
        "local_key": "same",
        "options": [{"name": "Color", "value": "Blue"}],
        "sku": "SAME",
        "price": "10",
    }
    with pytest.raises(ValueError, match="must be unique"):
        shopify_variant_inputs({}, [value, value])


@pytest.mark.parametrize(
    ("attempt", "jitter", "expected"),
    [(1, 1.0, 1.0), (2, 1.0, 2.0), (3, 1.0, 4.0), (9, 1.0, 10.0), (2, 1.2, 2.4)],
)
def test_retry_delay_is_exponential_bounded_and_deterministic(
    attempt: int, jitter: float, expected: float
) -> None:
    assert retry_delay_seconds(attempt, jitter_value=jitter) == expected


def test_retry_delay_respects_bounded_throttle_guidance() -> None:
    assert retry_delay_seconds(1, retry_after=7, jitter_value=1) == 7
    assert retry_delay_seconds(1, retry_after=90, jitter_value=1) == 10


def test_staged_upload_target_allowlist() -> None:
    _validate_staged_target("https://storage.googleapis.com/bucket")
    with pytest.raises(ConnectorFailure):
        _validate_staged_target("https://127.0.0.1/upload")
    with pytest.raises(ConnectorFailure):
        _validate_staged_target("https://storage.googleapis.com.evil.example/upload")


def test_staged_media_upload_never_forwards_admin_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "storage.googleapis.com":
            return httpx.Response(204)
        body = request.read().decode()
        if "VayujitStagedUpload" in body:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "stagedUploadsCreate": {
                            "stagedTargets": [
                                {
                                    "url": "https://storage.googleapis.com/upload",
                                    "resourceUrl": "https://storage.googleapis.com/resource",
                                    "parameters": [{"name": "key", "value": "safe"}],
                                }
                            ],
                            "userErrors": [],
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "productCreateMedia": {
                        "media": [{"id": "gid://shopify/MediaImage/1", "status": "READY"}],
                        "userErrors": [],
                    }
                }
            },
        )

    client = ShopifyGraphQLClient(
        shop_domain="unit-test.myshopify.com",
        access_token="secret-admin-token",
        api_version="2026-07",
        resolve_dns=False,
        transport=httpx.MockTransport(handler),
    )
    media = client.upload_product_media(
        product_id="gid://shopify/Product/1",
        filename="photo.png",
        mime_type="image/png",
        content=b"safe-image",
        alt_text="Safe alt",
    )
    assert media["id"] == "gid://shopify/MediaImage/1"
    upload = next(request for request in requests if request.url.host == "storage.googleapis.com")
    assert "X-Shopify-Access-Token" not in upload.headers


def test_product_create_updates_real_default_variant() -> None:
    operations: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        if "VayujitProductCreate" in body:
            operations.append("product_create")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "productCreate": {
                            "product": {
                                "id": "gid://shopify/Product/1",
                                "handle": "mapped",
                                "status": "DRAFT",
                                "variants": {
                                    "nodes": [
                                        {
                                            "id": "gid://shopify/ProductVariant/1",
                                            "inventoryItem": {
                                                "id": "gid://shopify/InventoryItem/1"
                                            },
                                        }
                                    ]
                                },
                            },
                            "userErrors": [],
                        }
                    }
                },
            )
        operations.append("variants_update")
        return httpx.Response(
            200,
            json={
                "data": {
                    "productVariantsBulkUpdate": {
                        "productVariants": [
                            {
                                "id": "gid://shopify/ProductVariant/1",
                                "sku": "SKU-1",
                                "inventoryItem": {"id": "gid://shopify/InventoryItem/1"},
                                "selectedOptions": [],
                            }
                        ],
                        "userErrors": [],
                    }
                }
            },
        )

    result = ShopifyGraphQLClient(
        shop_domain="unit-test.myshopify.com",
        access_token="secret-admin-token",
        api_version="2026-07",
        resolve_dns=False,
        transport=httpx.MockTransport(handler),
    ).publish(
        {"requested_action": "create_draft"},
        {"product_name": "Mapped", "sku": "SKU-1", "price_amount": "12.50"},
    )
    assert operations == ["product_create", "variants_update"]
    assert result.payload["variants"][0]["localKey"] == "default"  # type: ignore[index]


def test_standalone_fake_binds_to_loopback_and_rejects_unknown_operations() -> None:
    with FakeShopifyServer() as server:
        assert server.url.startswith("http://127.0.0.1:")
        response = httpx.post(
            f"{server.url}/graphql",
            headers={"X-Shopify-Access-Token": server.state.token},
            json={"query": "query Unknown { unknown }", "variables": {}},
        )
        assert response.status_code == 400


def test_standalone_fake_supports_every_predefined_operation_marker() -> None:
    expected_markers = {
        "validate",
        "collections",
        "publications",
        "product_create",
        "product_update",
        "options_create",
        "variants_create",
        "variants_update",
        "collection_add",
        "collection_remove",
        "publish",
        "unpublish",
        "staged_upload",
        "media_create",
        "product_status",
    }
    assert set(OPERATIONS) == expected_markers
