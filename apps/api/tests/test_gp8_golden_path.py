"""Focused GP-8 guided commerce journey integration coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.brands.models import Brand
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import Supplier
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration

CANONICAL_GOAL = (
    "I want to start selling a physical product on Amazon India with a total initial budget "
    "of ₹3,00,000. Help me identify promising product opportunities with moderate risk, healthy "
    "profit potential, manageable competition, and reliable supplier options. Prefer products "
    "that are lightweight, easy to ship, non-fragile, non-perishable, and do not require complex "
    "regulatory approvals."
)


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _setup_owner(api: TestClient, factory: sessionmaker[Session]) -> str:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "GP-8 Owner",
            "email": "gp8@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "gp8@example.com"))
        assert owner
        stamp = datetime.now(UTC)
        brand = Brand(
            owner_id=owner.id,
            name="GP-8 Fixture Brand",
            normalized_name="gp-8 fixture brand",
            slug="gp-8-fixture-brand",
            status="active",
            is_active_context=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(brand)
        db.flush()
        product = Product(
            owner_id=owner.id,
            brand_id=brand.id,
            name="GP-8 Disposable Product",
            normalized_name="gp-8 disposable product",
            slug="gp-8-disposable-product",
            sku="GP8-001",
            product_type="physical",
            status="active",
            category="Home",
            price_amount=Decimal("499"),
            price_currency="INR",
            inventory_quantity=10,
            low_stock_threshold=1,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(product)
        db.commit()
        return str(product.id)


def _assert_journey(api: TestClient, goal_id: str) -> dict[str, Any]:
    response = api.get("/api/v1/commerce-journeys/active", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()["journey"]
    assert body["id"] == goal_id
    assert body["human_controlled"] is True
    return cast(dict[str, Any], body)


def _create_assessment_and_score(api: TestClient, opportunity_id: str, key: str) -> str:
    constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={
            "currency": "INR",
            "available_capital": "300000",
            "maximum_landed_cost": "300",
            "maximum_moq": "100",
            "maximum_lead_time_days": 45,
            "acceptable_risk_level": "moderate",
            "idempotency_key": f"{key}-constraint",
        },
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "GP-8_LOCAL_FIXTURE"}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    assessment_id = cast(str, assessment.json()["id"])
    scored = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
        json={"idempotency_key": key},
        headers=ORIGIN,
    )
    assert scored.status_code == 201, scored.text
    return assessment_id


def test_gp8_guided_commerce_golden_path_is_persistent_owner_scoped_and_safe(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client

    assert api.get("/api/v1/commerce-journeys/active", headers=ORIGIN).status_code == 401
    product_id = _setup_owner(api, factory)
    clean = api.get("/api/v1/commerce-journeys/active", headers=ORIGIN)
    assert clean.status_code == 200 and clean.json()["journey"] is None

    goal_payload = {
        "raw_goal": CANONICAL_GOAL,
        "structured_goal": {
            "marketplace": "AMAZON_IN",
            "capital": 300000,
            "product_id": product_id,
            "risk_preference": "moderate",
        },
        "provenance": {"source": "owner_input", "mode": "LOCAL_DETERMINISTIC"},
        "idempotency_key": "gp8-goal",
    }
    first_goal = api.post(
        "/api/v1/intelligence/business-agent/goals", json=goal_payload, headers=ORIGIN
    )
    assert first_goal.status_code == 201, first_goal.text
    repeated_goal = api.post(
        "/api/v1/intelligence/business-agent/goals", json=goal_payload, headers=ORIGIN
    )
    assert repeated_goal.status_code == 201
    goal = first_goal.json()
    goal_id = goal["id"]
    assert repeated_goal.json()["id"] == goal_id
    assert goal["provenance"]["source"] == "owner_input"

    journey = _assert_journey(api, goal_id)
    assert journey["context_confirmation"]["required"] is True
    assert journey["next_action"]["code"] == "REVIEW_PLAN"
    assert journey["next_action"]["route"] == "/intelligence/business-agent"

    context_payload = {
        "confirmed": True,
        "marketplace": "AMAZON_IN",
        "budget_amount": 300000,
        "currency": "INR",
        "risk_preference": "moderate",
        "constraints": ["lightweight", "easy to ship", "non-fragile", "non-perishable"],
    }
    confirmed = api.post(
        f"/api/v1/commerce-journeys/{goal_id}/context-confirmation",
        json=context_payload,
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    repeated_context = api.post(
        f"/api/v1/commerce-journeys/{goal_id}/context-confirmation",
        json=context_payload,
        headers=ORIGIN,
    )
    assert repeated_context.status_code == 200
    assert repeated_context.json()["journey"]["context"]["values"]["budget_amount"] == 300000
    assert repeated_context.json()["journey"]["context_confirmation"]["source"] == "USER_CONFIRMED"

    plan = api.post(f"/api/v1/intelligence/business-agent/goals/{goal_id}/plan", headers=ORIGIN)
    assert plan.status_code == 200, plan.text
    repeated_plan = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal_id}/plan", headers=ORIGIN
    )
    assert repeated_plan.status_code == 200
    assert repeated_plan.json()["id"] == plan.json()["id"]
    assert all(step["side_effect_class"] == "NONE" for step in plan.json()["steps"])

    run_payload = {"idempotency_key": "gp8-run", "max_steps": 20}
    run = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
        json=run_payload,
        headers=ORIGIN,
    )
    assert run.status_code == 201, run.text
    repeated_run = api.post(
        f"/api/v1/intelligence/business-agent/goals/{goal_id}/runs",
        json=run_payload,
        headers=ORIGIN,
    )
    assert repeated_run.status_code == 201
    assert repeated_run.json()["id"] == run.json()["id"]
    started = api.post(
        f"/api/v1/intelligence/business-agent/runs/{run.json()['id']}/start", headers=ORIGIN
    )
    assert started.status_code == 200, started.text
    assert started.json()["result"]["external_writes"] == []
    assert started.json()["status"] == "WAITING_APPROVAL"
    approval = api.get(
        f"/api/v1/intelligence/business-agent/runs/{run.json()['id']}/approvals", headers=ORIGIN
    )
    assert approval.status_code == 200 and len(approval.json()) == 1
    approved = api.post(
        f"/api/v1/intelligence/business-agent/approvals/{approval.json()[0]['id']}/approve",
        json={"note": "GP-8 human review"},
        headers=ORIGIN,
    )
    assert approved.status_code == 200, approved.text
    assert (
        api.get(
            f"/api/v1/intelligence/business-agent/runs/{run.json()['id']}", headers=ORIGIN
        ).json()["status"]
        == "COMPLETED"
    )

    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "gp8@example.com"))
        assert owner
        opportunity = db.scalar(
            select(ProductOpportunity)
            .where(ProductOpportunity.owner_id == owner.id)
            .order_by(ProductOpportunity.created_at)
        )
        assert opportunity
        opportunity_id = str(opportunity.id)

    journey = _assert_journey(api, goal_id)
    assert journey["counts"]["runs"] == 1
    assert journey["next_action"]["code"] in {"RESEARCH_OPPORTUNITIES", "COMPARE_OPPORTUNITIES"}
    assert (
        next(stage for stage in journey["stages"] if stage["key"] == "SOURCE")["status"]
        == "BLOCKED"
    )

    second = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "GP-8 Comparison Candidate",
            "product_id": product_id,
            "category": "Home",
            "target_marketplace": "amazon",
            "origin": "manual",
            "idempotency_key": "gp8-comparison-candidate",
        },
        headers=ORIGIN,
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    first_assessment = _create_assessment_and_score(api, opportunity_id, "gp8-score-1")
    second_assessment = _create_assessment_and_score(api, second_id, "gp8-score-2")
    comparison = api.post(
        "/api/v1/intelligence/product-opportunities/score/compare",
        json={"assessment_ids": [first_assessment, second_assessment]},
        headers=ORIGIN,
    )
    assert comparison.status_code == 200, comparison.text
    assert len(comparison.json()["items"]) == 2
    selected = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{first_assessment}/decision",
        json={
            "action": "shortlist",
            "rationale": "Human selected for supplier validation.",
            "idempotency_key": "gp8-product-selection",
        },
        headers=ORIGIN,
    )
    assert selected.status_code == 201, selected.text
    repeated_selected = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{first_assessment}/decision",
        json={
            "action": "shortlist",
            "rationale": "Human selected for supplier validation.",
            "idempotency_key": "gp8-product-selection",
        },
        headers=ORIGIN,
    )
    assert repeated_selected.status_code == 201
    assert repeated_selected.json()["id"] == selected.json()["id"]

    results = api.get("/api/v1/intelligence/product-opportunities/research-results", headers=ORIGIN)
    assert results.status_code == 200, results.text
    assert results.json()["human_selection"]["provenance"] == "HUMAN"
    journey = _assert_journey(api, goal_id)
    assert journey["counts"]["selected_opportunities"] == 1
    assert journey["context"]["values"]["selected_product_opportunity_id"] == opportunity_id
    assert (
        next(stage for stage in journey["stages"] if stage["key"] == "SOURCE")["status"] == "READY"
    )

    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "gp8@example.com"))
        assert owner
        suppliers = list(
            db.scalars(
                select(CrossMarketplaceSupplier).where(
                    CrossMarketplaceSupplier.owner_id == owner.id
                )
            )
        )
        if not suppliers:
            now = datetime.now(UTC)
            suppliers = [
                CrossMarketplaceSupplier(
                    owner_id=owner.id,
                    canonical_key=f"gp8-fixture-{index}",
                    display_name=f"GP-8 Fixture Supplier {index}",
                    identity_state="MATCH",
                    aliases=[],
                    view_json={
                        "capabilities": ["home goods"],
                        "certifications": ["quality"],
                        "facilities": ["factory"],
                        "risk": {"level": "LOW"},
                        "confidence": {"score": 90, "dimensions": [{"score": 0.9}]},
                        "source_diversity": {"source_diversity_score": 2},
                        "freshness": {"overall": "fresh"},
                        "evidence_lineage": [{"source": "LOCAL_FIXTURE"}],
                    },
                    confidence_score=90,
                    source_diversity_score=2,
                    freshness_status="fresh",
                    created_at=now,
                    updated_at=now,
                )
                for index in (1, 2)
            ]
            db.add_all(suppliers)
            db.commit()
        supplier_ids = [str(item.id) for item in suppliers[:2]]
        economic_supplier = db.scalar(
            select(Supplier).where(Supplier.owner_id == owner.id).order_by(Supplier.created_at)
        )
        if economic_supplier is None:
            now = datetime.now(UTC)
            economic_supplier = Supplier(
                owner_id=owner.id,
                display_name="GP-8 Legacy Economics Supplier",
                legal_name="GP-8 Legacy Economics Supplier",
                supplier_type="manufacturer",
                country_code="IN",
                country="India",
                source_identity="LOCAL_FIXTURE",
                normalized_identity="gp8-legacy-economics-supplier",
                verification_state="verified",
                created_at=now,
                updated_at=now,
            )
            db.add(economic_supplier)
            db.commit()
            db.refresh(economic_supplier)
        economic_supplier_id = str(economic_supplier.id)
    assert len(supplier_ids) >= 2

    shortlist_context = api.post(
        "/api/v1/intelligence/supplier-shortlisting/contexts",
        json={
            "product_id": product_id,
            "target_market": "AMAZON_IN",
            "budget": 300000,
            "budget_currency": "INR",
            "idempotency_key": "gp8-shortlist-context",
        },
        headers=ORIGIN,
    )
    assert shortlist_context.status_code == 200, shortlist_context.text
    shortlist = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{shortlist_context.json()['id']}/shortlists",
        json={"idempotency_key": "gp8-shortlist"},
        headers=ORIGIN,
    )
    assert shortlist.status_code == 200, shortlist.text
    repeated_shortlist = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{shortlist_context.json()['id']}/shortlists",
        json={"idempotency_key": "gp8-shortlist"},
        headers=ORIGIN,
    )
    assert repeated_shortlist.status_code == 200
    assert repeated_shortlist.json()["id"] == shortlist.json()["id"]
    candidates = shortlist.json()["shortlist"] + shortlist.json()["review_required"]
    assert candidates
    supplier_id = candidates[0]["supplier_id"]
    supplier_compare = api.request(
        "GET",
        "/api/v1/intelligence/supplier-shortlisting/compare",
        json=supplier_ids,
        headers=ORIGIN,
    )
    assert supplier_compare.status_code == 200, supplier_compare.text
    supplier_decision = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{shortlist_context.json()['id']}/decisions",
        json={
            "shortlist_version_id": shortlist.json()["id"],
            "supplier_id": supplier_id,
            "decision": "APPROVE_FOR_SOURCING",
            "reason": "Human shortlisted for verification.",
            "decision_key": "gp8-supplier-selection",
        },
        headers=ORIGIN,
    )
    assert supplier_decision.status_code == 200, supplier_decision.text
    handoff = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{shortlist_context.json()['id']}/handoff",
        json={
            "decision_id": supplier_decision.json()["id"],
            "idempotency_key": "gp8-handoff",
            "confirmed": True,
        },
        headers=ORIGIN,
    )
    assert handoff.status_code == 200, handoff.text
    assert handoff.json()["external_dispatch"] is False

    due = api.post(
        "/api/v1/intelligence/supplier-due-diligence/contexts",
        json={
            "supplier_id": supplier_id,
            "product_id": product_id,
            "opportunity_id": opportunity_id,
            "shortlist_context_id": shortlist_context.json()["id"],
            "shortlist_version_id": shortlist.json()["id"],
            "idempotency_key": "gp8-due-context",
        },
        headers=ORIGIN,
    )
    assert due.status_code == 200, due.text
    due_id = due.json()["id"]
    due_assessment = api.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{due_id}/assess",
        headers=ORIGIN,
    )
    assert due_assessment.status_code == 200, due_assessment.text
    journey = _assert_journey(api, goal_id)
    assert journey["counts"]["shortlists"] >= 1
    assert journey["counts"]["due_diligence"] >= 1
    assert journey["next_action"]["code"] in {"CALCULATE_COSTS", "REVIEW_DECISION"}

    economic_context = api.post(
        "/api/v1/intelligence/sourcing-economics/contexts",
        json={
            "idempotency_key": "gp8-economic-context",
            "product_id": product_id,
            "supplier_id": economic_supplier_id,
            "source_marketplace": "AMAZON_IN",
            "origin_country": "IN",
            "destination_country": "IN",
            "target_channel": "amazon",
            "target_quantity": "10",
            "quantity_unit": "unit",
            "base_currency": "INR",
        },
        headers=ORIGIN,
    )
    assert economic_context.status_code == 201, economic_context.text
    economic_context_id = economic_context.json()["context"]["id"]
    for category, amount, basis in (
        ("PRODUCT_COST", "100", "PER_UNIT"),
        ("FREIGHT", "50", "ONE_TIME"),
    ):
        component = api.post(
            "/api/v1/intelligence/sourcing-economics/components",
            json={
                "context_id": economic_context_id,
                "category": category,
                "amount": amount,
                "currency": "INR",
                "unit_basis": basis,
                "provenance": "CONFIGURED",
            },
            headers=ORIGIN,
        )
        assert component.status_code == 201, component.text
    snapshot = api.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots?context_id={economic_context_id}",
        json={},
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    calculation = api.post(
        f"/api/v1/intelligence/sourcing-economics/snapshots/{snapshot.json()['snapshot']['id']}/calculate",
        json={},
        headers=ORIGIN,
    )
    assert calculation.status_code == 201, calculation.text
    baseline = calculation.json()["calculation"]
    scenario = api.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/contexts/{economic_context_id}",
        json={
            "idempotency_key": "gp8-economic-scenario",
            "name": "GP-8 reversible cost scenario",
            "description": "Deterministic local scenario for human review.",
            "baseline_calculation_id": baseline["id"],
            "overrides": {"product_unit_cost": "110", "reason": "GP-8 sensitivity"},
        },
        headers=ORIGIN,
    )
    assert scenario.status_code == 201, scenario.text
    scenario_run = api.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario.json()['id']}/run",
        json={"idempotency_key": "gp8-economic-scenario-run"},
        headers=ORIGIN,
    )
    assert scenario_run.status_code == 201, scenario_run.text
    sensitivity = api.post(
        f"/api/v1/intelligence/sourcing-economics/scenarios/{scenario.json()['id']}/sensitivity",
        json={
            "idempotency_key": "gp8-economic-sensitivity",
            "points": [
                {"dimension": "product_unit_cost", "value": "90"},
                {"dimension": "product_unit_cost", "value": "110"},
            ],
        },
        headers=ORIGIN,
    )
    assert sensitivity.status_code == 201, sensitivity.text
    brief = api.get(
        f"/api/v1/commerce-journeys/{goal_id}/decision-brief?opportunity_id={opportunity_id}&economic_context_id={economic_context_id}",
        headers=ORIGIN,
    )
    assert brief.status_code == 200, brief.text
    brief_body = brief.json()
    assert brief_body["provenance"]["opportunity_id"] == opportunity_id
    assert brief_body["external_writes"] == []
    assert brief_body["goal"]["provenance"] == "USER_PROVIDED"
    assert brief_body["economics"]["calculation"]["currency"] == "INR"

    non_proceed = api.post(
        f"/api/v1/commerce-journeys/{goal_id}/decision",
        json={
            "opportunity_id": opportunity_id,
            "action": "RESEARCH_FURTHER",
            "note": "Keep the candidate under review.",
            "economic_context_id": economic_context_id,
            "idempotency_key": "gp8-human-research-further",
        },
        headers=ORIGIN,
    )
    assert non_proceed.status_code == 200, non_proceed.text
    repeated_non_proceed = api.post(
        f"/api/v1/commerce-journeys/{goal_id}/decision",
        json={
            "opportunity_id": opportunity_id,
            "action": "RESEARCH_FURTHER",
            "note": "Keep the candidate under review.",
            "economic_context_id": economic_context_id,
            "idempotency_key": "gp8-human-research-further",
        },
        headers=ORIGIN,
    )
    assert repeated_non_proceed.status_code == 200
    assert (
        repeated_non_proceed.json()["decision"]["idempotency_key"] == "gp8-human-research-further"
    )
    blocked_proceed = api.post(
        f"/api/v1/commerce-journeys/{goal_id}/decision",
        json={
            "opportunity_id": opportunity_id,
            "action": "PROCEED_TO_LAUNCH_PREPARATION",
            "note": "Attempt launch only after the brief is ready.",
            "economic_context_id": economic_context_id,
            "idempotency_key": "gp8-human-proceed-guard",
        },
        headers=ORIGIN,
    )
    assert blocked_proceed.status_code in {200, 409}, blocked_proceed.text
    if blocked_proceed.status_code == 200:
        assert blocked_proceed.json()["external_writes"] == []
    final_journey = _assert_journey(api, goal_id)
    assert final_journey["counts"]["decisions"] >= 0
    assert final_journey["human_controlled"] is True

    app = cast(FastAPI, api.app)
    other_owner = User(id=uuid.uuid4(), email="gp8-other@example.com", full_name="Other GP-8")
    app.dependency_overrides[current_user] = lambda: other_owner
    try:
        assert api.get(f"/api/v1/commerce-journeys/{goal_id}", headers=ORIGIN).status_code == 404
        assert (
            api.get(
                "/api/v1/intelligence/product-opportunities/research-results", headers=ORIGIN
            ).json()["candidates"]
            == []
        )
        assert (
            api.get(
                f"/api/v1/commerce-journeys/{goal_id}/decision-brief?opportunity_id={opportunity_id}",
                headers=ORIGIN,
            ).status_code
            == 404
        )
        assert (
            api.post(
                f"/api/v1/commerce-journeys/{goal_id}/decision",
                json={
                    "opportunity_id": opportunity_id,
                    "action": "RESEARCH_FURTHER",
                    "idempotency_key": "gp8-other-owner",
                },
                headers=ORIGIN,
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides.pop(current_user)
