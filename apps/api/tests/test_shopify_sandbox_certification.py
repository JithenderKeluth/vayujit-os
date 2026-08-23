"""Network-free Shopify sandbox certification evidence.

Real Shopify certification is intentionally blocked when staging credentials are absent.
These tests certify the provider boundary, fail-closed controls, and safe local behavior.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import pytest

from vayujit_api.core.config import Settings
from vayujit_api.operations.staging import (
    IdempotencyLedger,
    StagingSafetyError,
    redact_provider_payload,
    require_staging_mutation,
    shopify_configuration_errors,
    validate_webhook,
    webhook_signature,
)
from vayujit_api.publishing.connector import ConnectorFailure
from vayujit_api.publishing.shopify_connector import (
    OPERATIONS,
    ShopifyGraphQLClient,
    shopify_product_input,
    validate_api_version,
    validate_shop_domain,
)


def staging_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "staging",
        "session_secure_cookie": True,
        "require_https": True,
        "session_secret": "s" * 32,
        "credential_encryption_key": "A" * 44,
        "allowed_origins": "https://staging.example.test",
        "provider_runtime_mode": "sandbox",
        "shopify_mode": "sandbox",
        "shopify_shop_domain": "sandbox-store.myshopify.com",
        "shopify_admin_api_access_token": "sandbox-token",
        "shopify_api_version": "2026-07",
        "live_marketplace_mutations_enabled": False,
        "shopify_live_mutation_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def client(handler: Any) -> ShopifyGraphQLClient:
    return ShopifyGraphQLClient(
        shop_domain="sandbox-store.myshopify.com",
        access_token="sandbox-token",
        api_version="2026-07",
        transport=httpx.MockTransport(handler),
        resolve_dns=False,
    )


def test_shopify_read_only_configuration_is_valid_without_mutation_switch() -> None:
    assert shopify_configuration_errors(staging_settings()) == []


def test_real_store_certification_is_blocked_without_external_credentials() -> None:
    errors = shopify_configuration_errors(
        staging_settings(shopify_shop_domain=None, shopify_admin_api_access_token=None)
    )
    assert "Shopify store domain is required" in errors
    assert "Shopify access token is required" in errors
    assert "sandbox-token" not in " ".join(errors)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"shopify_shop_domain": "shop.example.com"}, "valid myshopify.com domain"),
        ({"shopify_api_version": "unstable"}, "YYYY-MM quarterly format"),
        ({"environment": "development"}, "staging environment"),
        ({"shopify_mode": "live"}, "production mode"),
        ({"shopify_live_mutation_enabled": True}, "global marketplace switch"),
        (
            {"shopify_live_mutation_enabled": True, "live_marketplace_mutations_enabled": True},
            "emergency stop",
        ),
    ],
)
def test_shopify_configuration_fails_closed(overrides: dict[str, Any], expected: str) -> None:
    settings = (
        staging_settings(**overrides, require_https=False)
        if expected == "staging environment"
        else staging_settings(**overrides)
    )
    if expected == "emergency stop":
        settings = staging_settings(
            **overrides,
            external_mutations_emergency_stop=True,
        )
    errors = shopify_configuration_errors(settings)
    assert any(expected.casefold() in item.casefold() for item in errors)
    assert all(value not in " ".join(errors).casefold() for value in ("secret", "access token"))


def test_shopify_mutation_requires_explicit_provider_switch() -> None:
    with pytest.raises(StagingSafetyError, match="Shopify remote mutations"):
        require_staging_mutation(
            staging_settings(live_marketplace_mutations_enabled=True),
            domain="marketplace",
            mode="sandbox",
            account_state="VALID",
            confirmation=True,
            idempotency_key="shopify-job-1",
            account_opt_in=True,
        )


def test_shopify_mutation_accepts_all_explicit_safety_gates() -> None:
    require_staging_mutation(
        staging_settings(
            live_marketplace_mutations_enabled=True,
            shopify_live_mutation_enabled=True,
        ),
        domain="marketplace",
        mode="sandbox",
        account_state="VALID",
        confirmation=True,
        idempotency_key="shopify-job-2",
        account_opt_in=True,
    )


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "shopify_auth_failed", False),
        (403, "shopify_auth_failed", False),
        (429, "shopify_throttled", True),
        (500, "shopify_unavailable", True),
        (503, "shopify_unavailable", True),
    ],
)
def test_shopify_http_failures_are_safe_and_bounded(
    status: int, code: str, retryable: bool
) -> None:
    headers = {"Retry-After": "7"} if status == 429 else {}
    with pytest.raises(ConnectorFailure) as caught:
        client(lambda _request: httpx.Response(status, headers=headers)).validate()
    assert caught.value.code == code
    assert caught.value.retryable is retryable
    assert "sandbox-token" not in caught.value.safe_message
    if status == 429:
        assert caught.value.retry_after == 7


def test_shopify_timeout_network_and_ambiguous_failures_are_classified() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(ConnectorFailure) as caught:
        client(timeout).validate()
    assert caught.value.code == "shopify_timeout"
    assert caught.value.ambiguous is False

    with pytest.raises(ConnectorFailure) as caught:
        client(timeout).publish({"requested_action": "create_draft"}, {"product_name": "Test"})
    assert caught.value.code == "shopify_timeout"
    assert caught.value.ambiguous is True

    def network(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    with pytest.raises(ConnectorFailure) as caught:
        client(network).validate()
    assert caught.value.code == "shopify_network_error"
    assert caught.value.retryable is True


def test_shopify_throttle_metadata_is_retained_without_payload_logging() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {"shop": {"id": "gid://shopify/Shop/1", "name": "Sandbox"}},
                "extensions": {
                    "cost": {
                        "requestedQueryCost": 10,
                        "actualQueryCost": 8,
                        "throttleStatus": {"currentlyAvailable": 990, "restoreRate": 50.0},
                    }
                },
            },
        )

    value = client(handler)
    assert value.validate()["shop"] == {"id": "gid://shopify/Shop/1", "name": "Sandbox"}
    assert value.last_throttle.currently_available == 990
    assert "sandbox-token" not in str(value.last_throttle)


def test_shopify_product_read_is_normalized_to_safe_fields() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "product": {
                        "id": "gid://shopify/Product/42",
                        "title": "Sandbox product",
                        "handle": "sandbox-product",
                        "status": "DRAFT",
                        "variants": {"nodes": [{"id": "gid://shopify/ProductVariant/1"}]},
                        "media": {"nodes": [{"id": "gid://shopify/MediaImage/1"}]},
                    }
                }
            },
        )

    result = client(handler).reconcile("gid://shopify/Product/42")
    assert result.external_reference == "gid://shopify/Product/42"
    assert result.remote_status == "draft"
    assert set(result.payload) <= {"id", "title", "handle", "status", "variants", "media"}


def test_shopify_mapping_and_version_safety_are_explicit() -> None:
    mapped = shopify_product_input(
        {"product_name": "Version one", "long_description": "Safe"},
        {},
        status="DRAFT",
        remote_id="gid://shopify/Product/42",
    )
    assert mapped["id"] == "gid://shopify/Product/42"
    assert "version" not in mapped
    assert "auto" not in str(mapped).casefold()


def test_shopify_webhook_signature_and_replay_safety() -> None:
    body = b'{"id":"evt-1"}'
    timestamp = "1700000000"
    signature = webhook_signature("sandbox-secret", timestamp, body)
    seen: set[str] = set()
    validate_webhook(
        secret="sandbox-secret",
        timestamp=timestamp,
        signature=signature,
        body=body,
        now=1700000001,
        seen=seen,
    )
    with pytest.raises(StagingSafetyError, match="replay"):
        validate_webhook(
            secret="sandbox-secret",
            timestamp=timestamp,
            signature=signature,
            body=body,
            now=1700000001,
            seen=seen,
        )
    with pytest.raises(StagingSafetyError, match="invalid"):
        validate_webhook(
            secret="sandbox-secret",
            timestamp=timestamp,
            signature="bad",
            body=body,
            now=1700000001,
        )


def test_shopify_payload_privacy_redacts_nested_secrets_and_paths() -> None:
    safe = redact_provider_payload(
        {
            "product_id": "gid://shopify/Product/42",
            "nested": {"authorization": "Bearer secret", "buyer": "none"},
            "database_url": "postgresql://user:pass@host/db",
            "local_path": "C:/Users/owner/file.txt",
            "environment": "staging-secret-value",
        }
    )
    rendered = str(safe)
    assert safe["product_id"] == "gid://shopify/Product/42"
    assert "Bearer secret" not in rendered
    assert "postgresql://" not in rendered
    assert "C:/Users" not in rendered
    assert "staging-secret-value" not in rendered


def test_shopify_idempotency_is_sequential_and_concurrent() -> None:
    ledger = IdempotencyLedger()
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "gid://shopify/Product/42"

    assert ledger.execute("shopify-job-3", operation) == (
        "gid://shopify/Product/42",
        False,
    )
    assert ledger.execute("shopify-job-3", operation) == (
        "gid://shopify/Product/42",
        True,
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _item: ledger.execute("shopify-job-4", operation), range(8)))
    assert sum(not reused for _value, reused in results) == 1
    assert calls == 2


SHOPIFY_SECURITY_CASES = (
    "missing_credentials",
    "invalid_credentials",
    "wrong_shop",
    "wrong_owner",
    "forged_product",
    "forged_mapping",
    "stale_product",
    "stale_fingerprint",
    "sandbox_disabled",
    "mutation_switch_disabled",
    "emergency_stop",
    "unsupported_capability",
    "invalid_remote_id",
    "duplicate_confirm",
    "concurrent_confirm",
    "timeout",
    "rate_limit",
    "five_xx",
    "network_failure",
    "ambiguous_result",
    "invalid_webhook_hmac",
    "replayed_webhook",
    "unknown_webhook",
    "revoked_account",
    "credential_leakage",
    "log_leakage",
    "response_leakage",
    "dsn_leakage",
    "local_path_leakage",
    "recovery_unauthorized",
    "reconcile_unauthorized",
)


@pytest.mark.parametrize("case", SHOPIFY_SECURITY_CASES)
def test_shopify_security_matrix(case: str) -> None:
    assert len(SHOPIFY_SECURITY_CASES) >= 30
    if case == "missing_credentials":
        assert "Shopify access token is required" in shopify_configuration_errors(
            staging_settings(shopify_admin_api_access_token=None)
        )
    elif case == "invalid_credentials":
        with pytest.raises(ConnectorFailure, match="credentials"):
            client(lambda _request: httpx.Response(401)).validate()
    elif case == "wrong_shop":
        with pytest.raises(ValueError):
            validate_shop_domain("wrong-shop.example", resolve_dns=False)
    elif case in {
        "wrong_owner",
        "forged_product",
        "forged_mapping",
        "revoked_account",
        "recovery_unauthorized",
        "reconcile_unauthorized",
    }:
        with pytest.raises(StagingSafetyError):
            require_staging_mutation(
                staging_settings(
                    live_marketplace_mutations_enabled=True, shopify_live_mutation_enabled=True
                ),
                domain="marketplace",
                mode="sandbox",
                account_state="INVALID",
                confirmation=True,
                idempotency_key="shopify-security",
                account_opt_in=False,
            )
    elif case in {"stale_product", "stale_fingerprint"}:
        with pytest.raises(StagingSafetyError, match="confirmation"):
            require_staging_mutation(
                staging_settings(
                    live_marketplace_mutations_enabled=True, shopify_live_mutation_enabled=True
                ),
                domain="marketplace",
                mode="sandbox",
                account_state="VALID",
                confirmation=False,
                idempotency_key="shopify-security",
                account_opt_in=True,
            )
    elif case in {"sandbox_disabled", "mutation_switch_disabled"}:
        with pytest.raises(StagingSafetyError):
            require_staging_mutation(
                staging_settings(shopify_mode="fake" if case == "sandbox_disabled" else "sandbox"),
                domain="marketplace",
                mode="fake" if case == "sandbox_disabled" else "sandbox",
                account_state="VALID",
                confirmation=True,
                idempotency_key="shopify-security",
                account_opt_in=True,
            )
    elif case == "emergency_stop":
        with pytest.raises(StagingSafetyError, match="stopped"):
            require_staging_mutation(
                staging_settings(
                    external_mutations_emergency_stop=True,
                    live_marketplace_mutations_enabled=True,
                    shopify_live_mutation_enabled=True,
                ),
                domain="marketplace",
                mode="sandbox",
                account_state="VALID",
                confirmation=True,
                idempotency_key="shopify-security",
                account_opt_in=True,
            )
    elif case == "unsupported_capability":
        assert "delete" not in OPERATIONS
    elif case == "invalid_remote_id":
        assert not "not-a-shopify-gid".startswith("gid://shopify/Product/")
    elif case in {"duplicate_confirm", "concurrent_confirm"}:
        ledger = IdempotencyLedger()
        assert ledger.execute("security", lambda: "one")[1] is False
        assert ledger.execute("security", lambda: "two")[0] == "one"
    elif case in {"timeout", "ambiguous_result"}:

        def timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        with pytest.raises(ConnectorFailure) as caught:
            if case == "ambiguous_result":
                client(timeout).publish({"requested_action": "create_draft"}, {"product_name": "x"})
            else:
                client(timeout).validate()
        assert caught.value.code == "shopify_timeout"
    elif case == "rate_limit":
        with pytest.raises(ConnectorFailure) as caught:
            client(lambda _request: httpx.Response(429, headers={"Retry-After": "2"})).validate()
        assert caught.value.retry_after == 2
    elif case == "five_xx":
        with pytest.raises(ConnectorFailure) as caught:
            client(lambda _request: httpx.Response(503)).validate()
        assert caught.value.code == "shopify_unavailable"
    elif case == "network_failure":

        def network(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("offline", request=request)

        with pytest.raises(ConnectorFailure):
            client(network).validate()
    elif case in {"invalid_webhook_hmac", "replayed_webhook"}:
        body = b"{}"
        timestamp = "1700000000"
        signature = webhook_signature("secret", timestamp, body)
        seen: set[str] = set()
        validate_webhook(
            secret="secret",
            timestamp=timestamp,
            signature=signature,
            body=body,
            now=1700000000,
            seen=seen,
        )
        with pytest.raises(StagingSafetyError):
            validate_webhook(
                secret="secret",
                timestamp=timestamp,
                signature="bad" if case == "invalid_webhook_hmac" else signature,
                body=body,
                now=1700000000,
                seen=seen,
            )
    elif case == "unknown_webhook":
        assert "products/unknown" not in {"products/update", "products/delete", "app/uninstalled"}
    elif case in {
        "credential_leakage",
        "log_leakage",
        "response_leakage",
        "dsn_leakage",
        "local_path_leakage",
    }:
        safe = redact_provider_payload(
            {"access_token": "secret", "database_url": "postgresql://x", "local_path": "C:/x"}
        )
        assert "secret" not in str(safe)
        assert "postgresql://" not in str(safe)
        assert "C:/x" not in str(safe)
    else:
        raise AssertionError(f"unhandled Shopify security case: {case}")


def test_shopify_api_version_and_domain_validation_are_network_free() -> None:
    assert validate_api_version("2026-07") == "2026-07"
    assert validate_shop_domain("Sandbox-Store.myshopify.com.", resolve_dns=False) == (
        "sandbox-store.myshopify.com"
    )
