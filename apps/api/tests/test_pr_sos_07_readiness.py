"""Focused PR-SOS-07 production configuration and operational safety gates."""

from __future__ import annotations

from typing import Any, cast

import pytest

from vayujit_api.core.config import Settings


def production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://vayujit_app:secret@db.internal:5432/vayujit",
        "allowed_origins": "https://app.example.com",
        "session_secure_cookie": True,
        "session_secret": "s" * 48,
        "credential_encryption_key": "a" * 44,
        "require_https": True,
        "storage_provider": "s3",
        "storage_bucket": "vayujit-media",
        "public_api_url": "https://api.example.com",
        "public_web_url": "https://app.example.com",
    }
    values.update(overrides)
    return cast(Any, Settings)(**values)


def test_production_report_is_safe_and_mutations_default_deny() -> None:
    settings = production()
    report = settings.configuration_report()
    assert report["expected_migration_revision"] == "20261203_0146"
    assert report["external_mutations_default_deny"] is True
    assert report["emergency_stop_active"] is False
    serialized = str(report).casefold()
    assert "secret@" not in serialized
    assert "credential_encryption_key" not in serialized
    assert 'session_secret="' not in serialized


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "postgresql+psycopg://app:secret@127.0.0.1:5432/app"},
        {"database_url": "postgresql+psycopg://postgres:secret@db.internal:5432/app"},
        {"storage_provider": "filesystem"},
        {"public_api_url": "http://api.example.com"},
        {"public_web_url": "http://app.example.com"},
    ],
)
def test_production_rejects_unsafe_runtime_defaults(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        production(**overrides)


def test_expected_migration_revision_is_deployment_configurable() -> None:
    settings = production(expected_migration_revision="release-2026-10")
    assert settings.configuration_report()["expected_migration_revision"] == "release-2026-10"
