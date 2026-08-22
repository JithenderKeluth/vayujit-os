from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from vayujit_api.core.config import Settings
from vayujit_api.core.safety import (
    SafetyBoundaryError,
    require_ads_spend,
    require_live_provider,
)
from vayujit_api.main import app
from vayujit_api.operations import backup as backup_module
from vayujit_api.operations.backup import backup_path
from vayujit_api.publishing.connector import ConnectorFailure


def _production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://app:password@db.internal:5432/app",
        "allowed_origins": "https://app.example.com",
        "session_secure_cookie": True,
        "session_secret": "s" * 48,
        "credential_encryption_key": "a" * 44,
        "require_https": True,
        "storage_provider": "s3",
        "storage_bucket": "vayujit-prod",
    }
    values.update(overrides)
    return cast(Any, Settings)(**values)


@pytest.mark.parametrize("domain", ["ai", "social", "marketplace", "ads"])
def test_live_mutation_default_deny(domain: str) -> None:
    with pytest.raises(SafetyBoundaryError):
        require_live_provider(Settings(environment="local"), domain)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "spend"),
        ({"live_ads_mutations_enabled": True}, "invalid"),
        (
            {"live_ads_mutations_enabled": True, "ads_live_spend_enabled": True},
            "opt-in",
        ),
        (
            {
                "live_ads_mutations_enabled": True,
                "ads_live_spend_enabled": True,
                "ads_daily_spend_cap": 10,
                "ads_campaign_spend_cap": 10,
                "ads_marketing_plan_spend_cap": 10,
            },
            "cap",
        ),
    ],
)
def test_ads_spend_hard_gate(overrides: dict[str, object], expected: str) -> None:
    if expected == "invalid":
        with pytest.raises(ValueError):
            _production(**overrides)
        return
    settings = _production(**overrides)
    with pytest.raises(SafetyBoundaryError):
        require_ads_spend(
            settings,
            owner_opt_in=expected == "cap",
            account_opt_in=expected == "cap",
            daily_spend=10 if expected == "cap" else 0,
            campaign_spend=10 if expected == "cap" else 0,
            plan_spend=10 if expected == "cap" else 0,
            delta=1,
            currency="INR",
        )


def test_backup_path_confinement_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        backup_path("../outside.dump")
    with pytest.raises(ValueError):
        backup_path("nested/outside.dump")


def test_readiness_endpoint_requires_auth_and_health_is_redacted() -> None:
    client = TestClient(app)
    readiness = client.get("/api/v1/system/production-readiness")
    health = client.get("/health")
    assert readiness.status_code == 401
    assert health.status_code == 200
    body = health.json()
    serialized = str(body).casefold()
    assert "database_url" not in serialized
    assert "credential_encryption_key" not in serialized
    assert "password" not in serialized


def test_worker_concurrency_is_bounded() -> None:
    assert Settings(environment="local").publishing_worker_concurrency == 2
    with pytest.raises(ValueError):
        Settings(environment="local", publishing_worker_concurrency=0)
    with pytest.raises(ValueError):
        Settings(environment="local", publishing_worker_concurrency=33)


@pytest.mark.parametrize(
    ("code", "retryable", "ambiguous"),
    [
        ("provider_timeout", True, False),
        ("provider_rate_limited", True, False),
        ("provider_5xx", True, False),
        ("provider_auth_failed", False, False),
        ("provider_validation_failed", False, False),
        ("provider_ambiguous", True, True),
        ("provider_unavailable", True, False),
    ],
)
def test_provider_failure_classification_is_safe(
    code: str, retryable: bool, ambiguous: bool
) -> None:
    failure = ConnectorFailure(
        code,
        "Safe provider failure.",
        retryable=retryable,
        ambiguous=ambiguous,
    )
    assert failure.code == code
    assert failure.retryable is retryable
    assert failure.ambiguous is ambiguous
    assert "secret" not in failure.safe_message.casefold()


def test_database_backup_failure_is_safe(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backup_module, "backup_directory", lambda: tmp_path)
    monkeypatch.setattr(
        backup_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("pg_dump")),
    )
    with pytest.raises(RuntimeError, match="PostgreSQL backup command failed"):
        backup_module.create_backup(cast(Any, None), uuid.uuid4())
    assert not list(tmp_path.iterdir())
