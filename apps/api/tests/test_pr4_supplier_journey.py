"""Focused PR-4 canonical ProductOpportunity supplier journey regression."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.due_diligence_models import SupplierDueDiligenceContext
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import SupplierSearch
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


def test_product_opportunity_shortlist_creates_scoped_due_diligence(
    client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = client
    setup = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "PR-4 Owner",
            "email": "pr4@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    now = datetime.now(UTC)
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "pr4@example.com"))
        assert owner
        opportunity = ProductOpportunity(
            owner_id=owner.id,
            name="Gel Ice Pack",
            description="Reusable cold-chain product.",
            product_concept="Gel ice pack",
            category="Home",
            target_marketplace="amazon",
            target_region="IN",
            origin="supplier_discovery",
            lifecycle_status="ready_for_assessment",
            research_state="completed",
            evidence_state="available",
            idempotency_key="pr4-opportunity",
            created_at=now,
            updated_at=now,
        )
        supplier = CrossMarketplaceSupplier(
            owner_id=owner.id,
            canonical_key="gelidicepacks.com",
            display_name="Gel Ice Packs",
            identity_state="MATCH",
            aliases=["Gel Ice Packs"],
            view_json={
                "commercial": {},
                "evidence_lineage": [{"source_url": "https://gelidicepacks.com"}],
                "risk": {"level": "MEDIUM"},
            },
            confidence_score=80,
            source_diversity_score=1,
            freshness_status="fresh",
            created_at=now,
            updated_at=now,
        )
        db.add_all([opportunity, supplier])
        db.flush()
        db.add(
            SupplierSearch(
                owner_id=owner.id,
                product_id=None,
                requirements={"product_opportunity_id": str(opportunity.id)},
                source_policy={"mode": "LIVE_READ_ONLY", "external_connectors": "disabled"},
                correlation_id="pr4-search",
                status="completed",
                idempotency_key="pr4-search",
                summary_json={"supplier_ids": [str(supplier.id)]},
                created_at=now,
                updated_at=now,
                completed_at=now,
            )
        )
        db.commit()
        opportunity_id = str(opportunity.id)

    context = api.post(
        "/api/v1/intelligence/supplier-shortlisting/contexts",
        json={
            "opportunity_id": opportunity_id,
            "target_market": "AMAZON_IN",
            "budget": 300000,
            "budget_currency": "INR",
            "idempotency_key": "pr4-shortlist-context",
        },
        headers=ORIGIN,
    )
    assert context.status_code == 200, context.text
    context_id = context.json()["id"]
    shortlist = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{context_id}/shortlists",
        json={"idempotency_key": "pr4-shortlist"},
        headers=ORIGIN,
    )
    assert shortlist.status_code == 200, shortlist.text
    candidate = (shortlist.json()["shortlist"] + shortlist.json()["review_required"])[0]
    decision = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{context_id}/decisions",
        json={
            "shortlist_version_id": shortlist.json()["id"],
            "supplier_id": candidate["supplier_id"],
            "decision": "KEEP_UNDER_REVIEW",
            "reason": "Human shortlist for due diligence.",
            "decision_key": "pr4-shortlist-decision",
        },
        headers=ORIGIN,
    )
    assert decision.status_code == 200, decision.text
    with factory() as db:
        due = list(
            db.scalars(
                select(SupplierDueDiligenceContext).where(
                    SupplierDueDiligenceContext.shortlist_context_id == uuid.UUID(context_id)
                )
            )
        )
        assert len(due) == 1
        assert due[0].opportunity_id == uuid.UUID(opportunity_id)
        assert due[0].product_id is None

        due_id = str(due[0].id)
    assessed = api.post(
        f"/api/v1/intelligence/supplier-due-diligence/contexts/{due_id}/assess",
        headers=ORIGIN,
    )
    assert assessed.status_code == 200, assessed.text
