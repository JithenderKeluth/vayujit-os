"""PR-5B bounded deterministic landed-cost validation."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.intelligence.landed_cost_service import _provenance
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


def test_pr5b_preserves_source_claim_provenance_until_economic_mapping() -> None:
    assert _provenance({"provenance": "SOURCE_PROVIDED_CLAIM"}) == "SOURCE_PROVIDED_CLAIM"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _ok(response: Any) -> dict[str, Any]:
    assert response.status_code < 300, response.text
    return response.json()


def _prepare(api: TestClient) -> tuple[str, str]:
    _ok(
        api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "PR-5B Owner",
                "email": "pr5b-owner@example.com",
                "password": "correct horse battery staple",
                "password_confirmation": "correct horse battery staple",
            },
            headers=ORIGIN,
        )
    )
    opportunity = _ok(
        api.post(
            "/api/v1/intelligence/product-opportunities",
            json={
                "name": "Kids Lunch Box",
                "description": "A reusable lunch box for children.",
                "product_concept": "reusable kids lunch box",
                "category": "Kids",
                "subcategory": "Lunch Boxes",
                "target_marketplace": "AMAZON_IN",
                "target_region": "IN",
                "origin": "external_research",
                "research_state": "completed",
                "evidence_state": "available",
                "intelligence_profile": {
                    "normalized_product_concept": "reusable kids lunch box",
                    "evidence_environment": "DETERMINISTIC_TEST",
                },
                "lifecycle_status": "ready_for_assessment",
                "idempotency_key": "pr5b-opportunity",
            },
            headers=ORIGIN,
        )
    )
    oid = opportunity["id"]
    constraint = _ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{oid}/constraints",
            json={
                "available_capital": 300000,
                "currency": "INR",
                "marketplace": "AMAZON_IN",
                "country_region": "IN",
                "category_restrictions": ["Kids"],
                "idempotency_key": "pr5b-constraint",
            },
            headers=ORIGIN,
        )
    )
    assessment = _ok(
        api.post(
            f"/api/v1/intelligence/product-opportunities/{oid}/assessments",
            json={
                "constraint_version_id": constraint["id"],
                "evidence_state": "available",
                "status": "created",
                "input_snapshot": {"evidence_environment": "DETERMINISTIC_TEST"},
            },
            headers=ORIGIN,
        )
    )
    aid = assessment["id"]
    _ok(
        api.post(
            "/api/v1/intelligence/suppliers/research",
            json={
                "product_opportunity_id": oid,
                "product_query": "reusable kids lunch box",
                "category": "Kids",
                "country": "IN",
                "mode": "LOCAL_FIXTURE",
                "max_candidates": 1,
                "idempotency_key": "pr5b-supplier-search",
            },
            headers=ORIGIN,
        )
    )
    return oid, aid


def test_pr5b_readiness_gate_decimal_breakdown_idempotency_and_projection(
    client: TestClient,
) -> None:
    oid, aid = _prepare(client)
    readiness_url = (
        f"/api/v1/intelligence/product-opportunities/{oid}/assessments/{aid}/commercial-readiness"
    )
    blocked = _ok(
        client.post(readiness_url, json={"idempotency_key": "pr5b-missing"}, headers=ORIGIN)
    )
    assert blocked["readiness"]["calculations"]["LANDED_UNIT_COST"]["status"] == "NEEDS_INPUT"
    assumptions = [
        {
            "key": "supplier_unit_price",
            "value": "100.125",
            "unit": "per_unit",
            "currency": "INR",
            "reason": "Deterministic PR-5B scenario",
        },
        {"key": "supplier_currency", "value": "INR", "reason": "Deterministic PR-5B scenario"},
        {
            "key": "freight_cost",
            "value": "2500",
            "unit": "per_shipment",
            "currency": "INR",
            "reason": "Deterministic PR-5B scenario",
        },
        {"key": "freight_currency", "value": "INR", "reason": "Deterministic PR-5B scenario"},
        {"key": "origin", "value": "IN", "reason": "Deterministic PR-5B scenario"},
        {"key": "destination", "value": "IN", "reason": "Deterministic PR-5B scenario"},
    ]
    ready = _ok(
        client.post(
            readiness_url,
            json={
                "idempotency_key": "pr5b-ready",
                "scenario_key": "deterministic-pr5b",
                "assumptions": assumptions,
            },
            headers=ORIGIN,
        )
    )
    assert ready["readiness"]["calculations"]["LANDED_UNIT_COST"]["status"] == "READY"
    assert all(item["marker"] == "DETERMINISTIC_TEST" for item in ready["assumptions"])
    calc_url = f"/api/v1/intelligence/product-opportunities/{oid}/assessments/{aid}/landed-cost"
    result = _ok(
        client.post(
            calc_url,
            json={
                "idempotency_key": "pr5b-calc",
                "base_currency": "INR",
                "target_quantity": "500",
                "quantity_unit": "unit",
            },
            headers=ORIGIN,
        )
    )
    assert result["status"] == "CALCULATED"
    calculation = result["calculation"]
    assert calculation["calculation_version"] == "landed-cost-v5"
    assert calculation["currency"] == "INR"
    assert calculation["total_included_cost"] == "52562.50000000"
    assert calculation["per_unit_cost"] == "105.12500000"
    assert any(
        line["category"] == "PRODUCT_COST" and line["provenance"] == "ASSUMED"
        for line in result["breakdown"]
    )
    assert any(
        line["category"] == "FREIGHT" and line["basis"] == "PER_SHIPMENT"
        for line in result["breakdown"]
    )
    assert any(
        line["category"] == "IMPORT_TAX" and line["inclusion_status"] == "EXCLUDED"
        for line in result["breakdown"]
    )
    replay = _ok(
        client.post(
            calc_url,
            json={
                "idempotency_key": "pr5b-calc",
                "base_currency": "INR",
                "target_quantity": "500",
                "quantity_unit": "unit",
            },
            headers=ORIGIN,
        )
    )
    assert replay["idempotent_reuse"] is True and replay["calculation"]["id"] == calculation["id"]
    reconstructed = _ok(client.get(calc_url, headers=ORIGIN))
    assert reconstructed["calculation"]["id"] == calculation["id"]
    assert reconstructed["calculation"]["breakdown"]
    reconstruction_script = """
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_models import CommercialReadinessSnapshot
from vayujit_api.intelligence.economic_calculation_models import (
    EconomicCalculation,
    EconomicCalculationBreakdown,
)
engine = create_engine(os.environ["VAYUJIT_TEST_DATABASE_URL"])
with Session(engine) as db:
    owner = db.scalar(
        select(User).where(User.email == "pr5b-owner@example.com")
    )
    assert owner is not None
    calc = db.scalar(
        select(EconomicCalculation)
        .where(EconomicCalculation.owner_id == owner.id)
        .order_by(EconomicCalculation.created_at.desc())
    )
    assert calc is not None and str(calc.total_included_cost) == "52562.50000000"
    lines = list(
        db.scalars(
            select(EconomicCalculationBreakdown).where(
                EconomicCalculationBreakdown.calculation_id == calc.id
            )
        )
    )
    assert any(
        line.category == "IMPORT_TAX" and line.inclusion_status == "EXCLUDED"
        for line in lines
    )
    snapshot = db.scalar(
        select(CommercialReadinessSnapshot)
        .where(CommercialReadinessSnapshot.owner_id == owner.id)
        .order_by(CommercialReadinessSnapshot.created_at.desc())
    )
    assert snapshot is not None and snapshot.assumptions
"""
    subprocess.run(
        [sys.executable, "-c", reconstruction_script],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
    below = _ok(
        client.post(
            calc_url,
            json={
                "idempotency_key": "pr5b-below-moq",
                "base_currency": "INR",
                "target_quantity": "1",
                "quantity_unit": "unit",
            },
            headers=ORIGIN,
        )
    )
    assert below["status"] == "BLOCKED" and "target_quantity_below_moq" in below["missing_inputs"]
    projection = _ok(
        client.get(
            f"/api/v1/intelligence/product-opportunities/{oid}/sourcing-economics", headers=ORIGIN
        )
    )
    assert (
        projection["calculation"]["id"] == calculation["id"]
        and projection["calculation"]["per_unit_cost"] == "105.12500000"
    )
