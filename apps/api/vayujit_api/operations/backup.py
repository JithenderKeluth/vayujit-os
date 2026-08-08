import hashlib
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from vayujit_api import __version__
from vayujit_api.core.config import get_settings
from vayujit_api.operations.models import BackupRecord


def backup_directory() -> Path:
    configured = Path(get_settings().backup_directory)
    root = (configured if configured.is_absolute() else Path.cwd() / configured).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def backup_path(filename: str) -> Path:
    if Path(filename).name != filename:
        raise ValueError("Invalid backup filename.")
    path = (backup_directory() / filename).resolve()
    if path.parent != backup_directory():
        raise ValueError("Invalid backup path.")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_backup(db: Session, owner_id: uuid.UUID) -> BackupRecord:
    settings = get_settings()
    url = make_url(settings.database_url)
    stamp = datetime.now(UTC)
    key = stamp.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    filename = f"vayujit-{key}.dump"
    path = backup_path(filename)
    environment = os.environ.copy()
    if url.password:
        environment["PGPASSWORD"] = url.password
    pg_dump_command = "pg_dump"
    if settings.pg_dump_path:
        configured = Path(settings.pg_dump_path).expanduser()
        if configured.name.lower() != "pg_dump.exe" or not configured.is_file():
            raise RuntimeError("Configured PostgreSQL backup executable is invalid.")
        pg_dump_command = str(configured.resolve())
    args = [
        pg_dump_command,
        "-Fc",
        "--no-owner",
        "--no-privileges",
        "-h",
        str(url.host or "127.0.0.1"),
        "-p",
        str(url.port or 5432),
        "-U",
        str(url.username or ""),
        "-d",
        str(url.database or ""),
    ]
    try:
        with path.open("wb") as output:
            try:
                subprocess.run(
                    args,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    env=environment,
                    check=True,
                    timeout=300,
                )
            except FileNotFoundError:
                output.seek(0)
                output.truncate()
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "infrastructure-postgres-1",
                        "pg_dump",
                        "-Fc",
                        "--no-owner",
                        "--no-privileges",
                        "-U",
                        str(url.username or ""),
                        "-d",
                        str(url.database or ""),
                    ],
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=300,
                )
    except (OSError, subprocess.SubprocessError) as error:
        path.unlink(missing_ok=True)
        raise RuntimeError("PostgreSQL backup command failed.") from error
    revision = str(db.scalar(text("select version_num from alembic_version")) or "unknown")
    record = BackupRecord(
        owner_id=owner_id,
        backup_key=key,
        filename=filename,
        format="postgres-custom",
        size_bytes=path.stat().st_size,
        checksum_sha256=sha256(path),
        application_version=__version__,
        migration_revision=revision,
        database_name=str(url.database or ""),
        created_at=stamp,
        verification_status="pending",
        status="created",
    )
    db.add(record)
    db.flush()
    sidecar = {
        "backup_id": str(record.id),
        "backup_key": key,
        "created_at": stamp.isoformat(),
        "application_version": __version__,
        "migration_revision": revision,
        "database_name": record.database_name,
        "size_bytes": record.size_bytes,
        "checksum_sha256": record.checksum_sha256,
        "format": record.format,
        "encryption_status": "not_encrypted",
        "created_by_owner_id": str(owner_id),
        "verification_status": record.verification_status,
    }
    backup_path(f"{filename}.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return record


def verify_backup(record: BackupRecord) -> bool:
    path = backup_path(record.filename)
    valid = (
        path.is_file()
        and path.stat().st_size == record.size_bytes
        and sha256(path) == record.checksum_sha256
    )
    record.verification_status = "verified" if valid else "invalid"
    record.status = "verified" if valid else "failed"
    record.verified_at = datetime.now(UTC)
    if not valid:
        record.failure_code = "backup_verification_failed"
        record.safe_failure_message = "Backup checksum or size verification failed."
    return valid
