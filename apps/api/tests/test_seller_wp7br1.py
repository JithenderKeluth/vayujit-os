"""R1 regressions: migrated PostgreSQL, synthetic evidence, no provider execution."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from helpers.ads_acceptance import create_campaign, setup_ads_context
from sqlalchemy import inspect, select
from test_ai_integration import ORIGIN

from vayujit_api.ads.models import AdCampaign, AdMetric, AdPerformanceAnomaly
from vayujit_api.ads.optimization import metric_snapshot
from vayujit_api.identity.models import User

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def seed_metrics(campaign_id: str, values: dict[str, str]) -> None:
    import test_ai_integration as integration

    assert integration.factory is not None
    with integration.factory() as db:
        owner = db.scalar(select(User.id))
        assert owner is not None
        stamp = datetime.now(UTC)
        for key, value in values.items():
            db.add(
                AdMetric(
                    owner_id=owner,
                    campaign_id=uuid.UUID(campaign_id),
                    metric_key=key,
                    value=Decimal(value),
                    availability="synthetic",
                    source="qa_synthetic_fixture",
                    observed_at=stamp,
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        db.commit()


def test_budget_without_observed_spend_is_not_zero_spend_or_delivery_failure(
    client: TestClient,
) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="r1-unknown")
    response = client.get("/api/v1/ads/anomalies", params={"campaign_id": campaign["id"]})
    assert response.status_code == 200
    assert response.json() == []
    import test_ai_integration as integration

    assert integration.factory is not None
    with integration.factory() as db:
        record = db.get(AdCampaign, uuid.UUID(campaign["id"]))
        assert record is not None
        assert metric_snapshot(db, record.owner_id, record.id) == {}
        assert db.scalar(select(AdPerformanceAnomaly.id)) is None


def test_parallel_overview_and_anomaly_reads_share_one_persisted_identity(
    client: TestClient,
) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="r1-concurrent")
    seed_metrics(campaign["id"], {"spend": "125"})
    import test_ai_integration as integration

    assert integration.factory is not None
    with integration.factory() as db:
        assert "uq_ad_performance_anomaly_fingerprint" in {
            row["name"]
            for row in inspect(db.connection()).get_unique_constraints("ad_performance_anomalies")
        }, "The actual migration constraint must remain present"
    barrier = Barrier(4, timeout=10)

    def read(index: int) -> str:
        barrier.wait()
        path = "/api/v1/ads/anomalies" if index % 2 else "/api/v1/ads/optimization/overview"
        response = client.get(path)
        assert response.status_code == 200
        rows = response.json() if index % 2 else response.json()["anomalies"]
        assert len(rows) == 1 and rows[0]["id"] and rows[0]["status"] == "open"
        assert rows[0]["type"] == "missing_metrics_ingestion"
        assert rows[0]["synthetic"] is True
        return str(rows[0]["id"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        identities = list(pool.map(read, range(4)))
    assert len(set(identities)) == 1
    with integration.factory() as db:
        rows = list(db.scalars(select(AdPerformanceAnomaly)))
        assert len(rows) == 1 and str(rows[0].id) == identities[0]
        assert rows[0].source == "synthetic_local"
    again = client.get("/api/v1/ads/anomalies").json()
    assert again[0]["id"] == identities[0]


def test_missing_numerators_are_not_derived_zero_rates(client: TestClient) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="r1-missing-rates")
    seed_metrics(campaign["id"], {"impressions": "1200"})
    import test_ai_integration as integration

    assert integration.factory is not None
    with integration.factory() as db:
        record = db.get(AdCampaign, uuid.UUID(campaign["id"]))
        assert record is not None
        assert metric_snapshot(db, record.owner_id, record.id) == {"impressions": 1200.0}
    assert client.get("/api/v1/ads/anomalies").json() == []
    seed_metrics(campaign["id"], {"clicks": "0", "spend": "0", "conversions": "0"})
    with integration.factory() as db:
        record = db.get(AdCampaign, uuid.UUID(campaign["id"]))
        assert record is not None
        metrics = metric_snapshot(db, record.owner_id, record.id)
        assert metrics["ctr"] == 0 and metrics["budget_utilization"] == 0
        assert "cpc" not in metrics and "cpa" not in metrics


def test_unknown_scope_and_unauthenticated_access_remain_denied(client: TestClient) -> None:
    assert client.get("/api/v1/ads/anomalies").status_code == 401
    context = setup_ads_context(client)
    create_campaign(client, context, suffix="r1-scope")
    response = client.get(
        "/api/v1/ads/anomalies",
        params={"campaign_id": str(uuid.uuid4())},
        headers=ORIGIN,
    )
    assert response.status_code == 200 and response.json() == []
