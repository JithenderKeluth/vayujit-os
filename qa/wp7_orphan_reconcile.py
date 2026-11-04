"""One HUMAN-approved orphan reconciliation; never deletes a database.

Legacy lifecycle locks contain no process identity. This is deliberately not an
automatic stale-lock policy or an extension of the normal deletion authority.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from qa.postgres_instance import ROOT, GuardDenied, QaInstance, database_name

AUTHORIZED_TOKEN = "4963364d9460948d"
RESOLUTION = "HUMAN_AUTHORIZED_INDEPENDENT_ABSENCE_RECONCILIATION"


def require(condition, code):
    if not condition:
        raise GuardDenied(code)


def fingerprint(path):
    require(
        path.is_file() and not path.is_symlink() and not path.is_junction(),
        "WP7_REGULAR_FILE_REQUIRED",
    )
    stat = path.stat()
    return (
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def active_process(token):
    # Only the boolean leaves the child. Never persist process command lines.
    script = (
        "$ErrorActionPreference='Stop'; $n=@(Get-CimInstance Win32_Process | "
        "Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and "
        f"$_.CommandLine.Contains('{token}') -and "
        "$_.CommandLine -match 'fixture_server|qa[.]wp7_recover' }); "
        "if($n.Count){exit 2}else{exit 0}"
    )
    result = subprocess.run(
        [
            str(Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            base64.b64encode(script.encode("utf-16-le")).decode(),
        ],
        capture_output=True,
        timeout=20,
        check=False,
    )
    require(result.returncode in {0, 2}, "WP7_PROCESS_CHECK_UNAVAILABLE")
    return result.returncode == 2


def verify_absence(instance, token):
    instance.verify_server()
    engine = instance.engine()
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            name = database_name(token)
            require(
                not connection.scalar(
                    text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"),
                    {"name": name},
                ),
                "WP7_DATABASE_STILL_EXISTS",
            )
            require(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() "
                        "AND (datname=:name OR position(:name in query)>0)"
                    ),
                    {"name": name},
                )
                == 0,
                "WP7_ACTIVE_DATABASE_OPERATION",
            )
    finally:
        engine.dispose()


def reconcile(instance, token, *, approved=False, evidence_root=None, process_check=active_process):
    require(
        approved is True and token == AUTHORIZED_TOKEN, "WP7_EXACT_HUMAN_AUTHORIZATION_REQUIRED"
    )
    evidence = (evidence_root or ROOT / "tmp/qa-seller-browser") / token
    require(
        evidence.is_dir() and not evidence.is_symlink() and not evidence.is_junction(),
        "WP7_EVIDENCE_DIRECTORY_DENIED",
    )
    marker = evidence / "wp7-run.json"
    failure = evidence / "session-final.json"
    marker_fp, failure_fp = fingerprint(marker), fingerprint(failure)
    require(json.loads(marker.read_text())["token"] == token, "WP7_EVIDENCE_TOKEN_DENIED")
    previous = json.loads(failure.read_text())
    require(
        previous.get("token") == token
        and previous.get("child_exit") == "TIMEOUT"
        and previous.get("status") == "CLEANUP_BLOCKED",
        "WP7_ORIGINAL_INTERRUPTION_EVIDENCE_REQUIRED",
    )
    record = instance.load(token)  # Existing signature, instance, role and token authority.
    require(record.get("state") == "DROPPING", "WP7_ORPHAN_STATE_DENIED")
    require(type(record.get("oid")) is int and record["oid"] > 0, "WP7_CREATION_PROOF_REQUIRED")
    uuid.UUID(record["creation_id"])
    ledger = instance.ledger_path(token)
    ledger_fp = fingerprint(ledger)
    lock = ledger.with_suffix(".lock")
    lock_fp = fingerprint(lock)
    require(lock.read_text() == "owned-lifecycle-operation", "WP7_LEGACY_LOCK_CONTENT_DENIED")
    # Original lock continues to block normal lifecycle operations throughout.
    exclusive = ledger.with_suffix(".reconcile.lock")
    with exclusive.open("x") as handle:
        try:
            handle.write("exact-human-approved-reconciliation")
            handle.flush()
            require(not process_check(token), "WP7_ACTIVE_OWNER_PROCESS")
            verify_absence(instance, token)
            require(fingerprint(ledger) == ledger_fp, "WP7_LIFECYCLE_CHANGED")
            require(fingerprint(lock) == lock_fp, "WP7_LOCK_CHANGED")
            require(
                fingerprint(marker) == marker_fp and fingerprint(failure) == failure_fp,
                "WP7_EVIDENCE_CHANGED",
            )
            instance.save(
                token,
                {
                    **record,
                    "state": "DROPPED",
                    "cleanup_resolution": RESOLUTION,
                    "prior_state": "DROPPING",
                    "prior_record_sha256": ledger_fp[3],
                    "original_failure_sha256": failure_fp[3],
                    "reconciled_at": datetime.now(UTC).isoformat(),
                    "no_database_deleted_by_reconciliation": True,
                    "original_failure_preserved": True,
                },
            )
            # Only after signed terminal attestation is durable may this exact lock go.
            require(fingerprint(lock) == lock_fp, "WP7_LOCK_CHANGED")
            lock.unlink()
        finally:
            handle.close()
            exclusive.unlink()
    return {
        "token": token,
        "status": "ABSENCE_RECONCILED",
        "resolution": RESOLUTION,
        "database_absent": True,
        "database_deleted": False,
        "original_failure_preserved": True,
        "raw_output_persisted": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-approved-exact-orphan", action="store_true")
    args = parser.parse_args()
    failed = False
    try:
        result = reconcile(
            QaInstance(), AUTHORIZED_TOKEN, approved=args.human_approved_exact_orphan
        )
    except Exception as error:  # noqa: BLE001 - never print driver errors or raw output
        failed = True
        code = str(error) if isinstance(error, GuardDenied) else "WP7_RECONCILIATION_EXCEPTION"
        if not re.fullmatch(r"(?:QA|WP7)_[A-Z_]+", code):
            code = "WP7_RECONCILIATION_EXCEPTION"
        result = {
            "token": AUTHORIZED_TOKEN,
            "status": "BLOCKED",
            "safe_code": code,
            "raw_output_persisted": False,
        }
    (ROOT / "tmp/qa-wp7/orphan-absence-reconciliation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
