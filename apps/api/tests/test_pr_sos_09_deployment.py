from pathlib import Path

import pytest
from pydantic import ValidationError

from vayujit_api.core.config import Settings


def production_values() -> dict[str, object]:
    return {
        "_env_file": None,
        "environment": "production",
        "database_url": "postgresql+psycopg://app_role:secret@db.internal:5432/vayujit",
        "allowed_origins": "https://app.example.test",
        "public_api_url": "https://api.example.test",
        "public_web_url": "https://app.example.test",
        "require_https": True,
        "session_secure_cookie": True,
        "session_secret": "x" * 32,
        "credential_encryption_key": "y" * 32,
        "storage_provider": "s3",
        "storage_bucket": "private-vayujit",
        "backup_directory": "/var/lib/vayujit/backups",
        "external_mutations_emergency_stop": True,
    }


def test_production_reference_settings_accept_safe_non_default_values() -> None:
    settings = Settings(**production_values())
    report = settings.configuration_report()
    assert report["environment"] == "production"
    assert report["storage_provider"] == "s3"
    assert report["external_mutations_default_deny"] is True
    assert "database_url" not in report
    assert "session_secret" not in report


def test_production_reference_settings_reject_missing_session_secret() -> None:
    values = production_values()
    values["session_secret"] = None
    with pytest.raises(ValidationError, match="32-character session secret"):
        Settings(**values)


def test_deployment_reference_has_private_database_and_fail_closed_switches() -> None:
    compose = Path(__file__).parents[3] / "infrastructure" / "docker-compose.production.yml"
    env_template = Path(__file__).parents[3] / "infrastructure" / "production.env.example"
    text = compose.read_text(encoding="utf-8")
    env_text = env_template.read_text(encoding="utf-8")
    assert "ports:" not in text.split("  postgres:", 1)[1].split("  api:", 1)[0]
    assert "internal: true" in text
    assert "POSTGRES_DB=" in env_text
    assert "POSTGRES_USER=" in env_text
    assert "POSTGRES_PASSWORD=" in env_text
    assert "VAYUJIT_PUBLIC_WEB_DOMAIN=" in env_text
    assert "VAYUJIT_LIVE_MARKETPLACE_MUTATIONS_ENABLED=false" in env_text
    assert "VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true" in env_text


def test_production_reference_worker_and_loopback_ports() -> None:
    compose = Path(__file__).parents[3] / "infrastructure" / "docker-compose.production.yml"
    text = compose.read_text(encoding="utf-8")
    assert 'entrypoint: ["python", "-m", "vayujit_api.publishing.worker"]' in text
    assert "api: { condition: service_healthy }" in text
    assert '"${VAYUJIT_HTTP_BIND:-80}:80"' in text
    assert '"${VAYUJIT_HTTPS_BIND:-443}:443"' in text
