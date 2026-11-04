"""WP3 verifies existing authorities; synthetic disposable PostgreSQL only."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from test_ai_integration import ORIGIN, setup_context
from test_seller_wp1 import payload, post, seed

pytestmark = pytest.mark.integration


def test_manual_catalog_product_has_no_fabricated_opportunity_but_supports_known_cost_context(
    client,
):
    catalog = setup_context(client)
    product_id = catalog["product"]["id"]
    projection = client.get(f"/api/v1/catalog/products/{product_id}/economics").json()
    assert projection["available"] is False and projection.get("opportunity_id") is None
    request = {
        "product_id": product_id,
        "base_currency": "INR",
        "target_quantity": "10",
        "quantity_unit": "unit",
        "idempotency_key": "wp3-manual-known-cost",
    }
    context = post(client, "sourcing-economics/contexts", request)["context"]
    assert context["product_id"] == product_id
    assert context["product_opportunity_id"] is None
    assert context["canonical_supplier_id"] is None
    replay = post(client, "sourcing-economics/contexts", request)
    assert replay["context"]["id"] == context["id"] and replay["idempotent_reuse"]
    snapshot = post(client, f"sourcing-economics/snapshots?context_id={context['id']}", {})
    calculated = post(
        client, f"sourcing-economics/snapshots/{snapshot['snapshot']['id']}/calculate", {}
    )["calculation"]
    assert calculated["missing_inputs"]
    assert calculated["per_unit_cost"] is None  # Empty subtotal is not free inventory.
    assert Decimal(calculated["total_included_cost"]) == 0
    assert (
        client.get(f"/api/v1/catalog/products/{product_id}/economics").json()["available"] is False
    )


def test_supplier_scope_cannot_reuse_unrelated_saved_economics_or_legacy_ids(client):
    op, supplier = seed(client)
    scoped = post(client, "sourcing-economics/contexts", payload(op, supplier))["context"]
    other = post(
        client,
        "product-opportunities",
        {"name": "[QA SYNTHETIC] Other", "idempotency_key": "wp3-other"},
    )
    response = client.get(
        f"/api/v1/intelligence/product-opportunities/{other['id']}/decision-brief",
        params={"economic_context_id": scoped["id"]},
    )
    assert response.status_code in {404, 409}
    missing = client.get(f"/api/v1/intelligence/sourcing-economics/contexts/{uuid4()}")
    assert missing.status_code == 404


def test_empty_economics_brief_has_stable_collections_without_fabricating_calculations(client):
    op, supplier = seed(client)
    path = f"/api/v1/intelligence/product-opportunities/{op['id']}/decision-brief"
    empty = client.get(path)
    assert empty.status_code == 200
    context = post(client, "sourcing-economics/contexts", payload(op, supplier))["context"]
    scoped = client.get(path, params={"economic_context_id": context["id"]})
    assert scoped.status_code == 200
    for response in (empty, scoped):
        economics = response.json()["economics"]
        assert economics["scenario_comparisons"] == []
        assert economics["calculation"] is None and economics["unit_economics"] is None
        assert economics["readiness"] == "NOT_EVALUATED"
        assert economics["research_gaps"]
    assert scoped.json()["economics"]["canonical_supplier_id"] == supplier["id"]


def test_shortlist_summary_is_a_persisted_projection_not_an_optimistic_counter(client):
    op, supplier = seed(client)
    context = post(
        client,
        "supplier-shortlisting/contexts",
        {"opportunity_id": op["id"], "idempotency_key": "wp3-shortlist-context"},
    )
    shortlist = post(
        client,
        f"supplier-shortlisting/contexts/{context['id']}/shortlists",
        {
            "context_version": 1,
            "top_n": 5,
            "model_version": "shortlisting-v1",
            "idempotency_key": "wp3-shortlist-evaluate",
        },
    )
    decision = {
        "shortlist_version_id": shortlist["id"],
        "supplier_id": supplier["id"],
        "decision": "KEEP_UNDER_REVIEW",
        "reason": "Explicit synthetic HUMAN review only.",
        "evidence_ids": [],
        "decision_key": "wp3-shortlist-human",
    }
    first = post(client, f"supplier-shortlisting/contexts/{context['id']}/decisions", decision)
    second = post(client, f"supplier-shortlisting/contexts/{context['id']}/decisions", decision)
    assert first["id"] == second["id"]
    metrics = client.get("/api/v1/intelligence/supplier-shortlisting/operations").json()
    assert metrics["active_contexts"] == 1 and metrics["shortlist_count"] == 1
    assert metrics["integrity"]["decision_count"] == 1
    assert metrics["handoff_count"] == 0  # Shortlist is not supplier contact or procurement.


def quote_fixture(client):
    op, supplier = seed(client)
    detail = client.get(f"/api/v1/intelligence/cross-marketplace/suppliers/{supplier['id']}").json()
    source_id = detail["identity"]["supplier_ids"][0]
    requirement_data = {
        "product_id": op["product_id"],
        "opportunity_id": None,
        "idempotency_key": "wp3-local-requirement",
        "payload": {"target_quantity": 10},
    }
    requirement = post(client, "sourcing/requirements", requirement_data)["requirement"]
    rfq_data = {
        "requirement_id": requirement["id"],
        "requirement_version": 1,
        "supplier_ids": [source_id],
        "title": "[QA SYNTHETIC] Local draft, never send",
        "payload": {},
        "idempotency_key": "wp3-local-rfq",
    }
    rfq = post(client, "sourcing/rfqs", rfq_data)["rfq"]
    assert rfq["dispatch_status"] == "not_sent" and rfq["approved_at"] is None
    quote = {
        "rfq_id": rfq["id"],
        "supplier_id": source_id,
        "quote_reference": "[QA SYNTHETIC] Hypothetical quotation",
        "currency": "INR",
        "unit_price": 100.125,
        "moq": 10,
        "payload": {"evidence_environment": "DETERMINISTIC_TEST", "verification": "UNVERIFIED"},
        "evidence_refs": [],
        "lines": [],
        "idempotency_key": "wp3-local-quote",
    }
    return requirement_data, rfq_data, quote


def test_local_quote_identity_response_envelopes_replay_conflict_and_revision(client):
    req, rfq, data = quote_fixture(client)
    assert post(client, "sourcing/requirements", req)["idempotent_reuse"]
    assert post(client, "sourcing/rfqs", rfq)["idempotent_reuse"]
    for path, changed in (
        ("requirements", {**req, "payload": {"target_quantity": 11}}),
        ("rfqs", {**rfq, "title": "Conflicting title"}),
    ):
        assert (
            client.post(
                f"/api/v1/intelligence/sourcing/{path}", json=changed, headers=ORIGIN
            ).status_code
            == 409
        )
    created = post(client, "sourcing/quotes", data)
    assert created["supplier_id"] == data["supplier_id"] and created["version"] == 1
    assert post(client, "sourcing/quotes", data)["id"] == created["id"]
    assert (
        client.post(
            "/api/v1/intelligence/sourcing/quotes", json={**data, "unit_price": 101}, headers=ORIGIN
        ).status_code
        == 409
    )
    revised = post(
        client,
        "sourcing/quotes",
        {**data, "idempotency_key": "wp3-local-quote-v2", "unit_price": 101},
    )
    assert revised["version"] == 2 and revised["id"] != created["id"]
    saved = client.get(f"/api/v1/intelligence/sourcing/quotes/{created['id']}").json()
    assert saved["unit_price"] == 100.125 and saved["payload"]["verification"] == "UNVERIFIED"
    assert (
        client.get(f"/api/v1/intelligence/sourcing/rfqs/{data['rfq_id']}").json()["dispatch_status"]
        == "not_sent"
    )


def test_concurrent_identical_local_quote_creates_one_immutable_version(client):
    _, _, data = quote_fixture(client)

    def submit(_):
        return client.post("/api/v1/intelligence/sourcing/quotes", json=data, headers=ORIGIN)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert [r.status_code for r in results] == [201, 201]
    assert len({r.json()["id"] for r in results}) == 1
    assert {r.json()["version"] for r in results} == {1}


def test_local_quote_missing_unknown_supplier_stale_requirement_and_currency_mismatch(client):
    req, rfq, data = quote_fixture(client)
    assert (
        client.post(
            "/api/v1/intelligence/sourcing/quotes",
            json={**data, "supplier_id": str(uuid4())},
            headers=ORIGIN,
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/intelligence/sourcing/quotes",
            json={**data, "unit_price": None},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/intelligence/sourcing/quotes", json={**data, "moq": 0}, headers=ORIGIN
        ).status_code
        == 422
    )
    post(client, "sourcing/quotes", data)
    post(client, "sourcing/quotes", {**data, "currency": "USD", "idempotency_key": "wp3-usd"})
    comparison = client.get(f"/api/v1/intelligence/sourcing/rfqs/{data['rfq_id']}/compare").json()
    assert comparison["comparable"] is False
    versioned = client.post(
        f"/api/v1/intelligence/sourcing/requirements/{rfq['requirement_id']}/versions",
        json={"payload": {"target_quantity": 11}},
        headers=ORIGIN,
    )
    assert versioned.status_code < 300
    assert (
        client.post(
            "/api/v1/intelligence/sourcing/rfqs",
            json={**rfq, "idempotency_key": "wp3-stale"},
            headers=ORIGIN,
        ).status_code
        == 409
    )
