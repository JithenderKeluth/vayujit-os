import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from vayujit_api.core.logging import redact
from vayujit_api.main import app
from vayujit_api.operations import backup as backup_module
from vayujit_api.operations.models import BackupRecord


def test_liveness_and_correlation_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Correlation-ID": "operator-123"})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == "operator-123"
        generated = client.get("/health/live", headers={"X-Correlation-ID": "x" * 1000})
        assert generated.status_code == 200
        assert generated.headers["X-Correlation-ID"] != "x" * 1000
        assert len(generated.headers["X-Correlation-ID"]) <= 64


def test_maintenance_blocks_writes_but_allows_health(monkeypatch) -> None:
    monkeypatch.setattr("vayujit_api.core.observability.maintenance_enabled", lambda: True)
    with TestClient(app) as client:
        blocked = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "http://127.0.0.1:4200"},
            json={"email": "owner@example.com", "password": "not-a-real-password"},
        )
        assert blocked.status_code == 503
        assert blocked.json()["code"] == "maintenance_mode"
        assert client.get("/health/live").status_code == 200


def test_log_redaction() -> None:
    event = redact(
        object(),
        "info",
        {
            "event": "test",
            "password": "secret",
            "cookie": "session=secret",
            "authorization": "Bearer secret",
            "database_url": "postgresql://secret",
            "api_key": "secret",
            "encrypted_api_key": "secret",
            "credential_encryption_key": "secret",
        },
    )
    assert json.dumps(event).count("[REDACTED]") == 7
    assert "secret" not in json.dumps(event)


def test_backup_paths_and_checksum_verification(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backup_module, "backup_directory", lambda: tmp_path.resolve())
    try:
        backup_module.backup_path("../escape.dump")
        raise AssertionError("Traversal must be rejected.")
    except ValueError:
        pass
    path = tmp_path / "safe.dump"
    path.write_bytes(b"safe backup")
    record = BackupRecord(
        id=uuid4(),
        owner_id=uuid4(),
        backup_key="safe",
        filename="safe.dump",
        format="postgres-custom",
        size_bytes=path.stat().st_size,
        checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        application_version="0.1.0",
        migration_revision="20260812_0022",
        database_name="restore_test",
        created_at=datetime.now(UTC),
        verification_status="pending",
        status="created",
    )
    assert backup_module.verify_backup(record) is True
    path.write_bytes(b"tampered")
    assert backup_module.verify_backup(record) is False
