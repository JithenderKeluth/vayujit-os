from pathlib import Path

import pytest
from pydantic import ValidationError

from vayujit_api.core.config import Settings
from vayujit_api.core.safety import SafetyBoundaryError, require_live_provider


def pc_local_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "_env_file": None,
        "environment": "pc_local",
        "debug": False,
        "require_https": False,
        "session_secure_cookie": False,
        "session_same_site": "strict",
        "allow_missing_origin": False,
        "web_origin": "http://127.0.0.1:8443",
        "allowed_origins": "http://127.0.0.1:8443,http://localhost:8443",
        "session_secret": "a" * 64,
        "credential_encryption_key": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
        "database_url": (
            "postgresql+psycopg://vayujit_app:" + "b" * 64 + "@postgres:5432/vayujit_business"
        ),
        "storage_provider": "filesystem",
        "external_mutations_emergency_stop": True,
    }
    values.update(overrides)
    return values


def test_pc_local_profile_is_loopback_only_and_not_a_live_environment() -> None:
    settings = Settings(**pc_local_values())

    assert settings.is_live_environment is False
    assert settings.configuration_report()["external_mutations_default_deny"] is True
    with pytest.raises(SafetyBoundaryError, match="disabled by configuration"):
        require_live_provider(settings, "marketplace")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"session_secret": "short"}, "unique session secret"),
        ({"credential_encryption_key": "not-a-key"}, "decode to 32 bytes"),
        ({"allowed_origins": "https://example.com"}, "HTTP loopback"),
        ({"web_origin": "http://localhost:8444"}, "listed in allowed Origins"),
        (
            {"database_url": "postgresql://vayujit_app:password@localhost/vayujit_business"},
            "private Compose",
        ),
        (
            {
                "database_url": (
                    "postgresql://vayujit_app:" + "b" * 64 + "@postgres:5432/vayujit_test"
                )
            },
            "dedicated vayujit_business",
        ),
        ({"live_marketplace_mutations_enabled": True}, "cannot enable live provider writes"),
        ({"live_email_delivery_enabled": True}, "cannot enable live provider writes"),
        ({"external_mutations_emergency_stop": False}, "emergency stop"),
        ({"allow_missing_origin": True}, "exact Origin"),
        ({"require_https": True}, "loopback HTTP"),
        ({"debug": True}, "cannot enable debug"),
        ({"restore_enabled": True}, "API restore disabled"),
    ],
)
def test_pc_local_rejects_unsafe_configuration(override: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**pc_local_values(**override))


def test_pc_compose_is_private_and_has_explicit_business_volumes() -> None:
    root = Path(__file__).parents[3]
    compose = (root / "infrastructure" / "docker-compose.pc.yml").read_text(encoding="utf-8")
    postgres = compose.split("  postgres:", 1)[1].split("  api:", 1)[0]
    api = compose.split("  api:", 1)[1].split("  worker:", 1)[0]
    worker = compose.split("  worker:", 1)[1].split("  web:", 1)[0]
    proxy = compose.split("  proxy:", 1)[1].split("networks:", 1)[0]

    assert "ports:" not in postgres
    assert "ports:" not in api
    assert "ports:" not in worker
    assert '"127.0.0.1:${VAYUJIT_PC_HTTP_PORT:-8443}:8081"' in proxy
    assert "internal: true" in compose
    assert "healthcheck:" in proxy
    assert "${VAYUJIT_PC_VOLUME_PREFIX:?required}_postgres_data" in compose
    assert "${VAYUJIT_PC_VOLUME_PREFIX:?required}_media_data" in compose
    assert "${VAYUJIT_PC_VOLUME_PREFIX:?required}_runtime_control" in compose
    assert "pc-postgres-init.sh" in compose
    postgres_init = (root / "infrastructure" / "pc-postgres-init.sh").read_text(encoding="utf-8")
    assert "VAYUJIT_DATABASE_NAME" in postgres_init
    assert "vayujit_business" in (root / "infrastructure" / "pc-local.env.example").read_text(
        encoding="utf-8"
    )
    nginx = (root / "infrastructure" / "nginx.pc.conf").read_text(encoding="utf-8")
    assert 'add_header X-Frame-Options "DENY" always' in nginx
    assert 'add_header X-Content-Type-Options "nosniff" always' in nginx


