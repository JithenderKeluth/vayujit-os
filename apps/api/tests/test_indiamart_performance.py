from __future__ import annotations

import statistics
import time

import pytest
from fastapi.testclient import TestClient
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _sample(client: TestClient, operation: str, product_id: str, request_id: str) -> float:
    paths = {
        "normalization": "/api/v1/intelligence/indiamart/operations",
        "discovery list": "/api/v1/intelligence/indiamart/discoveries",
        "result detail": f"/api/v1/intelligence/indiamart/discoveries/{request_id}",
        "candidate list": "/api/v1/intelligence/suppliers/overview",
        "candidate detail": "/api/v1/intelligence/indiamart/report",
        "Evidence projection": "/api/v1/intelligence/indiamart/integrity",
        "Product Channel": f"/api/v1/intelligence/indiamart/product-channel/{product_id}",
        "Operations": "/api/v1/operations/intelligence/projection",
        "Integrity": "/api/v1/intelligence/indiamart/integrity",
    }
    started = time.perf_counter()
    response = client.get(paths[operation], headers=ORIGIN)
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    return elapsed


def test_indiamart_warm_operation_samples_have_bounded_latency(client: TestClient) -> None:
    context = setup_context(client)
    discovery = client.post(
        "/api/v1/intelligence/indiamart/discover",
        json={"query": "performance", "product_id": context["product"]["id"]},
        headers=ORIGIN,
    )
    assert discovery.status_code == 200, discovery.text
    request_id = discovery.json()["request"]["id"]
    operations = (
        "normalization",
        "discovery list",
        "result detail",
        "candidate list",
        "candidate detail",
        "Evidence projection",
        "Product Channel",
        "Operations",
        "Integrity",
    )
    for operation in operations:
        samples = [
            _sample(client, operation, context["product"]["id"], request_id) for _ in range(10)
        ]
        assert statistics.median(samples) >= 0
        assert sorted(samples)[9] < 5000, f"{operation} p95={sorted(samples)[9]:.1f}ms"
