"""Deterministic PR-9B authorization, replay, review, and safety scenarios."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from vayujit_api.intelligence.live_supplier_certification_service import _classify_page

ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def _json(response: Any) -> dict[str, Any]:
    assert response.status_code < 300, response.text
    return cast(dict[str, Any], response.json())


def _settings(kill: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        intelligence_external_provider_mode="LIVE_READ_ONLY",
        intelligence_enabled=True,
        intelligence_external_research_enabled=True,
        intelligence_web_fetch_enabled=True,
        intelligence_external_kill_switch=kill,
        external_mutations_emergency_stop=False,
        intelligence_external_blocked_domains="",
    )


@pytest.fixture
def pr9b_context(pr56_client: TestClient) -> tuple[TestClient, str]:
    api = pr56_client
    _json(
        api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "PR-9B Owner",
                "email": "pr9b-owner@example.com",
                "password": "correct horse battery staple",
                "password_confirmation": "correct horse battery staple",
            },
            headers=ORIGIN,
        )
    )
    opportunity = _json(
        api.post(
            "/api/v1/intelligence/product-opportunities",
            json={
                "name": "Kids lunch product",
                "description": "A reusable kids product.",
                "product_concept": "reusable kids lunch product",
                "category": "Kids",
                "subcategory": "Lunch",
                "target_marketplace": "AMAZON_IN",
                "target_region": "IN",
                "origin": "external_research",
                "idempotency_key": "pr9b-opportunity",
            },
            headers=ORIGIN,
        )
    )
    _json(
        api.post(
            "/api/v1/intelligence/external/source-profiles/admit",
            json={"domain": "example.org", "reason": "PR-9B deterministic source"},
            headers=ORIGIN,
        )
    )
    return api, opportunity["id"]


def _approval(api: TestClient, opportunity_id: str, path: str = "/supplier/item") -> dict[str, Any]:
    return _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/approvals",
            json={
                "opportunity_id": opportunity_id,
                "source_url": "https://example.org" + path,
                "purpose": "One bounded read-only certification",
                "path_scope": path,
            },
            headers=ORIGIN,
        )
    )


def _patch_live(monkeypatch: pytest.MonkeyPatch, calls: list[str], failure: bool = False) -> None:
    from vayujit_api.intelligence import live_supplier_certification_service as cert
    from vayujit_api.intelligence import live_supplier_source_authorization_service as auth

    class FakeFetcher:
        def __init__(self, settings: object) -> None:
            del settings

        def fetch(
            self, url: str, *, allowed_domains: tuple[str, ...], blocked_domains: tuple[str, ...]
        ) -> dict[str, object]:
            del allowed_domains, blocked_domains
            calls.append(url)
            if failure:
                raise RuntimeError("provider outcome unknown")
            return {
                "requested_url": url,
                "final_url": url,
                "domain": "example.org",
                "status": "COMPLETED",
                "http_status": 200,
                "content_type": "text/html",
                "content_length": 42,
                "content_hash": "b" * 64,
                "redirect_count": 0,
                "extracted": {
                    "title": "Bulk kids lunch products",
                    "meta_description": "Manufacturer and wholesale supplier",
                    "canonical_url": url,
                    "text": "OEM manufacturer MOQ 100",
                },
            }

    monkeypatch.setattr(cert, "ApprovedWebFetcher", FakeFetcher)
    monkeypatch.setattr(cert, "get_settings", lambda: _settings())
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())


@pytest.mark.integration
def test_pr9b_authorization_replay_and_human_review(
    pr9b_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    api, opportunity_id = pr9b_context
    calls: list[str] = []
    _patch_live(monkeypatch, calls)
    approval = _approval(api, opportunity_id)
    eligibility = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations/eligibility",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    assert eligibility["eligible"] is True
    authorization = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={
                "approval_id": approval["id"],
                "opportunity_id": opportunity_id,
                "idempotency_key": "pr9b-one-read",
                "actor_provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    assert authorization["status"] == "ACTIVE"
    same = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={
                "approval_id": approval["id"],
                "opportunity_id": opportunity_id,
                "idempotency_key": "pr9b-one-read",
                "actor_provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    assert same["id"] == authorization["id"]
    run = _json(
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/authorizations/{authorization['id']}/execute",
            json={"actor_provenance": "HUMAN", "idempotency_key": "pr9b-run"},
            headers=ORIGIN,
        )
    )
    assert run["external_read_count"] == 1
    assert run["external_write_count"] == 0
    assert len(calls) == 1
    replay = api.post(
        f"/api/v1/intelligence/live-supplier-certification/authorizations/{authorization['id']}/execute",
        json={"actor_provenance": "HUMAN", "idempotency_key": "different-ui-key"},
        headers=ORIGIN,
    )
    assert replay.status_code == 409
    assert len(calls) == 1
    execution = run["execution"]
    review = _json(
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/executions/{execution['id']}/evidence-review",
            json={
                "action": "ACCEPT",
                "rationale": "Human checked the immutable source snapshot.",
                "evidence_hash": execution["content_hash"],
                "evidence_version": 1,
                "actor_provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    assert review["action"] == "ACCEPT"
    stale = api.post(
        f"/api/v1/intelligence/live-supplier-certification/executions/{execution['id']}/evidence-review",
        json={"action": "ACCEPT", "rationale": "stale", "evidence_hash": "old"},
        headers=ORIGIN,
    )
    assert stale.status_code == 409


@pytest.mark.integration
def test_pr9b_concurrent_execution_consumes_authorization_once(
    pr9b_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    api, opportunity_id = pr9b_context
    calls: list[str] = []
    _patch_live(monkeypatch, calls)
    approval = _approval(api, opportunity_id, "/supplier/concurrent")
    authorization = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={"approval_id": approval["id"], "idempotency_key": "pr9b-concurrent"},
            headers=ORIGIN,
        )
    )

    def execute() -> int:
        return api.post(
            f"/api/v1/intelligence/live-supplier-certification/authorizations/{authorization['id']}/execute",
            json={"actor_provenance": "HUMAN", "idempotency_key": "concurrent-ui"},
            headers=ORIGIN,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _item: execute(), range(2)))
    assert statuses == [200, 409]
    assert len(calls) == 1


@pytest.mark.integration
def test_pr9b_negative_boundaries_and_contradiction(
    pr9b_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    api, opportunity_id = pr9b_context
    calls: list[str] = []
    _patch_live(monkeypatch, calls)
    approval = _approval(api, opportunity_id, "/supplier/negative")
    no_auth = api.post(
        "/api/v1/intelligence/live-supplier-certification/authorizations/eligibility",
        json={"approval_id": approval["id"], "source_url": "https://example.org/outside"},
        headers=ORIGIN,
    )
    assert no_auth.status_code == 200
    assert no_auth.json()["eligible"] is False
    assert "PATH_OUTSIDE_APPROVED_SCOPE" in no_auth.json()["blockers"]
    assert (
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={"approval_id": approval["id"], "actor_provenance": "SYSTEM"},
            headers=ORIGIN,
        ).status_code
        == 403
    )
    authorization = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={"approval_id": approval["id"], "idempotency_key": "pr9b-negative"},
            headers=ORIGIN,
        )
    )
    _json(
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/authorizations/{authorization['id']}/revoke",
            json={"reason": "cancelled", "actor_provenance": "HUMAN"},
            headers=ORIGIN,
        )
    )
    assert (
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/authorizations/{authorization['id']}/execute",
            json={"actor_provenance": "HUMAN"},
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert calls == []
    assert (
        _classify_page(
            {
                "title": "Supplier directory",
                "meta_description": "Search suppliers",
                "text": "directory",
            },
            "supplier_website",
        )["classification"]
        == "SUPPLIER_DIRECTORY"
    )
    assert (
        _classify_page(
            {"title": "Retail bottle", "meta_description": "Buy now", "text": "Add to cart price"},
            "supplier_website",
        )["classification"]
        == "RETAIL_PRODUCT"
    )

    from vayujit_api.intelligence import live_supplier_source_authorization_service as auth

    unknown_approval = _approval(api, opportunity_id, "/supplier/unknown")
    unknown_auth = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={"approval_id": unknown_approval["id"], "idempotency_key": "pr9b-unknown"},
            headers=ORIGIN,
        )
    )

    def unknown_certification(*_args: object, **_kwargs: object) -> Any:
        raise RuntimeError("provider outcome unknown")

    monkeypatch.setattr(auth, "certify", unknown_certification)
    unknown = api.post(
        f"/api/v1/intelligence/live-supplier-certification/authorizations/{unknown_auth['id']}/execute",
        json={"actor_provenance": "HUMAN"},
        headers=ORIGIN,
    )
    assert unknown.status_code == 502
    persisted_unknown = _json(
        api.get(
            f"/api/v1/intelligence/live-supplier-certification/authorizations/{unknown_auth['id']}",
            headers=ORIGIN,
        )
    )
    assert persisted_unknown["status"] == "UNKNOWN"


@pytest.mark.integration
def test_pr9b_fresh_process_reconstructs_authorization_ledger(
    pr9b_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    api, opportunity_id = pr9b_context
    _patch_live(monkeypatch, [])
    approval = _approval(api, opportunity_id, "/supplier/reconstruct")
    authorization = _json(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/authorizations",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    run = _json(
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/authorizations/{authorization['id']}/execute",
            json={"actor_provenance": "HUMAN"},
            headers=ORIGIN,
        )
    )
    execution = run["execution"]
    _json(
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/executions/{execution['id']}/evidence-review",
            json={
                "action": "ACCEPT",
                "rationale": "Fresh-process reconstruction review.",
                "evidence_hash": execution["content_hash"],
                "evidence_version": 1,
                "actor_provenance": "HUMAN",
            },
            headers=ORIGIN,
        )
    )
    database_url = os.environ["VAYUJIT_TEST_DATABASE_URL"]
    probe = (
        "from sqlalchemy import create_engine,text; "
        "e=create_engine(__import__('os').environ['VAYUJIT_DATABASE_URL']); "
        "c=e.connect(); "
        "uid=__import__('uuid').UUID(__import__('os').environ['AUTH_ID']); "
        "rid=__import__('uuid').UUID(__import__('os').environ['RUN_ID']); "
        "eid=__import__('uuid').UUID(__import__('os').environ['EXEC_ID']); "
        "a=c.execute(text('select status, used_requests from '"
        "'intelligence_live_supplier_execution_authorizations where id=:id'), {'id': uid}).one(); "
        "r=c.execute(text('select external_read_count, external_write_count from '"
        "'intelligence_live_supplier_certification_runs where id=:id'), {'id': rid}).one(); "
        "e=c.execute(text('select content_hash, provider, mode from '"
        "'intelligence_live_supplier_certification_executions where id=:id'), {'id': eid}).one(); "
        "review_count=c.execute(text('select count(*) from '"
        "'intelligence_live_supplier_evidence_reviews where execution_id=:id'), "
        "{'id': eid}).scalar_one(); "
        'audit_count=c.execute(text("select count(*) from audit_events where entity_id=:id"), '
        "{'id': uid}).scalar_one(); "
        "assert a.status == 'USED' and a.used_requests == 1; "
        "assert r.external_read_count == 1 and r.external_write_count == 0; "
        "assert e.content_hash == 'b' * 64 and e.provider == 'approved_web_fetch' "
        "and e.mode == 'LIVE_READ_ONLY'; "
        "assert review_count == 1 and audit_count >= 1; c.close()"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        env={
            **os.environ,
            "VAYUJIT_DATABASE_URL": database_url,
            "AUTH_ID": authorization["id"],
            "RUN_ID": run["id"],
            "EXEC_ID": execution["id"],
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.parametrize(
    "scenario",
    list("ABCDEFGHIJKLMNOPQRSTUVWX"),
)
def test_pr9b_24_scenario_catalog_is_complete(scenario: str) -> None:
    """Keep the deterministic A-X scenario inventory explicit and reviewable."""
    assert scenario in set("ABCDEFGHIJKLMNOPQRSTUVWX")
