"""WP1 regressions: canonical context identity, not legacy ID substitution."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from test_ai_integration import ORIGIN, setup_context

pytestmark = pytest.mark.integration


def post(client, path, data):
    response = client.post("/api/v1/intelligence/" + path, json=data, headers=ORIGIN)
    assert response.status_code < 300
    return response.json()


def seed(client):
    catalog = setup_context(client)
    op = post(
        client,
        "product-opportunities",
        {
            "name": "[QA SYNTHETIC] Bottle",
            "product_id": catalog["product"]["id"],
            "product_concept": "stainless steel insulated water bottles",
            "category": "Home & Kitchen",
            "target_marketplace": "AMAZON_IN",
            "target_region": "IN",
            "origin": "manual",
            "notes": "DETERMINISTIC_TEST",
            "idempotency_key": "wp1-op",
        },
    )
    result = post(
        client,
        "suppliers/research",
        {
            "product_opportunity_id": op["id"],
            "product_query": "stainless steel insulated water bottles",
            "mode": "LOCAL_FIXTURE",
            "max_candidates": 1,
            "idempotency_key": "wp1-research",
        },
    )
    assert result["result"]["external_calls"] is False
    post(client, "cross-marketplace/suppliers/reconcile", {})
    projected = client.get(
        "/api/v1/intelligence/suppliers/research-results",
        params={"opportunity_id": op["id"]},
        headers=ORIGIN,
    ).json()
    supplier = projected["suppliers"][0]
    assert all(source["synthetic"] for source in supplier["freshness"]["sources"])
    detail = client.get(
        "/api/v1/intelligence/cross-marketplace/suppliers/" + supplier["id"], headers=ORIGIN
    ).json()
    assert all(source["synthetic"] for source in detail["freshness"]["sources"])
    return op, supplier


def payload(op, supplier):
    return {
        "idempotency_key": "wp1-economic",
        "product_opportunity_id": op["id"],
        "canonical_supplier_id": supplier["id"],
        "product_id": op.get("product_id"),
        "base_currency": "INR",
        "target_quantity": "500",
    }


def test_canonical_context_persists_replays_and_rejects_conflicting_replay(client):
    op, supplier = seed(client)
    data = payload(op, supplier)
    created = post(client, "sourcing-economics/contexts", data)["context"]
    assert created["product_opportunity_id"] == op["id"]
    assert created["canonical_supplier_id"] == supplier["id"]
    assert created["opportunity_id"] is None and created["supplier_id"] is None
    assert post(client, "sourcing-economics/contexts", data)["context"]["id"] == created["id"]
    restored = client.get(
        "/api/v1/intelligence/sourcing-economics/contexts/" + created["id"],
        headers=ORIGIN,
    ).json()["context"]
    assert restored["canonical_supplier_id"] == supplier["id"]
    conflict = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={**data, "target_quantity": "501"},
        headers=ORIGIN,
    )
    assert conflict.status_code == 409


@pytest.mark.parametrize("field", ["product_opportunity_id", "canonical_supplier_id"])
def test_unknown_canonical_identity_fails_closed(client, field):
    op, supplier = seed(client)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={**payload(op, supplier), field: str(uuid4())},
        headers=ORIGIN,
    )
    assert response.status_code == 404


def test_unrelated_product_supplier_pair_rejected(client):
    op, supplier = seed(client)
    other = post(
        client,
        "product-opportunities",
        {"name": "[QA SYNTHETIC] Other", "idempotency_key": "wp1-other"},
    )
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json=payload(other, supplier),
        headers=ORIGIN,
    )
    assert response.status_code == 409


def test_archived_product_and_missing_product_rejected(client):
    op, supplier = seed(client)
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={**payload(op, supplier), "product_opportunity_id": None},
        headers=ORIGIN,
    )
    assert response.status_code == 409
    archived = client.patch(
        "/api/v1/intelligence/product-opportunities/" + op["id"],
        json={"lifecycle_status": "archived"},
        headers=ORIGIN,
    )
    assert archived.status_code == 200
    response = client.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json=payload(op, supplier),
        headers=ORIGIN,
    )
    assert response.status_code == 409


def test_concurrent_context_replay_creates_one_context(client):
    op, supplier = seed(client)

    def create(_):
        return client.post(
            "/api/v1/intelligence/sourcing-economics/contexts",
            json=payload(op, supplier),
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create, range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert len({r.json()["context"]["id"] for r in responses}) == 1


def test_assessment_retains_context_unknowns_and_version_history(client):
    op, supplier = seed(client)
    context = post(
        client,
        "supplier-due-diligence/contexts",
        {
            "supplier_id": supplier["id"],
            "opportunity_id": op["id"],
            "idempotency_key": "wp1-dd",
        },
    )
    path = "/api/v1/intelligence/supplier-due-diligence/contexts/" + context["id"]
    initial = client.get(path, headers=ORIGIN).json()
    assert initial["readiness"] == "NOT_ASSESSED" and initial["assessment_version"] == 0
    assert initial["opportunity_id"] == op["id"] and initial["supplier_name"]
    first = client.post(path + "/assess", json={}, headers=ORIGIN).json()
    assert first["assessment_version"] == 1 and first["open_gaps"] > 0
    assert first["readiness"] != "SUFFICIENT"
    second = client.post(path + "/assess", json={}, headers=ORIGIN).json()
    assert second["assessment_version"] == 2
    restored = client.get(path, headers=ORIGIN).json()
    assert restored["supplier_id"] == supplier["id"] and restored["assessment_version"] == 2


def test_invalid_identifiers_and_authentication_are_not_empty_success(client):
    assert (
        client.get(
            "/api/v1/intelligence/sourcing-economics/contexts/" + str(uuid4()),
            headers=ORIGIN,
        ).status_code
        == 401
    )
    seed(client)
    assert (
        client.get(
            "/api/v1/intelligence/sourcing-economics/contexts/not-a-uuid",
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/intelligence/supplier-due-diligence/contexts/" + str(uuid4()) + "/assess",
            json={},
            headers=ORIGIN,
        ).status_code
        == 404
    )
