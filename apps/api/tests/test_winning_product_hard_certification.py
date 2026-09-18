"""Focused Slice 9I-B hard-certification coverage for the 9A-9F flow."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
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
from vayujit_api.intelligence.product_opportunity_synthesis_models import (
    ProductOpportunityRiskEvidenceSynthesis,
)
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
pytestmark = pytest.mark.integration


@pytest.fixture
def harness() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client, factory
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _setup(
    api: TestClient,
    factory: sessionmaker[Session],
    *,
    email: str,
    listings: int = 3,
    prices: bool = True,
) -> tuple[str, str, str, list[str]]:
    response = api.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Winning Product Owner",
            "email": email,
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    stamp = datetime.now(UTC)
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == email))
        assert owner
        brand = Brand(
            owner_id=owner.id,
            name="Winning Product Brand",
            normalized_name="winning product brand",
            slug=f"winning-product-brand-{email.split('@')[0]}",
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
            name="Disposable Winning Product",
            normalized_name="disposable winning product",
            slug=f"disposable-winning-product-{email.split('@')[0]}",
            sku=f"WIN-{uuid.uuid4().hex[:8]}",
            product_type="physical",
            status="active",
            category="Home",
            price_amount=Decimal("100"),
            price_currency="INR",
            inventory_quantity=20,
            low_stock_threshold=2,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(product)
        db.flush()
        listing_ids: list[str] = []
        for index in range(listings):
            account = MarketplaceAccount(
                owner_id=owner.id,
                marketplace="amazon",
                display_name=f"Local evidence {index}",
                seller_account_id=f"winning-sandbox-{index}-{email.split('@')[0]}",
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
                local_listing_id=f"winning-local-{index}-{email.split('@')[0]}",
                remote_listing_id=f"winning-remote-{index}",
                marketplace_sku=f"WIN-SKU-{index}",
                title="Disposable Winning Product",
                status="active",
                publication_state="published",
                drift_state="none",
                last_synchronized_at=stamp - timedelta(hours=index),
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(listing)
            db.flush()
            listing_ids.append(str(listing.id))
            if prices:
                db.add(
                    MarketplacePrice(
                        owner_id=owner.id,
                        listing_id=listing.id,
                        currency="INR",
                        amount=Decimal("100") + index,
                        effective_from=stamp - timedelta(hours=index),
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
                    occurred_at=stamp - timedelta(hours=index),
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        db.commit()
        return str(owner.id), str(brand.id), str(product.id), listing_ids


def _add_price(factory: sessionmaker[Session], owner_id: str, listing_id: str) -> None:
    stamp = datetime.now(UTC)
    with factory() as db:
        db.add(
            MarketplacePrice(
                owner_id=uuid.UUID(owner_id),
                listing_id=uuid.UUID(listing_id),
                currency="INR",
                amount=Decimal("100"),
                effective_from=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        db.commit()


def _opportunity(
    api: TestClient,
    product_id: str,
    *,
    key: str,
    name: str = "Evidence-rich opportunity",
    description: str = "Deterministic evidence-backed opportunity",
) -> tuple[str, str]:
    opportunity = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": name,
            "description": description,
            "product_concept": "Bounded local certification product",
            "product_id": product_id,
            "category": "Home",
            "target_marketplace": "amazon",
            "origin": "marketplace_discovery",
            "idempotency_key": key,
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
            "idempotency_key": f"{key}-constraints",
        },
        headers=ORIGIN,
    )
    assert constraint.status_code == 201, constraint.text
    assessment = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments",
        json={"input_snapshot": {"source": "9i-b-hard-certification"}},
        headers=ORIGIN,
    )
    assert assessment.status_code == 201, assessment.text
    return opportunity_id, assessment.json()["id"]


def _landed_cost(factory: sessionmaker[Session], owner_id: str) -> str:
    from vayujit_api.intelligence.sourcing_models import CostScenario, LandedCostEstimate

    with factory() as db:
        scenario = CostScenario(
            owner_id=uuid.UUID(owner_id),
            name="9I-B canonical cost",
            version=1,
            currency="INR",
            inputs={"source": "local-certification"},
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


def _canonical_supplier(api: TestClient, factory: sessionmaker[Session], product_id: str) -> None:
    from vayujit_api.intelligence.supplier_models import SupplierProduct

    base = "/api/v1/intelligence/suppliers"
    search = api.post(
        base + "/searches",
        json={
            "product_id": product_id,
            "requirements": {"category": "Home"},
            "idempotency_key": f"9i-b-search-{uuid.uuid4()}",
        },
        headers=ORIGIN,
    )
    assert search.status_code == 200, search.text
    run = api.post(base + f"/searches/{search.json()['id']}/run", headers=ORIGIN)
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
    context = api.post(
        "/api/v1/intelligence/supplier-shortlisting/contexts",
        json={"product_id": product_id, "idempotency_key": f"9i-b-context-{uuid.uuid4()}"},
        headers=ORIGIN,
    )
    assert context.status_code == 200, context.text
    shortlist = api.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{context.json()['id']}/shortlists",
        json={"idempotency_key": f"9i-b-shortlist-{uuid.uuid4()}"},
        headers=ORIGIN,
    )
    assert shortlist.status_code == 200, shortlist.text
    assert selected_product_id


def _calculate_chain(
    api: TestClient,
    factory: sessionmaker[Session],
    *,
    owner_id: str,
    product_id: str,
    key: str,
    with_supplier: bool = True,
    evidence_mode: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    opportunity_id, assessment_id = _opportunity(api, product_id, key=key)
    for kind in ("demand", "competition"):
        response = api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/{kind}",
            json={"idempotency_key": f"{key}-{kind}"},
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    if with_supplier:
        _canonical_supplier(api, factory, product_id)
    commercial = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/commercial",
        json={
            "selling_price": "100",
            "selling_price_currency": "INR",
            "fee_per_unit": "12",
            "fixed_costs": "500",
            "moq": "10",
            "landed_cost_estimate_id": _landed_cost(factory, owner_id),
            "idempotency_key": f"{key}-commercial",
        },
        headers=ORIGIN,
    )
    assert commercial.status_code == 201, commercial.text
    feasibility = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/sourcing-feasibility",
        json={},
        headers=ORIGIN,
    )
    assert feasibility.status_code == 201, feasibility.text
    if evidence_mode:
        from vayujit_api.intelligence.product_opportunity_feasibility_models import (
            ProductOpportunitySourcingFeasibilityOutput,
        )
        from vayujit_api.intelligence.product_opportunity_intelligence_models import (
            ProductOpportunityIntelligenceOutput,
        )

        with factory() as db:
            sourcing_row = db.scalar(
                select(ProductOpportunitySourcingFeasibilityOutput).where(
                    ProductOpportunitySourcingFeasibilityOutput.assessment_id
                    == uuid.UUID(assessment_id)
                )
            )
            competition_row = db.scalar(
                select(ProductOpportunityIntelligenceOutput).where(
                    ProductOpportunityIntelligenceOutput.assessment_id == uuid.UUID(assessment_id),
                    ProductOpportunityIntelligenceOutput.kind == "competition",
                )
            )
            assert sourcing_row and competition_row
            sourcing_row.research_gaps = []
            if evidence_mode == "partial":
                sourcing_row.summary = {}
            if evidence_mode == "canonical":
                sourcing_row.upstream_lineage = {"portfolio": {"resilience": True}}
                sourcing_row.dimensions = [
                    *sourcing_row.dimensions,
                    {
                        "dimension": "SOURCING_RESILIENCE",
                        "value": 4,
                        "evidence_state": "AVAILABLE",
                    },
                ]
                competition_row.dimensions = [
                    *competition_row.dimensions,
                    {
                        "dimension": "DIFFERENTIATION_OPPORTUNITY",
                        "value": 60,
                        "evidence_state": "AVAILABLE",
                    },
                ]
            db.commit()
    synthesis = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/risk-evidence-synthesis",
        json={"idempotency_key": f"{key}-synthesis"},
        headers=ORIGIN,
    )
    assert synthesis.status_code == 201, synthesis.text
    score = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
        json={},
        headers=ORIGIN,
    )
    assert score.status_code == 201, score.text
    return opportunity_id, assessment_id, cast(dict[str, Any], score.json())


def test_canonical_9a_to_9f_evidence_rich_journey_and_reconciliation(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    owner_id, _brand_id, product_id, _listing_ids = _setup(
        api, factory, email="hard-canonical@example.com"
    )
    opportunity_id, assessment_id, score = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="canonical",
        evidence_mode="canonical",
    )
    assert score["eligibility"] == "SCORABLE"
    assert 0 <= Decimal(str(score["overall_score"])) <= 100
    assert score["confidence"] in {"HIGH", "MODERATE", "UNKNOWN"}
    assert score["risk_level"] in {"LOW", "MODERATE", "HIGH"}
    available = [
        row
        for row in score["dimensions"]
        if row["normalized_score"] is not None and row["evidence_state"] in {"AVAILABLE", "PARTIAL"}
    ]
    denominator = sum((Decimal(row["weight"]) for row in available), Decimal("0"))
    expected = (
        sum(
            (Decimal(row["normalized_score"]) * Decimal(row["weight"]) for row in available),
            Decimal("0"),
        )
        / denominator
    )
    assert Decimal(str(score["overall_score"])) == expected.quantize(Decimal("0.001"))
    explanation = api.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score/explanation",
        headers=ORIGIN,
    )
    assert explanation.status_code == 200 and len(explanation.json()) == 7
    decision_ids: list[str] = []
    for action in ("watch", "research_more", "shortlist", "reject", "archive"):
        decision = api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/decision",
            json={
                "action": action,
                "rationale": f"Human review: {action}",
                "idempotency_key": action,
            },
            headers=ORIGIN,
        )
        assert decision.status_code == 201, decision.text
        decision_ids.append(decision.json()["id"])
    assert len(set(decision_ids)) == 5
    history = api.get(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/score/history",
        headers=ORIGIN,
    )
    assert history.status_code == 200 and len(history.json()) == 1
    compare = api.post(
        "/api/v1/intelligence/product-opportunities/score/compare",
        json={"assessment_ids": [assessment_id, str(uuid.uuid4())]},
        headers=ORIGIN,
    )
    assert compare.status_code == 404
    assert (
        api.get(
            "/api/v1/intelligence/product-opportunities/score-system-doctor", headers=ORIGIN
        ).json()["status"]
        == "PASS"
    )


def test_sparse_partial_currency_negative_and_missing_resilience_semantics(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    owner_id, _brand_id, product_id, _listing_ids = _setup(
        api, factory, email="hard-sparse@example.com", listings=1, prices=False
    )
    opportunity_id, assessment_id = _opportunity(api, product_id, key="sparse")
    for kind in ("demand", "competition"):
        response = api.post(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/{kind}",
            json={},
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    score = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
        json={},
        headers=ORIGIN,
    )
    assert score.status_code == 201
    sparse = score.json()
    assert sparse["eligibility"] == "INSUFFICIENT_EVIDENCE"
    assert sparse["overall_score"] is None
    assert len(sparse["unavailable_dimensions"]) >= 6
    assert sparse["comparability"]["status"] == "NOT_COMPARABLE"
    _add_price(factory, owner_id, _listing_ids[0])
    partial_opportunity, partial_assessment, partial_score = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="partial",
        with_supplier=False,
        evidence_mode="partial",
    )
    assert partial_score["eligibility"] == "PARTIALLY_SCORABLE"
    assert partial_score["overall_score"] is not None
    assert partial_score["unavailable_dimensions"]
    negative_opportunity, negative_assessment = _opportunity(
        api, product_id, key="negative-economics"
    )
    mismatch_opportunity, mismatch_assessment = _opportunity(
        api, product_id, key="currency-mismatch"
    )
    negative = api.post(
        f"/api/v1/intelligence/product-opportunities/{negative_opportunity}/assessments/{negative_assessment}/commercial",
        json={
            "selling_price": "10",
            "selling_price_currency": "INR",
            "fee_per_unit": "12",
            "fixed_costs": "0",
            "moq": "10",
            "landed_cost_estimate_id": _landed_cost(factory, owner_id),
            "idempotency_key": "negative-economics",
        },
        headers=ORIGIN,
    )
    assert negative.status_code == 201
    economics = negative.json()["economics"]
    assert Decimal(str(economics["contribution_per_unit"])) < 0
    mismatch = api.post(
        f"/api/v1/intelligence/product-opportunities/{mismatch_opportunity}/assessments/{mismatch_assessment}/commercial",
        json={"selling_price": "100", "selling_price_currency": "USD"},
        headers=ORIGIN,
    )
    assert mismatch.status_code == 201
    assert mismatch.json()["economics"]["landed_cost_per_unit"] is None


def test_blocker_history_owner_isolation_xss_and_query_measurements(
    harness: tuple[TestClient, sessionmaker[Session]],
) -> None:
    api, factory = harness
    owner_id, _brand_id, product_id, _listing_ids = _setup(
        api, factory, email="hard-block@example.com"
    )
    opportunity_id, assessment_id, score = _calculate_chain(
        api,
        factory,
        owner_id=owner_id,
        product_id=product_id,
        key="blocker",
        with_supplier=False,
    )
    with factory() as db:
        synthesis = db.scalar(
            select(ProductOpportunityRiskEvidenceSynthesis).where(
                ProductOpportunityRiskEvidenceSynthesis.assessment_id == uuid.UUID(assessment_id)
            )
        )
        assert synthesis
        synthesis.risks = [
            {
                "category": "SUPPLIER",
                "type": "AUTHORITATIVE_BLOCK",
                "severity": "HIGH",
                "explanation": "Verified supplier block for hard certification.",
            }
        ]
        db.commit()
    blocked = api.post(
        f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
        json={
            "profile_version": "blocked-profile",
            "weights": {
                "DEMAND_ATTRACTIVENESS": 20,
                "COMPETITIVE_OPPORTUNITY": 15,
                "COMMERCIAL_VIABILITY": 20,
                "CAPITAL_EFFICIENCY": 15,
                "SUPPLIER_FEASIBILITY": 15,
                "SOURCING_RESILIENCE": 10,
                "DIFFERENTIATION_POTENTIAL": 5,
            },
        },
        headers=ORIGIN,
    )
    assert blocked.status_code == 201
    assert blocked.json()["eligibility"] == "BLOCKED"
    assert blocked.json()["overall_score"] is None
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/assessments/{assessment_id}/score",
            headers={"Origin": "http://127.0.0.1:4200"},
        ).status_code
        == 200
    )
    random_id = str(uuid.uuid4())
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{random_id}", headers=ORIGIN
        ).status_code
        == 404
    )
    assert (
        api.get(
            f"/api/v1/intelligence/product-opportunities/{random_id}/assessments/{assessment_id}/score",
            headers=ORIGIN,
        ).status_code
        == 404
    )
    xss = api.post(
        "/api/v1/intelligence/product-opportunities",
        json={
            "name": "<script>alert(1)</script>",
            "description": "<img src=x onerror=alert(1)>",
            "product_concept": "safe text",
            "idempotency_key": "xss-opportunity",
        },
        headers=ORIGIN,
    )
    assert xss.status_code == 201
    xss_detail = api.get(
        f"/api/v1/intelligence/product-opportunities/{xss.json()['id']}", headers=ORIGIN
    )
    assert xss_detail.status_code == 200
    assert xss_detail.headers["content-type"].startswith("application/json")
    assert xss_detail.json()["name"] == "<script>alert(1)</script>"
    assert score["risk_level"] in {"LOW", "MODERATE", "HIGH"}
    assert score["sensitivity"]["stability"] in {
        "UNKNOWN",
        "STABLE",
        "MODERATELY_SENSITIVE",
        "HIGHLY_SENSITIVE",
    }
    engine = cast(Engine, factory.kw["bind"])
    samples: dict[str, list[tuple[int, float]]] = {}
    for label, url in {
        "detail": f"/api/v1/intelligence/product-opportunities/{opportunity_id}",
        "score": (
            f"/api/v1/intelligence/product-opportunities/{opportunity_id}/"
            f"assessments/{assessment_id}/score"
        ),
    }.items():
        values: list[tuple[int, float]] = []
        for _ in range(3):
            count = 0

            def before_cursor_execute(*_args: object) -> None:
                nonlocal count
                count += 1

            event.listen(engine, "before_cursor_execute", before_cursor_execute)
            start = time.perf_counter()
            response = api.get(url, headers=ORIGIN)
            elapsed = time.perf_counter() - start
            event.remove(engine, "before_cursor_execute", before_cursor_execute)
            assert response.status_code == 200
            values.append((count, elapsed))
        samples[label] = values
    print(
        "HARD_CERT_QUERY_MEASUREMENTS="
        + json.dumps(
            {
                label: {
                    "queries": [q for q, _ in values],
                    "latency_ms": [round(t * 1000, 3) for _, t in values],
                    "median_latency_ms": round(median([t for _, t in values]) * 1000, 3),
                }
                for label, values in samples.items()
            },
            sort_keys=True,
        )
    )
    assert all(max(query for query, _ in values) < 100 for values in samples.values())
