"""Focused PR-9A certification-harness and safety regression tests."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from vayujit_api.intelligence.external_provider import validate_external_url
from vayujit_api.intelligence.live_supplier_certification_models import (
    LiveSupplierCertificationExecution,
    LiveSupplierCertificationRun,
    LiveSupplierSourceApproval,
)
from vayujit_api.intelligence.live_supplier_certification_service import (
    CHECKS,
    _classify_page,
    _path_in_scope,
    _settings_blockers,
)
from vayujit_api.intelligence.policy import UnsafeURL

ORIGIN = {"Origin": "http://127.0.0.1:4200"}
INTEGRATION_AVAILABLE = bool(os.environ.get("VAYUJIT_TEST_DATABASE_URL"))


pytestmark = pytest.mark.certification_infrastructure


def test_pr9a_models_are_distinct_durable_authorities() -> None:
    assert LiveSupplierSourceApproval.__tablename__ == "intelligence_live_supplier_source_approvals"
    assert (
        LiveSupplierCertificationRun.__tablename__
        == "intelligence_live_supplier_certification_runs"
    )
    assert (
        LiveSupplierCertificationExecution.__tablename__
        == "intelligence_live_supplier_certification_executions"
    )
    assert len(CHECKS) == 10


def test_pr9a_runtime_policy_fails_closed_before_network() -> None:
    settings = SimpleNamespace(
        intelligence_external_provider_mode="LOCAL_FIXTURE",
        intelligence_enabled=True,
        intelligence_external_research_enabled=True,
        intelligence_web_fetch_enabled=True,
        intelligence_external_kill_switch=False,
        external_mutations_emergency_stop=False,
    )
    assert "MODE_NOT_LIVE_READ_ONLY" in _settings_blockers(settings)


def test_pr9a_kill_switch_blocks_before_network() -> None:
    settings = SimpleNamespace(
        intelligence_external_provider_mode="LIVE_READ_ONLY",
        intelligence_enabled=True,
        intelligence_external_research_enabled=True,
        intelligence_web_fetch_enabled=True,
        intelligence_external_kill_switch=True,
        external_mutations_emergency_stop=False,
    )
    assert _settings_blockers(settings) == ["EXTERNAL_KILL_SWITCH"]


def test_pr9a_page_classification_keeps_supplier_and_retail_distinct() -> None:
    supplier = _classify_page(
        {
            "title": "Bulk stainless steel bottles",
            "meta_description": "OEM manufacturer",
            "text": "MOQ 100",
        },
        "supplier_website",
    )
    retail = _classify_page(
        {"title": "Insulated Bottle", "meta_description": "Buy now", "text": "Add to cart price"},
        "supplier_website",
    )
    assert supplier["classification"] == "SUPPLIER_SOURCE"
    assert supplier["supplier_relevance"] is True
    assert retail["classification"] == "RETAIL_PRODUCT"
    assert retail["supplier_relevance"] is False


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1/item", "https://localhost/item", "https://user:pass@example.org/item"]
)
def test_pr9a_ssrf_and_credentials_are_rejected(url: str) -> None:
    with pytest.raises(UnsafeURL):
        validate_external_url(url, allowed_domains=("example.org",))


def test_pr9a_path_scope_is_checked_by_url_parser() -> None:
    safe = validate_external_url(
        "https://example.org/suppliers/item", allowed_domains=("example.org",)
    )
    assert safe.endswith("/suppliers/item")
    assert _path_in_scope("/suppliers/item", "/suppliers")
    assert _path_in_scope("/suppliers/item/detail", "/suppliers")
    assert not _path_in_scope("/suppliers-other/item", "/suppliers")


def _ok(response: Any) -> dict[str, Any]:
    assert response.status_code < 300, response.text
    return cast(dict[str, Any], response.json())


@pytest.fixture
def pr9a_context(pr56_client: TestClient) -> tuple[TestClient, str]:
    """Create context exclusively through normal owner/source authorities."""
    api = pr56_client
    _ok(
        api.post(
            "/api/v1/auth/setup-owner",
            json={
                "full_name": "PR-9A Owner",
                "email": "pr9a-owner@example.com",
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
                "idempotency_key": "pr9a-opportunity",
            },
            headers=ORIGIN,
        )
    )
    _ok(
        api.post(
            "/api/v1/intelligence/external/source-profiles/admit",
            json={
                "domain": "example.org",
                "reason": "PR-9A bounded certification test source",
            },
            headers=ORIGIN,
        )
    )
    return api, opportunity["id"]


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION_AVAILABLE, reason="disposable PostgreSQL URL is not configured")
def test_pr9a_unapproved_source_is_blocked_without_network(
    pr9a_context: tuple[TestClient, str],
) -> None:
    api, opportunity_id = pr9a_context
    response = api.post(
        "/api/v1/intelligence/live-supplier-certification/approvals",
        json={
            "opportunity_id": opportunity_id,
            "source_url": "https://not-approved.example/item",
            "purpose": "Bounded read-only test",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION_AVAILABLE, reason="disposable PostgreSQL URL is not configured")
def test_pr9a_kill_switch_run_is_durable_and_idempotent(
    pr9a_context: tuple[TestClient, str],
) -> None:
    api, opportunity_id = pr9a_context
    approval = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/approvals",
            json={
                "opportunity_id": opportunity_id,
                "source_url": "https://example.org/supplier/item",
                "purpose": "Bounded read-only test",
            },
            headers=ORIGIN,
        )
    )
    run = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    replay = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    assert run["id"] == replay["id"]
    assert run["status"] == "BLOCKED"
    assert run["external_read_count"] == 0
    assert run["external_write_count"] == 0
    assert run["blockers"]


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION_AVAILABLE, reason="disposable PostgreSQL URL is not configured")
def test_pr9a_approved_fetch_records_hash_and_zero_writes(
    pr9a_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from vayujit_api.intelligence import live_supplier_certification_service as service

    api, opportunity_id = pr9a_context
    approval = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/approvals",
            json={
                "opportunity_id": opportunity_id,
                "source_url": "https://example.org/supplier/item",
                "purpose": "Bounded read-only test",
            },
            headers=ORIGIN,
        )
    )

    class FakeFetcher:
        def __init__(self, settings: object) -> None:
            del settings

        def fetch(
            self, url: str, *, allowed_domains: tuple[str, ...], blocked_domains: tuple[str, ...]
        ) -> dict[str, object]:
            assert url.startswith("https://example.org/")
            assert allowed_domains == ("example.org",)
            assert blocked_domains == ()
            return {
                "requested_url": url,
                "final_url": url,
                "domain": "example.org",
                "status": "COMPLETED",
                "http_status": 200,
                "content_type": "text/html",
                "content_length": 42,
                "content_hash": "a" * 64,
                "redirect_count": 0,
                "extracted": {
                    "title": "Bulk kids lunch products",
                    "meta_description": "Manufacturer and wholesale supplier",
                    "canonical_url": url,
                    "text": "OEM manufacturer MOQ 100",
                },
            }

    monkeypatch.setattr(service, "ApprovedWebFetcher", FakeFetcher)
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            intelligence_external_provider_mode="LIVE_READ_ONLY",
            intelligence_enabled=True,
            intelligence_external_research_enabled=True,
            intelligence_web_fetch_enabled=True,
            intelligence_external_kill_switch=False,
            external_mutations_emergency_stop=False,
            intelligence_external_blocked_domains="",
        ),
    )
    run = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    assert run["status"] == "PASS"
    assert run["external_read_count"] == 1
    assert run["external_write_count"] == 0
    assert run["execution"]["content_hash"] == "a" * 64
    assert run["gate_outcomes"]["immutable_evidence"] == "PASS"


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION_AVAILABLE, reason="disposable PostgreSQL URL is not configured")
def test_pr9a_revocation_blocks_new_run_and_preserves_prior_history(
    pr9a_context: tuple[TestClient, str],
) -> None:
    api, opportunity_id = pr9a_context
    approval = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/approvals",
            json={
                "opportunity_id": opportunity_id,
                "source_url": "https://example.org/supplier/revocable",
                "purpose": "Bounded revocation test",
            },
            headers=ORIGIN,
        )
    )
    revoked = _ok(
        api.post(
            f"/api/v1/intelligence/live-supplier-certification/approvals/{approval['id']}/revoke",
            json={"reason": "No longer needed", "actor_provenance": "HUMAN"},
            headers=ORIGIN,
        )
    )
    assert revoked["status"] == "REVOKED"
    run = _ok(
        api.post(
            "/api/v1/intelligence/live-supplier-certification/runs",
            json={"approval_id": approval["id"], "opportunity_id": opportunity_id},
            headers=ORIGIN,
        )
    )
    assert run["status"] == "BLOCKED"
    assert "SOURCE_APPROVAL_NOT_ACTIVE" in run["blockers"]
    assert run["external_read_count"] == 0
