"""Focused 12E validation and confidence API coverage."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

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
    engine.dispose()


def test_validation_is_deterministic_and_exposes_cross_source_contradiction(
    client: TestClient,
) -> None:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Trend Validation Owner",
            "email": "trend-12e@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    sources = []
    for provider in ("FIXTURE_A", "FIXTURE_B"):
        response = client.post(
            "/api/v1/intelligence/sources",
            json={
                "source_type": "trend_source",
                "display_name": f"12E {provider}",
                "provider": provider,
                "access_method": "manual_entry",
                "trust_classification": "trusted_internal",
            },
            headers=ORIGIN,
        )
        assert response.status_code == 201, response.text
        sources.append(response.json()["id"])
    context = client.post(
        "/api/v1/intelligence/trends/contexts",
        json={"name": "12E fixture", "subject_type": "CUSTOM", "subject_key": "trend-12e"},
        headers=ORIGIN,
    )
    assert context.status_code == 201, context.text
    context_id = context.json()["id"]
    signal = client.post(
        "/api/v1/intelligence/trends/signal-definitions",
        json={"signal_type": "TWELVE_E_INDEX", "measurement_type": "INDEX"},
        headers=ORIGIN,
    )
    assert signal.status_code == 201, signal.text
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for source_id, values in zip(sources, (("10", "12", "15"), ("15", "12", "10")), strict=True):
        for index, value in enumerate(values):
            response = client.post(
                f"/api/v1/intelligence/trends/contexts/{context_id}/observations",
                json={
                    "source_id": source_id,
                    "signal_definition_id": signal.json()["id"],
                    "observed_at": (start + timedelta(days=index)).isoformat(),
                    "period_start": (start + timedelta(days=index)).isoformat(),
                    "period_end": (start + timedelta(days=index)).isoformat(),
                    "granularity": "DAILY",
                    "value_numeric": value,
                    "unit": "index",
                    "scale": "100",
                    "geography_scope": "GLOBAL",
                    "freshness_state": "CURRENT",
                    "quality_state": "COMPLETE",
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
    analysis = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/analyses",
        json={"snapshot_id": snapshot.json()["id"]},
        headers=ORIGIN,
    )
    assert analysis.status_code == 201, analysis.text
    first = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/validations",
        json={"analysis_id": analysis.json()["id"]},
        headers=ORIGIN,
    )
    assert first.status_code == 201, first.text
    validation = first.json()
    assert validation["status"] == "CONTRADICTORY"
    assert validation["agreement_summary"]["state"] == "DISAGREE"
    assert validation["confidence"] in {"LOW", "MODERATE"}
    assert validation["downstream_readiness"] == "CONTRADICTORY"
    assert "demand" not in str(validation["evidence_coverage"]).lower()
    repeated = client.post(
        f"/api/v1/intelligence/trends/contexts/{context_id}/validations",
        json={"analysis_id": analysis.json()["id"]},
        headers=ORIGIN,
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == validation["id"]
    contradictions = client.get(
        f"/api/v1/intelligence/trends/contexts/{context_id}/validations/{validation['id']}/contradictions",
        headers=ORIGIN,
    )
    assert contradictions.status_code == 200, contradictions.text
    assert contradictions.json()[0]["contradiction_type"] == "DIRECTION_CONTRADICTION"
    hypotheses = client.get(
        f"/api/v1/intelligence/trends/contexts/{context_id}/validations/{validation['id']}/hypotheses",
        headers=ORIGIN,
    )
    assert hypotheses.status_code == 200, hypotheses.text
    assert len(hypotheses.json()) == 2
    doctor = client.get(
        "/api/v1/intelligence/trends/system-doctor",
        headers=ORIGIN,
    )
    assert doctor.status_code == 200, doctor.text
    checks = doctor.json()["checks"]
    assert checks["high_confidence_blocking_contradiction"] == 0
    assert checks["external_write_notification_exposure"] == 0
