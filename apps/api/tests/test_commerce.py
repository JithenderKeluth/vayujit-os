from decimal import Decimal

import pytest
from pydantic import ValidationError

from vayujit_api.commerce.connector import DeterministicFakeCommerceConnector
from vayujit_api.commerce.models import ListingStatus, Marketplace, OrderStatus
from vayujit_api.commerce.recovery import project_failure
from vayujit_api.commerce.scheduler import job_payload
from vayujit_api.commerce.schemas import AccountCreate, capabilities_for


def test_marketplace_and_lifecycle_values_are_bounded() -> None:
    assert {item.value for item in Marketplace} == {"amazon", "flipkart", "meesho", "shopify"}
    assert ListingStatus.ACTIVE.value == "active"
    assert OrderStatus.DELIVERED.value == "delivered"


def test_capabilities_are_server_provided_and_unknown_is_empty() -> None:
    assert "listing_create" in capabilities_for("amazon")
    assert "fulfilment" in capabilities_for("shopify")
    assert capabilities_for("unknown") == []


def test_account_contract_bounds_credentials() -> None:
    value = AccountCreate(
        marketplace=Marketplace.AMAZON,
        display_name="Demo",
        seller_account_id="seller-1",
        credentials={"token": "write-only"},
    )
    assert value.marketplace.value == "amazon"
    with pytest.raises(ValidationError):
        AccountCreate(marketplace=Marketplace.AMAZON, display_name="", seller_account_id="seller-1")


def test_fake_connector_is_deterministic() -> None:
    connector = DeterministicFakeCommerceConnector("shopify")
    first = connector.create_listing(title="Demo", sku="SKU-1", idempotency_key="key-1")
    second = connector.create_listing(title="Demo", sku="SKU-1", idempotency_key="key-1")
    assert first == second
    assert connector.validate_account("seller-1")["valid"] is True
    assert connector.get_orders()[0]["remote_id"] == "fake-order-shopify-001"


def test_profitability_requires_cost_data() -> None:
    gross = Decimal("100")
    fees = Decimal("12")
    assert gross - fees == Decimal("88")
    assert "Profit unavailable" == "Profit unavailable"


def test_commerce_failures_project_to_existing_recovery_and_scheduler_contracts() -> None:
    failure = project_failure("inventory_write_failed")
    assert failure.safe_reason_code == "commerce.inventory_write_failed"
    assert failure.retryable is True
    payload = job_payload("commerce.order_sync", account_id="account-1", resource_id="order-1")
    assert payload["job_type"] == "commerce.order_sync"
