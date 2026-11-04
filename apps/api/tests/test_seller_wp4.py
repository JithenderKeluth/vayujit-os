"""WP4: canonical local Product, assumption, media and listing boundaries only."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from test_ai_integration import setup_context

pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
ECON = "/api/v1/intelligence/sourcing-economics"


def post(client, path, data):
    response = client.post(path, json=data, headers=ORIGIN)
    assert response.status_code in (200, 201), response.text
    return response.json()


def scenario(client, product, key="wp4-cost", price="100.125"):
    context = post(
        client,
        ECON + "/contexts",
        {
            "product_id": product["id"],
            "base_currency": "INR",
            "target_quantity": "12",
            "quantity_unit": "each",
            "idempotency_key": key,
        },
    )["context"]
    data = {
        "context_id": context["id"],
        "product_id": product["id"],
        "idempotency_key": key + "-input",
        "unit_price": price,
        "currency": "INR",
        "unit_basis": "PER_UNIT",
        "provenance": "ASSUMED",
        "freshness": "UNKNOWN",
        "assumption_reason": "Synthetic QA assumption, not supplier evidence.",
    }
    return context, data


def calculate(client, context_id):
    snapshot = post(client, ECON + f"/snapshots?context_id={context_id}", {})["snapshot"]
    return post(client, ECON + f"/snapshots/{snapshot['id']}/calculate", {})["calculation"]


def test_manual_cost_estimate_preserves_precision_unknowns_and_no_fake_lineage(client):
    product = setup_context(client)["product"]
    context, data = scenario(client, product)
    quote = post(client, ECON + "/quotes", data)["quote"]
    assert quote["provenance"] == "ASSUMED" and quote["freshness"] == "UNKNOWN"
    result = calculate(client, context["id"])
    assert Decimal(result["total_included_cost"]) == Decimal("1201.50000000")
    assert Decimal(result["per_unit_cost"]) == Decimal("100.12500000")
    assert result["status"] == "PARTIAL" and "FREIGHT" in result["missing_inputs"]
    assert result["warnings"]
    reload = client.get(ECON + "/calculations/" + result["id"]).json()
    assert reload["calculation"] == result
    assert reload["exact_amounts"]["per_unit_cost"] == "100.12500000"
    assert reload["exact_amounts"]["total_included_cost"] == "1201.50000000"
    detail = client.get(f"/api/v1/catalog/products/{product['id']}").json()
    assert detail["lineage"] is None
    assert not detail["supplier_associations"]
    assert context["product_opportunity_id"] is None and context["canonical_supplier_id"] is None
    assert client.get("/api/v1/inventory").json() == []
    assert client.get("/api/v1/marketplaces/accounts").json() == []


def test_material_cost_changes_are_distinct_historical_scenarios(client):
    product = setup_context(client)["product"]
    first, data = scenario(client, product)
    post(client, ECON + "/quotes", data)
    old = calculate(client, first["id"])
    second, changed = scenario(client, product, "wp4-new-cost", "200.5")
    post(client, ECON + "/quotes", changed)
    current = calculate(client, second["id"])
    assert current["context_id"] != old["context_id"]
    assert Decimal(current["per_unit_cost"]) == Decimal("200.5")
    assert client.get(ECON + "/calculations/" + old["id"]).json()["calculation"] == old
    assert current["status"] == "PARTIAL"  # Not a new READY declaration.


def test_exact_cost_projection_does_not_round_away_subcent_decimal_lineage(client):
    product = setup_context(client)["product"]
    context, data = scenario(client, product, "wp4-exact-decimal", "9999999999.00000001")
    post(client, ECON + "/quotes", data)
    result = calculate(client, context["id"])
    exact = client.get(ECON + "/calculations/" + result["id"]).json()["exact_amounts"]
    assert exact["per_unit_cost"] == "9999999999.00000001"
    assert exact["total_included_cost"] == "119999999988.00000012"
    assert exact["target_quantity"] == "12.00000000"


def test_identical_cost_replay_does_not_duplicate_and_changed_key_conflicts(client):
    product = setup_context(client)["product"]
    context, data = scenario(client, product)
    first = post(client, ECON + "/quotes", data)
    replay = post(client, ECON + "/quotes", data)
    assert replay["quote"]["id"] == first["quote"]["id"] and replay["idempotent_reuse"]
    changed = client.post(ECON + "/quotes", json={**data, "unit_price": "200"}, headers=ORIGIN)
    assert changed.status_code == 409
    assert len(client.get(ECON + "/contexts/" + context["id"]).json()["quotes"]) == 1


def test_concurrent_identical_cost_input_and_snapshot_are_single_records(client):
    product = setup_context(client)["product"]
    context, data = scenario(client, product)
    with ThreadPoolExecutor(max_workers=3) as pool:
        quotes = list(pool.map(lambda _: post(client, ECON + "/quotes", data), range(3)))
    assert len({q["quote"]["id"] for q in quotes}) == 1
    with ThreadPoolExecutor(max_workers=3) as pool:
        snapshots = list(
            pool.map(
                lambda _: post(client, ECON + f"/snapshots?context_id={context['id']}", {}),
                range(3),
            )
        )
    assert len({s["snapshot"]["id"] for s in snapshots}) == 1


@pytest.mark.parametrize("value", [None, "0"])
def test_missing_cost_is_not_zero_but_explicit_zero_is_retained(client, value):
    product = setup_context(client)["product"]
    context, data = scenario(client, product, price=value)
    post(client, ECON + "/quotes", data)
    result = calculate(client, context["id"])
    if value is None:
        assert result["per_unit_cost"] is None and "PRODUCT_COST" in result["missing_inputs"]
    else:
        assert Decimal(result["per_unit_cost"]) == 0
    assert result["status"] != "COMPLETE"


def test_cost_requires_real_lineage_to_claim_quoted_provenance_and_product_match(client):
    catalog = setup_context(client)
    product = catalog["product"]
    context, data = scenario(client, product)
    assert (
        client.post(
            ECON + "/quotes", json={**data, "provenance": "QUOTED"}, headers=ORIGIN
        ).status_code
        == 422
    )
    other = post(
        client,
        "/api/v1/products",
        {
            "name": "[QA SYNTHETIC] Other",
            "brand_id": product["brand_id"],
            "product_type": "physical",
        },
    )
    assert (
        client.post(
            ECON + "/quotes", json={**data, "product_id": other["id"]}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert client.get(ECON + f"/contexts/{uuid4()}").status_code == 404


def test_listing_missing_fields_block_human_review_and_edit_invalidates_it(client):
    product = setup_context(client)["product"]
    path = f"/api/v1/catalog/products/{product['id']}"
    draft = post(client, path + "/listing-drafts", {"channel": "amazon_in"})
    assert draft["missing_fields"]
    base = "/api/v1/catalog/listing-drafts/" + draft["id"]
    assert (
        client.post(
            base + "/review",
            json={"version": draft["version"], "decision": "approve"},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    # Persist actual local product information, not a claim of marketplace authorization.
    edited = client.patch(
        base,
        json={
            "version": draft["version"],
            "title": product["name"],
            "description": "Synthetic local catalog description",
            "category": "Home",
            "image_refs": ["seller-upload://synthetic-local-test"],
            "intended_price_amount": "250",
            "intended_currency": "INR",
            "compliance": {"synthetic_review": True},
        },
        headers=ORIGIN,
    )
    assert edited.status_code == 200, edited.text
    ready = edited.json()
    if "sku" in ready["missing_fields"]:
        variant = post(
            client, path + "/variants", {"variant_key": "default", "sku": "QA-WP4-DEFAULT"}
        )
        assert variant["sku"] == "QA-WP4-DEFAULT"
        ready = client.patch(
            base, json={"version": ready["version"], "title": product["name"]}, headers=ORIGIN
        ).json()
    assert not ready["missing_fields"]
    reviewed = post(client, base + "/review", {"version": ready["version"], "decision": "approve"})
    assert reviewed["human_review_state"] == "approved"
    changed = client.patch(
        base, json={"version": reviewed["version"], "intended_price_amount": "275"}, headers=ORIGIN
    )
    assert changed.status_code == 200 and changed.json()["human_review_state"] != "approved"
    assert not client.get("/api/v1/marketplaces/listings").json()


def test_variant_stale_edits_and_duplicate_identity_fail_closed(client):
    product = setup_context(client)["product"]
    path = f"/api/v1/catalog/products/{product['id']}/variants"
    data = {"variant_key": "blue", "sku": "QA-WP4-BLUE", "title": "Blue"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(path, json=data, headers=ORIGIN), range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    variant = next(r.json() for r in responses if r.status_code == 201)
    edit = {
        "version": variant["version"],
        "variant_key": variant["variant_key"],
        "title": "Blue updated",
        "price_amount": "250.5",
        "currency": "INR",
    }
    url = "/api/v1/catalog/variants/" + variant["id"]
    assert client.patch(url, json=edit, headers=ORIGIN).status_code == 200
    assert client.patch(url, json=edit, headers=ORIGIN).status_code == 409
