"""Focused PR-6B explainable synthesis validation."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare

from vayujit_api.intelligence.decision_synthesis_service import (
    map_readiness_to_posture,
    synthesize_from_readiness,
)

pytest_plugins = ["test_pr5b_landed_cost"]
pytestmark = pytest.mark.integration


def _readiness(
    state: str,
    *,
    blockers: list[dict[str, object]] | None = None,
    warnings: list[dict[str, object]] | None = None,
    unknowns: list[dict[str, object]] | None = None,
    contradictions: list[dict[str, object]] | None = None,
    capital_fit: str = "UNKNOWN",
    contribution: str | None = None,
) -> dict[str, Any]:
    return {
        "decision_target": "COMMERCIAL_ASSESSMENT",
        "readiness_state": state,
        "policy_version": "decision-readiness-v1",
        "input_references": {"opportunity_id": "opportunity"},
        "trust_environment": {
            "supplier": {"trust": "DETERMINISTIC_TEST", "verification": "UNVERIFIED"},
            "demand": {"trust": "UNKNOWN", "state": "MISSING"},
        },
        "evidence_summary": {
            "product": {"name": "Fixture product", "category": "kids"},
            "product_selected": True,
            "economics": {
                "capital_fit": capital_fit,
                "positive_contribution": contribution == "positive",
            },
        },
        "blockers": blockers or [],
        "warnings": warnings or [],
        "unknowns": unknowns or [],
        "contradictions": contradictions or [],
        "limitations": ["Selling costs are modeled assumptions."],
    }


def _synthesize(readiness: dict[str, Any]) -> dict[str, Any]:
    return synthesize_from_readiness(
        readiness,
        snapshot_id=uuid.uuid4(),
        opportunity_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
    )


def test_pr6b_posture_mapping_preserves_pr6a_semantics() -> None:
    needs = _readiness(
        "NEEDS_EVIDENCE",
        unknowns=[
            {"code": "DEMAND_EVIDENCE_MISSING", "message": "Demand is unknown", "severity": "INFO"}
        ],
    )
    blocked = _readiness(
        "BLOCKED",
        blockers=[{"code": "ECONOMICS_CALCULATION_REQUIRED", "message": "Complete economics"}],
    )
    needs_with_blocker = _readiness(
        "NEEDS_EVIDENCE",
        blockers=[{"code": "SUPPLIER_NOT_VERIFIED", "message": "Verify supplier"}],
    )
    ready_with_blocker = _readiness(
        "READY",
        blockers=[{"code": "MATERIAL_BLOCKER", "message": "Resolve blocker"}],
    )
    ready = _readiness("READY", contribution="positive", capital_fit="FITS")
    capital = _readiness(
        "BLOCKED",
        capital_fit="DOES_NOT_FIT",
        blockers=[{"code": "CAPITAL_DOES_NOT_FIT", "message": "Capital shortfall"}],
    )

    assert map_readiness_to_posture(needs) == "CONTINUE_RESEARCH"
    assert map_readiness_to_posture(needs_with_blocker) == "HOLD"
    assert map_readiness_to_posture(ready_with_blocker) == "HOLD"
    assert map_readiness_to_posture(blocked) == "HOLD"
    assert map_readiness_to_posture(ready) == "READY_FOR_HUMAN_DECISION"
    assert map_readiness_to_posture(capital) == "CONSTRAINT_FAILED"
    ready_result = _synthesize(ready)
    assert "recommendation" not in ready_result


def test_pr6b_reason_ordering_and_safe_actions_are_deterministic() -> None:
    readiness = _readiness(
        "BLOCKED",
        blockers=[{"code": "ECONOMICS_CALCULATION_REQUIRED", "message": "Economics missing"}],
        contradictions=[
            {"code": "MATERIAL_CONTRADICTION", "message": "Evidence conflicts", "severity": "HIGH"}
        ],
        unknowns=[
            {"code": "DEMAND_EVIDENCE_MISSING", "message": "Demand is unknown", "severity": "INFO"}
        ],
        warnings=[
            {"code": "SUPPLIER_NOT_VERIFIED", "message": "Verify supplier", "severity": "HIGH"}
        ],
    )
    first = _synthesize(readiness)
    second = _synthesize(readiness)
    assert [row["category"] for row in first["reasons"]] == [
        "blocker",
        "contradiction",
        "warning",
        "optional_unknown",
    ]
    assert first["primary_reason"]["code"] == "ECONOMICS_CALCULATION_REQUIRED"
    assert first["safe_next_actions"][0]["external_action"] is False
    assert [row["code"] for row in first["safe_next_actions"]] == [
        row["code"] for row in second["safe_next_actions"]
    ]
    assert first["posture"] == "HOLD"


def test_pr6b_contradiction_missing_and_negative_economics_remain_distinct() -> None:
    contradiction = _synthesize(
        _readiness(
            "BLOCKED",
            contradictions=[
                {"code": "MATERIAL_CONTRADICTION", "message": "Price conflict", "severity": "HIGH"}
            ],
        )
    )
    missing = _synthesize(
        _readiness(
            "NEEDS_EVIDENCE",
            unknowns=[
                {
                    "code": "DEMAND_EVIDENCE_MISSING",
                    "message": "No demand evidence",
                    "severity": "INFO",
                }
            ],
        )
    )
    negative = _readiness("READY", capital_fit="FITS", contribution="negative")
    negative["evidence_summary"]["economics"]["contribution"] = "-10"
    negative_result = _synthesize(negative)
    assert contradiction["posture"] == "HOLD"
    assert contradiction["primary_reason"]["code"] == "MATERIAL_CONTRADICTION"
    assert missing["posture"] == "CONTINUE_RESEARCH"
    assert negative_result["posture"] == "READY_FOR_HUMAN_DECISION"
    assert negative_result["human_review_required"] is True


def test_pr6b_immutable_api_replay_and_decision_brief_projection(pr56_client: TestClient) -> None:
    opportunity_id, _assessment_id = _prepare(pr56_client)
    url = f"/api/v1/intelligence/product-opportunities/{opportunity_id}/decision-synthesis"
    payload = {
        "decision_target": "COMMERCIAL_ASSESSMENT",
        "idempotency_key": "pr6b-synthesis-replay",
    }
    first = _ok(pr56_client.post(url, json=payload, headers=ORIGIN))
    replay = _ok(pr56_client.post(url, json=payload, headers=ORIGIN))
    assert first["id"] == replay["id"]
    assert isinstance(first["id"], str)
    assert isinstance(first["opportunity_id"], str)
    assert isinstance(first["decision_evidence_snapshot_id"], str)
    json.dumps(first)
    assert first["decision_evidence_snapshot_id"]
    assert first["synthesis_policy_version"] == "decision-synthesis-v1"
    assert first["human_review_required"] is True
    assert first["recommendation"] is None
    assert first["external_writes"] == []
    assert all(item["external_action"] is False for item in first["safe_next_actions"])
    history = _ok(pr56_client.get(url + "/history?target=COMMERCIAL_ASSESSMENT", headers=ORIGIN))
    assert len(history) == 1
    brief = _ok(
        pr56_client.get(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/decision-brief",
            headers=ORIGIN,
        )
    )
    assert brief["decision_synthesis"]["id"] == first["id"]
    assert brief["decision_synthesis"]["posture"] in {
        "CONTINUE_RESEARCH",
        "HOLD",
        "READY_FOR_HUMAN_DECISION",
        "CONSTRAINT_FAILED",
    }
