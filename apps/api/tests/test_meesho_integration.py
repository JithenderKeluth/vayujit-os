import pytest

from vayujit_api.commerce.meesho import MeeshoCommerceConnector, reset_fake_meesho_state

pytestmark = pytest.mark.integration


def test_meesho_integration_boundary_is_deterministic() -> None:
    reset_fake_meesho_state()
    connector = MeeshoCommerceConnector(seller_id="integration-seller")
    assert connector.discover_categories(limit=10)
    result = connector.submit(
        sku="MS-INTEGRATION-1",
        payload={"title": "Integration listing"},
        idempotency_key="integration-listing-1",
    )
    assert result.remote_id is not None
    assert connector.reconcile_listing(result.remote_id)["status"] == "ACTIVE"
