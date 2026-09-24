"""Focused PostgreSQL API certification for Trend 12D."""

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
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    application = create_app()

    def override() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    application.dependency_overrides[get_session] = override
    with TestClient(application) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def test_change_comparison_is_ordered_idempotent_and_explainable(client: TestClient) -> None:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Trend Change Owner",
            "email": "trend-12d@example.com",
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
            "display_name": "12D Fixture",
            "provider": "LOCAL_FIXTURE",
            "access_method": "manual_entry",
            "trust_classification": "trusted_internal",
        },
        headers=ORIGIN,
    )
    assert source.status_code == 201, source.text
    context = client.post(
        "/api/v1/intelligence/trends/contexts",
        json={"name": "12D fixture", "subject_type": "CUSTOM", "subject_key": "trend-12d"},
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    signal = client.post(
        "/api/v1/intelligence/trends/signal-definitions",
        json={"signal_type": "TWELVE_D_INDEX", "measurement_type": "INDEX"},
        headers=ORIGIN,
    )
    assert signal.status_code == 201, signal.text
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index, value in enumerate(("10", "12", "15")):
        response = client.post(
            f"/api/v1/intelligence/trends/contexts/{context_id}/observations",
            json={
                "source_id": source.json()["id"],
                "signal_definition_id": signal.json()["id"],
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
    first_snapshot = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/snapshots", json={}, headers=ORIGIN
    )
    assert first_snapshot.status_code == 201, first_snapshot.text
    first_analysis = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses",
        json={"snapshot_id": first_snapshot.json()["id"]},
        headers=ORIGIN,
    )
    assert first_analysis.status_code == 201, first_analysis.text
    for index, value in enumerate(("20", "25", "30"), 3):
        response = client.post(
            f"/api/v1/intelligence/trends/contexts/{context_id}/observations",
            json={
                "source_id": source.json()["id"],
                "signal_definition_id": signal.json()["id"],
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
    second_snapshot = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/snapshots", json={}, headers=ORIGIN
    )
    assert second_snapshot.status_code == 201, second_snapshot.text
    second_analysis = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses",
        json={"snapshot_id": second_snapshot.json()["id"]},
        headers=ORIGIN,
    )
    assert second_analysis.status_code == 201, second_analysis.text
    payload = {
        "baseline_analysis_id": first_analysis.json()["id"],
        "current_analysis_id": second_analysis.json()["id"],
    }
    comparison = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/changes", json=payload, headers=ORIGIN
    )
    assert comparison.status_code == 201, comparison.text
    body = comparison.json()
    assert body["comparison"]["baseline_snapshot_id"] == first_snapshot.json()["id"]
    assert body["events"]
    assert any(item["momentum"] == "SUSTAINED_INCREASE" for item in body["events"])
    repeated = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/changes", json=payload, headers=ORIGIN
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["comparison"]["id"] == body["comparison"]["id"]
    events = client.get(
        f"/api/v1/intelligence/trends/contexts/{context_id}/changes/{body['comparison']['id']}/events",
        headers=ORIGIN,
    )
    assert events.status_code == 200, events.text
    assert Decimal(events.json()["items"][0]["absolute_delta"]) >= 0
    doctor = client.get("/api/v1/intelligence/trends/system-doctor", headers=ORIGIN)
    assert doctor.status_code == 200, doctor.text
    assert doctor.json()["status"] == "PASS", doctor.text
