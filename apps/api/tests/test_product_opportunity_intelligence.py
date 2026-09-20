"""Focused 9B demand and competition intelligence integration coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.brands.models import Brand
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceListing,
    MarketplacePrice,
)
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_commercial_models import (
    CompetitorCommercialAnalysis,
    CompetitorComparableCohortEntry,
)
from vayujit_api.intelligence.competitor_models import CompetitorContext, CompetitorProduct
from vayujit_api.intelligence.competitor_winning_product_models import (
    CompetitorWinningProductProjection,
)
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None
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


def _setup_owner(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Intelligence Owner",
            "email": "intelligence@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _product_context(factory: sessionmaker[Session]) -> tuple[str, str, str]:
    stamp = datetime.now(UTC)
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "intelligence@example.com"))
        assert owner is not None
        brand = Brand(
            owner_id=owner.id,
            name="Evidence Brand",
            normalized_name="evidence brand",
            slug="evidence-brand",
            status="active",
            is_active_context=False,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(brand)
        db.flush()
        product = Product(
            owner_id=owner.id,
            brand_id=brand.id,
            name="Disposable Evidence Organizer",
            normalized_name="disposable evidence organizer",
            slug="disposable-evidence-organizer",
            sku="EVIDENCE-001",
            product_type="physical",
            status="active",
            category="Home",
            price_amount=Decimal("25.00"),
            price_currency="INR",
            inventory_quantity=10,
            low_stock_threshold=1,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(product)
        db.flush()
        db.commit()
        return str(owner.id), str(brand.id), str(product.id)


def _add_marketplace_evidence(
    factory: sessionmaker[Session], owner_id: str, brand_id: str, product_id: str
) -> None:
    stamp = datetime.now(UTC)
    with factory() as db:
        account_a = MarketplaceAccount(
            owner_id=uuid.UUID(owner_id),
            marketplace="amazon",
            display_name="Evidence Amazon",
            seller_account_id="evidence-amazon",
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
        account_b = MarketplaceAccount(
            owner_id=uuid.UUID(owner_id),
            marketplace="shopify",
            display_name="Evidence Shopify",
            seller_account_id="evidence-shopify",
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
        db.add_all([account_a, account_b])
        db.flush()
        listing_a = MarketplaceListing(
            owner_id=uuid.UUID(owner_id),
            brand_id=uuid.UUID(brand_id),
            product_id=uuid.UUID(product_id),
            account_id=account_a.id,
            marketplace="amazon",
            local_listing_id="evidence-amazon-listing",
            title="Evidence Organizer Amazon",
            status="active",
            publication_state="published",
            drift_state="none",
            last_synchronized_at=stamp - timedelta(days=2),
            created_at=stamp,
            updated_at=stamp,
        )
        listing_b = MarketplaceListing(
            owner_id=uuid.UUID(owner_id),
            brand_id=uuid.UUID(brand_id),
            product_id=uuid.UUID(product_id),
            account_id=account_b.id,
            marketplace="shopify",
            local_listing_id="evidence-shopify-listing",
            title="Evidence Organizer Shopify",
            status="ready",
            publication_state="not_submitted",
            drift_state="none",
            last_synchronized_at=stamp - timedelta(days=4),
            created_at=stamp,
            updated_at=stamp,
        )
        db.add_all([listing_a, listing_b])
        db.flush()
        db.add_all(
            [
                MarketplacePrice(
                    owner_id=uuid.UUID(owner_id),
                    listing_id=listing_a.id,
                    currency="INR",
                    amount=Decimal("25.00"),
                    effective_from=stamp - timedelta(days=2),
                    created_at=stamp,
                    updated_at=stamp,
                ),
                MarketplacePrice(
                    owner_id=uuid.UUID(owner_id),
                    listing_id=listing_b.id,
                    currency="USD",
                    amount=Decimal("10.00"),
                    effective_from=stamp - timedelta(days=4),
                    created_at=stamp,
                    updated_at=stamp,
                ),
            ]
        )
        db.commit()


def _create_opportunity_and_assessment(api: TestClient, product_id: str) -> tuple[str, str]:
    opportunity = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "Evidence-backed organizer",
            "product_concept": "A bounded marketplace evidence test",
            "product_id": product_id,
            "category": "Home",
            "target_marketplace": "amazon",
            "origin": "marketplace_discovery",
            "idempotency_key": "intelligence-opportunity-1",
        },
        headers=ORIGIN,
    )
    assert opportunity.status_code == 201, opportunity.text
    opportunity_id = opportunity.json()["id"]
    constraint = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/constraints",
        json={"currency": "INR", "idempotency_key": "intelligence-constraint-1"},
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"sources": ["marketplace listings"]}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return opportunity_id, assessment.json()["id"]


def test_demand_and_competition_are_deterministic_and_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    assert api.get("/api/v1/intelligence/product-opportunities").status_code == 401
    _setup_owner(api)
    owner_id, brand_id, product_id = _product_context(factory)
    _add_marketplace_evidence(factory, owner_id, brand_id, product_id)
    opportunity_id, assessment_id = _create_opportunity_and_assessment(api, product_id)

    demand = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/demand",
        json={},
        headers=ORIGIN,
    )
    assert demand.status_code == 201, demand.text
    demand_body = demand.json()
    assert demand_body["kind"] == "demand"
    assert {row["dimension"] for row in demand_body["dimensions"]} == {
        "MARKET_ACTIVITY",
        "DEMAND_STRENGTH",
        "DEMAND_MOMENTUM",
        "DEMAND_STABILITY",
        "EVIDENCE_COVERAGE",
        "EVIDENCE_FRESHNESS",
    }
    assert (
        next(row for row in demand_body["dimensions"] if row["dimension"] == "DEMAND_STRENGTH")[
            "value"
        ]
        is None
    )

    competition = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/competition",
        json={},
        headers=ORIGIN,
    )
    assert competition.status_code == 201, competition.text
    competition_body = competition.json()
    assert competition_body["kind"] == "competition"
    assert competition_body["input_snapshot"]["competition_source"] == "LEGACY_9B_EVIDENCE"
    assert (
        next(
            row
            for row in competition_body["dimensions"]
            if row["dimension"] == "COMPETITOR_DENSITY"
        )["value"]
        == 2
    )
    prices = next(
        row for row in competition_body["dimensions"] if row["dimension"] == "PRICE_COMPETITION"
    )["value"]
    assert set(prices) == {"INR", "USD"}
    assert prices["INR"]["median"] == "25.00"
    assert (
        next(
            row
            for row in competition_body["dimensions"]
            if row["dimension"] == "BRAND_CONCENTRATION"
        )["value"]
        == 1.0
    )

    repeated = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/competition",
        json={"idempotency_key": "different-key"},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == competition_body["id"]
    listed = api.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/intelligence",
        headers=ORIGIN,
    )
    assert listed.status_code == 200
    assert {row["kind"] for row in listed.json()} == {"demand", "competition"}
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{uuid.uuid4()}/assessments/{assessment_id}/demand",
            headers=ORIGIN,
        ).status_code
        == 404
    )
    doctor = api.get(
        "/api/v1/intelligence/product-opportunities/intelligence-system-doctor", headers=ORIGIN
    )
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS"


def test_demand_without_marketplace_evidence_is_explicitly_unavailable(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    _, _, product_id = _product_context(factory)
    opportunity_id, assessment_id = _create_opportunity_and_assessment(api, product_id)
    response = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/demand",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    activity = next(row for row in body["dimensions"] if row["dimension"] == "MARKET_ACTIVITY")
    assert activity["value"] is None
    assert activity["evidence_state"] == "unknown"
    assert "SALES_EVIDENCE_REQUIRED" in {gap["code"] for gap in body["research_gaps"]}


def test_current_competitor_analysis_projects_into_9b_without_counting_ambiguous_or_rejected(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    owner_id, _, product_id = _product_context(factory)
    opportunity_id, assessment_id = _create_opportunity_and_assessment(api, product_id)
    stamp = datetime.now(UTC)
    context_id = uuid.uuid4()
    with factory() as db:
        owner_uuid = uuid.UUID(owner_id)
        opportunity_uuid = uuid.UUID(opportunity_id)
        context = CompetitorContext(
            id=context_id,
            owner_id=owner_uuid,
            subject_type="PRODUCT_OPPORTUNITY",
            subject_reference=opportunity_uuid,
            product_opportunity_id=opportunity_uuid,
            marketplace="amazon",
            market="IN",
            category="Home",
            status="ACTIVE",
            created_by=owner_uuid,
            idempotency_key="10e-context",
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(context)
        db.flush()
        products = [
            CompetitorProduct(
                owner_id=owner_uuid,
                context_id=context.id,
                title=f"Competitor {index}",
                marketplace="amazon",
                external_identifier=f"10e-{index}",
                identity_state=state,
                evidence_state="AVAILABLE",
                idempotency_key=f"10e-product-{index}",
                first_observed=stamp,
                last_observed=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
            for index, state in enumerate(("CONFIRMED", "PROBABLE", "AMBIGUOUS", "REJECTED"), 1)
        ]
        db.add_all(products)
        db.flush()
        analysis = CompetitorCommercialAnalysis(
            owner_id=owner_uuid,
            context_id=context.id,
            opportunity_id=opportunity_uuid,
            analysis_version=1,
            status="COMPLETED",
            input_fingerprint="10e-analysis-fingerprint",
            input_snapshot={"source": "fixture"},
            cohort_summary={"included_product_ids": [str(products[0].id), str(products[1].id)]},
            pricing_analysis={
                "status": "MULTI_CURRENCY_NOT_COMPARABLE",
                "currencies": {"INR": {"sample_count": 1}, "USD": {"sample_count": 1}},
            },
            concentration_analysis={"brand": {"hhi": 0.5}, "seller": {"hhi": 0.5}},
            rating_analysis={"barrier": "UNKNOWN"},
            review_analysis={"barrier": "UNKNOWN"},
            differentiation_analysis=[{"type": "POTENTIAL_DIFFERENTIATOR"}],
            evidence_coverage={"cohort_products": 4},
            freshness_summary={"state": "CURRENT"},
            competitive_gaps=[{"code": "FEATURE_EVIDENCE_REQUIRED"}],
            research_gaps=[{"code": "PRICE_EVIDENCE_REQUIRED", "reason": "fixture"}],
            idempotency_key="10e-analysis",
            created_at=stamp,
        )
        db.add(analysis)
        db.flush()
        db.add_all(
            [
                CompetitorComparableCohortEntry(
                    owner_id=owner_uuid,
                    analysis_id=analysis.id,
                    context_id=context.id,
                    product_id=product.id,
                    identity_state=product.identity_state,
                    included=product.identity_state in {"CONFIRMED", "PROBABLE"},
                    evidence_state="AVAILABLE",
                    freshness_state="CURRENT",
                    observation_ids=[],
                    created_at=stamp,
                )
                for product in products
            ]
        )
        db.commit()

    response = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/competition",
        json={},
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["input_snapshot"]["competition_source"] == "DEDICATED_COMPETITOR_INTELLIGENCE"
    density = next(row for row in body["dimensions"] if row["dimension"] == "COMPETITOR_DENSITY")
    assert density["value"] == 2, body
    pricing = next(row for row in body["dimensions"] if row["dimension"] == "PRICE_COMPETITION")
    assert pricing["value"]["status"] == "MULTI_CURRENCY_NOT_COMPARABLE"
    projection = api.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/competition-projection",
        headers=ORIGIN,
    )
    assert projection.status_code == 200, projection.text
    assert projection.json()["source_state"] == "DEDICATED_COMPETITOR_INTELLIGENCE"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(CompetitorWinningProductProjection)) == 1
    doctor = api.get(
        "/api/v1/intelligence/product-opportunities/intelligence-system-doctor",
        headers=ORIGIN,
    )
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS", doctor.text
