import pytest

from vayujit_api.commerce.flipkart import FlipkartCommerceConnector, reset_fake_flipkart_state

pytestmark = pytest.mark.integration


def test_flipkart_fake_e2e_has_separate_remote_identity() -> None:
    reset_fake_flipkart_state()
    connector = FlipkartCommerceConnector(seller_id="e2e-seller")
    first = connector.submit(sku="FK-E2E-1", payload={"title": "E2E"}, idempotency_key="e2e-1")
    assert first.remote_id and first.remote_id.startswith("FK-LISTING-")
    assert connector.reconcile_listing(first.remote_id)["status"] == "ACTIVE"
