from decimal import Decimal

import pytest

from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    AmazonMediaPolicy,
    AmazonPricingPolicy,
    AmazonVariantPolicy,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
    reset_fake_amazon_state,
)

pytestmark = pytest.mark.integration


def test_fake_amazon_coherent_acceptance_journey() -> None:
    reset_fake_amazon_state()
    transport = FakeAmazonSPAPITransport()
    connector = AmazonCommerceConnector(
        seller_id="seller-e2e",
        marketplace=amazon_marketplace("IN"),
        transport=transport,
    )
    assert connector.validate_account("seller-e2e")["valid"] is True
    product_type = connector.discover_product_types()[0]["id"]
    assert connector.product_type_attributes(str(product_type))
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
    variants = [
        {
            "stable_variant_key": "default",
            "sku": "E2E-SKU",
            "variation_theme": "Color",
            "price": "99",
        }
    ]
    price = {"list_price": "120", "selling_price": "99", "currency": "INR"}
    assert not AmazonMediaPolicy.validate(media)
    assert not AmazonVariantPolicy.validate(variants)
    assert not AmazonPricingPolicy.validate(price, "INR")
    preview = connector.preview(
        title="E2E Product",
        sku="E2E-SKU",
        product_type=str(product_type),
        attributes={"item_name": "E2E Product"},
        approved=True,
        media=media,
        variants=variants,
        price=price,
    )
    assert preview["ready"] is True
    submitted = connector.submit(
        sku="E2E-SKU",
        payload={
            "title": "E2E Product",
            "product_type": str(product_type),
            "attributes": {"item_name": "E2E Product"},
        },
        idempotency_key="e2e-submit",
    )
    assert submitted.remote_id is not None
    assert submitted.remote_status == "PROCESSING"
    assert (
        connector.submit(
            sku="E2E-SKU",
            payload={"title": "E2E Product", "product_type": str(product_type)},
            idempotency_key="e2e-submit",
        ).remote_id
        == submitted.remote_id
    )
    assert connector.submit_media(submitted.remote_id, media, "e2e-media").status == "succeeded"
    assert (
        connector.submit_variants(submitted.remote_id, variants, "e2e-variants").status
        == "succeeded"
    )
    assert connector.update_price(submitted.remote_id, price, "e2e-price").status == "succeeded"
    assert connector.update_inventory("E2E-SKU", 7)["quantity"] == 7
    assert connector.get_inventory("E2E-SKU")["quantity"] == 7
    assert connector.reconcile_listing(submitted.remote_id)["status"] == "ACTIVE"
    assert str(connector.get_orders()[0]["remote_id"]).startswith("FAKE-AMZ-ORDER")
    fees = connector.get_fees()
    assert fees[0]["type"] == "commission"
    assert fees[0]["currency"] == "INR"
    settlement = connector.get_settlements()[0]
    assert str(settlement["remote_id"]).startswith("fake-settlement-")
    assert Decimal(str(settlement["net"])) == Decimal("1125.00")
    assert connector.get_returns()[0]["status"] == "requested"
    drifted = transport.remote_drift(submitted.remote_id, changes={"title": "Remote title"})
    assert drifted.status == "succeeded"
    assert connector.get_listing(submitted.remote_id)["title"] == "Remote title"
