"""Focused 10A Competitor Intelligence foundation integration coverage."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorEntity,
    CompetitorObservation,
    CompetitorProduct,
    CompetitorSnapshot,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
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


def _setup_owner(api: TestClient, *, email: str = "competitor@example.com") -> None:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Competitor Owner",
            "email": email,
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def _opportunity(factory: sessionmaker[Session], owner_id: UUID) -> UUID:
    with factory() as db:
        value = ProductOpportunity(
            owner_id=owner_id,
            name="Disposable competitor research opportunity",
            description="A bounded foundation fixture.",
            product_concept="Reusable kitchen organizer",
            category="Home",
            target_marketplace="amazon",
            target_region="IN",
            research_objective="Compare factual market observations.",
            origin="competitor_research",
            idempotency_key="competitor-foundation-opportunity",
        )
        db.add(value)
        db.commit()
        db.refresh(value)
        return value.id


def _owner_id(factory: sessionmaker[Session]) -> UUID:
    with factory() as db:
        owner = db.scalar(select(User))
        assert owner is not None
        return owner.id


def test_context_is_owner_scoped_idempotent_and_archivable(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    assert api.get("/api/v1/intelligence/competitors/contexts", headers=ORIGIN).status_code == 401
    _setup_owner(api)
    opportunity_id = _opportunity(factory, _owner_id(factory))
    payload = {
        "subject_type": "PRODUCT_OPPORTUNITY",
        "subject_reference": str(opportunity_id),
        "marketplace": "amazon",
        "market": "IN",
        "category": "Home",
        "currency": "inr",
        "status": "ACTIVE",
        "idempotency_key": "competitor-context-1",
    }
    first = api.post("/api/v1/intelligence/competitors/contexts", json=payload, headers=ORIGIN)
    assert first.status_code == 201, first.text
    repeated = api.post("/api/v1/intelligence/competitors/contexts", json=payload, headers=ORIGIN)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == first.json()["id"]
    context_id = first.json()["id"]
    archived = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context_id}/archive", headers=ORIGIN
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"
    assert archived.json()["version"] == 2
    assert (
        api.get(f"/api/v1/intelligence/competitors/contexts/{uuid4()}", headers=ORIGIN).status_code
        == 404
    )
    with factory() as db:
        assert db.scalar(select(CompetitorContext)) is not None
        assert "intelligence.competitor_context_created" in set(
            db.scalars(select(AuditEvent.action))
        )
        assert "intelligence.competitor_context_archived" in set(
            db.scalars(select(AuditEvent.action))
        )


def test_entity_product_identity_and_observations_preserve_freshness_and_decimal(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    owner_id = _owner_id(factory)
    opportunity_id = _opportunity(factory, owner_id)
    context = api.post(
        "/api/v1/intelligence/competitors/contexts",
        json={
            "subject_type": "PRODUCT_OPPORTUNITY",
            "subject_reference": str(opportunity_id),
            "marketplace": "amazon",
            "market": "IN",
            "idempotency_key": "context-observations",
        },
        headers=ORIGIN,
    ).json()
    entity = api.post(
        "/api/v1/intelligence/competitors/entities",
        json={
            "display_name": "Example seller",
            "entity_type": "SELLER",
            "canonical_name": "Example Seller",
            "marketplace_identifiers": {"seller_id": "seller-1"},
            "evidence_state": "PARTIAL",
            "idempotency_key": "entity-1",
        },
        headers=ORIGIN,
    )
    assert entity.status_code == 201, entity.text
    product = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context['id']}/products",
        json={
            "entity_id": entity.json()["id"],
            "title": "Example competitor product",
            "marketplace": "amazon",
            "external_identifier": "ASIN-001",
            "identity_state": "AMBIGUOUS",
            "idempotency_key": "competitor-product-1",
        },
        headers=ORIGIN,
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]
    identity = api.patch(
        f"/api/v1/intelligence/competitors/products/{product_id}/identity",
        json={"identity_state": "CONFIRMED"},
        headers=ORIGIN,
    )
    assert identity.status_code == 200
    now = datetime.now(UTC)
    observation = api.post(
        f"/api/v1/intelligence/competitors/products/{product_id}/observations",
        json={
            "observation_type": "price",
            "observed_value": {"amount": "1499.00"},
            "numeric_value": "1499.00",
            "currency": "inr",
            "source_reference": "manual-disposable-source",
            "observed_at": now.isoformat(),
            "retrieved_at": now.isoformat(),
            "freshness_state": "CURRENT",
            "observation_key": "price:2026-01-01",
        },
        headers=ORIGIN,
    )
    assert observation.status_code == 201, observation.text
    assert observation.json()["numeric_value"] == "1499.000000"
    stale = api.post(
        f"/api/v1/intelligence/competitors/products/{product_id}/observations",
        json={
            "observation_type": "price",
            "observed_value": {"amount": "1599.00"},
            "numeric_value": "1599.00",
            "currency": "INR",
            "source_reference": "manual-disposable-source-2",
            "observed_at": (now - timedelta(days=2)).isoformat(),
            "retrieved_at": now.isoformat(),
            "freshness_state": "STALE",
            "observation_key": "price:2025-12-30",
        },
        headers=ORIGIN,
    )
    assert stale.status_code == 201, stale.text
    assert (
        len(
            api.get(
                f"/api/v1/intelligence/competitors/products/{product_id}/observations",
                headers=ORIGIN,
            ).json()
        )
        == 2
    )
    assert (
        api.post(
            f"/api/v1/intelligence/competitors/products/{product_id}/observations",
            json={
                **{
                    "observation_type": "rating",
                    "source_reference": "manual",
                    "observed_at": now.isoformat(),
                    "retrieved_at": now.isoformat(),
                    "observation_key": "rating:invalid",
                },
                "numeric_value": "5.1",
            },
            headers=ORIGIN,
        ).status_code
        == 422
    )
    with factory() as db:
        assert db.scalar(select(CompetitorEntity)) is not None
        assert db.scalar(select(CompetitorProduct)) is not None
        assert len(list(db.scalars(select(CompetitorObservation)))) == 2


def test_snapshots_are_versioned_idempotent_and_observation_linked(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    opportunity_id = _opportunity(factory, _owner_id(factory))
    context = api.post(
        "/api/v1/intelligence/competitors/contexts",
        json={
            "subject_type": "PRODUCT_OPPORTUNITY",
            "subject_reference": str(opportunity_id),
            "marketplace": "amazon",
            "market": "IN",
            "idempotency_key": "context-snapshots",
        },
        headers=ORIGIN,
    ).json()
    product = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context['id']}/products",
        json={
            "title": "Snapshot product",
            "external_identifier": "SNAP-1",
            "idempotency_key": "snap-product",
        },
        headers=ORIGIN,
    ).json()
    now = datetime.now(UTC).isoformat()
    observation = api.post(
        f"/api/v1/intelligence/competitors/products/{product['id']}/observations",
        json={
            "observation_type": "availability",
            "observed_value": {"state": "available"},
            "source_reference": "manual",
            "observed_at": now,
            "retrieved_at": now,
            "observation_key": "availability:1",
        },
        headers=ORIGIN,
    ).json()
    payload = {
        "product_id": product["id"],
        "snapshot_version": 1,
        "input_fingerprint": "fingerprint-1",
        "source_references": ["manual"],
        "observation_references": [observation["id"]],
        "payload": {"price": "1499.00"},
        "idempotency_key": "snapshot-1",
    }
    first = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context['id']}/snapshots",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    repeated = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context['id']}/snapshots",
        json=payload,
        headers=ORIGIN,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == first.json()["id"]
    second = api.post(
        f"/api/v1/intelligence/competitors/contexts/{context['id']}/snapshots",
        json={
            **payload,
            "snapshot_version": 2,
            "input_fingerprint": "fingerprint-2",
            "idempotency_key": "snapshot-2",
        },
        headers=ORIGIN,
    )
    assert second.status_code == 201, second.text
    assert second.json()["snapshot_version"] == 2
    detail = api.get(f"/api/v1/intelligence/competitors/products/{product['id']}", headers=ORIGIN)
    assert detail.status_code == 200
    assert len(detail.json()["snapshots"]) == 2
    with factory() as db:
        assert len(list(db.scalars(select(CompetitorSnapshot)))) == 2


def test_product_and_brand_contexts_and_system_doctor_are_owner_scoped(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    _setup_owner(api)
    owner_id = _owner_id(factory)
    with factory() as db:
        brand = Brand(
            owner_id=owner_id,
            name="Fixture Brand",
            normalized_name="fixture brand",
            slug="fixture-brand",
            status="active",
            is_active_context=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(brand)
        db.flush()
        product = Product(
            owner_id=owner_id,
            brand_id=brand.id,
            name="Fixture Product",
            normalized_name="fixture product",
            slug="fixture-product",
            product_type="physical",
            status="draft",
            inventory_quantity=0,
            low_stock_threshold=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(product)
        db.commit()
        db.refresh(brand)
        db.refresh(product)
        brand_id, product_id = brand.id, product.id
    for subject_type, subject_id, key in (
        ("BRAND", brand_id, "brand-context"),
        ("PRODUCT", product_id, "product-context"),
    ):
        response = api.post(
            "/api/v1/intelligence/competitors/contexts",
            json={
                "subject_type": subject_type,
                "subject_reference": str(subject_id),
                "marketplace": "amazon",
                "market": "IN",
                "idempotency_key": key,
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    assert (
        api.get(f"/api/v1/intelligence/competitors/contexts/{uuid4()}", headers=ORIGIN).status_code
        == 404
    )
    doctor = api.get("/api/v1/intelligence/competitors/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS"
    system_doctor = api.get("/api/v1/intelligence/system-doctor", headers=ORIGIN)
    assert system_doctor.status_code == 200
    assert system_doctor.json()["checks"]["competitor_intelligence"]["status"] == "PASS"
