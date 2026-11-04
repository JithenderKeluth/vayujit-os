"""WP6 bounded validation and preserved monetary projection contracts."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from test_qa_phase3a_remediation import ORIGIN, ctx
from test_seller_wp5 import (
    test_owned_order_lines_and_exact_product_handoff_survive_reload_and_replay as seed_order,
)
from vayujit_api.commerce.schemas import InventoryAdjustmentRequest

pytestmark = pytest.mark.integration
__all__ = ["ctx"]


@pytest.mark.parametrize("delta", [0, -2_000_000_001, 2_000_000_001])
def test_invalid_adjustment_contract_fails_closed(delta):
    with pytest.raises(ValidationError):
        InventoryAdjustmentRequest(
            delta=delta, reason="Synthetic QA", expected_version=1, idempotency_key="wp6"
        )


@pytest.mark.parametrize("delta", [-2_000_000_000, -1, 1, 2_000_000_000])
def test_nonzero_adjustment_contract_keeps_signed_bounds(delta):
    value = InventoryAdjustmentRequest(
        delta=delta, reason="Synthetic QA", expected_version=1, idempotency_key="wp6"
    )
    assert value.delta == delta


def test_zero_adjustment_api_does_not_change_inventory_or_version(ctx):
    client = ctx["client"]
    before = client.get("/api/v1/inventory").json()
    response = client.post(
        f"/api/v1/inventory/{ctx['item']['id']}/adjust",
        json={
            "delta": 0,
            "reason": "Synthetic QA",
            "expected_version": 1,
            "idempotency_key": "wp6-zero",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 422
    assert client.get("/api/v1/inventory").json() == before


def test_subpaise_source_line_is_not_reconstructed_from_rounded_projection(ctx):
    seed_order(ctx)
    order = ctx["client"].get("/api/v1/orders").json()[0]
    value = ctx["client"].get("/api/v1/orders/" + order["id"]).json()
    line = value["lines"][0]
    assert Decimal(line["unit_price"]) == Decimal("100.13")
    assert Decimal(line["total_price"]) == Decimal("200.25")
    assert Decimal(line["unit_price"]) * line["quantity"] != Decimal(line["total_price"])
    assert value["provenance_status"] == "SYNTHETIC"
