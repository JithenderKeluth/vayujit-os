"""WP2 persisted current-intent, catalog lineage and truthful research projections."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from test_ai_integration import setup_context

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://127.0.0.1:4200"}
BASE = "/api/v1/intelligence/product-opportunities"


def post(client, path, payload):
    response = client.post(path, json=payload, headers=ORIGIN)
    assert response.status_code in (200, 201), response.text
    return response.json()


def seed(client):
    catalog = setup_context(client)
    op = post(
        client,
        BASE,
        {
            "name": "[QA SYNTHETIC] WP2 Bottle",
            "description": "Manual synthetic QA only.",
            "product_concept": "Bottle",
            "category": "Kids",
            "origin": "manual",
            "idempotency_key": "wp2-op",
        },
    )
    constraint = post(
        client, f"{BASE}/{op['id']}/constraints", {"currency": "INR", "idempotency_key": "wp2-c"}
    )
    assessment = post(
        client,
        f"{BASE}/{op['id']}/assessments",
        {
            "constraint_version_id": constraint["id"],
            "evidence_state": "insufficient_evidence",
            "input_snapshot": {"evidence_environment": "DETERMINISTIC_TEST"},
            "idempotency_key": "wp2-a",
        },
    )
    post(client, f"{BASE}/{op['id']}/assessments/{assessment['id']}/score", {})
    return op, assessment, catalog


def decision(client, op, assessment, action, key=None):
    return post(
        client,
        f"{BASE}/{op['id']}/assessments/{assessment['id']}/decision",
        {
            "action": action,
            "rationale": "HUMAN synthetic QA " + action,
            **({"idempotency_key": key} if key else {}),
        },
    )


def test_empty_projection_is_not_an_executed_research_run(client):
    setup_context(client)
    projection = client.get(BASE + "/research-results", headers=ORIGIN).json()
    assert projection["research_execution"] == {"run_count": 0, "latest_status": None}
    assert projection["candidates"] == []


def test_reject_revokes_selection_and_conversion_reselect_preserves_history(client):
    op, assessment, catalog = seed(client)
    first = decision(client, op, assessment, "shortlist")
    assert decision(client, op, assessment, "shortlist")["id"] == first["id"]
    decision(client, op, assessment, "reject")
    projected = client.get(BASE + "/research-results", headers=ORIGIN).json()
    assert op["id"] not in projected["selected_candidate_ids"]
    assert projected["candidates"][0]["decision"]["action"] == "reject"
    path = f"/api/v1/catalog/opportunities/{op['id']}/convert"
    assert (
        client.post(path, json={"brand_id": catalog["brand"]["id"]}, headers=ORIGIN).status_code
        == 409
    )
    revised = decision(client, op, assessment, "shortlist")
    assert revised["id"] != first["id"]
    history = client.get(f"{BASE}/{op['id']}/decisions", headers=ORIGIN).json()
    assert [item["action"] for item in history] == ["shortlist", "reject", "shortlist"]
    result = post(client, path, {"brand_id": catalog["brand"]["id"]})
    assert (
        post(client, path, {"brand_id": catalog["brand"]["id"]})["product"]["id"]
        == result["product"]["id"]
    )
    assert result["lineage"]["assessment_id"] == assessment["id"]
    assert result["product"]["price_amount"] is None


def test_explicit_replay_conflict_and_stale_assessment_fail_closed(client):
    op, a, _ = seed(client)
    first = decision(client, op, a, "shortlist", "wp2-replay")
    assert decision(client, op, a, "shortlist", "wp2-replay")["id"] == first["id"]
    path = f"{BASE}/{op['id']}/assessments/{a['id']}/decision"
    assert (
        client.post(
            path,
            json={"action": "reject", "rationale": "Different", "idempotency_key": "wp2-replay"},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    post(
        client,
        f"{BASE}/{op['id']}/assessments",
        {
            "evidence_state": "insufficient_evidence",
            "input_snapshot": {"changed": True},
            "idempotency_key": "wp2-new-a",
        },
    )
    assert (
        client.post(
            path, json={"action": "reject", "rationale": "Stale review"}, headers=ORIGIN
        ).status_code
        == 409
    )
    assert (
        op["id"]
        not in client.get(BASE + "/research-results", headers=ORIGIN).json()[
            "selected_candidate_ids"
        ]
    )


def test_concurrent_conversion_is_one_atomic_product_and_lineage(client):
    op, a, catalog = seed(client)
    decision(client, op, a, "shortlist")

    def convert(_):
        return client.post(
            f"/api/v1/catalog/opportunities/{op['id']}/convert",
            json={"brand_id": catalog["brand"]["id"]},
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(convert, range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert len({r.json()["product"]["id"] for r in responses}) == 1
    # Public lineage omits its internal ID; independently assert the persisted row count.
    from sqlalchemy import func, select
    from test_ai_integration import factory

    from vayujit_api.catalog.models import CatalogProductLineage

    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CatalogProductLineage)
                .where(CatalogProductLineage.opportunity_id == op["id"])
            )
            == 1
        )


def test_decision_history_auth_unknown_and_invalid_identity(client):
    assert client.get(f"{BASE}/{uuid4()}/decisions", headers=ORIGIN).status_code == 401
    seed(client)
    assert client.get(f"{BASE}/{uuid4()}/decisions", headers=ORIGIN).status_code == 404
    assert client.get(f"{BASE}/not-a-uuid/decisions", headers=ORIGIN).status_code == 422


def test_scoped_goal_projection_never_substitutes_another_goal(client):
    op, _, _ = seed(client)
    goal = post(
        client,
        "/api/v1/intelligence/business-agent/goals",
        {
            "raw_goal": "Find products in kids category with INR 300000.",
            "structured_goal": {"category": "Kids", "product_opportunity_id": op["id"]},
            "idempotency_key": "wp2-goal",
        },
    )
    second = post(
        client,
        "/api/v1/intelligence/business-agent/goals",
        {
            "raw_goal": "Find products in kitchen category with INR 300000.",
            "structured_goal": {"category": "Kitchen"},
            "idempotency_key": "wp2-other-goal",
        },
    )
    result = client.get(
        BASE + "/research-results", params={"goal_id": goal["id"]}, headers=ORIGIN
    ).json()
    assert result["active_goal_id"] == goal["id"] and result["candidates"][0]["id"] == op["id"]
    assert (
        client.get(
            BASE + "/research-results", params={"goal_id": second["id"]}, headers=ORIGIN
        ).json()["candidates"]
        == []
    )


def test_conversion_rejects_unrelated_goal_even_when_product_is_selected(client):
    op, assessment, catalog = seed(client)
    decision(client, op, assessment, "shortlist")
    goal = post(
        client,
        "/api/v1/intelligence/business-agent/goals",
        {
            "raw_goal": "Find kitchen products with INR 300000.",
            "structured_goal": {"product_opportunity_id": str(uuid4())},
            "idempotency_key": "wp2-unrelated-goal",
        },
    )
    response = client.post(
        f"/api/v1/catalog/opportunities/{op['id']}/convert",
        json={"brand_id": catalog["brand"]["id"], "goal_id": goal["id"]},
        headers=ORIGIN,
    )
    assert response.status_code == 409
    assert "another product" in response.json()["detail"]


def test_concurrent_identical_human_decision_has_one_durable_identity(client):
    op, assessment, _ = seed(client)

    def decide(_):
        return client.post(
            f"{BASE}/{op['id']}/assessments/{assessment['id']}/decision",
            json={
                "action": "shortlist",
                "rationale": "Concurrent synthetic HUMAN review",
                "idempotency_key": "wp2-concurrent-decision",
            },
            headers=ORIGIN,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(decide, range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    assert len({r.json()["id"] for r in responses}) == 1
    assert len(client.get(f"{BASE}/{op['id']}/decisions", headers=ORIGIN).json()) == 1
