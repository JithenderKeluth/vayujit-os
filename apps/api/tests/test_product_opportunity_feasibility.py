"""Focused Slice 9D supplier and sourcing feasibility integration coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.brands.models import Brand
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.product_opportunity_feasibility_models import (
    ProductOpportunitySourcingFeasibilityOutput,
)
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

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


def _setup(api: TestClient, factory: sessionmaker[Session]) -> str:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Feasibility Owner",
            "email": "feasibility@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    stamp = datetime.now(UTC)
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "feasibility@example.com"))
        assert owner
        brand = Brand(
            owner_id=owner.id,
            name="Feasibility Brand",
            normalized_name="feasibility brand",
            slug="feasibility-brand",
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
            name="Disposable Feasibility Product",
            normalized_name="disposable feasibility product",
            slug="disposable-feasibility-product",
            sku="FEAS-001",
            product_type="physical",
            status="active",
            category="Home",
            price_amount=Decimal("20"),
            price_currency="INR",
            inventory_quantity=5,
            low_stock_threshold=1,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(product)
        db.commit()
        return str(product.id)


def _assessment(api: TestClient, product_id: str) -> tuple[str, str]:
    opportunity = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "Feasibility opportunity",
            "product_concept": "Bounded supplier test",
            "product_id": product_id,
            "category": "Home",
            "target_marketplace": "amazon",
            "origin": "supplier_discovery",
            "idempotency_key": "feasibility-opportunity",
        },
        headers=ORIGIN,
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = opportunity.json()["id"]
    constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={
            "currency": "INR",
            "maximum_landed_cost": "70",
            "maximum_moq": "20",
            "maximum_lead_time_days": 30,
            "idempotency_key": "feasibility-constraint",
        },
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "supplier"}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return opportunity_id, assessment.json()["id"]


def test_feasibility_is_assessment_bound_idempotent_and_safe(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    product_id = _setup(api, factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    path = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/"
        f"{assessment_id}/sourcing-feasibility"
    )
    response = api.post(path, json={}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["summary"]["feasibility_state"] == "INSUFFICIENT_EVIDENCE"
    assert "SUPPLIER_DISCOVERY_REQUIRED" in body["research_gaps"]
    assert "SUPPLIER_MATCH_REQUIRED" in body["research_gaps"]
    assert body["candidates"] == []
    assert body["constraint_snapshot"]["currency"] == "INR"
    assert all("password" not in str(value).lower() for value in body.values())

    repeated = api.post(path, json={"idempotency_key": "different-key"}, headers=ORIGIN)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == body["id"]
    with factory() as db:
        assert db.scalar(select(ProductOpportunitySourcingFeasibilityOutput.id)) is not None
        assert db.scalar(select(ProductOpportunitySourcingFeasibilityOutput.owner_id)) is not None

    assert api.get(path + "/suppliers", headers=ORIGIN).json()["candidates"] == []
    assert api.get(path + "/gaps", headers=ORIGIN).json() == body["research_gaps"]
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{uuid.uuid4()}"
            f"/assessments/{assessment_id}/sourcing-feasibility",
            headers=ORIGIN,
        ).status_code
        == 404
    )
    doctor = api.get(
        "/api/v1/intelligence/product-opportunities/sourcing-feasibility-system-doctor",
        headers=ORIGIN,
    )
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS", doctor.text


def test_canonical_supplier_projection_handoff_and_history(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """Exercise actual 8A discovery, canonical identity, 8B, and internal 8C handoff."""
    from vayujit_api.identity.router import current_user
    from vayujit_api.intelligence.supplier_models import SupplierProduct

    api, factory = client
    product_id = _setup(api, factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    supplier_base = "/api/v1/intelligence/suppliers"
    search = api.post(
        supplier_base + "/searches",
        json={
            "product_id": product_id,
            "requirements": {"category": "Home"},
            "idempotency_key": "9d-real-fixture-search",
        },
        headers=ORIGIN,
    )
    assert search.status_code == 200, search.text
    run = api.post(supplier_base + f"/searches/{search.json()['id']}/run", headers=ORIGIN)
    assert run.status_code == 200, run.text
    with factory() as db:
        products = list(db.scalars(select(SupplierProduct)))
        assert products
        supplier_ids = sorted({str(row.supplier_id) for row in products})
        selected_product_id = str(products[0].id)
    reconciled = api.post(
        "/api/v1/intelligence/cross-marketplace/suppliers/reconcile",
        json={"supplier_ids": supplier_ids},
        headers=ORIGIN,
    )
    assert reconciled.status_code == 200, reconciled.text
    canonical_ids = {row["id"] for row in reconciled.json()}
    shortlist_base = "/api/v1/intelligence/supplier-shortlisting"
    context = api.post(
        shortlist_base + "/contexts",
        json={
            "product_id": product_id,
            "idempotency_key": "9d-real-shortlist",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 200, context.text
    shortlist = api.post(
        shortlist_base + f"/contexts/{context.json()['id']}/shortlists",
        json={"idempotency_key": "9d-shortlist-version"},
        headers=ORIGIN,
    )
    assert shortlist.status_code == 200, shortlist.text
    path = (
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}"
        f"/assessments/{assessment_id}/sourcing-feasibility"
    )
    response = api.post(path, json={}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["summary"]["supplier_availability"]["discovered"] == len(canonical_ids)
    assert body["summary"]["candidate_product_count"] == len(products)
    assert all(row["canonical_supplier_id"] in canonical_ids for row in body["candidates"])
    assert all(row["shortlist"]["score_id"] for row in body["candidates"])
    assert all(row["shortlist"]["eligibility"] != "UNKNOWN" for row in body["candidates"])
    assert "NaN" not in response.text and "Infinity" not in response.text
    dimensions = {row["dimension"]: row for row in body["dimensions"]}
    assert dimensions["CAPITAL_FIT"]["value"] == "UNKNOWN"
    assert dimensions["LANDED_COST_FIT"]["value"] == "UNKNOWN"
    assert dimensions["MOQ_FIT"]["classification"] == "DERIVED_PROJECTION"
    assert body["summary"]["scenario_availability"] == "NO_SCENARIO"

    rejected = api.post(
        path + "/handoff", json={"supplier_product_id": selected_product_id}, headers=ORIGIN
    )
    assert rejected.status_code == 422
    handoff_payload = {"supplier_product_id": selected_product_id, "confirm": True}
    handoff = api.post(path + "/handoff", json=handoff_payload, headers=ORIGIN)
    assert handoff.status_code == 200, handoff.text
    assert handoff.json()["external_work_started"] is False
    context_id = handoff.json()["context_id"]
    repeat_handoff = api.post(path + "/handoff", json=handoff_payload, headers=ORIGIN)
    assert repeat_handoff.json()["context_id"] == context_id
    assert repeat_handoff.json()["reused"] is True
    assessed = api.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{context_id}/assess",
        headers=ORIGIN,
    )
    assert assessed.status_code == 200, assessed.text
    assert api.post(path, json={}, headers=ORIGIN).json() == body

    new_assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "9d-after-dd"}},
        headers=ORIGIN,
    )
    assert new_assessment.status_code == 201, new_assessment.text
    new_path = path.replace(assessment_id, new_assessment.json()["id"])
    missing = api.post(new_path, json={"supplier_product_ids": [str(uuid.uuid4())]}, headers=ORIGIN)
    assert missing.status_code == 404, missing.text
    assert missing.json() == {"detail": "Supplier product references unavailable."}
    portfolio = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "9D projection fixture", "idempotency_key": "9d-portfolio"},
        headers=ORIGIN,
    )
    assert portfolio.status_code == 201, portfolio.text
    portfolio_id = portfolio.json()["id"]
    for index, supplier_id in enumerate(sorted(canonical_ids)):
        member = api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members",
            json={
                "supplier_id": supplier_id,
                "allocation_percent": "100" if index == 0 else "0",
                "associated_products": [product_id],
                "country_region": "IN",
                "evidence_freshness": "fresh",
                "confidence": "75",
                "risk": "unknown",
                "alternate_source_status": "candidate",
            },
            headers=ORIGIN,
        )
        assert member.status_code == 201, member.text
    portfolio_assessment = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json={"idempotency_key": "9d-portfolio-assessment"},
        headers=ORIGIN,
    )
    assert portfolio_assessment.status_code == 201, portfolio_assessment.text
    for endpoint in ("concentration", "dependencies", "alternates"):
        derived = api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/{endpoint}",
            headers=ORIGIN,
        )
        assert derived.status_code == 200, derived.text
    fresh = api.post(new_path, json={}, headers=ORIGIN)
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["upstream_lineage"]["due_diligence_assessments"]
    projected_portfolio = fresh.json()["upstream_lineage"]["portfolio"]
    assert projected_portfolio["assessment_ids"] == [portfolio_assessment.json()["id"]]
    assert projected_portfolio["concentration"]
    assert projected_portfolio["resilience"] == []
    assert fresh.json()["summary"]["scenario_availability"] == "NO_SCENARIO"
    from vayujit_api.intelligence.portfolio_models import SupplierPortfolioConcentrationMetric

    with factory() as db:
        metrics = list(db.scalars(select(SupplierPortfolioConcentrationMetric)))
        stored = {str(row.id): str(row.value) for row in metrics}
        assert {row["id"]: row["value"] for row in projected_portfolio["concentration"]} == stored
    assert all(row["alternate_readiness"] != "READY" for row in fresh.json()["candidates"])
    assert fresh.json()["summary"]["supplier_availability"]["qualified_alternatives"] == 0

    assert len(api.get(new_path + "/history", headers=ORIGIN).json()) == 2
    assert (
        api.get(
            "/api/v1/intelligence/product-opportunities/sourcing-feasibility-system-doctor",
            headers=ORIGIN,
        ).json()["status"]
        == "PASS"
    )

    # Singleton-local owner storage uses an injected second principal to prove owner scope.
    other_owner = User(id=uuid.uuid4(), email="other@example.com", full_name="Other Owner")
    cast(FastAPI, api.app).dependency_overrides[current_user] = lambda: other_owner
    try:
        for section in (
            "",
            "/suppliers",
            "/shortlist",
            "/due-diligence",
            "/commercial",
            "/scenarios",
            "/alternatives",
            "/resilience",
            "/concentration",
            "/evidence",
            "/gaps",
            "/history",
        ):
            unavailable = api.get(path + section, headers=ORIGIN)
            assert unavailable.status_code == 404, unavailable.text
            assert unavailable.json() == {"detail": "Supplier feasibility assessment not found."}
        assert api.post(path, json={}, headers=ORIGIN).status_code == 404
        assert api.post(path + "/handoff", json=handoff_payload, headers=ORIGIN).status_code == 404
    finally:
        cast(FastAPI, api.app).dependency_overrides.pop(current_user)
