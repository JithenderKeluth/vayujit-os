import pytest

from vayujit_api.commerce.amazon import (
    AMAZON_MARKETPLACES,
    AmazonEndpointPolicy,
    AmazonIssueCode,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
)


def test_amazon_marketplace_region_mapping_includes_india() -> None:
    assert amazon_marketplace("IN").marketplace_id == "A21TJRUUN4KGV"
    assert amazon_marketplace("IN").currency == "INR"
    assert AMAZON_MARKETPLACES["US"].endpoint_host == "sellingpartnerapi-na.amazon.com"


def test_amazon_endpoint_policy_rejects_ssrf_and_wrong_region() -> None:
    assert AmazonEndpointPolicy.validate(
        "https://sellingpartnerapi-eu.amazon.com",
        expected_host="sellingpartnerapi-eu.amazon.com",
    )
    with pytest.raises(ValueError):
        AmazonEndpointPolicy.validate("http://sellingpartnerapi-eu.amazon.com")
    with pytest.raises(ValueError):
        AmazonEndpointPolicy.validate("https://example.invalid")
    with pytest.raises(ValueError):
        AmazonEndpointPolicy.validate(
            "https://sellingpartnerapi-na.amazon.com",
            expected_host="sellingpartnerapi-eu.amazon.com",
        )


def test_fake_transport_is_idempotent_and_processing_then_active() -> None:
    transport = FakeAmazonSPAPITransport()
    first = transport.submit_listing(
        seller_id="seller-1",
        marketplace_id=amazon_marketplace("IN").marketplace_id,
        sku="SKU-1",
        payload={"product_type": "PRODUCT", "title": "Demo"},
        idempotency_key="idempotency-1",
    )
    second = transport.submit_listing(
        seller_id="seller-1",
        marketplace_id=amazon_marketplace("IN").marketplace_id,
        sku="SKU-1",
        payload={"product_type": "PRODUCT", "title": "Demo"},
        idempotency_key="idempotency-1",
    )
    assert first.remote_id == second.remote_id
    assert first.remote_status == "PROCESSING"
    reconciled = transport.reconcile_listing(first.remote_id or "")
    assert reconciled.remote_status == "ACTIVE"


def test_fake_transport_safe_failure_classification() -> None:
    throttled = FakeAmazonSPAPITransport(scenario="throttle").submit_listing(
        seller_id="seller-1",
        marketplace_id=amazon_marketplace("IN").marketplace_id,
        sku="SKU-1",
        payload={"product_type": "PRODUCT"},
        idempotency_key="throttle-1",
    )
    assert throttled.retryable is True
    assert throttled.issues[0].code == AmazonIssueCode.THROTTLED
    rejected = FakeAmazonSPAPITransport(scenario="reject").submit_listing(
        seller_id="seller-1",
        marketplace_id=amazon_marketplace("IN").marketplace_id,
        sku="SKU-1",
        payload={"product_type": "PRODUCT"},
        idempotency_key="reject-1",
    )
    assert rejected.status == "rejected"
    assert rejected.payload == {}


def test_fake_financial_events_cover_normalized_category_matrix() -> None:
    events = FakeAmazonSPAPITransport().financial_events(
        seller_id="seller-finance",
        marketplace_id=amazon_marketplace("IN").marketplace_id,
    )
    categories = {str(event["type"]) for event in events}
    assert {
        "Commission",
        "Referral_Commission",
        "Fulfilment_Fee",
        "Shipping_Fee",
        "Storage_Fee",
        "Closing_Fee",
        "Refund",
        "Refund_Fee",
        "Promotion",
        "Advertising",
        "Tax",
        "Withholding",
        "Chargeback",
        "Adjustment",
        "Unknown_Remote_Category",
    } <= categories
