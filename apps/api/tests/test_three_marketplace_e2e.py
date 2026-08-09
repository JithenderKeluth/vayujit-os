from decimal import Decimal

import pytest

from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
    reset_fake_amazon_state,
)
from vayujit_api.commerce.flipkart import FlipkartCommerceConnector, reset_fake_flipkart_state
from vayujit_api.commerce.meesho import MeeshoCommerceConnector, reset_fake_meesho_state

pytestmark = pytest.mark.integration


def test_one_product_three_marketplaces_remain_isolated() -> None:
    reset_fake_amazon_state()
    reset_fake_flipkart_state()
    reset_fake_meesho_state()
    amazon = AmazonCommerceConnector(
        seller_id="three-seller",
        marketplace=amazon_marketplace("IN"),
        transport=FakeAmazonSPAPITransport(),
    )
    flipkart = FlipkartCommerceConnector(seller_id="three-seller")
    meesho = MeeshoCommerceConnector(seller_id="three-seller")
    product_type = str(amazon.discover_product_types()[0]["id"])
    amazon_result = amazon.submit(
        sku="AMZ-THREE-001",
        payload={"title": "Three Channel Product", "product_type": product_type},
        idempotency_key="three-amazon",
    )
    flipkart_result = flipkart.submit(
        sku="FK-THREE-001",
        payload={"title": "Three Channel Product"},
        idempotency_key="three-flipkart",
    )
    meesho_result = meesho.submit(
        sku="MSH-THREE-001",
        payload={"title": "Three Channel Product"},
        idempotency_key="three-meesho",
    )
    remote_ids = {amazon_result.remote_id, flipkart_result.remote_id, meesho_result.remote_id}
    assert None not in remote_ids
    assert len(remote_ids) == 3
    assert amazon.update_inventory("AMZ-THREE-001", 8)["quantity"] == 8
    assert flipkart.update_inventory("FK-THREE-001", 6)["quantity"] == 6
    assert meesho.update_inventory("MSH-THREE-001", 4)["quantity"] == 4
    assert amazon.get_inventory("AMZ-THREE-001")["quantity"] == 8
    assert flipkart.get_inventory("FK-THREE-001")["quantity"] == 6
    assert meesho.get_inventory("MSH-THREE-001")["quantity"] == 4
    assert amazon.get_orders() and flipkart.get_orders() and meesho.get_orders()
    assert amazon.get_settlements() and flipkart.get_settlements() and meesho.get_settlements()
    assert Decimal(str(amazon.get_settlements()[0]["net"])) > Decimal("0")
    assert Decimal(str(flipkart.get_settlements()[0]["net"])) > Decimal("0")
    assert Decimal(str(meesho.get_settlements()[0]["net"])) > Decimal("0")
