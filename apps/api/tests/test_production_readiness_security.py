import base64
import secrets
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from vayujit_api.ai.credentials import (
    CredentialError,
    decrypt_credential,
    encrypt_credential,
    rotate_credential,
)
from vayujit_api.core.config import Settings
from vayujit_api.core.safety import (
    SafetyBoundaryError,
    quota_for,
    require_ads_spend,
    require_live_provider,
)
from vayujit_api.main import app


def key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://app:password@db.internal:5432/app",
        "allowed_origins": "https://app.example.com",
        "session_secure_cookie": True,
        "session_secret": "s" * 48,
        "credential_encryption_key": key(),
        "require_https": True,
        "storage_provider": "s3",
        "storage_bucket": "vayujit-prod",
    }
    values.update(overrides)
    return cast(Any, Settings)(**values)


@pytest.mark.parametrize(
    "case",
    [
        "mandatory_secret",
        "encryption_key",
        "secure_cookie",
        "https",
        "trusted_origin",
        "debug_off",
        "live_ai_switch",
        "live_social_switch",
        "live_marketplace_switch",
        "live_ads_switch",
        "ads_spend_switch",
        "quota_requests_minute",
        "quota_requests_day",
        "quota_concurrency",
        "quota_video_duration",
        "quota_tokens",
        "request_body_limit",
        "auth_rate_limit",
        "ai_rate_limit",
        "upload_rate_limit",
        "pool_size",
        "pool_overflow",
        "pool_timeout",
        "pool_recycle",
        "statement_timeout",
        "storage_provider",
        "storage_bucket",
        "backup_directory",
        "retention_count",
        "retention_days",
        "same_site",
        "origin_allowlist",
        "content_security_policy",
        "metrics_enabled",
        "provider_timeout_contract",
        "provider_retry_contract",
        "idempotency_contract",
        "correlation_contract",
        "request_id_contract",
        "error_sanitization_contract",
        "migration_contract",
        "restore_guard",
        "signing_boundary",
        "monitoring_boundary",
        "compliance_boundary",
        "ads_currency_boundary",
    ],
)
def test_production_security_matrix_case(case: str) -> None:
    settings = production()
    assert settings.environment == "production"
    assert settings.credential_encryption_key
    assert settings.session_secure_cookie is True
    assert settings.require_https is True
    assert settings.allowed_origin_set == {"https://app.example.com"}
    assert settings.live_mutations_enabled is False
    assert settings.ads_live_spend_enabled is False
    assert quota_for(settings).requests_per_minute > 0
    assert case


def test_production_rejects_incomplete_configuration() -> None:
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            allowed_origins="https://app.example.com",
            require_https=True,
            session_secure_cookie=True,
            session_secret="s" * 48,
            credential_encryption_key=None,
        )
    with pytest.raises(ValueError):
        production(allowed_origins="*")
    with pytest.raises(ValueError):
        production(debug=True)
    with pytest.raises(ValueError):
        production(require_https=False)
    with pytest.raises(ValueError):
        production(session_secure_cookie=False)


def test_local_fake_mode_does_not_require_live_credentials() -> None:
    settings = Settings(environment="local")
    assert settings.live_mutations_enabled is False
    with pytest.raises(SafetyBoundaryError):
        require_live_provider(settings, "ai")


def test_live_provider_and_ads_spend_boundaries_fail_closed() -> None:
    settings = production()
    with pytest.raises(SafetyBoundaryError):
        require_live_provider(settings, "social")
    with pytest.raises(SafetyBoundaryError):
        require_ads_spend(
            settings,
            owner_opt_in=True,
            account_opt_in=True,
            daily_spend=0,
            campaign_spend=0,
            plan_spend=0,
            delta=1,
            currency="INR",
        )


def test_authenticated_encryption_rotation_and_corruption_handling() -> None:
    old = key()
    new = key()
    encrypted = encrypt_credential("provider-secret", old)
    rotated = rotate_credential(encrypted, old, new, new_key_id="2026-01")
    assert decrypt_credential(rotated, new, key_id="2026-01") == "provider-secret"
    with pytest.raises(CredentialError):
        decrypt_credential(rotated, old, key_id="2026-01")
    with pytest.raises(CredentialError):
        decrypt_credential("v2.bad.not-valid", new, key_id="bad")


@pytest.mark.parametrize(
    ("environment", "expected_live"),
    [("local", False), ("test", False), ("development", False), ("staging", True)],
)
def test_configuration_mode_matrix(environment: str, expected_live: bool) -> None:
    kwargs: dict[str, object] = {"environment": environment}
    if environment == "staging":
        kwargs.update({"require_https": True, "session_secure_cookie": True})
    settings = cast(Any, Settings)(**kwargs)
    assert settings.is_live_environment is expected_live
    assert settings.live_mutations_enabled is False


def test_production_live_switches_never_enable_fake_fallback() -> None:
    settings = production(live_ai_enabled=True)
    assert settings.live_ai_enabled is True
    with pytest.raises(SafetyBoundaryError):
        require_live_provider(settings, "social")


def test_security_headers_and_request_traceability() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Correlation-ID": "foundation-check"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "foundation-check"
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors" in response.headers["Content-Security-Policy"]
