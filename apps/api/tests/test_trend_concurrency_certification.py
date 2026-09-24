"""Real PostgreSQL concurrency certification for Trend Intelligence 12H-B."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import vayujit_api.intelligence.cross_marketplace_models as _cross_marketplace_models  # noqa: F401
import vayujit_api.intelligence.models as _intelligence_models  # noqa: F401
import vayujit_api.intelligence.trend_analysis_models as _trend_analysis_models  # noqa: F401
import vayujit_api.intelligence.trend_ingestion_models as _trend_ingestion_models  # noqa: F401
import vayujit_api.intelligence.trend_models as _trend_models  # noqa: F401
import vayujit_api.main as _main  # noqa: F401
from vayujit_api.core.database import Base
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.models import User, UserRole, UserStatus
from vayujit_api.intelligence.models import IntelligenceSource
from vayujit_api.intelligence.trend_analysis_models import TrendAnalysis
from vayujit_api.intelligence.trend_analysis_schemas import TrendAnalysisCreate
from vayujit_api.intelligence.trend_analysis_service import create_analysis
from vayujit_api.intelligence.trend_ingestion_models import TrendIngestionBatch
from vayujit_api.intelligence.trend_ingestion_schemas import (
    TrendIngestionRequest,
    TrendRawCandidate,
)
from vayujit_api.intelligence.trend_ingestion_service import ingest
from vayujit_api.intelligence.trend_models import TrendContext, TrendObservation, TrendSnapshot
from vayujit_api.intelligence.trend_schemas import (
    TrendContextCreate,
    TrendSignalDefinitionCreate,
    TrendSnapshotCreate,
)
from vayujit_api.intelligence.trend_service import (
    create_context,
    create_signal_definition,
    create_snapshot,
)

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture
def factory() -> Generator[sessionmaker[Session], None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    value = sessionmaker(bind=engine, expire_on_commit=False)
    yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def _parallel[T](
    factory: sessionmaker[Session], worker: Callable[[Session], T], *, count: int = 3
) -> tuple[list[T], list[str]]:
    barrier = threading.Barrier(count)
    values: list[T] = []
    errors: list[str] = []
    lock = threading.Lock()

    def invoke() -> None:
        try:
            with factory() as db:
                barrier.wait(timeout=30)
                result = worker(db)
                with lock:
                    values.append(result)
        except Exception as exc:  # pragma: no cover - surfaced by assertions below
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=invoke) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert all(not thread.is_alive() for thread in threads), "Trend concurrency worker hung"
    return values, errors


def _seed(factory: sessionmaker[Session]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    with factory() as db:
        owner = User(
            full_name="Trend concurrency owner",
            email=f"trend-concurrency-{uuid.uuid4()}@example.com",
            normalized_email=f"trend-concurrency-{uuid.uuid4()}@example.com",
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
        source = IntelligenceSource(
            owner_id=owner.id,
            source_type="trend_source",
            display_name="Trend concurrency fixture",
            provider="LOCAL_FIXTURE",
            access_method="manual_entry",
            trust_classification="trusted_internal",
            enabled=True,
            configuration_status="configured",
            terms_policy_status="accepted",
            metadata_json={},
            created_at=now,
            updated_at=now,
        )
        db.add(source)
        db.commit()
        owner_id, source_id = owner.id, source.id

    with factory() as db:
        loaded_owner = db.get(User, owner_id)
        assert loaded_owner is not None
        context = create_context(
            db,
            loaded_owner,
            TrendContextCreate(
                name="Trend concurrency context",
                subject_type="CUSTOM",
                subject_key="trend-concurrency",
                idempotency_key="trend-concurrency-context",
            ),
        )
        create_signal_definition(
            db,
            loaded_owner,
            TrendSignalDefinitionCreate(signal_type="CONCURRENCY_INDEX", measurement_type="INDEX"),
        )
        return owner_id, source_id, context.id


def test_trend_postgres_concurrency_is_idempotent_and_consistent(
    factory: sessionmaker[Session],
) -> None:
    owner_id, source_id, context_id = _seed(factory)
    observed_at = datetime(2026, 1, 1, tzinfo=UTC)
    request = TrendIngestionRequest(
        source_id=source_id,
        mode="LOCAL_FIXTURE",
        provider="LOCAL_FIXTURE",
        idempotency_key="trend-concurrency-ingestion",
        candidates=[
            TrendRawCandidate(
                provider_observation_id="trend-concurrency-observation",
                signal_key="CONCURRENCY_INDEX",
                measurement_type="INDEX",
                value_numeric=Decimal("42"),
                observed_at=observed_at,
                period_start=observed_at,
                period_end=observed_at,
                granularity="DAILY",
                geography_scope="GLOBAL",
            )
        ],
    )

    def run_ingestion(db: Session) -> uuid.UUID:
        owner = db.get(User, owner_id)
        context = db.get(TrendContext, context_id)
        assert owner is not None and context is not None
        return ingest(db, owner, context, request).id

    ingestion_ids, ingestion_errors = _parallel(factory, run_ingestion)
    assert not ingestion_errors, ingestion_errors
    assert len(set(ingestion_ids)) == 1

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(TrendIngestionBatch)) == 1
        assert db.scalar(select(func.count()).select_from(TrendObservation)) == 1
        batch = db.get(TrendIngestionBatch, ingestion_ids[0])
        assert batch is not None and batch.accepted_count == 1

    def run_snapshot(db: Session) -> uuid.UUID:
        owner = db.get(User, owner_id)
        context = db.get(TrendContext, context_id)
        assert owner is not None and context is not None
        return create_snapshot(db, owner, context, TrendSnapshotCreate()).id

    snapshot_ids, snapshot_errors = _parallel(factory, run_snapshot)
    assert not snapshot_errors, snapshot_errors
    assert len(set(snapshot_ids)) == 1

    def run_analysis(db: Session) -> uuid.UUID:
        owner = db.get(User, owner_id)
        context = db.get(TrendContext, context_id)
        assert owner is not None and context is not None
        return create_analysis(
            db, owner, context, TrendAnalysisCreate(snapshot_id=snapshot_ids[0])
        ).id

    analysis_ids, analysis_errors = _parallel(factory, run_analysis)
    assert not analysis_errors, analysis_errors
    assert len(set(analysis_ids)) == 1

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(TrendSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(TrendAnalysis)) == 1
        snapshot = db.get(TrendSnapshot, snapshot_ids[0])
        analysis = db.get(TrendAnalysis, analysis_ids[0])
        assert snapshot is not None and snapshot.observation_count == 1
        assert analysis is not None and analysis.snapshot_id == snapshot.id
