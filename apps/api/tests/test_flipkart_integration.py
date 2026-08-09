import pytest

from vayujit_api.commerce.flipkart import FlipkartCommerceConnector, reset_fake_flipkart_state

pytestmark = pytest.mark.integration


def test_flipkart_integration_boundary_is_deterministic() -> None:
    reset_fake_flipkart_state()
    connector = FlipkartCommerceConnector(seller_id="integration-seller")
    assert connector.discover_categories(limit=10)
    result = connector.submit(
        sku="FK-INTEGRATION-1",
        payload={"title": "Integration listing"},
        idempotency_key="integration-listing-1",
    )
    assert result.remote_id is not None
    assert connector.reconcile_listing(result.remote_id)["status"] == "ACTIVE"
