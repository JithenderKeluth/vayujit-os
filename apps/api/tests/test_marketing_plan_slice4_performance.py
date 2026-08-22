from __future__ import annotations

import json
import math
import statistics
import time

import pytest
from helpers.ads_acceptance import setup_ads_context
from test_ai_integration import ORIGIN
from test_marketing_plan_slice4_concurrency import _confirm, _plan_payload

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _summary(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    return {
        "count": len(samples),
        "median_ms": round(statistics.median(samples) * 1000, 3),
        "p95_ms": round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)] * 1000, 3),
    }


def test_marketing_plan_warm_performance_matrix(client) -> None:
    context = setup_ads_context(client)
    payload = _plan_payload(context)
    plan = _confirm(client, payload)
    plan_id = plan["id"]
    product_id = context["product"]["id"]
    readiness = {
        "brand_id": payload["brand_id"],
        "product_ids": payload["product_ids"],
        "target_channels": payload["target_channels"],
        "idempotency_key": "performance-readiness",
    }
    preview_payload = {"plan": payload, "expected_version": 1}
    calls = {
        "plan_list": lambda: client.get("/api/v1/ads/marketing/plans", headers=ORIGIN),
        "plan_detail": lambda: client.get(f"/api/v1/ads/marketing/plans/{plan_id}", headers=ORIGIN),
        "readiness": lambda: client.post(
            "/api/v1/ads/marketing/plans/readiness", json=readiness, headers=ORIGIN
        ),
        "preview": lambda: client.post(
            "/api/v1/ads/marketing/plans/preview", json=preview_payload, headers=ORIGIN
        ),
        "channel_status": lambda: client.get(
            f"/api/v1/ads/marketing/plans/{plan_id}/execution", headers=ORIGIN
        ),
        "analytics": lambda: client.get(
            f"/api/v1/ads/marketing/plans/{plan_id}/analytics", headers=ORIGIN
        ),
        "optimization": lambda: client.get(
            f"/api/v1/ads/marketing/plans/{plan_id}/optimization", headers=ORIGIN
        ),
        "recovery": lambda: client.get(
            f"/api/v1/ads/marketing/plans/{plan_id}/recovery", headers=ORIGIN
        ),
        "history": lambda: client.get(
            f"/api/v1/ads/marketing/plans/{plan_id}/history", headers=ORIGIN
        ),
        "calendar": lambda: client.get("/api/v1/ads/marketing/calendar", headers=ORIGIN),
        "product_channel": lambda: client.get(
            f"/api/v1/ads/marketing/product-channel/{product_id}", headers=ORIGIN
        ),
        "budget_preview": lambda: client.post(
            f"/api/v1/ads/marketing/plans/{plan_id}/budget/preview",
            json={
                "proposed": payload["budget_envelope"],
                "expected_version": 1,
                "preview_fingerprint": "unused-preview-input",
                "confirm": False,
            },
            headers=ORIGIN,
        ),
    }
    timings: dict[str, dict[str, float | int]] = {}
    for name, call in calls.items():
        samples: list[float] = []
        for _ in range(10):
            started = time.perf_counter()
            response = call()
            samples.append(time.perf_counter() - started)
            assert response.status_code == 200, f"{name}: {response.text}"
        timings[name] = _summary(samples)

    confirmation_preview = client.post(
        "/api/v1/ads/marketing/plans/preview",
        json=preview_payload,
        headers=ORIGIN,
    )
    assert confirmation_preview.status_code == 200
    confirmation_request = {
        "plan": payload,
        "expected_version": 1,
        "preview_fingerprint": confirmation_preview.json()["fingerprint"],
        "confirm": True,
    }
    samples = []
    for _ in range(10):
        started = time.perf_counter()
        response = client.post(
            "/api/v1/ads/marketing/plans/confirm",
            json=confirmation_request,
            headers=ORIGIN,
        )
        samples.append(time.perf_counter() - started)
        assert response.status_code == 201, response.text
    timings["confirmation"] = _summary(samples)
    print(f"MARKETING_PERFORMANCE {json.dumps(timings, sort_keys=True)}")
