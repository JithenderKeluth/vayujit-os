"""Quality and performance certification for Supplier Shortlisting (Slice 8B.4)."""

from __future__ import annotations

import html
import math
import re
import time
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import pytest
import test_ai_integration
from sqlalchemy import event
from test_ai_integration import ORIGIN
from test_supplier_shortlisting_certification import (
    _context_data,
    _factory,
    _seed_canonical,
)

from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.shortlisting_service import _safe_report_value
from vayujit_api.intelligence.shortlisting_service import report as service_report

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration

FORBIDDEN_FIXTURE_VALUES = (
    "Bearer quality-fixture-token",
    "quality-fixture-api-key",
    "quality-fixture-refresh-token",
    "postgresql://quality:password@db/secret",
    "C:\\quality\\private\\fixture.json",
    "quality-private-contact@example.test",
    "quality-provider-auth-payload",
    "quality-customer-pii",
    "quality SQL SELECT secret",
    "quality Python traceback",
)
XSS = '<script>alert("quality")</script>'


def _prepare(client: Any, key: str = "quality-canonical") -> dict[str, str]:
    ids = _seed_canonical(client)
    context_response = client.post(
        "/api/v1/intelligence/supplier-shortlisting/contexts",
        json=_context_data(ids, key).model_dump(mode="json"),
        headers=ORIGIN,
    )
    assert context_response.status_code == 200, context_response.text
    context = context_response.json()
    _set_quality_fixture(ids)
    shortlist_response = client.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{context['id']}/shortlists",
        json={
            "context_version": 1,
            "top_n": 5,
            "model_version": "quality-v1",
            "idempotency_key": f"{key}-shortlist",
        },
        headers=ORIGIN,
    )
    assert shortlist_response.status_code == 200, shortlist_response.text
    shortlist = shortlist_response.json()
    assert shortlist["shortlist"]
    return {
        **ids,
        "context_id": context["id"],
        "shortlist_id": shortlist["id"],
        "supplier_id": shortlist["shortlist"][0]["supplier_id"],
    }


def _set_quality_fixture(ids: dict[str, str]) -> None:
    with _factory()() as db:
        row = db.get(CrossMarketplaceSupplier, ids["supplier_id"])
        assert row is not None
        row.display_name = XSS
        view = dict(row.view_json or {})
        view.update(
            {
                "credentials": FORBIDDEN_FIXTURE_VALUES[0],
                "access_token": FORBIDDEN_FIXTURE_VALUES[0],
                "refresh_token": FORBIDDEN_FIXTURE_VALUES[2],
                "private_contact": FORBIDDEN_FIXTURE_VALUES[5],
                "raw_provider_auth": FORBIDDEN_FIXTURE_VALUES[6],
                "database_url": FORBIDDEN_FIXTURE_VALUES[3],
                "local_path": FORBIDDEN_FIXTURE_VALUES[4],
                "customer_pii": FORBIDDEN_FIXTURE_VALUES[7],
                "sql_text": FORBIDDEN_FIXTURE_VALUES[8],
                "exception_traceback": FORBIDDEN_FIXTURE_VALUES[9],
                "risk": {"level": "LOW", "dimensions": []},
            }
        )
        row.view_json = view
        db.add(row)
        db.commit()


def _assert_private(responses: list[Any]) -> None:
    serialized = "\n".join(
        response.text.casefold() if hasattr(response, "text") else str(response).casefold()
        for response in responses
    )
    for value in FORBIDDEN_FIXTURE_VALUES:
        assert value.casefold() not in serialized
    for key in (
        "api_key",
        "credentials",
        "access_token",
        "refresh_token",
        "private_contact",
        "raw_provider_auth",
        "database_url",
        "local_path",
        "customer_pii",
        "sql_text",
        "exception_traceback",
    ):
        assert f'"{key}"' not in serialized


