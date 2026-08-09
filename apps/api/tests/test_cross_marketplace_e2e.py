from decimal import Decimal

import pytest

from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
    reset_fake_amazon_state,
)
from vayujit_api.commerce.flipkart import FlipkartCommerceConnector, reset_fake_flipkart_state

pytestmark = pytest.mark.integration


def test_amazon_and_flipkart_keep_independent_channel_state_and_profit_inputs() -> None:
    reset_fake_amazon_state()
    reset_fake_flipkart_state()
    amazon = AmazonCommerceConnector(
        seller_id="cross-seller",
        marketplace=amazon_marketplace("IN"),
        transport=FakeAmazonSPAPITransport(),
    )
    flipkart = FlipkartCommerceConnector(seller_id="cross-seller")
    product_type = str(amazon.discover_product_types()[0]["id"])
    amazon_result = amazon.submit(
        sku="AMZ-CROSS-SKU",
        payload={"title": "Cross Product", "product_type": product_type},
        idempotency_key="cross-amazon",
    )
    flipkart_result = flipkart.submit(
        sku="FK-CROSS-SKU", payload={"title": "Cross Product"}, idempotency_key="cross-flipkart"
    )
    assert amazon_result.remote_id and flipkart_result.remote_id
    assert amazon_result.remote_id != flipkart_result.remote_id
    assert amazon.update_inventory("AMZ-CROSS-SKU", 6)["quantity"] == 6
    assert flipkart.update_inventory("FK-CROSS-SKU", 3)["quantity"] == 3
    assert amazon.get_inventory("AMZ-CROSS-SKU")["quantity"] == 6
    assert flipkart.get_inventory("FK-CROSS-SKU")["quantity"] == 3
    amazon_category = amazon.product_type_attributes(product_type)
    flipkart_category = flipkart.discover_categories(search="Home", offset=0, limit=1)[0]
    assert amazon_category and flipkart.category_attributes(str(flipkart_category["id"]))
    assert (
        amazon.submit_media(
            amazon_result.remote_id,
            [{"url": "https://cdn.example/amz.jpg", "alt": "Amazon"}],
            "cross-amazon-media",
        ).status
        == "succeeded"
    )
    assert (
        amazon.submit_variants(
            amazon_result.remote_id,
            [{"sku": "AMZ-CROSS-SKU-RED", "options": {"Color": "Red"}}],
            "cross-amazon-variants",
        ).status
        == "succeeded"
    )
    assert (
        amazon.update_price(
            amazon_result.remote_id, {"amount": "119.00", "currency": "INR"}, "cross-amazon-price"
        ).status
        == "succeeded"
    )
    assert (
        flipkart.update_price(
            remote_id=flipkart_result.remote_id,
            payload={"amount": "129.00", "currency": "INR"},
            idempotency_key="cross-flipkart-price",
        )["operation_status"]
        == "succeeded"
    )
    assert len(amazon.get_orders()) >= 1 and len(flipkart.get_orders()) >= 1
    assert len(amazon.get_fees()) >= 1 and len(flipkart.get_fees()) >= 1
    settlement = amazon.get_settlements()[0]
    assert Decimal(str(settlement["net"])) > Decimal("0")
    assert flipkart.get_settlements()[0]["currency"] == "INR"
