"""Focused PR-6A decision evidence/readiness validation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare

pytest_plugins = ["test_pr5b_landed_cost"]
pytestmark = pytest.mark.integration


def test_pr6a_target_policy_snapshot_replay_and_truthful_gaps(pr56_client: TestClient) -> None:
    opportunity_id, _assessment_id = _prepare(pr56_client)
    url = f"/api/v1/intelligence/product-opportunities/{opportunity_id}/decision-readiness"
    payload = {
        "decision_target": "COMMERCIAL_ASSESSMENT",
        "idempotency_key": "pr6a-commercial-replay",
    }
    first = _ok(pr56_client.post(url, json=payload, headers=ORIGIN))
    assert first["decision_target"] == "COMMERCIAL_ASSESSMENT"
    assert first["readiness_state"] in {"NEEDS_EVIDENCE", "BLOCKED"}
    assert first["policy_version"] == "decision-readiness-v1"
    assert first["recommendation"] is None
    assert first["external_writes"] == []
    assert any(item["code"] == "DEMAND_EVIDENCE_MISSING" for item in first["unknowns"])
    assert first["trust_environment"]["demand"]["trust"] == "UNKNOWN"
    replay = _ok(pr56_client.post(url, json=payload, headers=ORIGIN))
    assert replay["id"] == first["id"]
    assert replay["input_fingerprint"] == first["input_fingerprint"]
    history = _ok(pr56_client.get(url + "/history?target=COMMERCIAL_ASSESSMENT", headers=ORIGIN))
    assert len(history) == 1


def test_pr6a_launch_target_does_not_turn_positive_or_missing_data_into_approval(
    pr56_client: TestClient,
) -> None:
    opportunity_id, _assessment_id = _prepare(pr56_client)
    url = f"/api/v1/intelligence/product-opportunities/{opportunity_id}/decision-readiness"
    launch = _ok(
        pr56_client.post(
            url,
            json={"decision_target": "LAUNCH_DECISION", "idempotency_key": "pr6a-launch"},
            headers=ORIGIN,
        )
    )
    assert launch["readiness_state"] == "BLOCKED"
    codes = {item["code"] for item in launch["blockers"]}
    assert "DEMAND_EVIDENCE_REQUIRED" in codes
    assert launch["recommendation"] is None
    assert launch["safe_next_action"]["external_action"] is False


def test_pr6a_decision_brief_projects_canonical_readiness_without_replacing_legacy(
    pr56_client: TestClient,
) -> None:
    opportunity_id, _assessment_id = _prepare(pr56_client)
    brief = _ok(
        pr56_client.get(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/decision-brief",
            headers=ORIGIN,
        )
    )
    assert brief["decision_target"] == "COMMERCIAL_ASSESSMENT"
    assert brief["decision_readiness_state"] in {"READY", "NEEDS_EVIDENCE", "BLOCKED"}
    assert brief["decision_evidence"]["recommendation"] is None
    assert brief["external_writes"] == []
