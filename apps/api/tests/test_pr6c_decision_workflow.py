"""Focused deterministic PR-6C recommendation and human-decision validation."""

from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare

from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user

pytest_plugins = ["test_pr5b_landed_cost"]
pytestmark = pytest.mark.integration


def test_recommendation_is_advisory_and_human_decision_is_explicit(
    pr56_client: TestClient,
) -> None:
    client = pr56_client
    opportunity_id, _assessment_id = _prepare(client)
    recommendation_url = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/recommendation-assessment"
    )
    first = _ok(
        client.post(
            recommendation_url,
            json={"decision_target": "COMMERCIAL_ASSESSMENT", "idempotency_key": "pr6c-rec"},
            headers=ORIGIN,
        )
    )
    replay = _ok(
        client.post(
            recommendation_url,
            json={"decision_target": "COMMERCIAL_ASSESSMENT", "idempotency_key": "pr6c-rec-2"},
            headers=ORIGIN,
        )
    )
    assert first["id"] == replay["id"]
    assert first["recommendation_state"] == "NOT_ELIGIBLE"
    assert first["human_review_required"] is True
    assert first["external_writes"] == []
    assert "probability" not in str(first).lower()

    brief = _ok(
        client.get(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/decision-brief",
            headers=ORIGIN,
        )
    )
    assert brief["recommendation"]["id"] == first["id"]
    assert brief["human_decision"] is None

    decision_url = f"/api/v1/intelligence/product-opportunities/{opportunity_id}/human-decision"
    keep = _ok(
        client.post(
            decision_url,
            json={
                "decision_target": "COMMERCIAL_ASSESSMENT",
                "decision": "KEEP_UNDER_REVIEW",
                "recommendation_id": first["id"],
                "synthesis_id": first["synthesis_id"],
                "reason": "Review the missing evidence first.",
                "idempotency_key": "pr6c-human-keep",
            },
            headers=ORIGIN,
        )
    )
    assert keep["decision"] == "KEEP_UNDER_REVIEW"
    assert keep["provenance"] == "HUMAN"
    assert keep["actor_id"] == keep["owner_id"]
    repeated = _ok(
        client.post(
            decision_url,
            json={
                "decision_target": "COMMERCIAL_ASSESSMENT",
                "decision": "KEEP_UNDER_REVIEW",
                "recommendation_id": first["id"],
                "synthesis_id": first["synthesis_id"],
                "reason": "Review the missing evidence first.",
                "idempotency_key": "pr6c-human-keep",
            },
            headers=ORIGIN,
        )
    )
    assert repeated["id"] == keep["id"]
    history = _ok(client.get(decision_url + "/history", headers=ORIGIN))
    assert len(history) == 1
    changed = _ok(
        client.post(
            decision_url,
            json={
                "decision_target": "COMMERCIAL_ASSESSMENT",
                "decision": "DO_NOT_PROCEED",
                "recommendation_id": first["id"],
                "synthesis_id": first["synthesis_id"],
                "reason": "Do not continue this bounded scenario.",
                "idempotency_key": "pr6c-human-stop",
            },
            headers=ORIGIN,
        )
    )
    assert changed["decision"] == "DO_NOT_PROCEED"
    assert changed["supersedes_decision_id"] == keep["id"]
    assert len(_ok(client.get(decision_url + "/history", headers=ORIGIN))) == 2


def test_recommendation_blocks_proceed_and_owner_scope_is_enforced(
    pr56_client: TestClient,
) -> None:
    client = pr56_client
    opportunity_id, _assessment_id = _prepare(client)
    recommendation = _ok(
        client.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/recommendation-assessment",
            json={"decision_target": "COMMERCIAL_ASSESSMENT"},
            headers=ORIGIN,
        )
    )
    decision = client.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/human-decision",
        json={
            "decision_target": "COMMERCIAL_ASSESSMENT",
            "decision": "PROCEED",
            "recommendation_id": recommendation["id"],
            "idempotency_key": "pr6c-proceed-blocked",
        },
        headers=ORIGIN,
    )
    assert decision.status_code == 409

    app = cast(FastAPI, client.app)
    other = User(email="pr6c-other@example.com", full_name="Other PR-6C")
    app.dependency_overrides[current_user] = lambda: other
    try:
        assert (
            client.get(
                f"/api/v1/intelligence/product-opportunities/{opportunity_id}/recommendation-assessment/latest",
                headers=ORIGIN,
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/intelligence/product-opportunities/{opportunity_id}/human-decision",
                json={
                    "decision_target": "COMMERCIAL_ASSESSMENT",
                    "decision": "KEEP_UNDER_REVIEW",
                    "recommendation_id": recommendation["id"],
                    "idempotency_key": "pr6c-cross-owner",
                },
                headers=ORIGIN,
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides.pop(current_user)


def test_system_cannot_claim_human_provenance(pr56_client: TestClient) -> None:
    client = pr56_client
    opportunity_id, _assessment_id = _prepare(client)
    recommendation = _ok(
        client.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/recommendation-assessment",
            json={"decision_target": "COMMERCIAL_ASSESSMENT"},
            headers=ORIGIN,
        )
    )
    response = client.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/human-decision",
        json={
            "decision_target": "COMMERCIAL_ASSESSMENT",
            "decision": "KEEP_UNDER_REVIEW",
            "recommendation_id": recommendation["id"],
            "idempotency_key": "pr6c-system-provenance",
            "provenance": "AI",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 422


def test_journey_decision_brief_uses_requested_goal_context(
    pr56_client: TestClient,
) -> None:
    """A brief opened from a journey must not borrow the owner's latest goal budget."""
    client = pr56_client
    opportunity_id, _assessment_id = _prepare(client)

    first_goal = _ok(
        client.post(
            "/api/v1/intelligence/business-agent/goals",
            json={
                "raw_goal": "Evaluate a kids product with an INR 300000 budget.",
                "structured_goal": {"marketplace": "AMAZON_IN", "capital": 300000},
                "idempotency_key": "pr6c-context-goal-one",
            },
            headers=ORIGIN,
        )
    )
    second_goal = _ok(
        client.post(
            "/api/v1/intelligence/business-agent/goals",
            json={
                "raw_goal": "Evaluate a home product with an INR 5000 budget.",
                "structured_goal": {"marketplace": "AMAZON_IN", "capital": 5000},
                "idempotency_key": "pr6c-context-goal-two",
            },
            headers=ORIGIN,
        )
    )
    for goal, budget in ((first_goal, 300000), (second_goal, 5000)):
        confirmed = _ok(
            client.post(
                f"/api/v1/commerce-journeys/{goal['id']}/context-confirmation",
                json={
                    "confirmed": True,
                    "marketplace": "AMAZON_IN",
                    "budget_amount": budget,
                    "currency": "INR",
                },
                headers=ORIGIN,
            )
        )
        assert confirmed["confirmed"] is True

    first_brief = _ok(
        client.get(
            f"/api/v1/commerce-journeys/{first_goal['id']}/decision-brief"
            f"?opportunity_id={opportunity_id}",
            headers=ORIGIN,
        )
    )
    second_brief = _ok(
        client.get(
            f"/api/v1/commerce-journeys/{second_goal['id']}/decision-brief"
            f"?opportunity_id={opportunity_id}",
            headers=ORIGIN,
        )
    )
    assert float(first_brief["budget_fit"]["budget"]) == 300000
    assert float(second_brief["budget_fit"]["budget"]) == 5000
    assert first_brief["goal"]["provenance"] == "USER_PROVIDED"
    assert second_brief["goal"]["provenance"] == "USER_PROVIDED"
