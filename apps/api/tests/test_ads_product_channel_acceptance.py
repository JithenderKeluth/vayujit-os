from __future__ import annotations

import pytest
import test_ai_integration as integration_fixture
from helpers.ads_acceptance import create_campaign, setup_ads_context
from sqlalchemy import func, select
from test_ai_integration import ORIGIN

from vayujit_api.ads.models import (
    Ad,
    AdAccount,
    AdCampaign,
    AdCreative,
    AdGroup,
    AdJob,
    AdRemoteMapping,
)
from vayujit_api.identity.models import User

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def test_product_channel_actions_are_owner_scoped_and_server_derived(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="channel-actions")
    channel = client.get(f"/api/v1/ads/product-channel/{context['product']['id']}", headers=ORIGIN)
    assert channel.status_code == 200
    provider = channel.json()["providers"][0]
    assert {"create_ad", "open_campaign", "preview_ad"} <= set(provider["actions"])
    assert provider["recovery"]["available"] is False
    response = client.post(
        "/api/v1/ads/recovery",
        json={
            "action": "retry",
            "entity_type": "campaign",
            "entity_id": campaign["id"],
            "failure_code": "ads.invalid_budget",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 422


def test_calendar_and_storage_integrity_counters_are_owner_scoped(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="calendar-storage")
    calendar = client.get("/api/v1/ads/calendar", headers=ORIGIN)
    assert calendar.status_code == 200
    assert isinstance(calendar.json(), list)
    assert integration_fixture.factory is not None
    with integration_fixture.factory() as db:
        assert db.scalar(select(func.count()).select_from(AdCampaign)) == 1
        assert db.scalar(select(func.count()).select_from(AdAccount)) == 1
        assert db.scalar(select(func.count()).select_from(AdGroup)) == 0
        assert db.scalar(select(func.count()).select_from(Ad)) == 0
        assert db.scalar(select(func.count()).select_from(AdCreative)) == 0
        assert db.scalar(select(func.count()).select_from(AdRemoteMapping)) == 0
        assert db.scalar(select(func.count()).select_from(AdJob)) == 0
        owner_id = db.scalar(select(User.id).where(User.email == "owner@example.com"))
        assert owner_id is not None
        assert str(campaign["product_id"]) == context["product"]["id"]


def test_analytics_is_unavailable_for_missing_or_incompatible_revenue(client) -> None:
    context = setup_ads_context(client)
    campaign = create_campaign(client, context, suffix="analytics-safety")
    analytics = client.get(f"/api/v1/ads/campaigns/{campaign['id']}/analytics", headers=ORIGIN)
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["roas"] is None
    assert body["profitability"] == "Unavailable"
    assert body["currency_compatible"] is True
    integrity = client.get("/api/v1/ads/storage/integrity", headers=ORIGIN)
    assert integrity.status_code == 200, integrity.text
    assert integrity.json()["duplicates"]["logical_job"] == 0
    assert integrity.json()["safe"] is True
