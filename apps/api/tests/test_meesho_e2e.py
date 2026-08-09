import pytest

from vayujit_api.commerce.meesho import MeeshoCommerceConnector, reset_fake_meesho_state

pytestmark = pytest.mark.integration


def test_meesho_fake_e2e_has_separate_remote_identity() -> None:
    reset_fake_meesho_state()
    connector = MeeshoCommerceConnector(seller_id="e2e-seller")
    first = connector.submit(sku="MS-E2E-1", payload={"title": "E2E"}, idempotency_key="e2e-1")
    assert first.remote_id and first.remote_id.startswith("MS-LISTING-")
    assert connector.reconcile_listing(first.remote_id)["status"] == "ACTIVE"
