from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
import test_ai_integration
from helpers.ads_acceptance import create_account, setup_ads_context
from sqlalchemy import func, select
from test_ai_integration import ORIGIN

from vayujit_api.ads import service as ads_service
from vayujit_api.ads.connectors import CONNECTORS
from vayujit_api.ads.models import AdJob, AdRemoteMapping
from vayujit_api.ads.service import now
from vayujit_api.ads.worker import run_next_ads_job
from vayujit_api.audit.models import AuditEvent
from vayujit_api.identity.models import User

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _reset(provider: str) -> Any:
    connector = CONNECTORS[provider]
    connector.state.calls.clear()
    for entities in connector.state.entities.values():
        entities.clear()
    connector.state.failures.clear()
    return connector


def _owner_id() -> Any:
    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        return db.scalar(select(User.id).where(User.email == "owner@example.com"))


def _marketplace_payload(
    client: Any, context: dict[str, Any], provider: str, *, target_type: str = "product"
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    account = create_account(client, provider, f"closure-{provider}")
    listing = client.post(
        "/api/v1/ads/marketplace/listings",
        json={
            "account_id": account["id"],
            "product_id": context["product"]["id"],
            "marketplace": provider,
            "listing_id": f"{provider.upper()}-CLOSURE-{uuid.uuid4().hex[:8]}",
            "version": 1,
            "title": f"{provider.title()} closure product",
            "sku": f"{provider.upper()}-CLOSURE-{uuid.uuid4().hex[:8]}",
        },
        headers=ORIGIN,
    )
    assert listing.status_code == 201, listing.text
    item = listing.json()
    payload = {
        "provider": provider,
        "marketplace": provider,
        "account_id": account["id"],
        "brand_id": context["brand"]["id"],
        "product_id": context["product"]["id"],
        "listing_id": item["listing_id"],
        "listing_version": item["version"],
        "listing_state": item["state"],
        "name": f"{provider.title()} closure campaign",
        "objective": "sales",
        "bidding_strategy": "dynamic_down_only" if provider == "amazon" else "manual_cpc",
        "targeting_summary": {
            "target_type": target_type,
            "listing_id": item["listing_id"],
            "positive_keywords": ["heritage"] if target_type == "keywords" else [],
            "negative_keywords": ["clearance"] if target_type == "keywords" else [],
            "match_type": "exact",
            "locale": "en-IN",
        },
        "budget": {"daily_amount": "25", "currency": "INR"},
        "idempotency_key": f"{provider}-closure-{uuid.uuid4().hex}-{target_type}",
    }
    return account, item, payload


def _queue_marketplace(client: Any, context: dict[str, Any], provider: str) -> dict[str, Any]:
    account, listing, payload = _marketplace_payload(client, context, provider)
    preview = client.post("/api/v1/ads/marketplace/campaigns/preview", json=payload, headers=ORIGIN)
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/ads/marketplace/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200, confirmed.text
    return {
        "account": account,
        "listing": listing,
        "payload": payload,
        "campaign": confirmed.json()["campaign"],
        "job_id": confirmed.json()["job"]["id"],
    }


def _manual_creative(
    client: Any, campaign: dict[str, Any], key: str, headline: str
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/creatives",
        json={
            "campaign_id": campaign["id"],
            "product_id": campaign["product_id"],
            "creative_type": "manual",
            "headline": headline,
            "primary_text": "Approved marketplace content.",
            "cta": "shop_now",
            "destination_url": "https://example.com/product",
            "placements": ["search"],
            "idempotency_key": key,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _publish_ad(client: Any, queued: dict[str, Any]) -> dict[str, Any]:
    campaign = queued["campaign"]
    group = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/groups",
        json={
            "name": "Marketplace targeting group",
            "targeting": {"target_type": "product", "listing_id": queued["listing"]["listing_id"]},
            "idempotency_key": f"group-{campaign['id']}",
        },
        headers=ORIGIN,
    )
    assert group.status_code == 201, group.text
    assert (
        client.post(f"/api/v1/ads/jobs/{group.json()['job_id']}/run", headers=ORIGIN).json()[
            "status"
        ]
        == "succeeded"
    )
    creative = _manual_creative(client, campaign, f"creative-{campaign['id']}", "Marketplace v1")
    ad = client.post(
        f"/api/v1/ads/groups/{group.json()['id']}/ads",
        json={
            "creative_id": creative["id"],
            "placement": "search",
            "idempotency_key": f"ad-{campaign['id']}",
        },
        headers=ORIGIN,
    )
    assert ad.status_code == 201, ad.text
    assert (
        client.post(f"/api/v1/ads/jobs/{ad.json()['job_id']}/run", headers=ORIGIN).json()["status"]
        == "succeeded"
    )
    return {"group": group.json(), "creative": creative, "ad": ad.json()}


def _measure(label: str, operation: Any, *, samples: int = 5) -> Any:
    durations: list[float] = []
    response = None
    for _ in range(samples):
        started = time.perf_counter()
        response = operation()
        durations.append((time.perf_counter() - started) * 1000)
        assert response.status_code < 400, response.text
    ordered = sorted(durations)
    median = ordered[len(ordered) // 2]
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(f"marketplace {label}: median={median:.1f}ms p95={p95:.1f}ms samples={samples}")
    return response


def test_marketplace_local_performance_baseline(client: Any) -> None:
    context = setup_ads_context(client)
    _reset("amazon")
    _, listing, payload = _marketplace_payload(client, context, "amazon")
    readiness_url = "/api/v1/ads/marketplace/campaigns/readiness"
    preview_url = "/api/v1/ads/marketplace/campaigns/preview"
    _measure(
        "capabilities", lambda: client.get("/api/v1/ads/marketplace/capabilities", headers=ORIGIN)
    )
    _measure("readiness", lambda: client.post(readiness_url, json=payload, headers=ORIGIN))
    preview = _measure("preview", lambda: client.post(preview_url, json=payload, headers=ORIGIN))
    started = time.perf_counter()
    confirmed = client.post(
        "/api/v1/ads/marketplace/campaigns/confirm",
        json={
            "campaign": payload,
            "preview_fingerprint": preview.json()["fingerprint"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    confirm_ms = (time.perf_counter() - started) * 1000
    assert confirmed.status_code == 200, confirmed.text
    print(f"marketplace confirmation HTTP: {confirm_ms:.1f}ms")
    campaign_id = confirmed.json()["campaign"]["id"]
    started = time.perf_counter()
    run = client.post(f"/api/v1/ads/jobs/{confirmed.json()['job']['id']}/run", headers=ORIGIN)
    connector_ms = (time.perf_counter() - started) * 1000
    assert run.status_code == 200 and run.json()["status"] == "succeeded", run.text
    print(f"amazon fake connector mutation: {connector_ms:.1f}ms")
    client.post(f"/api/v1/ads/marketplace/campaigns/{campaign_id}/metrics/import", headers=ORIGIN)
    _measure(
        "detail",
        lambda: client.get(f"/api/v1/ads/marketplace/campaigns/{campaign_id}", headers=ORIGIN),
    )
    _measure(
        "reconciliation",
        lambda: client.post(
            f"/api/v1/ads/marketplace/campaigns/{campaign_id}/reconcile", headers=ORIGIN
        ),
    )
    _measure(
        "metrics",
        lambda: client.get(
            f"/api/v1/ads/marketplace/campaigns/{campaign_id}/metrics", headers=ORIGIN
        ),
    )
    _measure(
        "Product Channel",
        lambda: client.get(
            f"/api/v1/ads/marketplace/product-channel/{context['product']['id']}", headers=ORIGIN
        ),
    )
    _measure("Recovery", lambda: client.get("/api/v1/ads/recovery", headers=ORIGIN))
    _measure(
        "optimization", lambda: client.get("/api/v1/ads/optimization/overview", headers=ORIGIN)
    )
    assert listing["listing_id"] in payload["listing_id"]


def test_amazon_crash_before_after_ambiguity_and_throttling(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = setup_ads_context(client)
    connector = _reset("amazon")
    owner_id = _owner_id()
    assert owner_id is not None and test_ai_integration.factory is not None

    before = _queue_marketplace(client, context, "amazon")
    original_create = connector.create_campaign

    def crash_before(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("simulated Amazon crash before connector")

    monkeypatch.setattr(connector, "create_campaign", crash_before)
    with test_ai_integration.factory() as db, pytest.raises(RuntimeError, match="before connector"):
        run_next_ads_job(db, owner_id=owner_id, worker_id="amazon-before-a")
    with test_ai_integration.factory() as db:
        job = db.get(AdJob, before["job_id"])
        assert job is not None
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(connector, "create_campaign", original_create)
    with test_ai_integration.factory() as db:
        resumed = run_next_ads_job(db, owner_id=owner_id, worker_id="amazon-before-b")
        assert resumed is not None and resumed.status == "succeeded"
        assert db.scalar(select(func.count()).select_from(AdRemoteMapping)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "ads.ad_campaign_created")
            )
            == 1
        )

    after = _queue_marketplace(client, context, "amazon")
    original_event = ads_service.record_event
    raised = False

    def crash_after(*args: Any, **kwargs: Any) -> Any:
        nonlocal raised
        if kwargs.get("action") == "ads.ad_campaign_created" and not raised:
            raised = True
            raise RuntimeError("simulated Amazon crash after checkpoint")
        return original_event(*args, **kwargs)

    monkeypatch.setattr(ads_service, "record_event", crash_after)
    with test_ai_integration.factory() as db, pytest.raises(RuntimeError, match="after checkpoint"):
        run_next_ads_job(db, owner_id=owner_id, worker_id="amazon-after-a")
        db.rollback()
    with test_ai_integration.factory() as db:
        job = db.get(AdJob, after["job_id"])
        assert job is not None and isinstance(job.result_json, dict)
        checkpoint = cast(dict[str, Any], job.result_json["remote_checkpoint"])
        remote_id = checkpoint["remote_id"]
        job.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(ads_service, "record_event", original_event)
    with test_ai_integration.factory() as db:
        resumed = run_next_ads_job(db, owner_id=owner_id, worker_id="amazon-after-b")
        assert resumed is not None and resumed.status == "succeeded"
        resumed_result = cast(dict[str, Any], resumed.result_json)
        assert resumed_result["remote_id"] == remote_id

    ambiguous = _queue_marketplace(client, context, "amazon")
    connector.state.failures["create_campaign"] = "ambiguous"
    response = client.post(f"/api/v1/ads/jobs/{ambiguous['job_id']}/run", headers=ORIGIN)
    connector.state.failures.clear()
    assert response.status_code == 200 and response.json()["status"] == "succeeded"
    assert (
        len([call for call in connector.state.calls if call["operation"] == "create_campaign"]) == 3
    )

    throttled = _queue_marketplace(client, context, "amazon")
    connector.state.failures["create_campaign"] = "throttled"
    retry = client.post(f"/api/v1/ads/jobs/{throttled['job_id']}/run", headers=ORIGIN)
    assert retry.status_code == 200 and retry.json()["status"] == "retry_wait"
    connector.state.failures.clear()
    with test_ai_integration.factory() as db:
        job = db.get(AdJob, throttled["job_id"])
        assert job is not None
        job.next_retry_at = now() - timedelta(seconds=1)
        db.commit()
    resumed = client.post(f"/api/v1/ads/jobs/{throttled['job_id']}/run", headers=ORIGIN)
    assert resumed.status_code == 200 and resumed.json()["status"] == "succeeded"
    assert len(connector.state.entities["campaign"]) == 4


def test_amazon_targeting_replacement_product_channel_calendar_and_analytics(client: Any) -> None:
    context = setup_ads_context(client)
    queued = _queue_marketplace(client, context, "amazon")
    published = _publish_ad(client, queued)
    campaign = queued["campaign"]
    unsupported = dict(queued["payload"], targeting_summary={"target_type": "unsupported"})
    rejected = client.post(
        "/api/v1/ads/marketplace/campaigns/preview", json=unsupported, headers=ORIGIN
    )
    assert rejected.status_code == 422 and "unsupported" in rejected.text.lower()
    target = dict(
        queued["payload"],
        targeting_summary={"target_type": "listing", "listing_id": queued["listing"]["listing_id"]},
    )
    assert (
        client.post(
            "/api/v1/ads/marketplace/campaigns/preview", json=target, headers=ORIGIN
        ).status_code
        == 200
    )
    wrong_target = dict(target, targeting_summary={"target_type": "listing", "listing_id": "OTHER"})
    assert (
        client.post(
            "/api/v1/ads/marketplace/campaigns/preview", json=wrong_target, headers=ORIGIN
        ).status_code
        == 422
    )
    metrics = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/metrics/import", headers=ORIGIN
    )
    assert metrics.status_code == 200
    analytics = client.get(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/analytics", headers=ORIGIN
    )
    assert analytics.status_code == 200 and analytics.json()["roas"] is not None
    schedule = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/schedule",
        json={"start_at": "2030-01-01T00:00:00Z", "timezone": "Asia/Kolkata"},
        headers=ORIGIN,
    )
    assert schedule.status_code == 201, schedule.text
    calendar = client.get("/api/v1/ads/calendar", headers=ORIGIN)
    assert calendar.status_code == 200 and any(
        str(row["campaign_id"]) == str(campaign["id"]) for row in calendar.json()
    )
    channel = client.get(
        f"/api/v1/ads/marketplace/product-channel/{context['product']['id']}", headers=ORIGIN
    )
    assert (
        channel.status_code == 200
        and channel.json()["providers"]["meesho"]["status"] == "not_supported"
    )
    assert any(str(row["id"]) == str(campaign["id"]) for row in channel.json()["campaigns"])
    first = published["creative"]
    second = _manual_creative(client, campaign, f"creative-v2-{campaign['id']}", "Marketplace v2")
    preview = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{published['ad']['id']}/creative/preview",
        json={"creative_id": second["id"]},
        headers=ORIGIN,
    )
    assert preview.status_code == 200 and preview.json()["mutates"] is False
    replacement = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{published['ad']['id']}/creative/confirm",
        json={
            "creative_id": second["id"],
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": f"replace-{campaign['id']}",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert replacement.status_code == 200
    assert (
        client.post(f"/api/v1/ads/jobs/{replacement.json()['job_id']}/run", headers=ORIGIN).json()[
            "status"
        ]
        == "succeeded"
    )
    repeated = client.post(
        f"/api/v1/ads/campaigns/{campaign['id']}/ads/{published['ad']['id']}/creative/confirm",
        json={
            "creative_id": second["id"],
            "preview_fingerprint": preview.json()["fingerprint"],
            "idempotency_key": f"replace-{campaign['id']}",
            "confirm": True,
        },
        headers=ORIGIN,
    )
    assert repeated.status_code == 200 and repeated.json()["job_id"] == replacement.json()["job_id"]
    assert first["id"] != second["id"]


def test_flipkart_full_e2e_and_version_safety(client: Any) -> None:
    context = setup_ads_context(client)
    queued = _queue_marketplace(client, context, "flipkart")
    campaign = queued["campaign"]
    assert (
        client.post(f"/api/v1/ads/jobs/{queued['job_id']}/run", headers=ORIGIN).json()["status"]
        == "succeeded"
    )
    published = _publish_ad(client, queued)
    metrics = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/metrics/import", headers=ORIGIN
    )
    conversion = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/conversions",
        json={
            "provider_event_id": "flipkart-order-closure",
            "conversion_type": "sale",
            "occurred_at": datetime.now(UTC).isoformat(),
            "value": "250",
            "currency": "INR",
        },
        headers=ORIGIN,
    )
    assert metrics.status_code == 200 and conversion.status_code == 201
    detail = client.get(f"/api/v1/ads/marketplace/campaigns/{campaign['id']}", headers=ORIGIN)
    reconcile = client.post(
        f"/api/v1/ads/marketplace/campaigns/{campaign['id']}/reconcile", headers=ORIGIN
    )
    history = client.get("/api/v1/ads/marketplace/history", headers=ORIGIN)
    assert (
        detail.status_code == 200
        and reconcile.json()["reconciliation_state"] == "matched"
        and history.status_code == 200
    )
    listing_v2 = client.post(
        "/api/v1/ads/marketplace/listings",
        json={
            "account_id": queued["account"]["id"],
            "product_id": context["product"]["id"],
            "marketplace": "flipkart",
            "listing_id": queued["listing"]["listing_id"],
            "version": 2,
            "title": "Flipkart v2",
        },
        headers=ORIGIN,
    )
    assert listing_v2.status_code == 201
    changed = dict(queued["payload"], listing_version=2)
    changed_preview = client.post(
        "/api/v1/ads/marketplace/campaigns/preview", json=changed, headers=ORIGIN
    )
    assert changed_preview.status_code == 200 and campaign["listing_version"] == 1
    assert published["ad"]["creative_id"]


def test_meesho_cross_marketplace_currency_privacy_and_storage_boundaries(client: Any) -> None:
    context = setup_ads_context(client)
    capabilities = client.get("/api/v1/ads/marketplace/capabilities", headers=ORIGIN)
    assert (
        capabilities.status_code == 200
        and capabilities.json()["meesho"]["status"] == "not_supported"
    )
    forged = client.post(
        "/api/v1/ads/marketplace/campaigns/preview",
        json={"provider": "meesho", "marketplace": "meesho"},
        headers=ORIGIN,
    )
    assert forged.status_code == 422 and "traceback" not in forged.text.lower()
    amazon = _queue_marketplace(client, context, "amazon")
    flipkart = _queue_marketplace(client, context, "flipkart")
    comparison = client.get(
        f"/api/v1/ads/marketplace/comparison/{context['product']['id']}", headers=ORIGIN
    )
    assert comparison.status_code == 200 and comparison.json()["compatible"] is True
    assert "never-returned" not in comparison.text and "password" not in comparison.text.lower()
    integrity = client.get("/api/v1/ads/storage/integrity", headers=ORIGIN)
    assert integrity.status_code == 200 and integrity.json()["safe"] is True
    assert amazon["campaign"]["id"] != flipkart["campaign"]["id"]
