"""Focused authenticated 12C API integration coverage."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.main import create_app

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    assert TEST_DATABASE_URL and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session() -> Generator[Session, None, None]:
        with factory() as value:
            yield value

    app = create_app()
    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def test_analysis_is_snapshot_bound_descriptive_and_idempotent(client: TestClient) -> None:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Trend Owner",
            "email": "trend-12c@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    source = client.post(
        "/api/v1/intelligence/sources",
        json={
            "source_type": "trend_source",
            "display_name": "12C Fixture",
            "provider": "LOCAL_FIXTURE",
            "access_method": "manual_entry",
            "trust_classification": "trusted_internal",
        },
        headers=ORIGIN,
    )
    assert source.status_code == 201, source.text
    source_id = source.json()["id"]
    context = client.post(
        "/api/v1/intelligence/trends/contexts",
        json={"name": "12C fixture", "subject_type": "CUSTOM", "subject_key": "trend-12c"},
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    signal = client.post(
        "/api/v1/intelligence/trends/signal-definitions",
        json={"signal_type": "TWELVE_C_INDEX", "measurement_type": "INDEX"},
        headers=ORIGIN,
    )
    assert signal.status_code == 201, signal.text
    signal_id = signal.json()["id"]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index, value in enumerate(("10", "12", "15")):
        response = client.post(
            f"/api/v1/intelligence/trends/contexts/{context_id}/observations",
            json={
                "source_id": source_id,
                "signal_definition_id": signal_id,
                "observed_at": (start + timedelta(days=index)).isoformat(),
                "period_start": (start + timedelta(days=index)).isoformat(),
                "period_end": (start + timedelta(days=index)).isoformat(),
                "granularity": "DAILY",
                "value_numeric": value,
                "unit": "index",
                "scale": "100",
                "geography_scope": "GLOBAL",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
    snapshot = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/snapshots",
        json={},
        headers=ORIGIN,
    )
    assert snapshot.status_code == 201, snapshot.text
    payload = {"snapshot_id": snapshot.json()["id"]}
    first = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses",
        json=payload,
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    analysis = first.json()
    assert analysis["readiness"] == "AVAILABLE"
    repeated = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses",
        json=payload,
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == analysis["id"]
    series = client.get(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses/{analysis['id']}/series",
        headers=ORIGIN,
    )
    assert series.status_code == 200, series.text
    item = series.json()["items"][0]
    assert item["direction"] == "INCREASING"
    assert item["persistence"] == "PERSISTENT_INCREASE"
    assert item["change"]["absolute"] == "5"
    assert Decimal(item["change"]["relative_percent"]) == Decimal("50")
    doctor = client.get(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses/{analysis['id']}/doctor",
        headers=ORIGIN,
    )
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS"
