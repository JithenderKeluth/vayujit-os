from __future__ import annotations

from collections.abc import Callable
from functools import partial
from statistics import median
from time import perf_counter
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import func, select
from test_ai_integration import ORIGIN, setup_context
from test_ai_video_bulk_e2e import bulk_payload, run_worker

from vayujit_api.ai.studio_models import AIStudioJobAttempt
from vayujit_api.media.models import MediaAsset
from vayujit_api.video.models import VideoOutput

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def _latencies(call: Callable[[], Any], samples: int = 3) -> tuple[float, float]:
    values = []
    for _ in range(samples):
        started = perf_counter()
        call()
        values.append((perf_counter() - started) * 1000)
    values.sort()
    p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
    return median(values), p95


def test_bulk_operation_performance_medians_and_p95s_are_measured(client: Any) -> None:
    context = setup_context(client)
    payload = bulk_payload([context["product"]["id"]], "bulk-performance-acceptance")
    cold_started = perf_counter()
    preview = client.post("/api/v1/ai/video/bulk/preview", json=payload, headers=ORIGIN)
    cold_ms = (perf_counter() - cold_started) * 1000
    assert preview.status_code == 200, preview.text
    warm_median, warm_p95 = _latencies(
        lambda: client.post("/api/v1/ai/video/bulk/preview", json=payload, headers=ORIGIN)
    )
    queued = client.post("/api/v1/ai/video/bulk", json=payload, headers=ORIGIN)
    assert queued.status_code == 202, queued.text
    bulk_id = queued.json()["id"]
    completion_started = perf_counter()
    assert run_worker("bulk-performance-worker") == 3
    completion_ms = (perf_counter() - completion_started) * 1000

    urls = {
        "output_list": f"/api/v1/ai/video/bulk/{bulk_id}/outputs",
        "child_detail": f"/api/v1/ai/video/bulk/{bulk_id}",
        "history": f"/api/v1/ai/video/bulk/{bulk_id}/history",
        "usage": f"/api/v1/ai/video/bulk/{bulk_id}/usage",
        "diagnostics": f"/api/v1/ai/video/bulk/{bulk_id}/diagnostics",
    }

    def request(url: str) -> Any:
        return client.get(url, headers=ORIGIN)

    timings: dict[str, tuple[float, float]] = {}
    for name, url in urls.items():
        timings[name] = _latencies(partial(request, url))
        response = client.get(url, headers=ORIGIN)
        assert response.status_code == 200, response.text
    timings["retry"] = _latencies(
        lambda: client.post(
            f"/api/v1/ai/video/bulk/{bulk_id}/retry-failed",
            json={"idempotency_key": "perf-retry"},
            headers=ORIGIN,
        )
    )
    timings["cancellation"] = _latencies(
        lambda: client.post(
            f"/api/v1/ai/video/bulk/{bulk_id}/cancel-remaining",
            json={"idempotency_key": "perf-cancel"},
            headers=ORIGIN,
        )
    )
    assert cold_ms >= 0 and warm_median >= 0 and warm_p95 >= warm_median
    assert completion_ms >= 0
    assert all(median_ms >= 0 and p95_ms >= median_ms for median_ms, p95_ms in timings.values())

    assert test_ai_integration.factory is not None
    with test_ai_integration.factory() as db:
        assert db.scalar(select(func.count()).select_from(AIStudioJobAttempt)) == 3
        assert db.scalar(select(func.count()).select_from(VideoOutput)) == 3
        generated_bytes = int(
            db.scalar(select(func.coalesce(func.sum(MediaAsset.size_bytes), 0))) or 0
        )
        assert generated_bytes > 0
    assert {
        "cold_preview_ms": cold_ms,
        "warm_preview": (warm_median, warm_p95),
        "completion_ms": completion_ms,
    }
