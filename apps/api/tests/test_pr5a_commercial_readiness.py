# ruff: noqa: E501
"""PR-5A commercial evidence/readiness integration proof."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.supplier_models import SupplierCommercialTerm, SupplierProduct
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


def test_pr5a_source_readiness_assumptions_idempotency_and_reconstruction(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _assert_ok(
        api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "PR-5A Readiness Owner",
                "email": "pr5a-readiness@example.com",
                "password": "correct horse battery staple",
                "password_confirmation": "correct horse battery staple",
            },
            headers=ORIGIN,
        )
    )
    opportunity = _assert_ok(
        api.post(
            "/api/v1/intelligence/product-opportunities",
            json={
                "name": "Stainless Steel Lunch Box",
                "description": "A reusable lunch box for children.",
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
                "idempotency_key": "pr5a-readiness-opportunity",
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
                "idempotency_key": "pr5a-readiness-constraint",
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
    assessment_id = assessment["id"]
    _assert_ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
            json={"idempotency_key": "pr5a-readiness-score"},
            headers=ORIGIN,
        )
    )
    _assert_ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/decision",
            json={
                "action": "shortlist",
                "rationale": "Human-selected product for PR-5A readiness.",
                "idempotency_key": "pr5a-readiness-product-selection",
            },
            headers=ORIGIN,
        )
    )
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
                "idempotency_key": "pr5a-readiness-supplier-search",
            },
            headers=ORIGIN,
        )
    )
    assert discovery["result"]["accepted_candidate_count"] == 1

    readiness_url = f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial-readiness"
    source = _assert_ok(
        api.post(readiness_url, json={"idempotency_key": "pr5a-source-readiness"}, headers=ORIGIN)
    )
    assert source["readiness"]["overall"] == "NEEDS_INPUT"
    assert source["readiness"]["economics_calculated"] is False
    assert any(
        item["key"] == "supplier_moq" and float(item["value"]) == 500.0 for item in source["claims"]
    )
    assert {item["key"] for item in source["unknown_inputs"]} >= {
        "supplier_unit_price",
        "supplier_currency",
    }
    assert source["lineage"]["mode"] == "LOCAL_FIXTURE"
    assert any(
        item["key"] == "supplier_unit_price" and item["provenance"] == "UNKNOWN"
        for item in source["unknown_inputs"]
    )
    assert any(
        item["key"] == "supplier_unit_price" and "price_basis" in item
        for item in source["unknown_inputs"]
    )
    assert source["lineage"]["candidate"]["evidence_ids"]

    replay = _assert_ok(
        api.post(readiness_url, json={"idempotency_key": "pr5a-source-readiness"}, headers=ORIGIN)
    )
    assert replay["id"] == source["id"]

    assumed = _assert_ok(
        api.post(
            readiness_url,
            json={
                "idempotency_key": "pr5a-test-assumptions",
                "scenario_key": "deterministic-test-scenario",
                "assumptions": [
                    {
                        "key": "supplier_unit_price",
                        "value": "100",
                        "unit": "unit",
                        "currency": "INR",
                        "reason": "Explicit deterministic test input",
                    },
                    {
                        "key": "supplier_currency",
                        "value": "INR",
                        "reason": "Explicit deterministic test input",
                    },
                    {
                        "key": "selling_price",
                        "value": "250",
                        "unit": "unit",
                        "currency": "INR",
                        "reason": "Explicit deterministic test input",
                    },
                    {
                        "key": "selling_currency",
                        "value": "INR",
                        "reason": "Explicit deterministic test input",
                    },
                    {
                        "key": "marketplace_fee_per_unit",
                        "value": "20",
                        "unit": "unit",
                        "currency": "INR",
                        "reason": "Explicit deterministic test input",
                    },
                ],
            },
            headers=ORIGIN,
        )
    )
    assert assumed["readiness"]["calculations"]["MOQ_AFFORDABILITY"]["status"] == "READY"
    assert assumed["readiness"]["calculations"]["BASIC_UNIT_MARGIN"]["status"] == "READY"
    assert assumed["readiness"]["economics_calculated"] is False
    assert any(
        item["provenance"] == "ASSUMED" and item["marker"] == "DETERMINISTIC_TEST"
        for item in assumed["assumptions"]
    )
    assert any(
        item["key"] == "supplier_moq" and float(item["value"]) == 500.0
        for item in assumed["claims"]
    )
    assert all(
        item["value"] != 0 for item in assumed["unknown_inputs"] if item["key"] == "freight_cost"
    )

    latest = _assert_ok(api.get(readiness_url, headers=ORIGIN))
    assert latest["id"] == assumed["id"]

    goal = _assert_ok(
        api.post(
            "/api/v1/intelligence/business-agent/goals",
            json={
                "raw_goal": "I have INR 300000 and want to start selling on Amazon India. Help me find a product in Kids category.",
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
                "idempotency_key": "pr5a-readiness-business-goal",
            },
            headers=ORIGIN,
        )
    )
    _assert_ok(
        api.post(
            f"/api/v1/intelligence/business-agent/goals/{goal['id']}/plan",
            headers=ORIGIN,
        )
    )
    journey = _assert_ok(api.get(f"/api/v1/commerce-journeys/{goal['id']}", headers=ORIGIN))[
        "journey"
    ]
    projected_readiness = journey["commercial_readiness"]
    assert projected_readiness["readiness"]["economics_calculated"] is False
    assert (
        projected_readiness["readiness"]["calculations"]["MOQ_AFFORDABILITY"]["status"] == "READY"
    )
    assert projected_readiness["assumptions"]
    assert projected_readiness["unknown_inputs"]
    run = _assert_ok(
        api.post(
            f"/api/v1/intelligence/business-agent/goals/{goal['id']}/runs",
            json={"idempotency_key": "pr5a-readiness-business-run", "max_steps": 20},
            headers=ORIGIN,
        )
    )
    started = _assert_ok(
        api.post(
            f"/api/v1/intelligence/business-agent/runs/{run['id']}/start",
            headers=ORIGIN,
        )
    )
    assert started["result"]["external_writes"] == []
    run_readiness = started["result"]["commercial_readiness"]
    assert run_readiness["readiness"]["economics_calculated"] is False
    assert run_readiness["known_inputs"]
    assert run_readiness["claims"]
    assert run_readiness["assumptions"]
    assert run_readiness["unknown_inputs"]
    assert run_readiness["missing_inputs"]
    assert run_readiness["readiness"]["safe_next_action"]
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "pr5a-readiness@example.com"))
        assert owner is not None
        rows = list(
            db.scalars(
                select(CommercialReadinessSnapshot).where(
                    CommercialReadinessSnapshot.owner_id == owner.id
                )
            )
        )
        assert len(rows) == 2
        term = db.scalar(
            select(SupplierCommercialTerm).where(SupplierCommercialTerm.owner_id == owner.id)
        )
        product = db.scalar(select(SupplierProduct).where(SupplierProduct.owner_id == owner.id))
        assert term is not None and term.moq == 500
        assert product is not None and product.moq == 500
        assert term.source_evidence_ids
        assert rows[-1].lineage["candidate"]["commercial_term_ids"]

    reconstruction_script = """
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
with Session(engine) as db:
    owner = db.scalar(select(User).where(User.email == "pr5a-readiness@example.com"))
    assert owner is not None
    assert db.scalar(select(ProductOpportunity).where(ProductOpportunity.owner_id == owner.id)) is not None
    snapshot = db.scalar(select(CommercialReadinessSnapshot).where(CommercialReadinessSnapshot.owner_id == owner.id).order_by(CommercialReadinessSnapshot.created_at.desc()))
    assert snapshot is not None
    assert snapshot.readiness["economics_calculated"] is False
    assert snapshot.lineage["candidate"]["evidence_ids"]
"""
    subprocess.run(
        [sys.executable, "-c", reconstruction_script],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
