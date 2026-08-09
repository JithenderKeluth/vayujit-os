from decimal import Decimal

from vayujit_api.commerce.flipkart import (
    FLIPKART_MARKETPLACE,
    FakeFlipkartTransport,
    FlipkartCommerceConnector,
    FlipkartEndpointPolicy,
    FlipkartMediaPolicy,
    FlipkartPricingPolicy,
    FlipkartVariantPolicy,
    reset_fake_flipkart_state,
)


def test_fake_flipkart_coherent_listing_lifecycle() -> None:
    reset_fake_flipkart_state()
    connector = FlipkartCommerceConnector(seller_id="seller-flipkart")
    assert connector.validate_account("seller-flipkart")["valid"] is True
    category = connector.discover_categories()[0]["id"]
    variants = [{"stable_variant_key": "default", "sku": "FK-SKU-1", "price": "99"}]
    media = [
        {
            "position": 0,
            "mime_type": "image/jpeg",
            "width": 1000,
            "height": 1000,
            "size_bytes": 1000,
            "checksum_sha256": "a" * 64,
        }
    ]
    price = {"list_price": "120", "selling_price": "99", "currency": "INR"}
    assert not FlipkartMediaPolicy.validate(media)
    assert not FlipkartVariantPolicy.validate(variants)
    assert not FlipkartPricingPolicy.validate(price, FLIPKART_MARKETPLACE.currency)
    preview = connector.preview(
        title="Flipkart product",
        sku="FK-SKU-1",
        category_id=str(category),
        attributes={"brand": "Demo"},
        approved=True,
        media=media,
        variants=variants,
        price=price,
    )
    assert preview["ready"] is True
    submitted = connector.submit(
        sku="FK-SKU-1", payload={"title": "Flipkart product"}, idempotency_key="flipkart-submit-1"
    )
    assert submitted.remote_id is not None
    assert submitted.remote_status == "PROCESSING"
    repeated = connector.submit(
        sku="FK-SKU-1", payload={"title": "Flipkart product"}, idempotency_key="flipkart-submit-1"
    )
    assert repeated.remote_id == submitted.remote_id
    assert connector.reconcile_listing(submitted.remote_id)["status"] == "ACTIVE"
    assert connector.get_inventory("FK-SKU-1")["quantity"] == 10
    assert connector.update_inventory("FK-SKU-1", 7, "inventory-1")["quantity"] == 7
    remote_price = connector.update_price(
        remote_id=submitted.remote_id,
        payload={"selling_price": "95", "currency": "INR"},
        idempotency_key="price-1",
    )
    assert remote_price["operation_status"] == "succeeded"
    assert connector.get_inventory("FK-SKU-1")["quantity"] == 7
    assert connector.get_orders()[0]["remote_id"] == "FK-ORDER-001"
    assert Decimal(str(connector.get_financial_events()[0]["net"])) == Decimal("1125.00")
    assert connector.get_returns()[0]["status"] == "REQUESTED"


def test_flipkart_endpoint_policy_rejects_unverified_urls() -> None:
    assert FlipkartEndpointPolicy.validate("https://seller.flipkart.com") == "seller.flipkart.com"
    for value in (
        "http://seller.flipkart.com",
        "https://evil.example",
        "https://user:pass@seller.flipkart.com",
    ):
        try:
            FlipkartEndpointPolicy.validate(value)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe Flipkart endpoint was accepted")


def test_fake_transport_has_no_live_network_boundary() -> None:
    transport = FakeFlipkartTransport()
    assert transport.categories(search="home", offset=0, limit=10)[0]["id"] == "fk-home"


def test_fake_flipkart_throttling_is_bounded_and_retryable() -> None:
    reset_fake_flipkart_state()
    connector = FlipkartCommerceConnector(seller_id="seller-flipkart")
    first = connector.submit(
        sku="FK-THROTTLE-1",
        payload={"title": "Throttle"},
        idempotency_key="throttle-listing-1",
    )
    assert first.status == "throttled"
    assert first.retryable is True
    assert first.retry_after_seconds == 2
    second = connector.submit(
        sku="FK-THROTTLE-1",
        payload={"title": "Throttle"},
        idempotency_key="throttle-listing-1",
    )
    assert second.remote_id is not None


def test_fake_flipkart_ambiguous_mutation_is_reconciled() -> None:
    reset_fake_flipkart_state()
    connector = FlipkartCommerceConnector(seller_id="seller-flipkart")
    submitted = connector.submit(
        sku="FK-AMBIGUOUS-1",
        payload={"title": "Ambiguous"},
        idempotency_key="ambiguous-listing-1",
    )
    assert submitted.ambiguous is True
    assert submitted.remote_id is not None
    reconciled = connector.reconcile_listing(submitted.remote_id)
    assert reconciled["status"] == "ACTIVE"
    updated = connector.update_listing(
        remote_id=submitted.remote_id,
        title="Ambiguous updated",
        sku="FK-AMBIGUOUS-1",
        idempotency_key="ambiguous-update-1",
    )
    assert updated["remote_id"] == submitted.remote_id
