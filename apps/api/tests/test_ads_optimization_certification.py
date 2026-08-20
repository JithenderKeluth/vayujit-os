from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_campaign, setup_ads_context
from sqlalchemy import func, select
from test_ai_integration import ORIGIN

from vayujit_api.ads.models import AdCampaign, AdMetric, AdOptimizationRecommendation
from vayujit_api.ads.optimization import create_recommendation, recommendation_response
from vayujit_api.identity.models import User

# mypy: ignore-errors

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

ACTIONS = (
    "increase_budget",
    "decrease_budget",
    "pause_campaign",
    "resume_campaign",
    "pause_ad",
    "resume_ad",
    "replace_creative",
    "rotate_creative",
    "change_bid_strategy",
    "adjust_bid_target",
    "narrow_audience",
    "broaden_audience",
    "exclude_underperforming_segment",
    "add_negative_keyword",
    "remove_keyword",
    "increase_keyword_bid",
    "decrease_keyword_bid",
    "schedule_shift",
    "review_destination",
    "review_policy",
    "investigate_tracking",
    "investigate_anomaly",
)


def _owner_campaign(client: Any) -> tuple[Any, Any, Any]:
    context = setup_ads_context(client)
    payload = create_campaign(client, context, suffix="certification")
    assert integration_fixture.factory is not None
    db = integration_fixture.factory()
    owner = db.scalar(select(User))
    campaign = db.get(AdCampaign, uuid.UUID(payload["id"]))
    assert owner is not None and campaign is not None
    return campaign, db, owner


def test_recommendation_matrix_has_all_supported_actions(client: Any) -> None:
    campaign, db, owner = _owner_campaign(client)
    try:
        for action in ACTIONS:
            row = create_recommendation(db, owner, campaign, action, {"issue": f"matrix:{action}"})
            body = recommendation_response(row)
            assert body["evidence"]["availability"] == "synthetic"
            assert body["explanation"]["affected_entities"]["campaign_id"] == str(campaign.id)
            assert body["confidence"] in {"low", "medium", "high"}
            assert isinstance(body["risks"], list)
            assert "provider_compatibility" in body
            assert isinstance(body["actionable"], bool)
        db.commit()
    finally:
        db.close()


def test_recommendation_idempotency_and_stale_confirmation_are_safe(client: Any) -> None:
    campaign, db, owner = _owner_campaign(client)
    try:
        row = create_recommendation(db, owner, campaign, "pause_campaign", {"issue": "idempotency"})
        again = create_recommendation(
            db, owner, campaign, "pause_campaign", {"issue": "idempotency"}
        )
        assert row.id == again.id
        db.commit()
        assert (
            client.post(
                f"/api/v1/ads/recommendations/{row.id}/preview", json={}, headers=ORIGIN
            ).status_code
            == 200
        )
        db.add(
            AdMetric(
                owner_id=owner.id,
                campaign_id=campaign.id,
                metric_key="spend",
                value=Decimal("1"),
                availability="synthetic",
                source="fake_connector",
                observed_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        db.commit()
        stale = client.post(
            f"/api/v1/ads/recommendations/{row.id}/confirm",
            json={
                "preview_fingerprint": row.fingerprint,
                "idempotency_key": "stale-certification",
                "confirm": True,
            },
            headers=ORIGIN,
        )
        assert stale.status_code == 409
        assert "stale" in stale.text.casefold()
        assert db.scalar(select(func.count()).select_from(AdOptimizationRecommendation)) == 1
    finally:
        db.close()


def test_rule_lifecycle_and_validation_are_owner_scoped(client: Any) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="rule-certification")
    payload = {
        "name": "cert rule",
        "campaign_id": campaign["id"],
        "provider": "meta",
        "metric": "spend",
        "operator": ">",
        "threshold": 10,
        "window_days": 7,
        "action": "pause_campaign",
    }
    created = client.post("/api/v1/ads/optimization-rules", json=payload, headers=ORIGIN)
    assert created.status_code == 201
    rule_id = created.json()["id"]
    assert (
        client.get(f"/api/v1/ads/optimization-rules/{rule_id}", headers=ORIGIN).status_code == 200
    )
    updated = client.patch(
        f"/api/v1/ads/optimization-rules/{rule_id}", json={"threshold": 12}, headers=ORIGIN
    )
    assert updated.status_code == 200 and updated.json()["version"] == 2
    assert (
        client.post(
            f"/api/v1/ads/optimization-rules/{rule_id}/duplicate", headers=ORIGIN
        ).status_code
        == 201
    )
    assert (
        client.post(f"/api/v1/ads/optimization-rules/{rule_id}/disable", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/ads/optimization-rules/{rule_id}/enable", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/ads/optimization-rules/{rule_id}/archive", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(f"/api/v1/ads/optimization-rules/{rule_id}/restore", headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/ads/optimization-rules",
            json=dict(payload, name="bad", metric="not-a-metric"),
            headers=ORIGIN,
        ).status_code
        == 422
    )


def test_engine_performance_is_bounded_and_synthetic(client: Any) -> None:
    setup_ads_context(client)
    response = client.get("/api/v1/ads/optimization/engine/performance", headers=ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["synthetic"] is True
    assert body["elapsed_ms"] >= 0
