# ruff: noqa: E501
"""PR-4.2 deterministic functional validation.

This test is intentionally isolated from live supplier evidence and uses the
existing provider-neutral local fixture as its only deterministic source.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence, SupplierSource
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _assert_ok(response: Any) -> Any:
    assert response.status_code < 300, response.text
    return response.json()


def test_pr42_deterministic_supplier_shortlist_dd_reconstructs(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    setup = _assert_ok(
        api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "PR-4.2 Functional Owner",
                "email": "pr42-functional@example.com",
                "password": "correct horse battery staple",
                "password_confirmation": "correct horse battery staple",
            },
            headers=ORIGIN,
        )
    )
    assert setup["email"] == "pr42-functional@example.com"

    # Canonical application authority creates the product opportunity.
    opportunity = _assert_ok(
        api.post(
            "/api/v1/intelligence/product-opportunities",
            json={
                "name": "Madhura's Recipe Stainless Steel Lunch Box for Kids & Family",
                "description": "A stainless steel lunch box for children and families.",
                "product_concept": "reusable insulated food container",
                "category": "Kids",
                "subcategory": "Lunch Boxes",
                "target_marketplace": "AMAZON_IN",
                "target_region": "IN",
                "origin": "external_research",
                "research_state": "completed",
                "evidence_state": "available",
                "intelligence_profile": {
                    "normalized_product_concept": "reusable insulated food container",
                    "evidence_environment": "DETERMINISTIC_TEST",
                },
                "lifecycle_status": "ready_for_assessment",
                "idempotency_key": "pr42-functional-opportunity",
            },
            headers=ORIGIN,
        )
    )
    opportunity_id = opportunity["id"]
    constraint = _assert_ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
            json={
                "available_capital": 300000,
                "currency": "INR",
                "marketplace": "AMAZON_IN",
                "country_region": "IN",
                "category_restrictions": ["Kids"],
                "idempotency_key": "pr42-functional-constraint",
            },
            headers=ORIGIN,
        )
    )
    assessment = _assert_ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
            json={
                "constraint_version_id": constraint["id"],
                "evidence_state": "available",
                "status": "created",
                "input_snapshot": {"evidence_environment": "DETERMINISTIC_TEST"},
            },
            headers=ORIGIN,
        )
    )
    score = _assert_ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment['id']}/score",
            json={"idempotency_key": "pr42-functional-score"},
            headers=ORIGIN,
        )
    )
    assert score["eligibility"] in {"SCORABLE", "PARTIALLY_SCORABLE", "INSUFFICIENT_EVIDENCE"}
    selection = _assert_ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment['id']}/decision",
            json={
                "action": "shortlist",
                "rationale": "Human-selected functional validation product.",
                "idempotency_key": "pr42-functional-product-selection",
            },
            headers=ORIGIN,
        )
    )
    assert selection["action"] == "shortlist"

    # Existing bounded deterministic supplier authority; max_candidates=1
    # ensures this functional scenario has exactly one supplier candidate.
    discovery = _assert_ok(
        api.post(
            "/api/v1/intelligence/suppliers/research",
            json={
                "product_opportunity_id": opportunity_id,
                "product_query": "reusable insulated food container",
                "category": "Kids",
                "country": "IN",
                "mode": "LOCAL_FIXTURE",
                "max_candidates": 1,
                "idempotency_key": "pr42-functional-supplier-search",
            },
            headers=ORIGIN,
        )
    )
    assert discovery["result"]["external_calls"] is False
    assert discovery["result"]["accepted_candidate_count"] == 1

    # Reconcile through the canonical cross-marketplace authority.
    canonical = _assert_ok(
        api.post(
            "/api/v1/intelligence/cross-marketplace/suppliers/reconcile", json={}, headers=ORIGIN
        )
    )
    assert len(canonical) == 1
    supplier_id = canonical[0]["id"]
    detail = _assert_ok(
        api.get(f"/api/v1/intelligence/cross-marketplace/suppliers/{supplier_id}", headers=ORIGIN)
    )
    assert detail["display_name"]
    assert len(detail["evidence_lineage"]) == 1
    assert detail["evidence_lineage"][0]["verification"] == "unverified"
    projection = _assert_ok(
        api.get(
            f"/api/v1/intelligence/suppliers/research-results?opportunity_id={opportunity_id}",
            headers=ORIGIN,
        )
    )
    assert projection["count"] == 1, projection
    projection_summary = projection["research"]["summary"]
    projection_identity = projection["suppliers"][0].get("identity", {})
    assert projection_summary.get("supplier_ids"), {
        "summary_ids": projection_summary.get("supplier_ids"),
        "identity": projection_identity,
    }
    assert projection_identity.get("supplier_ids"), {
        "summary_ids": projection_summary.get("supplier_ids"),
        "identity": projection_identity,
    }

    # Bind the canonical product and its explicit category to a normal
    # Business Agent goal. The journey projection is the seller-facing BA
    # aggregation; no run is started here, so this validation cannot invoke a
    # second supplier search or create external activity.
    goal = _assert_ok(
        api.post(
            "/api/v1/intelligence/business-agent/goals",
            json={
                "raw_goal": (
                    "I have INR 300000 and want to start selling on Amazon India. "
                    "Help me find a product in Kids category."
                ),
                "structured_goal": {
                    "marketplace": "AMAZON_IN",
                    "category": "Kids",
                    "currency": "INR",
                    "capital": 300000,
                    "product_opportunity_id": opportunity_id,
                },
                "provenance": {
                    "mode": "LOCAL_FIXTURE",
                    "evidence_environment": "DETERMINISTIC_TEST",
                    "external_live_evidence": False,
                },
                "idempotency_key": "pr42-functional-business-goal",
            },
            headers=ORIGIN,
        )
    )
    goal_id = goal["id"]
    plan = _assert_ok(
        api.post(f"/api/v1/intelligence/business-agent/goals/{goal_id}/plan", headers=ORIGIN)
    )
    assert plan["goal_id"] == goal_id
    pre_shortlist_journey = _assert_ok(
        api.get(f"/api/v1/commerce-journeys/{goal_id}", headers=ORIGIN)
    )["journey"]
    assert pre_shortlist_journey["context"]["values"]["category"] == "Kids"
    assert pre_shortlist_journey["counts"]["opportunities"] == 1
    assert pre_shortlist_journey["stages"][4]["key"] == "VERIFY"
    assert pre_shortlist_journey["stages"][4]["status"] == "BLOCKED"
    assert pre_shortlist_journey["next_action"]["human_controlled"] is True

    context = _assert_ok(
        api.post(
            "/api/v1/intelligence/supplier-shortlisting/contexts",
            json={
                "opportunity_id": opportunity_id,
                "target_market": "AMAZON_IN",
                "budget": 300000,
                "budget_currency": "INR",
                "idempotency_key": "pr42-functional-shortlist-context",
            },
            headers=ORIGIN,
        )
    )
    context_id = context["id"]
    shortlist = _assert_ok(
        api.post(
            f"/api/v1/intelligence/supplier-shortlisting/contexts/{context_id}/shortlists",
            json={"top_n": 1, "idempotency_key": "pr42-functional-shortlist"},
            headers=ORIGIN,
        )
    )
    candidates = shortlist["shortlist"] + shortlist["review_required"]
    assert len(candidates) == 1, shortlist
    assert candidates[0]["supplier_id"] == supplier_id
    decision_payload = {
        "shortlist_version_id": shortlist["id"],
        "supplier_id": supplier_id,
        "decision": "KEEP_UNDER_REVIEW",
        "reason": "Human shortlist for bounded deterministic due diligence.",
        "decision_key": "pr42-functional-supplier-decision",
    }
    decision = _assert_ok(
        api.post(
            f"/api/v1/intelligence/supplier-shortlisting/contexts/{context_id}/decisions",
            json=decision_payload,
            headers=ORIGIN,
        )
    )
    replay = _assert_ok(
        api.post(
            f"/api/v1/intelligence/supplier-shortlisting/contexts/{context_id}/decisions",
            json=decision_payload,
            headers=ORIGIN,
        )
    )
    assert replay["id"] == decision["id"]
    assert replay["idempotent_reuse"] is True

    post_shortlist_journey = _assert_ok(
        api.get(f"/api/v1/commerce-journeys/{goal_id}", headers=ORIGIN)
    )["journey"]
    assert post_shortlist_journey["counts"]["shortlists"] == 1
    assert post_shortlist_journey["stages"][4]["status"] == "READY"
    assert post_shortlist_journey["stages"][4]["status"] != "COMPLETED"
    assert post_shortlist_journey["next_action"]["code"] in {
        "VERIFY_SUPPLIERS",
        "COMPARE_SUPPLIERS",
    }

    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "pr42-functional@example.com"))
        assert owner
        assert (
            db.scalar(
                select(func.count()).select_from(Supplier).where(Supplier.owner_id == owner.id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierSource)
                .where(SupplierSource.owner_id == owner.id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierEvidence)
                .where(SupplierEvidence.owner_id == owner.id)
            )
            == 1
        )
        canonical_row = db.scalar(
            select(CrossMarketplaceSupplier).where(CrossMarketplaceSupplier.owner_id == owner.id)
        )
        assert canonical_row
        view = canonical_row.view_json if isinstance(canonical_row.view_json, dict) else {}
        identity = view.get("identity")
        identity = identity if isinstance(identity, dict) else {}
        source_ids = identity.get("supplier_ids", [])
        assert len(source_ids) == 1
        source = db.scalar(
            select(SupplierSource).where(
                SupplierSource.supplier_id == uuid.UUID(str(source_ids[0]))
            )
        )
        assert source is not None
        assert source.status == "local_fixture"
        assert source.metadata_json.get("fixture") is True
        assert source.metadata_json.get("evidence_environment") == "DETERMINISTIC_TEST"

    due_contexts = _assert_ok(
        api.get("/api/v1/intelligence/supplier-due-diligence/contexts", headers=ORIGIN)
    )
    assert len(due_contexts) == 1
    due_id = due_contexts[0]["id"]
    with factory() as db:
        due_row = db.get(SupplierDueDiligenceContext, uuid.UUID(due_id))
        assert due_row is not None
        assert due_row.owner_id == owner.id
        assert due_row.supplier_id == uuid.UUID(supplier_id)
        assert due_row.opportunity_id == uuid.UUID(opportunity_id)
        assert due_row.shortlist_context_id == uuid.UUID(context_id)
        assert due_row.shortlist_version_id == uuid.UUID(shortlist["id"])
    assessed = _assert_ok(
        api.post(
            f"/api/v1/intelligence/supplier-due-diligence/contexts/{due_id}/assess", headers=ORIGIN
        )
    )
    assert assessed["readiness"] in {"REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE", "SUFFICIENT"}

    final_journey = _assert_ok(api.get(f"/api/v1/commerce-journeys/{goal_id}", headers=ORIGIN))[
        "journey"
    ]
    assert final_journey["counts"]["suppliers"] == 1
    assert final_journey["counts"]["shortlists"] == 1
    assert final_journey["counts"]["due_diligence"] == 1
    assert final_journey["context"]["values"]["selected_product_opportunity_id"] == opportunity_id
    assert final_journey["next_action"]["human_controlled"] is True
    assert final_journey["trust"]["mode"] == "LOCAL_FIXTURE"

    # A separate interpreter reconstructs the durable chain from PostgreSQL;
    # this guards against process-memory-only state.
    reconstruction_script = """