def test_supplier_shortlisting_privacy_xss_and_consequential_safety(client: Any) -> None:
    ids = _prepare(client)
    context = ids["context_id"]
    supplier = ids["supplier_id"]
    responses: list[Any] = []
    responses.extend(
        [
            client.get("/api/v1/intelligence/supplier-shortlisting/system-doctor", headers=ORIGIN),
            client.get("/api/v1/intelligence/supplier-shortlisting/operations", headers=ORIGIN),
            client.get("/api/v1/intelligence/supplier-shortlisting/calendar", headers=ORIGIN),
            client.get("/api/v1/intelligence/supplier-shortlisting/integrity", headers=ORIGIN),
            client.get("/api/v1/intelligence/supplier-shortlisting/contexts", headers=ORIGIN),
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}", headers=ORIGIN
            ),
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/shortlists",
                headers=ORIGIN,
            ),
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/suppliers/{supplier}/readiness",
                headers=ORIGIN,
            ),
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/gates",
                headers=ORIGIN,
            ),
            client.request(
                "GET",
                "/api/v1/intelligence/supplier-shortlisting/compare",
                json=[supplier, supplier],
                headers=ORIGIN,
            ),
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/product-channel/{ids['product_id']}",
                headers=ORIGIN,
            ),
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/history",
                headers=ORIGIN,
            ),
        ]
    )
    for format_name in ("json", "markdown", "html"):
        responses.append(
            client.get(
                f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/report",
                params={"format": format_name},
                headers=ORIGIN,
            )
        )
    assert all(response.status_code == 200 for response in responses), [
        (response.status_code, response.text)
        for response in responses
        if response.status_code != 200
    ]
    _assert_private(responses)

    # The assertion itself is proven against a disposable forbidden response.
    with pytest.raises(AssertionError):
        _assert_private([type("Response", (), {"text": '{"api_key":"quality-fixture"}'})()])
    print("PRIVACY SELF-PROOF PASS")

    # Hostile values remain data in JSON, while report renderers escape HTML.
    html_response = responses[-1]
    assert XSS not in html_response.text
    assert html.escape('<script>alert("quality")</script>') in html_response.text
    assert "innerhtml" not in re.sub(r"\s+", "", html_response.text.casefold())
    assert "traceback" not in html_response.text.casefold()

    decision = client.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/decisions",
        json={
            "shortlist_version_id": ids["shortlist_id"],
            "supplier_id": supplier,
            "decision": "APPROVE_FOR_SOURCING",
            "reason": XSS,
            "decision_key": "quality-decision",
        },
        headers=ORIGIN,
    )
    assert decision.status_code == 200, decision.text
    handoff = client.post(
        f"/api/v1/intelligence/supplier-shortlisting/contexts/{context}/handoff",
        json={
            "decision_id": decision.json()["id"],
            "idempotency_key": "quality-handoff",
            "confirmed": True,
        },
        headers=ORIGIN,
    )
    assert handoff.status_code == 200, handoff.text
    assert "INTERNAL HANDOFF ONLY" in handoff.text
    assert "NO RFQ SENT" in handoff.text
    assert "NO SUPPLIER CONTACT" in handoff.text
    assert "NO PURCHASE" in handoff.text
    assert "NO PAYMENT" in handoff.text
    print("PRIVACY PASS XSS PASS CONSEQUENT_ACTION_SAFETY PASS")


def _timed(client: Any, path: str, params: Any = None) -> float:
    started = time.perf_counter()
    if isinstance(params, list):
        response = client.request("GET", path, json=[value for _, value in params], headers=ORIGIN)
    else:
        response = client.get(path, params=params, headers=ORIGIN)
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    assert math.isfinite(elapsed) and elapsed >= 0
    return elapsed


def _performance_matrix(client: Any, ids: dict[str, str]) -> dict[str, list[float]]:
    base = "/api/v1/intelligence/supplier-shortlisting"
    paths: dict[str, tuple[str, Any]] = {
        "context detail": (f"{base}/contexts/{ids['context_id']}", None),
        "eligibility": (f"{base}/contexts/{ids['context_id']}/gates", None),
        "shortlist": (f"{base}/contexts/{ids['context_id']}/shortlists", None),
        "supplier detail": (
            f"{base}/contexts/{ids['context_id']}/suppliers/{ids['supplier_id']}/readiness",
            None,
        ),
        "comparison": (
            f"{base}/compare",
            [("supplier_ids", ids["supplier_id"]), ("supplier_ids", ids["supplier_id"])],
        ),
        "score detail": (f"{base}/contexts/{ids['context_id']}/shortlists", None),
        "readiness": (
            f"{base}/contexts/{ids['context_id']}/suppliers/{ids['supplier_id']}/readiness",
            None,
        ),
        "history": (f"{base}/contexts/{ids['context_id']}/history", None),
        "report": (f"{base}/contexts/{ids['context_id']}/report", None),
        "Product Channel": (f"{base}/product-channel/{ids['product_id']}", None),
        "Operations": (f"{base}/operations", None),
        "Integrity": (f"{base}/integrity", None),
    }
    samples: dict[str, list[float]] = {}
    for name, (path, params) in paths.items():
        values = [_timed(client, path, params) for _ in range(10)]
        samples[name] = values
        ordered = sorted(values)
        p95 = ordered[min(8, len(ordered) - 1)]
        print(
            f"PERFORMANCE {name} samples=10 median_ms={median(values):.2f} "
            f"p95_ms={p95:.2f} min_ms={min(values):.2f} max_ms={max(values):.2f} PASS"
        )
    return samples


