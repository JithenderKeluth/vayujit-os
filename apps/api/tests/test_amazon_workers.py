import uuid

from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    AmazonMediaPolicy,
    AmazonPricingPolicy,
    AmazonVariantPolicy,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
)
from vayujit_api.commerce.amazon_worker import (
    amazon_idempotency_key,
    parse_account_id,
    reconcile_ambiguous,
    retry_delay_seconds,
)


def test_amazon_job_identity_and_backoff_are_bounded() -> None:
    account_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    key = amazon_idempotency_key(
        operation="listing_submission",
        account_id=account_id,
        resource_id=resource_id,
        fingerprint="artifact:1",
    )
    assert key.startswith("amazon:listing_submission:")
    assert parse_account_id(f"amazon:{account_id}") == account_id
    assert parse_account_id("shopify:bad") is None
    assert retry_delay_seconds(1, retry_after_seconds=2) == 2
    assert retry_delay_seconds(99) == 3600


def test_ambiguous_submission_reconciles_by_sku_without_resubmit() -> None:
    transport = FakeAmazonSPAPITransport()
    connector = AmazonCommerceConnector(
        seller_id="seller-1",
        marketplace=amazon_marketplace("IN"),
        transport=transport,
    )
    accepted = connector.submit(
        sku="SKU-AMBIGUOUS",
        payload={"product_type": "PRODUCT", "title": "Demo"},
        idempotency_key="stable-key",
    )
    assert accepted.remote_id is not None
    resolved = reconcile_ambiguous(connector, sku="SKU-AMBIGUOUS")
    assert resolved.status == "succeeded"
    assert resolved.remote_id == accepted.remote_id


def test_amazon_readiness_policies_are_typed() -> None:
    assert (
        AmazonMediaPolicy.validate(
            [
                {
                    "position": 0,
                    "mime_type": "image/jpeg",
                    "width": 1000,
                    "height": 1000,
                    "size_bytes": 1000,
                    "checksum_sha256": "a" * 64,
                }
            ]
        )
        == []
    )
    assert AmazonMediaPolicy.validate([])[0].field == "main_image"
    assert (
        AmazonVariantPolicy.validate(
            [
                {
                    "stable_variant_key": "red",
                    "sku": "SKU-RED",
                    "variation_theme": "Color",
                    "price": "10",
                }
            ]
        )
        == []
    )
    assert (
        AmazonPricingPolicy.validate(
            {"selling_price": "10", "list_price": "20", "currency": "INR"}, "INR"
        )
        == []
    )


def test_crash_before_request_recovery_submits_once() -> None:
    from vayujit_api.commerce.amazon import (
        fake_amazon_listing_count,
        reset_fake_amazon_state,
    )

    reset_fake_amazon_state()
    transport = FakeAmazonSPAPITransport()
    connector = AmazonCommerceConnector(
        seller_id="seller-crash-before",
        marketplace=amazon_marketplace("IN"),
        transport=transport,
    )
    # The claimed worker crashes before the connector call; the replacement owns the request.
    result = connector.submit(
        sku="SKU-CRASH-BEFORE",
        payload={"product_type": "PRODUCT", "title": "Crash before"},
        idempotency_key="crash-before-key",
    )
    assert result.remote_id is not None
    assert fake_amazon_listing_count() == 1
    repeated = connector.submit(
        sku="SKU-CRASH-BEFORE",
        payload={"product_type": "PRODUCT", "title": "Crash before"},
        idempotency_key="crash-before-key",
    )
    assert repeated.remote_id == result.remote_id
    assert fake_amazon_listing_count() == 1


def test_crash_after_success_recovery_reconciles_without_resubmit() -> None:
    from vayujit_api.commerce.amazon import (
        fake_amazon_listing_count,
        reset_fake_amazon_state,
    )

    reset_fake_amazon_state()
    transport = FakeAmazonSPAPITransport()
    connector = AmazonCommerceConnector(
        seller_id="seller-crash-after",
        marketplace=amazon_marketplace("IN"),
        transport=transport,
    )
    accepted = connector.submit(
        sku="SKU-CRASH-AFTER",
        payload={"product_type": "PRODUCT", "title": "Crash after"},
        idempotency_key="crash-after-key",
    )
    assert accepted.remote_id is not None
    assert fake_amazon_listing_count() == 1
    recovered = reconcile_ambiguous(connector, sku="SKU-CRASH-AFTER")
    assert recovered.remote_id == accepted.remote_id
    assert fake_amazon_listing_count() == 1
