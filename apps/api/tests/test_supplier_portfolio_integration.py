"""Focused 8E.5 operational integration coverage."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioContext,
    SupplierPortfolioHumanAction,
)
from vayujit_api.intelligence.sourcing_models import SourcingCalendarItem
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL is not None, "VAYUJIT_TEST_DATABASE_URL is required."
    engine = create_engine(TEST_DATABASE_URL)
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


def _setup(api: TestClient, factory: sessionmaker[Session]) -> tuple[str, uuid.UUID]:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Integration Owner",
            "email": "portfolio-integration@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        brand = Brand(
            owner_id=owner.id,
            name="Integration Brand",
            slug="integration-brand",
            normalized_name="integration brand",
            description="",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(brand)
        db.flush()
        product = Product(
            owner_id=owner.id,
            brand_id=brand.id,
            name="Integration Product",
            normalized_name="integration product",
            slug="integration-product",
            sku="INT-001",
            product_type="physical",
            status="active",
            inventory_quantity=0,
            low_stock_threshold=0,
            tags=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        supplier = CrossMarketplaceSupplier(
            owner_id=owner.id,
            canonical_key="integration-supplier",
            display_name="Integration Supplier",
            identity_state="MATCH",
            aliases=[],
            view_json={"capabilities": ["assembly"], "certifications": ["ISO"]},
            confidence_score=90,
            source_diversity_score=2,
            freshness_status="fresh",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add_all([product, supplier])
        db.commit()
        product_id = product.id
    portfolio = api.post(
        "/api/v1/intelligence/supplier-portfolios",
        json={"name": "Operational portfolio", "idempotency_key": "integration-portfolio-1"},
        headers=ORIGIN,
    )
    assert portfolio.status_code == 201, portfolio.text
    portfolio_id = portfolio.json()["id"]
    member = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/members",
        json={
            "supplier_id": str(supplier.id),
            "allocation_percent": 100,
            "associated_products": [str(product_id)],
            "country_region": "IN",
            "evidence_freshness": "fresh",
            "confidence": 90,
            "risk": "low",
            "capabilities": ["assembly"],
            "alternate_source_status": "qualified",
        },
        headers=ORIGIN,
    )
    assert member.status_code == 201, member.text
    assessment = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/assess",
        json={"idempotency_key": "integration-assessment-1"},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return portfolio_id, supplier.id


def test_operational_projection_handoffs_and_replay(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    portfolio_id, supplier_id = _setup(api, factory)

    resilience = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/resilience",
        headers=ORIGIN,
    )
    assert resilience.status_code == 200, resilience.text
    first_channel = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/product-channel",
        headers=ORIGIN,
    )
    replay_channel = api.get(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/product-channel",
        headers=ORIGIN,
    )
    assert first_channel.status_code == replay_channel.status_code == 200
    assert first_channel.json()["events"] == replay_channel.json()["events"]
    assert {row["event_type"] for row in first_channel.json()["events"]} >= {
        "PORTFOLIO_ASSESSMENT_CREATED",
        "PORTFOLIO_RESILIENCE_CHANGED",
    }

    calendar = api.get("/api/v1/intelligence/supplier-portfolios/calendar", headers=ORIGIN)
    assert calendar.status_code == 200
    assert calendar.json() == []
    operations = api.get("/api/v1/intelligence/supplier-portfolios/operations", headers=ORIGIN)
    assert operations.status_code == 200
    assert operations.json()["portfolio_contexts"] == 1
    assert operations.json()["current_assessments"] == 1
    assert operations.json()["drill_down"]["portfolios"] == [portfolio_id]
    doctor = api.get("/api/v1/intelligence/supplier-portfolios/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200
    assert doctor.json()["status"] == "PASS"

    payload = {
        "action": "REQUEST_DUE_DILIGENCE",
        "supplier_id": str(supplier_id),
        "rationale": "Verify current supplier evidence.",
        "idempotency_key": "integration-dd-request-1",
    }
    handoff = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/actions",
        json=payload,
        headers=ORIGIN,
    )
    replay = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/actions",
        json=payload,
        headers=ORIGIN,
    )
    assert handoff.status_code == replay.status_code == 200
    assert handoff.json()["idempotent_reuse"] is False
    assert replay.json()["idempotent_reuse"] is True
    with factory() as db:
        assert db.scalar(select(SupplierDueDiligenceContext)) is not None
        assert len(list(db.scalars(select(SupplierPortfolioHumanAction)))) == 1
        audit = list(
            db.scalars(select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(portfolio_id)))
        )
        assert (
            sum(
                row.metadata_json.get("event_type") == "PORTFOLIO_DUE_DILIGENCE_REQUESTED"
                for row in audit
            )
            == 1
        )


def test_stale_recovery_and_owner_scope_are_safe(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    portfolio_id, _ = _setup(api, factory)
    with factory() as db:
        portfolio = db.get(SupplierPortfolioContext, uuid.UUID(portfolio_id))
        assert portfolio is not None
        portfolio.status = "stale"
        db.commit()
    due = api.get("/api/v1/intelligence/supplier-portfolios/calendar", headers=ORIGIN)
    due_replay = api.get("/api/v1/intelligence/supplier-portfolios/calendar", headers=ORIGIN)
    assert due.status_code == due_replay.status_code == 200
    assert len(due.json()) == len(due_replay.json()) == 1
    assert due.json()[0]["kind"] == "PORTFOLIO_RESILIENCE_REVIEW_DUE"
    payload = {
        "action": "RECALCULATE_STALE_PORTFOLIO_ASSESSMENT",
        "reason": "Scheduled resilience review.",
        "idempotency_key": "integration-recovery-1",
        "confirm": True,
    }
    first = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    replay = api.post(
        f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recovery",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == replay.status_code == 200, first.text
    assert first.json()["idempotent_reuse"] is False
    assert replay.json()["idempotent_reuse"] is True
    assert (
        api.get(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/operations",
            headers={"Origin": "http://127.0.0.1:4200"},
        ).status_code
        == 404
    )
    assert (
        api.post(
            f"/api/v1/intelligence/supplier-portfolios/{portfolio_id}/recovery",
            json={
                **payload,
                "action": "RETRY_FAILED_PORTFOLIO_SIMULATION",
                "idempotency_key": "unsupported-1",
            },
            headers=ORIGIN,
        ).status_code
        == 409
    )
    with factory() as db:
        assert len(list(db.scalars(select(SupplierPortfolioContext)))) == 1
        assert len(list(db.scalars(select(SourcingCalendarItem)))) == 1
