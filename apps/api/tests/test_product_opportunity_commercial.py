"""Focused Slice 9C commercial viability integration coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.brands.models import Brand
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceFee,
    MarketplaceListing,
    MarketplacePrice,
)
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.sourcing_models import CostScenario, LandedCostEstimate
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

    def test_session():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _setup(api: TestClient, factory: sessionmaker[Session]) -> tuple[str, str, str, str]:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Commercial Owner",
            "email": "commercial@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    stamp = datetime.now(UTC)
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "commercial@example.com"))
        assert owner
        brand = Brand(
            owner_id=owner.id,
            name="Commercial Brand",
            normalized_name="commercial brand",
            slug="commercial-brand",
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
            name="Disposable Commercial Product",
            normalized_name="disposable commercial product",
            slug="disposable-commercial-product",
            sku="COMM-001",
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
        db.flush()
        account = MarketplaceAccount(
            owner_id=owner.id,
            marketplace="amazon",
            display_name="Commercial Sandbox",
            seller_account_id="commercial-sandbox",
            environment="sandbox",
            enabled=True,
            credential_status="configured",
            encrypted_credentials="test-only",
            validation_status="valid",
            capabilities_json={},
            configuration_json={},
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(account)
        db.flush()
        listing = MarketplaceListing(
            owner_id=owner.id,
            brand_id=brand.id,
            product_id=product.id,
            account_id=account.id,
            marketplace="amazon",
            local_listing_id="commercial-listing",
            title="Commercial Product",
            status="active",
            publication_state="published",
            drift_state="none",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(listing)
        db.flush()
        db.add(
            MarketplacePrice(
                owner_id=owner.id,
                listing_id=listing.id,
                currency="INR",
                amount=Decimal("100"),
                effective_from=stamp - timedelta(days=2),
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.add(
            MarketplaceFee(
                owner_id=owner.id,
                account_id=account.id,
                fee_type="commission",
                amount=Decimal("12"),
                currency="INR",
                occurred_at=stamp - timedelta(days=1),
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()
        return str(owner.id), str(brand.id), str(product.id), str(listing.id)


def _assessment(api: TestClient, product_id: str) -> tuple[str, str]:
    opportunity = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "Commercial opportunity",
            "product_concept": "Bounded commercial test",
            "product_id": product_id,
            "category": "Home",
            "target_marketplace": "amazon",
            "origin": "marketplace_discovery",
            "idempotency_key": "commercial-opportunity",
        },
        headers=ORIGIN,
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = opportunity.json()["id"]
    constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={
            "currency": "INR",
            "available_capital": "10000",
            "target_margin": "0.20",
            "maximum_landed_cost": "70",
            "maximum_moq": "20",
            "maximum_lead_time_days": 30,
            "target_selling_price_min": "80",
            "target_selling_price_max": "150",
            "idempotency_key": "commercial-constraint",
        },
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "commercial"}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return opportunity_id, assessment.json()["id"]


def _landed(factory: sessionmaker[Session], owner_id: str) -> str:
    with factory() as db:
        scenario = CostScenario(
            owner_id=uuid.UUID(owner_id),
            name="COMM",
            version=1,
            currency="INR",
            inputs={"source": "test"},
            result={"landed_cost_per_unit": "45"},
            confidence="HIGH",
        )
        db.add(scenario)
        db.flush()
        estimate = LandedCostEstimate(
            owner_id=uuid.UUID(owner_id),
            scenario_id=scenario.id,
            per_unit=Decimal("45"),
            total=Decimal("900"),
            breakdown={"canonical": True},
            confidence="HIGH",
        )
        db.add(estimate)
        db.commit()
        return str(estimate.id)


def test_commercial_unknowns_and_owner_scoping(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    assert api.get("/api/v1/intelligence/product-opportunities").status_code == 401
    owner_id, _, product_id, _ = _setup(api, factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    response = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial",
        json={"selling_price": "100", "selling_price_currency": "INR"},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["economics"]["landed_cost_per_unit"] is None
    assert body["economics"]["selling_price_provenance"] == "USER_ASSUMPTION"
    assert any(gap["code"] == "LANDED_COST_REQUIRED" for gap in body["research_gaps"])
    assert any(row["dimension"] == "CONSTRAINT_FIT" for row in body["dimensions"])
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial/unit-economics",
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{uuid.uuid4()}/assessments/{assessment_id}/commercial",
            headers=ORIGIN,
        ).status_code
        == 404
    )
    doctor = api.get(
        "/api/v1/intelligence/product-opportunities/commercial-system-doctor", headers=ORIGIN
    )
    assert doctor.status_code == 200 and doctor.json()["status"] == "PASS"
    assert owner_id


def test_commercial_complete_economics_and_sensitivity_are_decimal_safe(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    owner_id, _, product_id, _ = _setup(api, factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    estimate_id = _landed(factory, owner_id)
    payload = {
        "selling_price": "100",
        "selling_price_currency": "INR",
        "fee_per_unit": "12",
        "fixed_costs": "500",
        "moq": "10",
        "landed_cost_estimate_id": estimate_id,
        "idempotency_key": "commercial-complete",
    }
    response = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial",
        json=payload,
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["economics"]["contribution_per_unit"] == "43.0000"
    assert body["economics"]["contribution_margin_percent"] == "43.0000"
    assert body["economics"]["break_even_units"] == "12"
    assert {item["scenario"] for item in body["sensitivity"]["combined"]} == {
        "BASELINE",
        "SCENARIO",
    }
    assert body["dimensions"]
    repeated = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial",
        json=payload,
        headers=ORIGIN,
    )
    assert repeated.status_code == 201 and repeated.json()["id"] == body["id"]
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial/constraints",
            headers=ORIGIN,
        ).json()["maximum_landed_cost"]
        == "WITHIN_LIMIT"
    )


def test_commercial_currency_mismatch_is_unknown_not_converted(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    owner_id, _, product_id, _ = _setup(api, factory)
    opportunity_id, assessment_id = _assessment(api, product_id)
    estimate_id = _landed(factory, owner_id)
    response = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial",
        json={
            "selling_price": "100",
            "selling_price_currency": "USD",
            "landed_cost_estimate_id": estimate_id,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["economics"]["landed_cost_per_unit"] is None
    assert body["dimensions"]
