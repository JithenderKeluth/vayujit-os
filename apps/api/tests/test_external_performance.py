from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration
from sqlalchemy import event, select
from sqlalchemy.engine import Engine

from vayujit_api.intelligence.external_models import ExternalSearchRequest

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_external_endpoint_performance_projection_has_warm_samples(client: Any) -> None:
    integration.setup_context(client)
    response = client.get("/api/v1/intelligence/external/performance", headers=ORIGIN)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classification"] == "PASS"
    assert body["live_search_latency"] is None
    assert body["live_fetch_latency"] is None
    assert len(body["measurements"]) >= 10
    assert all(
        row["samples"] >= 10 and row["p95_ms"] >= row["median_ms"] for row in body["measurements"]
    )


def test_external_query_safety_has_no_obvious_n_plus_one(client: Any) -> None:
    integration.setup_context(client)
    assert integration.factory is not None
    with integration.factory() as db:
        owner = db.scalar(
            select(integration.User).where(integration.User.email == "owner@example.com")
        )
        assert owner is not None
        for index in range(8):
            db.add(
                ExternalSearchRequest(
                    owner_id=owner.id,
                    query=f"q-{index}",
                    provider="local",
                    mode="LOCAL_FIXTURE",
                    status="COMPLETED",
                    correlation_id=f"q-{index}",
                    identity_key=f"q-{index}",
                )
            )
        db.commit()
        engine = db.get_bind()
        assert isinstance(engine, Engine)
        counts: list[int] = []

        def before_cursor(
            _conn: Any,
            _cursor: Any,
            _statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            counts[-1] += 1

        event.listen(engine, "before_cursor_execute", before_cursor)
        try:
            for path in (
                "/api/v1/intelligence/external/searches",
                "/api/v1/intelligence/external/integrity",
                "/api/v1/intelligence/external/history",
            ):
                counts.append(0)
                response = client.get(path, headers=ORIGIN)
                assert response.status_code == 200, response.text
            assert max(counts) < 80
        finally:
            event.remove(engine, "before_cursor_execute", before_cursor)
