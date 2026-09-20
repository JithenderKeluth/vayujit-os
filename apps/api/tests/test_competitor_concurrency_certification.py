"""Focused real-PostgreSQL concurrency certification for Competitor Intelligence."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import vayujit_api.intelligence.cross_marketplace_models as _cross_marketplace_models  # noqa: F401
from vayujit_api.core.database import Base
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User, UserRole, UserStatus
from vayujit_api.intelligence.competitor_change_models import CompetitorChangeComparison
from vayujit_api.intelligence.competitor_change_schemas import ChangeComparisonCreate
from vayujit_api.intelligence.competitor_change_service import run_comparison
from vayujit_api.intelligence.competitor_commercial_models import CompetitorCommercialAnalysis
from vayujit_api.intelligence.competitor_commercial_schemas import CommercialAnalysisCreate
from vayujit_api.intelligence.competitor_commercial_service import run_analysis
from vayujit_api.intelligence.competitor_models import (
    CompetitorContext,
    CompetitorEntity,
    CompetitorObservation,
    CompetitorProduct,
    CompetitorSnapshot,
)
from vayujit_api.intelligence.competitor_schemas import (
    CompetitorProductCreate,
    ContextCreate,
    EntityCreate,
    ObservationCreate,
    SnapshotCreate,
)
from vayujit_api.intelligence.competitor_service import (
    create_context,
    create_entity,
    create_observation,
    create_product,
    create_snapshot,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture
def factory() -> Generator[sessionmaker[Session], None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    value = sessionmaker(bind=engine, expire_on_commit=False)
    yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _seed(factory: sessionmaker[Session]) -> tuple[uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    with factory() as db:
        owner = User(
            full_name="Competitor concurrency owner",
            email=f"competitor-concurrency-{uuid.uuid4()}@example.com",
            normalized_email=f"competitor-concurrency-{uuid.uuid4()}@example.com",
            password_hash="test-only",
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        # Keep normalized_email aligned with email while avoiding any auth dependency.
        owner.normalized_email = owner.email
        db.add(owner)
        db.flush()
        opportunity = ProductOpportunity(
            owner_id=owner.id,
            name="Concurrency fixture opportunity",
            description="Disposable real PostgreSQL concurrency fixture.",
            product_concept="Kitchen organizer",
            category="Home",
            target_marketplace="amazon",
            target_region="IN",
            research_objective="Bounded concurrency certification.",
            origin="competitor_research",
            idempotency_key=f"concurrency-opportunity-{uuid.uuid4()}",
        )
        db.add(opportunity)
        db.commit()
        return owner.id, opportunity.id


def _run_concurrent[T](
    factory: sessionmaker[Session], worker: Callable[[Session, User], T], *, count: int = 3
) -> tuple[list[T], list[str]]:
    barrier = threading.Barrier(count)
    values: list[T] = []
    errors: list[str] = []
    lock = threading.Lock()

    def invoke() -> None:
        try:
            with factory() as db:
                owner = db.scalar(select(User))
                assert owner is not None
                barrier.wait(timeout=30)
                result = worker(db, owner)
                with lock:
                    values.append(result)
        except Exception as exc:  # pragma: no cover - surfaced in assertion below
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=invoke) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert all(not thread.is_alive() for thread in threads), "concurrency worker hung"
    return values, errors


def test_foundation_idempotency_under_real_postgresql_concurrency(
    factory: sessionmaker[Session],
) -> None:
    owner_id, opportunity_id = _seed(factory)
    context_data = ContextCreate(
        subject_type="PRODUCT_OPPORTUNITY",
        subject_reference=opportunity_id,
        marketplace="amazon",
        market="IN",
        category="Home",
        currency="INR",
        status="ACTIVE",
        idempotency_key="concurrency-context",
    )
    context_values, context_errors = _run_concurrent(
        factory, lambda db, owner: create_context(db, owner, context_data).id
    )
    assert not context_errors, context_errors
    assert len(set(context_values)) == 1
    context_id = context_values[0]

    entity_data = EntityCreate(
        display_name="Concurrency brand",
        entity_type="BRAND",
        canonical_name="concurrency-brand",
        evidence_state="AVAILABLE",
        idempotency_key="concurrency-entity",
    )
    entity_values, entity_errors = _run_concurrent(
        factory, lambda db, owner: create_entity(db, owner, entity_data).id
    )
    assert not entity_errors, entity_errors
    assert len(set(entity_values)) == 1
    entity_id = entity_values[0]

    product_data = CompetitorProductCreate(
        entity_id=entity_id,
        title="Concurrency product",
        marketplace="amazon",
        external_identifier="concurrency-product",
        category="Home",
        identity_state="CONFIRMED",
        evidence_state="AVAILABLE",
        idempotency_key="concurrency-product",
    )
    product_values, product_errors = _run_concurrent(
        factory,
        lambda db, owner: create_product(
            db,
            owner,
            cast(CompetitorContext, db.get(CompetitorContext, context_id)),
            product_data,
        ).id,
    )
    assert not product_errors, product_errors
    assert len(set(product_values)) == 1
    product_id = product_values[0]

    now = datetime.now(UTC)
    observation_data = ObservationCreate(
        observation_type="price",
        numeric_value=Decimal("199.00"),
        currency="INR",
        source_reference="concurrency-fixture",
        observed_at=now,
        retrieved_at=now,
        freshness_state="CURRENT",
        verification_state="OBSERVED",
        observation_key="concurrency-price",
    )
    observation_values, observation_errors = _run_concurrent(
        factory,
        lambda db, owner: create_observation(
            db,
            owner,
            cast(CompetitorProduct, db.get(CompetitorProduct, product_id)),
            observation_data,
        ).id,
    )
    assert not observation_errors, observation_errors
    assert len(set(observation_values)) == 1
    observation_id = observation_values[0]

    snapshot_data = SnapshotCreate(
        product_id=product_id,
        snapshot_version=1,
        input_fingerprint="concurrency-snapshot-fingerprint",
        observation_references=[observation_id],
        source_references=["concurrency-fixture"],
        payload={"fixture": True},
        schema_version="competitor-snapshot-v1",
        idempotency_key="concurrency-snapshot",
    )
    snapshot_values, snapshot_errors = _run_concurrent(
        factory,
        lambda db, owner: create_snapshot(
            db, owner, cast(CompetitorContext, db.get(CompetitorContext, context_id)), snapshot_data
        ).id,
    )
    assert not snapshot_errors, snapshot_errors
    assert len(set(snapshot_values)) == 1

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(CompetitorContext)) == 1
        assert db.scalar(select(func.count()).select_from(CompetitorEntity)) == 1
        assert db.scalar(select(func.count()).select_from(CompetitorProduct)) == 1
        assert db.scalar(select(func.count()).select_from(CompetitorObservation)) == 1
        assert db.scalar(select(func.count()).select_from(CompetitorSnapshot)) == 1


def test_analysis_and_change_idempotency_under_real_postgresql_concurrency(
    factory: sessionmaker[Session],
) -> None:
    owner_id, opportunity_id = _seed(factory)
    with factory() as db:
        owner = db.get(User, owner_id)
        assert owner is not None
        context = create_context(
            db,
            owner,
            ContextCreate(
                subject_type="PRODUCT_OPPORTUNITY",
                subject_reference=opportunity_id,
                marketplace="amazon",
                market="IN",
                category="Home",
                currency="INR",
                status="ACTIVE",
                idempotency_key="analysis-context",
            ),
        )
        product = create_product(
            db,
            owner,
            context,
            CompetitorProductCreate(
                title="Analysis product",
                marketplace="amazon",
                external_identifier="analysis-product",
                category="Home",
                identity_state="CONFIRMED",
                evidence_state="AVAILABLE",
                idempotency_key="analysis-product",
            ),
        )
        now = datetime.now(UTC)
        create_observation(
            db,
            owner,
            product,
            ObservationCreate(
                observation_type="price",
                numeric_value=Decimal("199"),
                currency="INR",
                source_reference="analysis-concurrency",
                observed_at=now,
                retrieved_at=now,
                freshness_state="CURRENT",
                verification_state="OBSERVED",
                observation_key="analysis-price",
            ),
        )
        context_id = context.id
        db.commit()

    analysis_data = CommercialAnalysisCreate(idempotency_key="concurrency-analysis")
    analysis_values, analysis_errors = _run_concurrent(
        factory, lambda db, owner: run_analysis(db, owner, context_id, analysis_data).id
    )
    assert not analysis_errors, analysis_errors
    assert len(set(analysis_values)) == 1
    baseline_analysis_id = analysis_values[0]
    with factory() as db:
        owner = db.scalar(select(User))
        context = cast(CompetitorContext, db.get(CompetitorContext, context_id))
        assert owner is not None and context is not None
        product = create_product(
            db,
            owner,
            context,
            CompetitorProductCreate(
                title="Analysis product two",
                marketplace="amazon",
                external_identifier="analysis-product-two",
                category="Home",
                identity_state="CONFIRMED",
                evidence_state="AVAILABLE",
                idempotency_key="analysis-product-two",
            ),
        )
        now = datetime.now(UTC)
        create_observation(
            db,
            owner,
            product,
            ObservationCreate(
                observation_type="price",
                numeric_value=Decimal("249"),
                currency="INR",
                source_reference="analysis-concurrency",
                observed_at=now,
                retrieved_at=now,
                freshness_state="CURRENT",
                verification_state="OBSERVED",
                observation_key="analysis-price-two",
            ),
        )
        current_analysis_id = run_analysis(
            db,
            owner,
            context_id,
            CommercialAnalysisCreate(idempotency_key="concurrency-analysis-current"),
        ).id

    comparison_data = ChangeComparisonCreate(
        baseline_analysis_id=baseline_analysis_id,
        current_analysis_id=current_analysis_id,
        idempotency_key="concurrency-comparison",
    )
    comparison_values, comparison_errors = _run_concurrent(
        factory, lambda db, owner: run_comparison(db, owner, context_id, comparison_data).id
    )
    assert not comparison_errors, comparison_errors
    assert len(set(comparison_values)) == 1

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(CompetitorCommercialAnalysis)) == 2
        assert db.scalar(select(func.count()).select_from(CompetitorChangeComparison)) == 1
