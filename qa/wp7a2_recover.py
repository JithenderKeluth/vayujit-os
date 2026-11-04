"""One-time HUMAN-approved recovery for two interrupted WP7A2 runs only.

This is not a fallback in the normal deletion authority. Null-filled evidence
is quarantined, never called a valid historical signature. A present database
must independently prove its instance, role, exact marker and inactivity before
the existing non-FORCE deletion authority is used.
"""

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

from sqlalchemy import text

from qa.postgres_instance import MARKER, ROLE, ROOT, QaInstance, database_name

APPROVED_INSTANCE = "389b97d2-a4cd-4d9b-972e-6bb2bf5785eb"
APPROVED_CONTAINER = "a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23"
APPROVED = {"67abc9a3296a0694": 452, "325de41be0b7492f": 453}


def validate_damage(token, value):
    if token not in APPROVED or len(value) != APPROVED[token] or any(value):
        raise ValueError("EXACT_APPROVED_NULL_RECORD_REQUIRED")


def validate_identity(token, row, marker):
    if row[1] != ROLE or row[2] == -2:
        raise ValueError("RECOVERY_DATABASE_OWNER_OR_STATE_DENIED")
    if marker[:2] != (MARKER, token):
        raise ValueError("RECOVERY_MARKER_DENIED")
    uuid.UUID(marker[2])


def validate_tombstone(token, row):
    # Separate, subsequent HUMAN approval: no other token/OID can use this
    # exception. The inaccessible marker is never represented as reverified.
    if token != "325de41be0b7492f" or tuple(row) != (8996294, ROLE, -2):
        raise ValueError("EXACT_APPROVED_TOMBSTONE_REQUIRED")


