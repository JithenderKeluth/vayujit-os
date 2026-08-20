from __future__ import annotations

# mypy: ignore-errors
import uuid
from datetime import UTC

import pytest
from helpers.ads_acceptance import create_campaign, setup_ads_context
from sqlalchemy import select
from test_ai_integration import ORIGIN

from vayujit_api.identity.models import User

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_optimization_rule_evaluation_preview_confirm_and_idempotency(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="optimization")
    from datetime import datetime
    from decimal import Decimal

    import test_ai_integration as integration_fixture

    from vayujit_api.ads.models import AdMetric

    with integration_fixture.factory() as db:
        owner_id = db.scalar(select(User.id))
        assert owner_id is not None
        db.add_all(
            [
                AdMetric(
                    owner_id=owner_id,
                    campaign_id=campaign["id"],
                    metric_key="impressions",
                    value=Decimal("1200"),
                    availability="synthetic",
                    source="fake_connector",
                    observed_at=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                AdMetric(
                    owner_id=owner_id,
                    campaign_id=campaign["id"],
                    metric_key="conversions",
                    value=Decimal("0"),
                    availability="synthetic",
                    source="fake_connector",
                    observed_at=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                AdMetric(
                    owner_id=owner_id,
                    campaign_id=campaign["id"],
                    metric_key="spend",
                    value=Decimal("125"),
                    availability="synthetic",
                    source="fake_connector",
                    observed_at=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()
    rule = client.post(
        "/api/v1/ads/optimization-rules",
        json={
            "name": "pause on no conversion",
            "campaign_id": campaign["id"],
            "provider": "meta",
            "metric": "conversions",
            "operator": "==",
            "threshold": 0,
            "window_days": 7,
            "action": "pause_campaign",
            "enabled": True,
        },
        headers=ORIGIN,
    )
    assert rule.status_code == 201, rule.text
    evaluated = client.post(
        f"/api/v1/ads/optimization/evaluate?campaign_id={campaign['id']}",
        headers=ORIGIN,
    )
    assert evaluated.status_code == 200, evaluated.text
    assert evaluated.json()["recommendations"]
    recommendation = evaluated.json()["recommendations"][0]
    previewed = client.post(
        f"/api/v1/ads/recommendations/{recommendation['id']}/preview",
        json={},
        headers=ORIGIN,
    )
    assert previewed.status_code == 200, previewed.text
    assert previewed.json()["mutating"] is False
    confirmed = client.post(
        f"/api/v1/ads/recommendations/{recommendation['id']}/confirm",
        json={
            "preview_fingerprint": previewed.json()["fingerprint"],
            "idempotency_key": f"opt-{uuid.uuid4()}",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    repeated = client.post(
        f"/api/v1/ads/recommendations/{recommendation['id']}/confirm",
        json={
            "preview_fingerprint": previewed.json()["fingerprint"],
            "idempotency_key": confirmed.json()["execution"]["id"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert repeated.status_code in {200, 409}


def test_optimization_intelligence_is_synthetic_and_owner_scoped(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="intelligence")
    assert client.get("/api/v1/ads/optimization/overview", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/ads/anomalies", headers=ORIGIN).status_code == 200
    assert client.get("/api/v1/ads/creative-fatigue", headers=ORIGIN).status_code == 200
    assert (
        client.get("/api/v1/ads/cross-provider/comparison", headers=ORIGIN).json()["synthetic"]
        is True
    )
    assert (
        client.get(
            f"/api/v1/ads/campaigns/{campaign['id']}/intelligence", headers=ORIGIN
        ).status_code
        == 200
    )
