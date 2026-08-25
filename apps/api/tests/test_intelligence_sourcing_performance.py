from __future__ import annotations

from statistics import median
from time import perf_counter
from typing import Any

import pytest
import test_ai_integration as integration_helpers
from sqlalchemy import event
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ["test_ai_integration"]
pytestmark = pytest.mark.integration


def test_sourcing_endpoint_timing_and_query_safety(client: Any) -> None:
    setup_context(client)
    endpoints = (
        "/api/v1/intelligence/sourcing/overview",
        "/api/v1/intelligence/sourcing/requirements",
        "/api/v1/intelligence/sourcing/rfqs",
        "/api/v1/intelligence/sourcing/quotes",
        "/api/v1/intelligence/sourcing/samples",
        "/api/v1/intelligence/sourcing/inspections",
        "/api/v1/intelligence/sourcing/scenarios",
        "/api/v1/intelligence/sourcing/history/unified",
        "/api/v1/intelligence/sourcing/report/json",
        "/api/v1/intelligence/sourcing/storage/inventory",
    )
    timings: dict[str, list[float]] = {endpoint: [] for endpoint in endpoints}
    for endpoint in endpoints:
        for _ in range(10):
            start = perf_counter()
            response = client.get(endpoint, headers=ORIGIN)
            elapsed = (perf_counter() - start) * 1000
            assert response.status_code == 200, response.text
            timings[endpoint].append(elapsed)
    print("SOURCING PERFORMANCE TIMING")
    print("ENDPOINT\\tSAMPLES\\tMEDIAN_MS\\tP95_MS")
    for endpoint, samples in timings.items():
        ordered = sorted(samples)
        p95 = ordered[min(len(ordered) - 1, 9)]
        med = median(samples)
        print(f"{endpoint}\\t{len(samples)}\\t{med:.3f}\\t{p95:.3f}")
        assert med < 1000
        assert p95 < 3000

    assert integration_helpers.factory is not None
    engine = integration_helpers.factory.kw["bind"]
    queries: list[str] = []

    def count_queries(
        _conn: Any, _cursor: Any, statement: str, _params: Any, _context: Any, _many: bool
    ) -> None:
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        response = client.get("/api/v1/intelligence/sourcing/history/unified", headers=ORIGIN)
        assert response.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)
    assert len(queries) <= 40
