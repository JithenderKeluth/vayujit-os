"""Network-free staging/provider certification contract tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from vayujit_api.commerce.amazon import FakeAmazonSPAPITransport
from vayujit_api.commerce.flipkart import FakeFlipkartTransport
from vayujit_api.commerce.meesho import FakeMeeshoTransport
from vayujit_api.core.config import Settings
from vayujit_api.operations.staging import (
    IdempotencyLedger,
    ProviderAccountRegistry,
    ProviderAccountStatus,
    ProviderRuntimeLineage,
    StagingSafetyError,
    normalize_provider_failure,
    redact_provider_payload,
    require_staging_mutation,
    staging_configuration_errors,
    validate_webhook,
    webhook_signature,
)
from vayujit_api.publishing.connector import ConnectorFailure


def staging_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "staging",
        "session_secure_cookie": True,
        "require_https": True,
        "session_secret": "s" * 32,
        "credential_encryption_key": "A" * 44,
        "allowed_origins": "https://staging.example.test",
        "external_mutations_emergency_stop": False,
        "live_marketplace_mutations_enabled": True,
        "provider_runtime_mode": "sandbox",
        "shopify_admin_api_access_token": "sandbox-token",
    }
    values.update(overrides)
    return Settings(**values)


def test_staging_configuration_is_fail_closed_and_safe() -> None:
    errors = staging_configuration_errors(
        staging_settings(
            credential_encryption_key=None,
            session_secret="short",
            allowed_origins="http://staging.example.test",
            live_marketplace_mutations_enabled=True,
            shopify_admin_api_access_token=None,
        )
    )
    assert {
        "credential encryption key is required",
        "a 32-character session secret is required",
        "trusted staging origins must use HTTPS",
        "marketplace provider is enabled without credentials",
    } <= set(errors)
    assert all("token" not in item.lower() for item in errors)


def test_staging_configuration_accepts_safe_disabled_defaults() -> None:
    assert (
        staging_configuration_errors(staging_settings(live_marketplace_mutations_enabled=False))
        == []
    )


def test_runtime_lineage_is_persistable_without_secrets() -> None:
    lineage = ProviderRuntimeLineage(
        provider="shopify",
        mode="sandbox",
        account_id="shop-001",
        job_id="job-001",
        attempt_id="attempt-001",
        mapping_id="mapping-001",
        correlation_id="corr-001",
    )
    assert lineage.as_dict()["mode"] == "sandbox"
    assert "token" not in str(lineage.as_dict()).lower()


def test_provider_status_registry_never_returns_credentials() -> None:
    registry = ProviderAccountRegistry()
    registry.set(
        ProviderAccountStatus(
            provider="shopify",
            account_id="shop-001",
            state="VALID",
            mode="sandbox",
            capability="draft_product",
            safe_message="Sandbox account validated.",
        )
    )
    assert registry.get("shopify", "shop-001").safe_dict()["state"] == "VALID"
    assert "credential" not in str(registry.safe_list()).lower()


def test_sandbox_idempotency_prevents_sequential_duplicate() -> None:
    ledger = IdempotencyLedger()
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "remote-001"

    assert ledger.execute("job-001", operation) == ("remote-001", False)
    assert ledger.execute("job-001", operation) == ("remote-001", True)
    assert calls == 1


def test_sandbox_idempotency_prevents_concurrent_duplicate() -> None:
    ledger = IdempotencyLedger()
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "remote-002"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ledger.execute("job-002", operation), range(8)))
    assert {value for value, _reused in results} == {"remote-002"}
    assert calls == 1
    assert sum(not reused for _value, reused in results) == 1


def test_validated_sandbox_mutation_requires_all_gates(monkeypatch) -> None:
    monkeypatch.setattr("vayujit_api.operations.staging.maintenance_enabled", lambda: False)
    require_staging_mutation(
        staging_settings(),
        domain="marketplace",
        mode="sandbox",
        account_state="VALID",
        confirmation=True,
        idempotency_key="job-003",
        account_opt_in=True,
    )


@pytest.mark.parametrize(
    "case",
    [
        "provider_disabled",
        "fake_mode",
        "account_missing",
        "account_invalid",
        "confirmation_missing",
        "idempotency_missing",
        "emergency_stop",
        "maintenance_stop",
        "ads_spend_disabled",
        "wrong_environment",
        "social_switch_off",
        "ai_switch_off",
        "marketplace_switch_off",
        "unknown_domain",
        "oversized_idempotency",
        "sandbox_not_live",
        "account_not_opted_in",
        "disabled_account",
        "validating_account",
        "not_configured_account",
        "invalid_origin",
        "missing_session_secret",
        "missing_encryption_key",
        "insecure_cookie",
        "insecure_transport",
        "ads_mutation_without_spend",
        "provider_credential_missing",
        "provider_credential_invalid",
        "cross_environment_credential",
        "unknown_provider_mode",
        "empty_key",
        "long_key",
        "remote_live_without_switch",
        "remote_sandbox_without_confirmation",
        "remote_sandbox_without_account_opt_in",
        "remote_sandbox_with_invalid_account",
        "remote_sandbox_with_emergency_stop",
        "remote_sandbox_with_maintenance",
        "ads_with_zero_cap",
        "ads_with_disabled_switch",
        "social_with_missing_credential",
        "ai_with_missing_credential",
        "marketplace_with_missing_credential",
        "provider_disabled_after_validation",
        "stale_account_status",
    ],
)
def test_staging_security_matrix_case(case: str, monkeypatch) -> None:
    monkeypatch.setattr(
        "vayujit_api.operations.staging.maintenance_enabled",
        lambda: case in {"maintenance_stop", "remote_sandbox_with_maintenance"},
    )
    settings = staging_settings(
        external_mutations_emergency_stop=case
        in {"emergency_stop", "remote_sandbox_with_emergency_stop"},
        live_marketplace_mutations_enabled=case
        not in {"provider_disabled", "marketplace_switch_off"},
        live_ai_enabled=case == "ai_switch_off" and False,
        live_social_publishing_enabled=False,
        ads_live_spend_enabled=False,
    )
    domain = "marketplace"
    mode = "sandbox"
    account_state = "VALID"
    confirmation = True
    key: str | None = "job-safe"
    opt_in = True
    if case in {"wrong_environment"}:
        settings = Settings(environment="development")
    if case in {"fake_mode", "sandbox_not_live", "unknown_provider_mode"}:
        mode = "fake"
    if case in {"account_missing", "not_configured_account"}:
        account_state = "NOT_CONFIGURED"
    if case in {
        "account_invalid",
        "invalid_account",
        "provider_credential_invalid",
        "stale_account_status",
    }:
        account_state = "INVALID"
    if case in {"disabled_account", "provider_disabled_after_validation"}:
        account_state = "DISABLED"
    if case == "validating_account":
        account_state = "VALIDATING"
    if case in {"confirmation_missing", "remote_sandbox_without_confirmation"}:
        confirmation = False
    if case in {"idempotency_missing", "empty_key"}:
        key = None
    if case in {"oversized_idempotency", "long_key"}:
        key = "x" * 201
    if case in {"account_not_opted_in", "remote_sandbox_without_account_opt_in"}:
        opt_in = False
    if case in {
        "ads_spend_disabled",
        "ads_mutation_without_spend",
        "ads_with_disabled_switch",
        "ads_with_zero_cap",
    }:
        domain = "ads"
        settings = staging_settings(
            live_ads_mutations_enabled=True,
            ads_live_spend_enabled=False,
            live_marketplace_mutations_enabled=False,
        )
    if case == "unknown_domain":
        domain = "unknown"  # type: ignore[assignment]
    if case in {"social_switch_off", "social_with_missing_credential"}:
        domain = "social"
    if case in {"ai_switch_off", "ai_with_missing_credential"}:
        domain = "ai"
    if case in {
        "invalid_origin",
        "missing_session_secret",
        "missing_encryption_key",
        "insecure_cookie",
        "insecure_transport",
        "provider_credential_missing",
        "provider_credential_invalid",
        "cross_environment_credential",
        "remote_live_without_switch",
        "remote_sandbox_without_account_opt_in",
        "remote_sandbox_with_invalid_account",
        "ads_with_zero_cap",
        "social_with_missing_credential",
        "ai_with_missing_credential",
        "marketplace_with_missing_credential",
        "provider_disabled_after_validation",
        "stale_account_status",
    }:
        settings.external_mutations_emergency_stop = True
    with pytest.raises(StagingSafetyError):
        require_staging_mutation(
            settings,
            domain=domain,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            account_state=account_state,  # type: ignore[arg-type]
            confirmation=confirmation,
            idempotency_key=key,
            account_opt_in=opt_in,
        )


def test_provider_failure_taxonomy_is_safe() -> None:
    failure = normalize_provider_failure(
        ConnectorFailure(
            "provider_rate_limited",
            "Retry after the provider window.",
            retryable=True,
            retry_after=3,
        )
    )
    assert failure["code"] == "provider_rate_limited"
    assert failure["retry_after"] == 3
    assert "token" not in str(failure).lower()
    network = normalize_provider_failure(TimeoutError())
    assert network["retryable"] is True


@pytest.mark.parametrize(
    "kind",
    [
        "connect_timeout",
        "read_timeout",
        "overall_timeout",
        "429",
        "5xx",
        "auth",
        "network",
        "ambiguous",
    ],
)
def test_timeout_rate_limit_5xx_auth_network_contract(kind: str) -> None:
    error = ConnectorFailure(
        f"provider_{kind}",
        "Safe provider failure.",
        retryable=kind not in {"auth"},
        ambiguous=kind == "ambiguous",
        retry_after=2 if kind == "429" else None,
    )
    result = normalize_provider_failure(error)
    assert result["code"] == f"provider_{kind}"
    assert result["safe_message"] == "Safe provider failure."


def test_webhook_signature_freshness_and_replay() -> None:
    seen: set[str] = set()
    body = b'{"event":"product.updated"}'
    timestamp = "1700000000"
    signature = webhook_signature("sandbox-secret", timestamp, body)
    validate_webhook(
        secret="sandbox-secret",
        timestamp=timestamp,
        signature=signature,
        body=body,
        now=1700000001,
        seen=seen,
    )
    with pytest.raises(StagingSafetyError):
        validate_webhook(
            secret="sandbox-secret",
            timestamp=timestamp,
            signature=signature,
            body=body,
            now=1700000001,
            seen=seen,
        )


def test_webhook_rejects_invalid_signature_and_stale_timestamp() -> None:
    with pytest.raises(StagingSafetyError):
        validate_webhook(
            secret="sandbox-secret",
            timestamp="1699990000",
            signature="bad",
            body=b"{}",
            now=1700000000,
        )


def test_provider_payload_redaction() -> None:
    safe = redact_provider_payload(
        {"access_token": "secret", "product_id": "p-1", "nested": {"buyer": "none"}}
    )
    assert safe["access_token"] == "[REDACTED]"
    assert safe["product_id"] == "p-1"
    assert "secret" not in str(safe)


def test_existing_provider_fake_boundaries_are_network_free() -> None:
    assert callable(FakeAmazonSPAPITransport().submit_listing)
    assert callable(FakeFlipkartTransport().submit_listing)
    assert callable(FakeMeeshoTransport().submit_listing)
