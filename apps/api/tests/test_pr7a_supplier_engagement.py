"""PR-7A controlled supplier engagement regression coverage."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_pr5b_landed_cost import ORIGIN, _ok, _prepare

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import (
    CrossMarketplaceSupplier,
    CrossMarketplaceSupplierLink,
)
from vayujit_api.intelligence.decision_evidence_models import DecisionEvidenceSnapshot
from vayujit_api.intelligence.decision_recommendation_models import (
    HumanDecision,
    RecommendationAssessment,
)
from vayujit_api.intelligence.decision_synthesis_models import DecisionSynthesisSnapshot
from vayujit_api.intelligence.supplier_models import Supplier

TEST_DATABASE_URL = os.environ.get("VAYUJIT_TEST_DATABASE_URL")
pytest_plugins = ["test_pr5b_landed_cost"]
pytestmark = pytest.mark.integration


def _supplier_and_contact(api: TestClient) -> tuple[str, str]:
    supplier = _ok(
        api.post(
            "/api/v1/intelligence/suppliers/manual",
            json={
                "display_name": "PR-7A Fixture Supplier",
                "supplier_type": "manufacturer",
                "country_code": "IN",
                "country": "India",
                "website": "https://fixture.example",
                "source_type": "manual_entry",
                "provenance": "DETERMINISTIC_TEST",
            },
            headers=ORIGIN,
        )
    )
    contact = _ok(
        api.post(
            f"/api/v1/intelligence/suppliers/{supplier['id']}/contacts",
            json={
                "name": "Fixture Contact",
                "role": "Sales",
                "business_email": "sales@fixture.example",
                "preferred_method": "email",
                "source": "DETERMINISTIC_TEST",
                "verification": "unverified",
            },
            headers=ORIGIN,
        )
    )
    return str(supplier["id"]), str(contact["id"])


def _seed_current_proceed(
    opportunity_id: str, supplier_id: str, decision_value: str = "PROCEED"
) -> str:
    """Create canonical PR-6 snapshots and a HUMAN decision for test-only setup."""
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        owner = db.scalar(select(User).where(User.email == "pr5b-owner@example.com"))
        supplier = db.get(Supplier, uuid.UUID(supplier_id))
        assert owner is not None and supplier is not None
        timestamp = datetime.now(UTC)
        canonical = CrossMarketplaceSupplier(
            owner_id=owner.id,
            canonical_key=f"pr7a-{uuid.uuid4().hex}",
            display_name=supplier.display_name,
            identity_state="MATCH",
            aliases=[supplier.display_name],
            view_json={"source": "DETERMINISTIC_TEST"},
            confidence_score=90,
            source_diversity_score=1,
            freshness_status="fresh",
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(canonical)
        db.flush()
        db.add(
            CrossMarketplaceSupplierLink(
                owner_id=owner.id,
                canonical_supplier_id=canonical.id,
                supplier_id=supplier.id,
                match_state="MATCH",
                rationale="DETERMINISTIC_TEST",
                evidence_ids=[],
                created_at=timestamp,
            )
        )
        fingerprint = uuid.uuid4().hex
        evidence = DecisionEvidenceSnapshot(
            owner_id=owner.id,
            opportunity_id=uuid.UUID(opportunity_id),
            supplier_id=canonical.id,
            decision_target="SUPPLIER_SELECTION",
            decision_version=1,
            policy_version="decision-readiness-v1",
            input_references={"fixture": "PR-7A"},
            trust_environment={"environment": "DETERMINISTIC_TEST"},
            evidence_summary={"supplier": "canonical fixture"},
            blockers=[],
            warnings=[],
            unknowns=[],
            contradictions=[],
            limitations=[],
            freshness_summary={"state": "fresh"},
            readiness_state="READY",
            safe_next_action={"external_action": False},
            input_fingerprint=fingerprint,
            idempotency_key=f"pr7a-evidence-{fingerprint}",
            created_at=timestamp,
            notes="Bounded deterministic test evidence.",
        )
        db.add(evidence)
        db.flush()
        synthesis = DecisionSynthesisSnapshot(
            owner_id=owner.id,
            opportunity_id=uuid.UUID(opportunity_id),
            supplier_id=canonical.id,
            decision_evidence_snapshot_id=evidence.id,
            decision_target="SUPPLIER_SELECTION",
            readiness_state="READY",
            readiness_policy_version="decision-readiness-v1",
            synthesis_policy_version="decision-synthesis-v1",
            posture="READY_FOR_HUMAN_DECISION",
            primary_reason={"code": "FIXTURE_READY"},
            reasons=[],
            supporting_evidence=[{"id": str(evidence.id)}],
            blockers=[],
            warnings=[],
            unknowns=[],
            contradictions=[],
            limitations=[],
            trust_summary={"environment": "DETERMINISTIC_TEST"},
            economics_summary={},
            capital_fit_state="UNKNOWN",
            safe_next_actions=[{"external_action": False}],
            human_review_required=True,
            input_fingerprint=uuid.uuid4().hex,
            idempotency_key=f"pr7a-synthesis-{uuid.uuid4().hex}",
            created_at=timestamp,
            explanation="Fixture is ready for explicit human review.",
            notes="Bounded deterministic test evidence.",
        )
        db.add(synthesis)
        db.flush()
        recommendation = RecommendationAssessment(
            owner_id=owner.id,
            opportunity_id=uuid.UUID(opportunity_id),
            supplier_id=canonical.id,
            decision_evidence_snapshot_id=evidence.id,
            synthesis_id=synthesis.id,
            decision_target="SUPPLIER_SELECTION",
            recommendation_policy_version="decision-recommendation-v1",
            recommendation_state="SYSTEM_SUPPORTS_PROCEEDING",
            supporting_reasons=[{"code": "FIXTURE_READY"}],
            counter_reasons=[],
            warnings=[],
            unknowns=[],
            contradictions=[],
            limitations=[],
            trust_summary={"environment": "DETERMINISTIC_TEST"},
            economics_summary={},
            capital_fit_state="UNKNOWN",
            human_review_required=True,
            input_fingerprint=uuid.uuid4().hex,
            idempotency_key=f"pr7a-recommendation-{uuid.uuid4().hex}",
            created_at=timestamp,
            explanation="Fixture requires explicit HUMAN decision.",
            notes="Bounded deterministic test evidence.",
        )
        db.add(recommendation)
        db.flush()
        decision = HumanDecision(
            owner_id=owner.id,
            actor_id=owner.id,
            opportunity_id=uuid.UUID(opportunity_id),
            supplier_id=canonical.id,
            decision_evidence_snapshot_id=evidence.id,
            synthesis_id=synthesis.id,
            recommendation_id=recommendation.id,
            decision_target="SUPPLIER_SELECTION",
            decision=decision_value,
            reason=f"Explicit PR-7A test decision: {decision_value}.",
            provenance="HUMAN",
            context_fingerprint=uuid.uuid4().hex,
            idempotency_key=f"pr7a-human-{uuid.uuid4().hex}",
            created_at=timestamp,
            external_writes=[],
        )
        db.add(decision)
        db.commit()
        decision_id = str(decision.id)
    engine.dispose()
    return decision_id


def _engagement(
    api: TestClient, opportunity_id: str, supplier_id: str, contact_id: str, key: str
) -> dict[str, Any]:
    return _ok(
        api.post(
            "/api/v1/intelligence/engagements",
            json={
                "opportunity_id": opportunity_id,
                "supplier_id": supplier_id,
                "contact_id": contact_id,
                "engagement_type": "REQUEST_QUOTE",
                "decision_target": "SUPPLIER_SELECTION",
                "requested_quantity": 100,
                "destination_region": "IN",
                "requested_fields": ["unit_price", "moq", "lead_time"],
                "idempotency_key": key,
            },
            headers=ORIGIN,
        )
    )


def _supersede_decision(opportunity_id: str, old_decision_id: str, decision_value: str) -> None:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as db:
        old = db.get(HumanDecision, uuid.UUID(old_decision_id))
        assert old is not None
        replacement = HumanDecision(
            owner_id=old.owner_id,
            actor_id=old.actor_id,
            opportunity_id=uuid.UUID(opportunity_id),
            supplier_id=old.supplier_id,
            decision_evidence_snapshot_id=old.decision_evidence_snapshot_id,
            synthesis_id=old.synthesis_id,
            recommendation_id=old.recommendation_id,
            supersedes_decision_id=old.id,
            decision_target=old.decision_target,
            decision=decision_value,
            reason=f"Superseded PR-7A test decision: {decision_value}.",
            provenance="HUMAN",
            context_fingerprint=uuid.uuid4().hex,
            idempotency_key=f"pr7a-supersede-{uuid.uuid4().hex}",
            created_at=datetime.now(UTC),
            external_writes=[],
        )
        db.add(replacement)
        db.commit()
    engine.dispose()


def test_pr7a_blocks_without_human_proceed_and_never_sends(client: TestClient) -> None:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    blocked = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7a-blocked")
    assert blocked["status"] == "BLOCKED"
    assert blocked["current_draft"] is None
    assert "HUMAN_PROCEED_REQUIRED" in {item["code"] for item in blocked["blocking_reasons"]}
    readiness = _ok(
        client.get(
            f"/api/v1/intelligence/engagements/{blocked['id']}/send-readiness", headers=ORIGIN
        )
    )
    assert readiness["can_send"] is False
    assert readiness["provider_calls"] == 0
    assert readiness["external_writes"] == []


@pytest.mark.parametrize("decision_value", ["KEEP_UNDER_REVIEW", "DO_NOT_PROCEED"])
def test_pr7a_non_proceed_human_decisions_remain_blocked(
    client: TestClient, decision_value: str
) -> None:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity_id, supplier_id, decision_value)
    blocked = _engagement(
        client,
        opportunity_id,
        supplier_id,
        contact_id,
        f"pr7a-{decision_value.lower()}",
    )
    assert blocked["status"] == "BLOCKED"
    assert any(item["code"] == f"HUMAN_{decision_value}" for item in blocked["blocking_reasons"])


def test_pr7a_draft_approval_edit_idempotency_and_cancel(client: TestClient) -> None:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    decision_id = _seed_current_proceed(opportunity_id, supplier_id)
    created = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7a-flow")
    assert created["status"] == "NEEDS_REVIEW"
    assert created["current_draft"]["version"] == 1
    assert created["current_draft"]["provenance"] == "SYSTEM_DRAFT"
    assert created["current_draft"]["contact"]["provenance"] == "DETERMINISTIC_TEST"
    replay = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7a-flow")
    assert replay["id"] == created["id"]

    approved = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{created['id']}/approve",
            json={"idempotency_key": "pr7a-approve", "reason": "Human review complete"},
            headers=ORIGIN,
        )
    )
    assert approved["status"] == "APPROVED_FOR_SEND"
    assert approved["latest_approval"]["provenance"] == "HUMAN"
    replay_approval = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{created['id']}/approve",
            json={"idempotency_key": "pr7a-approve", "reason": "Human review complete"},
            headers=ORIGIN,
        )
    )
    assert replay_approval["id"] == created["id"]

    revised = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{created['id']}/drafts",
            json={
                "requested_quantity": 125,
                "destination_region": "IN",
                "requested_fields": ["unit_price", "moq"],
                "idempotency_key": "pr7a-edit",
                "provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    assert revised["status"] == "NEEDS_REVIEW"
    assert revised["current_draft"]["version"] == 2
    assert revised["current_draft"]["structured_request"]["requested_quantity"] == 125
    assert revised["latest_approval"]["state"] == "INVALIDATED"
    revision_replay = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{created['id']}/drafts",
            json={
                "requested_quantity": 125,
                "destination_region": "IN",
                "requested_fields": ["unit_price", "moq"],
                "idempotency_key": "pr7a-edit",
                "provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    assert revision_replay["current_draft"]["id"] == revised["current_draft"]["id"]
    assert revision_replay["current_draft"]["version"] == 2

    history = cast(
        list[dict[str, Any]],
        _ok(
            client.get(f"/api/v1/intelligence/engagements/{created['id']}/history", headers=ORIGIN)
        ),
    )
    assert [item["event_type"] for item in history] == [
        "engagement_created",
        "engagement_draft_created",
        "engagement_draft_approved",
        "engagement_approval_invalidated",
        "engagement_draft_edited",
    ]
    cancelled = _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{created['id']}/cancel",
            json={"idempotency_key": "pr7a-cancel", "reason": "Stop review"},
            headers=ORIGIN,
        )
    )
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["send_status"] == "NOT_EXECUTED"
    assert decision_id


def test_pr7a_superseded_proceed_revokes_future_send_readiness(client: TestClient) -> None:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    decision_id = _seed_current_proceed(opportunity_id, supplier_id)
    created = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7a-stale")
    _ok(
        client.post(
            f"/api/v1/intelligence/engagements/{created['id']}/approve",
            json={"idempotency_key": "pr7a-stale-approve", "reason": "Review complete"},
            headers=ORIGIN,
        )
    )
    _supersede_decision(opportunity_id, decision_id, "DO_NOT_PROCEED")
    detail = _ok(client.get(f"/api/v1/intelligence/engagements/{created['id']}", headers=ORIGIN))
    assert detail["status"] == "NEEDS_REVIEW"
    assert detail["can_send"] is False
    assert any(item["code"] == "HUMAN_DECISION_SUPERSEDED" for item in detail["blocking_reasons"])
    readiness = _ok(
        client.get(
            f"/api/v1/intelligence/engagements/{created['id']}/send-readiness", headers=ORIGIN
        )
    )
    assert readiness["can_send"] is False
    assert readiness["provider_calls"] == 0


def test_pr7a_rejects_non_human_approval_and_cross_owner_access(client: TestClient) -> None:
    opportunity_id, _ = _prepare(client)
    supplier_id, contact_id = _supplier_and_contact(client)
    _seed_current_proceed(opportunity_id, supplier_id)
    created = _engagement(client, opportunity_id, supplier_id, contact_id, "pr7a-access")
    bad = client.post(
        f"/api/v1/intelligence/engagements/{created['id']}/approve",
        json={"idempotency_key": "pr7a-ai-approval", "provenance": "AI"},
        headers=ORIGIN,
    )
    assert bad.status_code == 422

    other = User(id=uuid.uuid4(), full_name="Other Owner", email="pr7a-other@example.com")

    from vayujit_api.identity.router import current_user

    api_app: Any = client.app
    api_app.dependency_overrides[current_user] = lambda: other
    try:
        hidden = client.get(f"/api/v1/intelligence/engagements/{created['id']}", headers=ORIGIN)
        assert hidden.status_code == 404
    finally:
        api_app.dependency_overrides.pop(current_user, None)
    assert other.id != uuid.UUID(created["owner_id"])
