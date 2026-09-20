"""Realistic ~100-product Competitor Intelligence performance certification."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, cast

import pytest
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

import vayujit_api.intelligence.cross_marketplace_models as _cross_marketplace_models  # noqa: F401
from vayujit_api.ai import models as _ai_models  # noqa: F401
from vayujit_api.core.database import Base
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User, UserRole, UserStatus
from vayujit_api.intelligence.competitor_agent_service import competitor_decision_brief
from vayujit_api.intelligence.competitor_change_schemas import ChangeComparisonCreate
from vayujit_api.intelligence.competitor_change_service import run_comparison
from vayujit_api.intelligence.competitor_commercial_models import CompetitorCommercialAnalysis
from vayujit_api.intelligence.competitor_commercial_schemas import CommercialAnalysisCreate
from vayujit_api.intelligence.competitor_commercial_service import run_analysis
from vayujit_api.intelligence.competitor_discovery_models import (
    CompetitorDiscoveryRequest,
    CompetitorDiscoverySnapshot,
)
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorObservation,
    CompetitorProduct,
)
from vayujit_api.intelligence.competitor_schemas import ContextCreate
from vayujit_api.intelligence.competitor_service import create_context
from vayujit_api.intelligence.competitor_winning_product_service import get_or_create_projection
from vayujit_api.intelligence.product_opportunity_models import (
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
    ProductOpportunityInputSnapshot,
)
from vayujit_api.media import models as _media_models  # noqa: F401

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture
def harness() -> Generator[tuple[sessionmaker[Session], Engine], None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory, engine
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _seed(factory: sessionmaker[Session]) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    now = datetime.now(UTC)
    with factory() as db:
        owner = User(
            full_name="Competitor benchmark owner",
            email=f"competitor-benchmark-{uuid.uuid4()}@example.com",
            normalized_email=f"competitor-benchmark-{uuid.uuid4()}@example.com",
            password_hash="test-only",
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        owner.normalized_email = owner.email
        db.add(owner)
        db.flush()
        opportunity = ProductOpportunity(
            owner_id=owner.id,
            name="100-product competitor benchmark",
            description="Disposable performance fixture.",
            product_concept="Home organization",
            category="Home",
            target_marketplace="amazon",
            target_region="IN",
            research_objective="Benchmark deterministic evidence processing.",
            origin="competitor_research",
            idempotency_key=f"benchmark-opportunity-{uuid.uuid4()}",
        )
        db.add(opportunity)
        db.flush()
        context = create_context(
            db,
            owner,
            ContextCreate(
                subject_type="PRODUCT_OPPORTUNITY",
                subject_reference=opportunity.id,
                marketplace="amazon",
                market="IN",
                category="Home",
                currency="INR",
                status="ACTIVE",
                idempotency_key=f"benchmark-context-{uuid.uuid4()}",
            ),
        )
        products: list[CompetitorProduct] = []
        observations: list[CompetitorObservation] = []
        for index in range(100):
            state = (
                "CONFIRMED"
                if index < 50
                else "PROBABLE" if index < 80 else "AMBIGUOUS" if index < 90 else "REJECTED"
            )
            product = CompetitorProduct(
                owner_id=owner.id,
                context_id=context.id,
                title=f"Benchmark product {index:03d}",
                brand_reference=f"Brand {index % 10}",
                seller_reference=f"Seller {index % 12}",
                marketplace="amazon",
                external_identifier=f"benchmark-{index:03d}",
                category="Home",
                availability_state="AVAILABLE",
                identity_state=state,
                evidence_state="AVAILABLE" if index < 90 else "INSUFFICIENT_EVIDENCE",
                idempotency_key=f"benchmark-product-{index:03d}",
            )
            products.append(product)
            db.add(product)
        db.flush()
        for index, product in enumerate(products):
            stamp = datetime.now(UTC)
            rows: tuple[tuple[str, Decimal | None, str | None, dict[str, Any]], ...] = (
                ("price", Decimal(100 + index), "INR", {"amount": str(100 + index)}),
                ("rating", Decimal("4.0") + Decimal(index % 10) / Decimal("10"), None, {}),
                ("review_count", Decimal(50 + index * 3), None, {}),
                ("brand", None, None, {"value": f"Brand {index % 10}"}),
                ("seller", None, None, {"value": f"Seller {index % 12}"}),
                ("features", None, None, {"values": ["stackable", "washable"]}),
            )
            for kind, numeric, currency, observed in rows:
                observations.append(
                    CompetitorObservation(
                        owner_id=owner.id,
                        competitor_product_id=product.id,
                        observation_type=kind,
                        observed_value=observed,
                        numeric_value=numeric,
                        currency=currency,
                        source_reference="local-100-product-benchmark",
                        observed_at=stamp,
                        retrieved_at=stamp,
                        freshness_state="CURRENT" if index % 7 else "STALE",
                        verification_state="OBSERVED",
                        observation_key=f"benchmark-{index:03d}-{kind}",
                        created_at=stamp,
                    )
                )
        db.add_all(observations)
        request = CompetitorDiscoveryRequest(
            owner_id=owner.id,
            context_id=context.id,
            marketplace="amazon",
            market="IN",
            category="Home",
            query_inputs={"fixture_size": 100},
            filters={},
            source_selection=["LOCAL_FIXTURE"],
            maximum_candidates=100,
            provider_mode="LOCAL_FIXTURE",
            input_fingerprint="benchmark-discovery-request",
            status="COMPLETED",
            version=1,
            created_by=owner.id,
            idempotency_key="benchmark-discovery-request",
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        db.add(request)
        db.flush()
        snapshots = [
            CompetitorDiscoverySnapshot(
                owner_id=owner.id,
                request_id=request.id,
                context_id=context.id,
                snapshot_version=version,
                candidate_count=100,
                accepted_candidate_count=80,
                ambiguous_count=10,
                rejected_count=10,
                source_counts={"LOCAL_FIXTURE": 100},
                source_diversity=1,
                evidence_coverage=Decimal("1"),
                competitor_product_references=[],
                input_fingerprint=f"benchmark-snapshot-{version}",
                idempotency_key=f"benchmark-snapshot-{version}",
                source_freshness={"LOCAL_FIXTURE": "CURRENT"},
                captured_at=now,
                created_at=now,
            )
            for version in range(1, 7)
        ]
        db.add_all(snapshots)
        db.commit()
        return owner.id, opportunity.id, [snapshot.id for snapshot in snapshots]


def _measure(engine: Engine, operation: Callable[[], object]) -> dict[str, object]:
    statements: list[str] = []

    def before_execute(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_execute)
    started = perf_counter()
    try:
        result = operation()
    finally:
        elapsed = perf_counter() - started
        event.remove(engine, "before_cursor_execute", before_execute)
    return {"queries": len(statements), "seconds": round(elapsed, 6), "result": result}


def _assessment(
    factory: sessionmaker[Session], owner_id: uuid.UUID, opportunity_id: uuid.UUID, version: int
) -> uuid.UUID:
    with factory() as db:
        constraint = ProductOpportunityConstraintVersion(
            owner_id=owner_id,
            opportunity_id=opportunity_id,
            version=version,
            marketplace="amazon",
            country_region="IN",
            currency="INR",
            idempotency_key=f"benchmark-constraint-{version}",
        )
        db.add(constraint)
        db.flush()
        snapshot = ProductOpportunityInputSnapshot(
            owner_id=owner_id,
            opportunity_id=opportunity_id,
            snapshot_version=version,
            payload={"source": "10G benchmark", "version": version},
            evidence_state="available",
        )
        db.add(snapshot)
        db.flush()
        assessment = ProductOpportunityAssessment(
            owner_id=owner_id,
            opportunity_id=opportunity_id,
            version=version,
            constraint_version_id=constraint.id,
            input_snapshot_id=snapshot.id,
            calculation_version="product-opportunity-foundation-v1",
            evidence_state="partial",
            status="created",
        )
        db.add(assessment)
        db.commit()
        return assessment.id


def test_realistic_100_product_fixture_benchmark(
    harness: tuple[sessionmaker[Session], Engine],
) -> None:
    factory, engine = harness
    owner_id, opportunity_id, snapshot_ids = _seed(factory)
    with factory() as db:
        context = db.scalar(select(CompetitorContext).where(CompetitorContext.owner_id == owner_id))
        assert context is not None
        counts = {
            "confirmed": db.scalar(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(CompetitorProduct.identity_state == "CONFIRMED")
            ),
            "probable": db.scalar(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(CompetitorProduct.identity_state == "PROBABLE")
            ),
            "ambiguous": db.scalar(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(CompetitorProduct.identity_state == "AMBIGUOUS")
            ),
            "rejected": db.scalar(
                select(func.count())
                .select_from(CompetitorProduct)
                .where(CompetitorProduct.identity_state == "REJECTED")
            ),
        }
        assert counts == {"confirmed": 50, "probable": 30, "ambiguous": 10, "rejected": 10}
        context_id = context.id

    analyses: list[uuid.UUID] = []
    commercial_measurements: list[dict[str, object]] = []
    for index, snapshot_id in enumerate(snapshot_ids[:3]):
        with factory() as db:
            owner = cast(User, db.get(User, owner_id))
            assert owner is not None

            def analysis_operation(
                db: Session = db,
                owner: User = owner,
                snapshot_id: uuid.UUID = snapshot_id,
                index: int = index,
            ) -> object:
                return run_analysis(
                    db,
                    owner,
                    context_id,
                    CommercialAnalysisCreate(
                        discovery_snapshot_id=snapshot_id,
                        maximum_products=100,
                        idempotency_key=f"benchmark-analysis-{index}",
                    ),
                )

            measurement = _measure(engine, analysis_operation)
            analyses.append(cast(CompetitorCommercialAnalysis, measurement["result"]).id)
            commercial_measurements.append({k: v for k, v in measurement.items() if k != "result"})

    change_measurements: list[dict[str, object]] = []
    for index, (baseline, current) in enumerate(
        ((analyses[0], analyses[1]), (analyses[1], analyses[2]), (analyses[0], analyses[2]))
    ):
        with factory() as db:
            owner = cast(User, db.get(User, owner_id))
            assert owner is not None

            def comparison_operation(
                db: Session = db,
                owner: User = owner,
                baseline: uuid.UUID = baseline,
                current: uuid.UUID = current,
                index: int = index,
            ) -> object:
                return run_comparison(
                    db,
                    owner,
                    context_id,
                    ChangeComparisonCreate(
                        baseline_analysis_id=baseline,
                        current_analysis_id=current,
                        idempotency_key=f"benchmark-comparison-{index}",
                    ),
                )

            measurement = _measure(engine, comparison_operation)
            change_measurements.append({k: v for k, v in measurement.items() if k != "result"})

    projection_measurements: list[dict[str, object]] = []
    for version in range(1, 4):
        assessment_id = _assessment(factory, owner_id, opportunity_id, version)
        with factory() as db:
            owner = cast(User, db.get(User, owner_id))
            opportunity = cast(ProductOpportunity, db.get(ProductOpportunity, opportunity_id))
            assessment = cast(
                ProductOpportunityAssessment, db.get(ProductOpportunityAssessment, assessment_id)
            )
            assert owner is not None and opportunity is not None and assessment is not None

            def projection_operation(
                db: Session = db,
                owner: User = owner,
                opportunity: ProductOpportunity = opportunity,
                assessment: ProductOpportunityAssessment = assessment,
            ) -> object:
                return get_or_create_projection(db, owner, opportunity, assessment)

            measurement = _measure(engine, projection_operation)
            db.commit()
            projection_measurements.append({k: v for k, v in measurement.items() if k != "result"})

    agent_measurements: list[dict[str, object]] = []
    for _ in range(3):
        with factory() as db:
            owner = cast(User, db.get(User, owner_id))
            opportunity = cast(ProductOpportunity, db.get(ProductOpportunity, opportunity_id))
            assert owner is not None and opportunity is not None

            def agent_operation(
                db: Session = db,
                owner: User = owner,
                opportunity: ProductOpportunity = opportunity,
            ) -> object:
                return competitor_decision_brief(db, owner, opportunity)

            measurement = _measure(engine, agent_operation)
            agent_measurements.append({k: v for k, v in measurement.items() if k != "result"})

    with factory() as db:
        owner = cast(User, db.get(User, owner_id))
        assert owner is not None
        with_ten = _measure(
            engine,
            lambda: run_analysis(
                db,
                owner,
                context_id,
                CommercialAnalysisCreate(
                    discovery_snapshot_id=snapshot_ids[3],
                    maximum_products=10,
                    idempotency_key="benchmark-analysis-ten",
                ),
            ),
        )
        with_hundred = _measure(
            engine,
            lambda: run_analysis(
                db,
                owner,
                context_id,
                CommercialAnalysisCreate(
                    discovery_snapshot_id=snapshot_ids[4],
                    maximum_products=100,
                    idempotency_key="benchmark-analysis-hundred-repeat",
                ),
            ),
        )

    benchmark = {
        "fixture": {"products": 100, **counts, "observations": 600, "snapshots": 6},
        "10C": commercial_measurements,
        "10D": change_measurements,
        "10E_to_9B_9E_9F": projection_measurements,
        "business_agent": agent_measurements,
        "n_plus_one": {
            "ten_products": {k: with_ten[k] for k in ("queries", "seconds")},
            "hundred_products": {k: with_hundred[k] for k in ("queries", "seconds")},
        },
    }
    print(f"COMPETITOR_10G_BENCHMARK={json.dumps(benchmark, sort_keys=True)}")
    assert all(cast(int, item["queries"]) < 80 for item in commercial_measurements)
    assert all(cast(int, item["queries"]) < 120 for item in change_measurements)
    assert all(cast(int, item["queries"]) < 80 for item in projection_measurements)
    assert all(cast(int, item["queries"]) < 40 for item in agent_measurements)
    assert cast(int, with_hundred["queries"]) <= cast(int, with_ten["queries"]) + 10
