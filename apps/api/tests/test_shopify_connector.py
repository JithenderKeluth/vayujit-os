import httpx
import pytest

from vayujit_api.publishing.connector import ConnectorFailure
from vayujit_api.publishing.shopify_connector import (
    ShopifyGraphQLClient,
    safe_description_html,
    shopify_product_input,
    validate_api_version,
    validate_shop_domain,
)


@pytest.mark.parametrize(
    "value",
    [
        "https://shop.myshopify.com",
        "shop.example.com",
        "localhost.myshopify.com/path",
        "shop.myshopify.com?token=secret",
        "user@shop.myshopify.com",
    ],
)
def test_rejects_unsafe_shop_domains(value: str) -> None:
    with pytest.raises(ValueError):
        validate_shop_domain(value, resolve_dns=False)


def test_accepts_normalized_shopify_domain() -> None:
    assert (
        validate_shop_domain("Example-Shop.myshopify.com.", resolve_dns=False)
        == "example-shop.myshopify.com"
    )


def test_rejects_unversioned_api() -> None:
    with pytest.raises(ValueError):
        validate_api_version("unstable")


def test_product_mapping_escapes_html_and_disables_inventory() -> None:
    mapped = shopify_product_input(
        {
            "product_name": "Safe product",
            "long_description": "<script>alert(1)</script>",
            "brand_name": "VAYUJIT",
            "seo_title": "SEO title",
        },
        {"default_tags": ["one", "one", "two"]},
        status="DRAFT",
    )
    assert mapped["status"] == "DRAFT"
    assert "<script>" not in str(mapped["descriptionHtml"])
    assert "&lt;script&gt;" in str(mapped["descriptionHtml"])
    assert mapped["tags"] == ["one", "two"]
    assert "inventoryQuantities" not in mapped


def test_safe_description_uses_no_unsafe_markup() -> None:
    assert safe_description_html("<iframe src=x>") == "<p>&lt;iframe src=x&gt;</p>"


def client(handler: object) -> ShopifyGraphQLClient:
    return ShopifyGraphQLClient(
        shop_domain="unit-test.myshopify.com",
        access_token="secret-token",
        api_version="2026-07",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        resolve_dns=False,
    )


def test_predefined_validation_and_throttle_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-shopify-access-token"] == "secret-token"
        assert b"VayujitValidate" in request.content
        return httpx.Response(
            200,
            json={
                "data": {"shop": {"id": "gid://shopify/Shop/1", "name": "Test"}},
                "extensions": {
                    "cost": {
                        "requestedQueryCost": 1,
                        "actualQueryCost": 1,
                        "throttleStatus": {"currentlyAvailable": 999, "restoreRate": 50.0},
                    }
                },
            },
        )

    value = client(handler)
    assert value.validate()["shop"]["name"] == "Test"  # type: ignore[index]
    assert value.last_throttle.currently_available == 999


def test_rejects_arbitrary_graphql_operation() -> None:
    with pytest.raises(ValueError):
        client(lambda _: httpx.Response(200)).execute("raw_query", {})


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "shopify_auth_failed", False),
        (429, "shopify_throttled", True),
        (503, "shopify_unavailable", True),
    ],
)
def test_safe_http_error_classification(status: int, code: str, retryable: bool) -> None:
    with pytest.raises(ConnectorFailure) as caught:
        client(lambda _: httpx.Response(status)).validate()
    assert caught.value.code == code
    assert caught.value.retryable is retryable
    assert "secret-token" not in caught.value.safe_message


def test_graphql_user_error_is_non_retryable() -> None:
    response = {
        "data": {
            "productCreate": {
                "product": None,
                "userErrors": [{"field": ["title"], "message": "Invalid", "code": "INVALID"}],
            }
        }
    }
    with pytest.raises(ConnectorFailure) as caught:
        client(lambda _: httpx.Response(200, json=response)).publish(
            {"requested_action": "create_draft"}, {"product_name": "Test"}
        )
    assert caught.value.code == "shopify_user_error"
    assert caught.value.retryable is False


def test_draft_creation_returns_safe_admin_url() -> None:
    response = {
        "data": {
            "productCreate": {
                "product": {
                    "id": "gid://shopify/Product/42",
                    "title": "Test",
                    "handle": "test",
                    "status": "DRAFT",
                },
                "userErrors": [],
            }
        }
    }
    result = client(lambda _: httpx.Response(200, json=response)).publish(
        {"requested_action": "create_draft"}, {"product_name": "Test"}
    )
    assert result.external_reference == "gid://shopify/Product/42"
    assert result.external_url == "https://unit-test.myshopify.com/admin/products/42"
    assert result.remote_status == "draft"
