import pytest

from vayujit_api.commerce.amazon import FakeAmazonSPAPITransport, amazon_marketplace

pytestmark = pytest.mark.integration


def test_fake_amazon_boundary_is_network_free() -> None:
    transport = FakeAmazonSPAPITransport()
    result = transport.validate_account(
        seller_id="integration-seller",
        marketplace_id=amazon_marketplace("IN").marketplace_id,
    )
    assert result.status == "succeeded"
    assert result.payload["marketplace_id"] == "A21TJRUUN4KGV"