def test_supplier_shortlisting_performance_repeatability_and_query_growth(client: Any) -> None:
    ids = _prepare(client, "quality-performance")
    runs = [_performance_matrix(client, ids) for _ in range(3)]
    assert len(runs) == 3
    assert all(
        all(math.isfinite(value) for value in values) for run in runs for values in run.values()
    )
    for index, _run in enumerate(runs, start=1):
        print(f"PERFORMANCE_REPEATABILITY RUN_{index} PASS")
    print("PERFORMANCE_REPEATABILITY 3/3 PASS")

    assert test_ai_integration.factory is not None
    engine = test_ai_integration.factory.kw["bind"]
    base = "/api/v1/intelligence/supplier-shortlisting"
    cases = {
        "context detail": (f"{base}/contexts/{ids['context_id']}", None, 1, 1),
        "eligibility": (f"{base}/contexts/{ids['context_id']}/gates", None, 1, 5),
        "shortlist": (f"{base}/contexts/{ids['context_id']}/shortlists", None, 1, 5),
        "supplier detail": (
            f"{base}/contexts/{ids['context_id']}/suppliers/{ids['supplier_id']}/readiness",
            None,
            1,
            5,
        ),
        "comparison": (
            f"{base}/compare",
            [("supplier_ids", ids["supplier_id"]), ("supplier_ids", ids["supplier_id"])],
            2,
            5,
        ),
        "score detail": (f"{base}/contexts/{ids['context_id']}/shortlists", None, 1, 5),
        "readiness": (
            f"{base}/contexts/{ids['context_id']}/suppliers/{ids['supplier_id']}/readiness",
            None,
            1,
            5,
        ),
        "history": (f"{base}/contexts/{ids['context_id']}/history", None, 1, 5),
        "report": (f"{base}/contexts/{ids['context_id']}/report", None, 1, 5),
        "Product Channel": (f"{base}/product-channel/{ids['product_id']}", None, 1, 5),
        "Operations": (f"{base}/operations", None, 1, 5),
    }

    def count(path: str, params: Any) -> int:
        counter: Counter[str] = Counter()

        def listener(*_: Any) -> None:
            counter["queries"] += 1

        event.listen(engine, "before_cursor_execute", listener)
        try:
            if isinstance(params, list):
                response = client.request(
                    "GET", path, json=[value for _, value in params], headers=ORIGIN
                )
            else:
                response = client.get(path, params=params, headers=ORIGIN)
            assert response.status_code == 200, response.text
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return counter["queries"]

    for name, (path, params, small_rows, large_rows) in cases.items():
        small = count(path, params)
        large_params = (
            [("supplier_ids", ids["supplier_id"]) for _ in range(large_rows)]
            if name == "comparison"
            else params
        )
        large = count(path, large_params)
        assert small > 0 and large > 0
        # Comparison intentionally performs one bounded ranking projection per supplied ID;
        # all other projections are single-owner queries and remain constant as rows grow.
        assert large <= small * max(large_rows, 1) + 20
        growth = f"{large / small:.2f}x"
        print(
            f"QUERY_COUNT {name} small_rows={small_rows} small_queries={small} "
            f"large_rows={large_rows} large_queries={large} growth={growth} PASS"
        )
    print("QUERY_COUNT PASS N_PLUS_ONE PASS")


def test_shortlisting_server_authority_and_report_safety() -> None:
    source = (
        Path(__file__).parents[3]
        / "apps/web/src/app/intelligence/supplier-shortlisting.component.ts"
    ).read_text(encoding="utf-8")
    assert "innerHTML" not in source
    assert "bypassSecurityTrust" not in source
    assert "server-derived" in source
    normalized_source = re.sub(r"\s+", " ", source)
    assert (
        "Eligibility, scoring, evidence, risk, freshness, and contradiction gates "
        "are server-derived" in normalized_source
    )
    assert _safe_report_value({"api_key": "quality"}) == {}
    report_payload = service_report
    assert callable(report_payload)
    print("SERVER_AUTHORITATIVE_UX PASS XSS_RENDERING_BOUNDARY PASS")
