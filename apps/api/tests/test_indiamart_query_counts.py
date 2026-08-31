from __future__ import annotations

from collections import Counter

import pytest
import test_ai_integration
from fastapi.testclient import TestClient
from sqlalchemy import event
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _count_request(client: TestClient, path: str) -> int:
    assert test_ai_integration.factory is not None
    engine = test_ai_integration.factory.kw["bind"]
    statements: Counter[str] = Counter()

    def count(_conn, _cursor, _statement, _parameters, _context, _executemany) -> None:
        statements[path] += 1

    event.listen(engine, "before_cursor_execute", count)
    try:
        response = client.get(path, headers=ORIGIN)
        assert response.status_code == 200, response.text
    finally:
        event.remove(engine, "before_cursor_execute", count)
    return statements[path]


def test_indiamart_query_counts_do_not_show_obvious_n_plus_one_growth(client: TestClient) -> None:
    context = setup_context(client)
    for query, key in (("small fixture", "query-small"), ("larger fixture", "query-large")):
        response = client.post(
            "/api/v1/intelligence/indiamart/discover",
            json={"query": query, "product_id": context["product"]["id"], "idempotency_key": key},
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
    counts = {
        path: _count_request(client, path)
        for path in (
            "/api/v1/intelligence/indiamart/discoveries",
            "/api/v1/intelligence/suppliers/overview",
            "/api/v1/intelligence/indiamart/report",
            "/api/v1/intelligence/indiamart/integrity",
        )
    }
    assert all(value < 100 for value in counts.values())
    assert max(counts.values()) - min(counts.values()) < 50