def no_task_processes(token):
    # Inspect process arguments only in memory; emit a boolean, never arguments.
    script = (
        "$all=@(Get-CimInstance Win32_Process -ErrorAction Stop);"
        "$exclude=@($PID);$p=$PID;"
        "while($p){$r=$all|Where-Object ProcessId -eq $p;"
        "$p=$r.ParentProcessId;if($p){$exclude+= $p}};"
        f"$matches=@($all|Where-Object {{$_.CommandLine -like '*{token}*' "
        "-and $_.Name -in @('python.exe','node.exe','powershell.exe') "
        "-and $_.ProcessId -notin $exclude});"
        "if($matches.Count){exit 1}"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise ValueError("RECOVERY_ACTIVE_PROCESS_OR_INSPECTION_DENIED")


def recover(token):
    if token not in APPROVED:
        raise ValueError("EXACT_HUMAN_APPROVED_TOKEN_REQUIRED")
    q = QaInstance()
    q.verify_server()
    if (q.manifest["instance_id"], q.manifest["container_id"]) != (
        APPROVED_INSTANCE,
        APPROVED_CONTAINER,
    ):
        raise ValueError("RECOVERY_INSTANCE_DENIED")
    ledger = q.ledger_path(token)
    raw = ledger.read_bytes()
    validate_damage(token, raw)
    folder = ROOT / (
        f"tmp/qa-seller-browser/{token}"
        if token == "67abc9a3296a0694"
        else f"tmp/qa-wp7a2-backend/{token}"
    )
    if folder.is_symlink() or folder.is_junction() or not (folder / "openapi.json").is_file():
        raise ValueError("RECOVERY_RUN_EVIDENCE_REQUIRED")
    if token == "67abc9a3296a0694":
        witness = json.loads((folder / "wp7a2-run.json").read_text())
        if witness.get("token") != token or witness.get("synthetic") is not True:
            raise ValueError("RECOVERY_RUN_OWNERSHIP_DENIED")
    elif not (folder / "backend-results.xml").is_file():
        raise ValueError("RECOVERY_BACKEND_EVIDENCE_REQUIRED")
    no_task_processes(token)
    lock = ledger.with_suffix(".lock")
    if lock.exists():
        if lock.is_symlink() or lock.is_junction():
            raise ValueError("RECOVERY_LOCK_PATH_DENIED")
        contents = lock.read_bytes()
        if (
            contents not in (b"owned-lifecycle-operation", b"\0" * len(contents))
            or len(contents) > 64
        ):
            raise ValueError("RECOVERY_LOCK_FORMAT_DENIED")
        quarantine(lock, lock.with_suffix(".wp7a2-corrupt-lock"), contents)
        lock.unlink()  # Exact explicitly approved stale QA lock, not a database.
    with q.lease(token):
        no_task_processes(token)
        if ledger.read_bytes() != raw:
            raise ValueError("RECOVERY_LEDGER_CHANGED")
        admin = q.engine()
        try:
            with admin.connect() as c:
                name = database_name(token)
                row = c.execute(
                    text(
                        "SELECT d.oid::bigint,r.rolname,d.datconnlimit FROM pg_database d "
                        "JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:n"
                    ),
                    {"n": name},
                ).one_or_none()
                if c.scalar(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname=:n"), {"n": name}
                ):
                    raise ValueError("RECOVERY_ACTIVE_DATABASE_SESSIONS")
            marker = None
            tombstone = row is not None and row[2] == -2
            if tombstone:
                validate_tombstone(token, row)
            if row and not tombstone:
                target = q.engine(name)
                try:
                    with target.connect() as c:
                        marker = c.execute(
                            text(
                                "SELECT project_identifier,suite_token,creation_id "
                                "FROM test_database_marker WHERE marker_id=1"
                            )
                        ).one()
                        validate_identity(token, row, tuple(marker))
                finally:
                    target.dispose()
            quarantine(ledger, ledger.with_suffix(".wp7a2-corrupt-record"), raw)
            record = {
                "instance_id": q.manifest["instance_id"],
                "container_id": q.manifest["container_id"],
                "database": name,
                "owner": ROLE,
                "token": token,
                "oid": row[0] if row else None,
                "creation_id": marker[2] if marker else None,
                "state": "DROPPING" if tombstone else "ACTIVE" if row else "DROPPED",
                "wp7a2_human_approved_recovery": True,
                "original_signature_unavailable": True,
                "corrupt_record_sha256": hashlib.sha256(raw).hexdigest(),
                "absence_only_attestation": row is None,
                "human_authorized_tombstone_marker_exception": tombstone,
            }
            q.save(token, record)
            if row:
                # Same lease; instance, exact OID/owner, sessions, non-FORCE DROP
                # and independent absence rerun through the existing authority.
                q._drop(token, resume=tombstone, timeout_ms=90000)
            with admin.connect() as c:
                absent = not c.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": name}
                )
            if not absent:
                raise ValueError("RECOVERY_DATABASE_REMAINS")
        finally:
            admin.dispose()
    proof = {
        "token": token,
        "status": "PASS",
        "human_approved_scope": True,
        "original_signature_unavailable": True,
        "database_previously_present": row is not None,
        "database_absent": absent,
        "marker_reverified": marker is not None,
        "absence_only_attestation": row is None,
        "human_authorized_tombstone_marker_exception": tombstone,
        "force_or_session_termination": False,
    }
    destination = ROOT / f"tmp/qa-wp7a2/recovery-{token}.json"
    destination.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps(proof))


def quarantine(source: Path, destination: Path, contents: bytes):
    if destination.exists():
        if destination.read_bytes() != contents:
            raise ValueError("RECOVERY_QUARANTINE_CONFLICT")
        return
    with destination.open("xb") as f:
        f.write(contents)
        f.flush()
        os.fsync(f.fileno())


if __name__ == "__main__":
    import sys

    try:
        recover(*sys.argv[1:])
    except Exception as error:
        # Never print raw SQL, process output, environment or connection strings.
        print(json.dumps({"status": "BLOCKED", "classification": type(error).__name__}))
        raise SystemExit(1) from None
