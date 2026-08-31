from __future__ import annotations

from typing import cast

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from helpers.indiamart_certification import evidence, mission, task
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context

from vayujit_api.identity.models import User
from vayujit_api.intelligence.autonomous_models import AutonomousResearchContradiction
from vayujit_api.intelligence.autonomous_service import _materiality
from vayujit_api.intelligence.external_intelligence import (
    confidence_handoff,
    record_external_contradiction,
    source_diversity_evaluation,
)
from vayujit_api.intelligence.supplier_service import risk_matrix

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "change_type,previous,current,expected",
    (
        ("price", {"value": 100}, {"value": 105}, "NON_MATERIAL"),
        ("price", {"value": 100}, {"value": 130}, "MATERIAL"),
        ("moq", {"value": 100}, {"value": 500}, "NON_MATERIAL"),
        ("lead_time", {"value": 10}, {"value": 45}, "NON_MATERIAL"),
        ("listing_status", {"value": "active"}, {"value": "removed"}, "NON_MATERIAL"),
        (
            "supplier_verification",
            {"value": "verified"},
            {"value": "conflict"},
            "REQUIRES_REVIEW",
        ),
        ("business_identity", {"value": "Acme"}, {"value": "Other"}, "NON_MATERIAL"),
    ),
)
def test_indiamart_materiality_matrix_is_deterministic(
    client: TestClient,
    change_type: str,
    previous: dict[str, object],
    current: dict[str, object],
    expected: str,
) -> None:
    setup_context(client)
    classification, delta, reason = _materiality(change_type, previous, current)
    assert classification == expected
    assert reason
    if change_type == "price":
        assert delta == cast(float, current["value"]) - cast(float, previous["value"])


@pytest.mark.parametrize(
    "risk_dimension",
    (
        "identity",
        "location",
        "commercial",
        "verification",
        "listing",
        "freshness",
        "identity_ambiguity",
    ),
)
def test_indiamart_risk_matrix_is_fail_closed(client: TestClient, risk_dimension: str) -> None:
    context = setup_context(client)
    discovery = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": f"risk {risk_dimension}", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert discovery.status_code == 200, discovery.text
    supplier_id = discovery.json()["results"][0]["supplier_id"]
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        result = risk_matrix(db, owner, supplier_id)
        dimensions = {
            item["dimension"]: item for item in cast(list[dict[str, object]], result["dimensions"])
        }
        assert risk_dimension not in dimensions or dimensions[risk_dimension]["status"] in {
            "unknown",
            "observed",
            "REQUIRES REVIEW",
        }
        assert all(
            "fraud" not in str(item.get("reason", "")).lower()
            for item in cast(list[dict[str, object]], result["dimensions"])
        )


def test_indiamart_contradiction_matrix_deduplicates_reverse_pairs(client: TestClient) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, "contradiction-matrix")
        worker = task(db, owner, parent)
        left = evidence(db, owner, parent, worker, reference="website-moq", value=100)
        right = evidence(db, owner, parent, worker, reference="indiamart-moq", value=500)
        before = db.scalar(select(func.count()).select_from(AutonomousResearchContradiction)) or 0
        first = record_external_contradiction(db, parent, left, right, claim_key="MOQ")
        db.commit()
        reverse = record_external_contradiction(db, parent, right, left, claim_key="MOQ")
        db.commit()
        after = db.scalar(select(func.count()).select_from(AutonomousResearchContradiction)) or 0
        assert first.id == reverse.id
        assert first.status == "UNRESOLVED"
        assert first.resolution_strategy == "REQUIRES_HUMAN_REVIEW"
        assert after - before == 1
        confidence = confidence_handoff(
            [left, right], contradiction_count=1, critical_unknowns=1, complete=False
        )
        assert cast(float, confidence["overall_confidence"]) < 0.85
        assert source_diversity_evaluation([left, right])["duplicate_source_count"] == 0


@pytest.mark.parametrize(
    "left_ref,right_ref,claim_key,left_value,right_value",
    (
        ("website-lead-time", "indiamart-lead-time", "LEAD_TIME", 10, 45),
        ("website-verification", "indiamart-verification", "VERIFICATION", "verified", "conflict"),
        ("website-identity", "indiamart-identity", "IDENTITY", "Acme", "Other"),
    ),
)
def test_indiamart_additional_contradiction_cases(
    client: TestClient,
    left_ref: str,
    right_ref: str,
    claim_key: str,
    left_value: object,
    right_value: object,
) -> None:
    setup_context(client)
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert owner is not None
        parent = mission(db, owner, f"contradiction:{claim_key}")
        worker = task(db, owner, parent)
        left = evidence(db, owner, parent, worker, reference=left_ref, value=left_value)
        right = evidence(db, owner, parent, worker, reference=right_ref, value=right_value)
        before = db.scalar(select(func.count()).select_from(AutonomousResearchContradiction)) or 0
        first = record_external_contradiction(db, parent, left, right, claim_key=claim_key)
        db.commit()
        replay = record_external_contradiction(db, parent, left, right, claim_key=claim_key)
        reverse = record_external_contradiction(db, parent, right, left, claim_key=claim_key)
        db.commit()
        after = db.scalar(select(func.count()).select_from(AutonomousResearchContradiction)) or 0
        assert first.id == replay.id == reverse.id
        assert first.resolution_strategy == "REQUIRES_HUMAN_REVIEW"
        assert after - before == 1