def test_pc_env_template_disables_external_actions_and_has_no_real_secrets() -> None:
    root = Path(__file__).parents[3]
    env_template = (root / "infrastructure" / "pc-local.env.example").read_text(encoding="utf-8")
    assert "VAYUJIT_ENVIRONMENT=pc_local" in env_template
    assert "VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true" in env_template
    assert "VAYUJIT_LIVE_MARKETPLACE_MUTATIONS_ENABLED=false" in env_template
    assert "VAYUJIT_LIVE_EMAIL_DELIVERY_ENABLED=false" in env_template
    assert "CHANGE_ME" in env_template
    assert "vayujit_dev" not in env_template
    assert "AGE-SECRET-KEY" not in env_template


def test_pc_startup_requires_explicit_activation_and_never_removes_named_volumes() -> None:
    root = Path(__file__).parents[3]
    startup = (root / "scripts" / "start-pc-first.ps1").read_text(encoding="utf-8")
    initializer = (root / "scripts" / "initialize-pc-first.ps1").read_text(encoding="utf-8")
    assert '"START VAYUJIT BUSINESS DATABASE"' in startup
    assert "prepared_not_started" in initializer
    assert "--detach" in startup
    assert "down -v" not in startup
    assert "insert into" not in initializer.casefold()
    assert "seed_demo" not in initializer.casefold()


def test_pc_backup_uses_encryption_and_separate_physical_disk_guard() -> None:
    root = Path(__file__).parents[3]
    initializer = (root / "scripts" / "initialize-pc-first.ps1").read_text(encoding="utf-8")
    backup = (root / "scripts" / "backup-pc-first.ps1").read_text(encoding="utf-8")
    restore = (root / "scripts" / "verify-pc-restore.ps1").read_text(encoding="utf-8")
    assert "Get-Partition" in initializer
    assert "age --encrypt" in backup
    assert "verify-pc-restore.ps1" in backup
    assert "--network none" in restore
    assert "pg_restore --exit-on-error" in restore
    assert "ck_users_single_owner" in restore
    assert "pc_media_backup_cli verify" in backup
    assert "maintenance-on --confirm" in backup
    assert "stop --timeout 45 worker" in backup
    assert "stop --timeout 30 api" in backup
    assert "pc_media_backup_cli create" in backup
    assert "maintenance-off --confirm" in backup


def test_pc_backup_validates_stable_media_artifacts_before_encrypting() -> None:
    root = Path(__file__).parents[3]
    backup = (root / "scripts" / "backup-pc-first.ps1").read_text(encoding="utf-8")
    cli_path = root / "apps" / "api" / "vayujit_api" / "operations" / "pc_media_backup_cli.py"
    cli = cli_path.read_text(encoding="utf-8")

    assert 'destination / "media.zip"' in cli
    assert 'destination / "media.json"' in cli
    assert "Get-VayujitMediaBackupArtifacts -OutputDirectory $workRoot" in backup
    assert 'Get-ChildItem -LiteralPath $workRoot -Filter "media-*.zip"' not in backup
    assert 'Get-ChildItem -LiteralPath $workRoot -Filter "media-*.json"' not in backup
    assert "database_dump_validation_failed" in backup
    assert "media_backup_validation_failed" in backup
    assert backup.index("database_dump_validation_failed") < backup.index('"database encryption"')
    assert backup.index("media_backup_validation_failed") < backup.index('"media encryption"')


def test_pc_backup_task_is_daily_user_scoped_and_requires_confirmation() -> None:
    root = Path(__file__).parents[3]
    task = (root / "scripts" / "register-pc-backup-task.ps1").read_text(encoding="utf-8")
    assert "-Daily" in task
    assert "-LogonType Interactive" in task
    assert "-ConfirmRegistration" in task
    assert "owner_activated" in task
    assert "DisallowStartIfOnBatteries" in task


def test_pc_rebuild_requires_recent_verified_backup() -> None:
    root = Path(__file__).parents[3]
    startup = (root / "scripts" / "start-pc-first.ps1").read_text(encoding="utf-8")
    assert "$Rebuild" in startup
    assert "verified encrypted backup created within the last 24 hours" in startup
    assert "up --build --detach" in startup


def test_pc_local_application_backup_route_cannot_create_plaintext_dump(monkeypatch) -> None:
    from vayujit_api.operations import backup

    monkeypatch.setattr(backup, "get_settings", lambda: Settings(**pc_local_values()))
    with pytest.raises(RuntimeError, match="Unencrypted application backups are disabled"):
        backup.create_backup(None, None)