import os
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from vayujit_api.identity.models import User
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceAssessment
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.product_opportunity_scoring_models import ProductOpportunityDecision
from vayujit_api.intelligence.shortlisting_models import SupplierShortlistDecision
from vayujit_api.intelligence.supplier_models import Supplier, SupplierEvidence, SupplierSource
engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
with Session(engine) as db:
    owner = db.scalar(select(User).where(User.email == "pr42-functional@example.com"))
    assert owner is not None
    assert db.scalar(select(BusinessAgentGoal).where(BusinessAgentGoal.owner_id == owner.id)) is not None
    product_decision = db.scalar(select(ProductOpportunityDecision).where(ProductOpportunityDecision.owner_id == owner.id))
    assert product_decision is not None and product_decision.action == "shortlist"
    assert db.scalar(select(ProductOpportunity).where(ProductOpportunity.owner_id == owner.id)) is not None
    assert db.scalar(select(CrossMarketplaceSupplier).where(CrossMarketplaceSupplier.owner_id == owner.id)) is not None
    assert db.scalar(select(func.count()).select_from(Supplier).where(Supplier.owner_id == owner.id)) == 1
    assert db.scalar(select(func.count()).select_from(SupplierSource).where(SupplierSource.owner_id == owner.id)) == 1
    assert db.scalar(select(func.count()).select_from(SupplierEvidence).where(SupplierEvidence.owner_id == owner.id)) == 1
    assert db.scalar(select(func.count()).select_from(SupplierShortlistDecision).where(SupplierShortlistDecision.owner_id == owner.id)) == 1
    assert db.scalar(select(func.count()).select_from(SupplierDueDiligenceContext).where(SupplierDueDiligenceContext.owner_id == owner.id)) == 1
    assert db.scalar(select(func.count()).select_from(SupplierDueDiligenceAssessment).where(SupplierDueDiligenceAssessment.owner_id == owner.id)) == 1
"""
    subprocess.run(
        [sys.executable, "-c", reconstruction_script],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
    # Fresh sessions reconstruct the canonical chain and preserve fixture identity.
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "pr42-functional@example.com"))
        assert owner
        assert db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.id == uuid.UUID(opportunity_id),
            )
        )
        assert db.scalar(
            select(CrossMarketplaceSupplier).where(
                CrossMarketplaceSupplier.owner_id == owner.id,
                CrossMarketplaceSupplier.id == uuid.UUID(supplier_id),
            )
        )
