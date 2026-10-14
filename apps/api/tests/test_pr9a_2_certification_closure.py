"""PR-9A.2 missing-gate regression coverage.

The tests exercise existing PR-9A authorities only.  All database scenarios
use the disposable fixture and a fake fetcher; no supplier network is used.
"""

from __future__ import annotations

import ipaddress
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient

from vayujit_api.intelligence import external_provider
from vayujit_api.intelligence.external_provider import ApprovedWebFetcher

ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _ok(response: Any) -> dict[str, object]:
    assert response.status_code < 300, response.text
    return cast(dict[str, object], response.json())


@pytest.fixture
def pr9a2_context(pr56_client: TestClient) -> tuple[TestClient, str]:
    api = pr56_client
    _ok(
        api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "PR-9A.2 Owner",
                "email": "pr9a2-owner@example.com",
                "password": "correct horse battery staple",
                "password_confirmation": "correct horse battery staple",
            },
            headers=ORIGIN,
        )
    )
    opportunity = _ok(
        api.post(
            "/api/v1/intelligence/product-opportunities",
            json={
                "name": "Kids Lunch Box",
                "description": "A reusable kids product.",
                "product_concept": "reusable kids lunch box",
                "category": "Kids",
                "subcategory": "Lunch Boxes",
                "target_marketplace": "AMAZON_IN",
                "target_region": "IN",
                "origin": "external_research",
                "idempotency_key": "pr9a2-opportunity",
            },
            headers=ORIGIN,
        )
    )
    _ok(
        api.post(
            "/api/v1/intelligence/external/source-profiles/admit",
            json={"domain": "example.org", "reason": "PR-9A.2 deterministic source"},
            headers=ORIGIN,
        )
    )
    return api, str(opportunity["id"])


def test_pr9a2_dns_rebinding_fails_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public = [ipaddress.ip_address("93.184.216.34")]
    private = [ipaddress.ip_address("10.0.0.7")]
    resolutions = iter([public, private])
    monkeypatch.setattr(external_provider, "_resolved_addresses", lambda _host: next(resolutions))

    calls: list[str] = []

    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, url: str, **_kwargs: object) -> object:
            calls.append(url)
            return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: Client())
    from test_pr9a_1_certification_closure import _settings

    with pytest.raises(RuntimeError, match="dns_rebinding_blocked"):
        ApprovedWebFetcher(_settings()).fetch(
            "https://supplier.example/item", allowed_domains=("supplier.example",)
        )
    assert calls == []


def test_pr9a2_retry_boundary_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    from test_pr9a_1_certification_closure import _Client, _Response, _settings

    monkeypatch.setattr(
        external_provider,
        "_resolved_addresses",
        lambda _host: [ipaddress.ip_address("93.184.216.34")],
    )
    client = _Client([_Response("https://supplier.example/item", status_code=503)])
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: client)
    with pytest.raises(RuntimeError, match="fetch_5xx"):
        ApprovedWebFetcher(_settings()).fetch(
            "https://supplier.example/item", allowed_domains=("supplier.example",)
        )
    assert len(client.calls) == 1


@pytest.mark.integration
def test_pr9a2_ambiguous_supplier_correlation_is_retained(
    pr9a2_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_pr9a_1_certification_closure import _live_page, _ok, _settings

    from vayujit_api.intelligence import live_supplier_certification_service as service

    api, opportunity_id = pr9a2_context
    for name in ("PR9A.2 Supplier A", "PR9A.2 Supplier B"):
        _ok(
            api.post(
                "/api/v1/intelligence/suppliers/manual",
                json={
                    "display_name": name,
                    "supplier_type": "manufacturer",
                    "country_code": "IN",
                    "country": "India",
                    "website": "https://example.org",
                    "source_type": "manual_entry",
                    "provenance": "PR9A.2_TEST",
                },
                headers=ORIGIN,
            )
        )
    approval = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/approvals",
            json={
                "opportunity_id": opportunity_id,
                "source_url": "https://example.org/supplier/ambiguous",
                "purpose": "PR9A.2 ambiguous identity",
            },
            headers=ORIGIN,
        )
    )

    class FakeFetcher:
        def __init__(self, _settings: object) -> None:
            pass

        def fetch(self, url: str, **_kwargs: object) -> dict[str, object]:
            return _live_page(url)

    monkeypatch.setattr(service, "ApprovedWebFetcher", FakeFetcher)
    monkeypatch.setattr(service, "get_settings", lambda: _settings())
    result = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    assert result["supplier_correlation"]["outcome"] == "AMBIGUOUS"
    assert result["supplier_correlation"]["supplier_ids"]
    assert result["supplier_correlation"]["supplier_ids"] == sorted(
        result["supplier_correlation"]["supplier_ids"]
    )
    assert result["evidence_refs"] == []
    assert result["gate_outcomes"]["downstream_eligibility"] == "BLOCKED"


@pytest.mark.integration
def test_pr9a2_equivalent_replay_and_explicit_refresh(
    pr9a2_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_pr9a_1_certification_closure import _live_page, _ok, _settings

    from vayujit_api.intelligence import live_supplier_certification_service as service

    api, opportunity_id = pr9a2_context
    supplier = _ok(
        api.post(
            "/api/v1/intelligence/suppliers/manual",
            json={
                "display_name": "PR9A.2 Replay Supplier",
                "supplier_type": "manufacturer",
                "country_code": "IN",
                "country": "India",
                "website": "https://example.org",
                "source_type": "manual_entry",
                "provenance": "PR9A.2_TEST",
            },
            headers=ORIGIN,
        )
    )
    approval = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/approvals",
            json={
                "opportunity_id": opportunity_id,
                "source_url": "https://example.org/supplier/replay",
                "purpose": "PR9A.2 replay",
            },
            headers=ORIGIN,
        )
    )

    class FakeFetcher:
        def __init__(self, _settings: object) -> None:
            pass

        def fetch(self, url: str, **_kwargs: object) -> dict[str, object]:
            return _live_page(url)

    monkeypatch.setattr(service, "ApprovedWebFetcher", FakeFetcher)
    monkeypatch.setattr(service, "get_settings", lambda: _settings())
    payload = {"approval_id": approval["id"], "opportunity_id": opportunity_id}
    first = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json=payload,
            headers=ORIGIN,
        )
    )
    replay = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json=payload,
            headers=ORIGIN,
        )
    )
    refreshed = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json={**payload, "refresh": True, "idempotency_key": "refresh-1"},
            headers=ORIGIN,
        )
    )
    assert first["id"] == replay["id"]
    assert refreshed["id"] != first["id"]
    assert first["supplier_correlation"]["supplier_id"] == supplier["id"]
    assert refreshed["evidence_refs"]
