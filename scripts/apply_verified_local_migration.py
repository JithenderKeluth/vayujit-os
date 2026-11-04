"""Explicit exact-source operation, gated by owner approval and a fresh rehearsal.

Never initializes databases, touches QA, enables external actions, or auto-restores.
Reports contain no credentials, raw SQL errors, command output or business data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

import audit_local_migration_contract as audit
import local_migration_rehearsal as safe
import local_reconciliation_copy as repair
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))


def source_url_allowed(url):
    return (
        url.get_backend_name() == "postgresql"
        and url.host == "127.0.0.1"
        and url.port == 5432
        and url.database == "vayujit"
        and url.username == "vayujit"
    )


def require(value, code):
    if not value:
        raise safe.SafeFailure(code)


def exact_plan(operations):
    return Counter(o["operation"] for o in operations) == {
        "set_canonical_default": 31,
        "add_canonical_index": 24,
    }


def source_engine(*, readonly=False):
    from vayujit_api.core.config import Settings

    url = make_url(Settings().database_url)
    require(source_url_allowed(url), "exact_source_url_required")
    return sa.create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "options": "-c TimeZone=UTC -c statement_timeout=60000 -c lock_timeout=5000"
            + (" -c default_transaction_read_only=on" if readonly else ""),
            "application_name": "vayujit_owner_approved_local_upgrade",
        },
    )


def verify_records(db, state, *, migrated):
    require(
        bool(state["preservation"]["columns"])
        and state["preservation"]["columns"].keys()
        == state["preservation"]["fingerprints"].keys(),
        "preservation_contract_missing",
    )
    require(
        db.scalar(sa.text("SELECT current_database()")) == "vayujit"
        and db.scalar(sa.text("SELECT current_user")) == "vayujit",
        "source_identity_changed",
    )
    require(
        db.scalar(
            sa.text("SELECT oid FROM pg_database WHERE datname=current_database()")
        )
        == state["database_oid"],
        "source_database_oid_changed",
    )
    for table, columns in state["preservation"]["columns"].items():
        if migrated and table == "alembic_version":
            continue
        require(
            db.scalar(sa.text(safe.fingerprint_sql(table, columns, migrated=migrated)))
            == state["preservation"]["fingerprints"][table],
            "source_preservation_mismatch",
        )
    require(
        db.scalar(sa.text("SELECT count(*) FROM users")) == 1
        and db.scalar(
            sa.text(
                "SELECT count(*) FROM pg_constraint WHERE "
                "conname='ck_users_single_owner' AND convalidated"
            )
        )
        == 1,
        "single_owner_constraint_changed",
    )
    if migrated:
        require(
            db.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == repair.HEAD,
            "source_head_not_reached",
        )
        for table, expected in repair.expected_contracts().items():
            repair.verify_canonical(
                expected, audit.actual_contract(sa.inspect(db), table)
            )


def private_state(path):
    safe.no_reparse(path)
    token = path.parent.name
    expected = (
        Path(os.environ["LOCALAPPDATA"])
        / "VAYUJIT OS/migration-stage"
        / token
        / "source-state.json"
    )
    require(
        bool(re.fullmatch(r"[a-f0-9]{16}", token))
        and path.resolve() == expected.resolve()
        and (path.parent / "migration-run.marker").read_text() == token,
        "private_state_path_invalid",
    )
    return json.loads(path.read_text())


def fresh_verify(path):
    state = private_state(path)
    engine = source_engine(readonly=True)
    try:
        with engine.connect() as db:
            require(
                db.scalar(sa.text("SHOW transaction_read_only")) == "on",
                "read_only_not_enforced",
            )
            verify_records(db, state, migrated=True)
        print(
            json.dumps(
                {
                    "status": "FRESH_SOURCE_PROCESS_VERIFIED",
                    "head": repair.HEAD,
                    "original_tables_verified": len(state["preservation"]["columns"]),
                }
            )
        )
    finally:
        engine.dispose()


def main():
    from vayujit_api.core.config import Settings
    from vayujit_api.core.observability import maintenance_marker

    os.chdir(ROOT)
    token = secrets.token_hex(8)
    report_path = ROOT / f"tmp/local-source-migration-{token}.json"
    report = {
        "token": token,
        "status": "RUNNING",
        "source_database_modified": False,
        "source_transaction_committed": False,
        "external_actions_enabled": False,
        "raw_output_persisted": False,
        "recovery": {},
    }
    stage = "exact_target_preflight"
    private = None
    marker_owned = False
    pause_armed = False
    committed = False
    engine = None
    cfg = Settings()
    process_env = os.environ.copy()
    process_env["PYTHONPATH"] = str(ROOT / "apps/api")
    # Preserve controls by keeping external mutations blocked on resumed API.
    process_env["VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP"] = "true"
    process_env["VAYUJIT_LIVE_MUTATIONS_ENABLED"] = "false"
    started = time.monotonic()

    def persist():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def process_action(action):
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts/local-api-maintenance.ps1"),
                "-Action",
                action,
                "-Token",
                token,
            ],
            env=process_env,
            capture_output=True,
            check=False,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        child = json.loads(result.stdout)
        if result.returncode:
            code = child.get("failure_code", "api_process_operation_failed")
            require(bool(re.fullmatch(r"[a-z_]+", code)), "api_process_report_invalid")
            report["api_process_failure"] = {"code": code, "line": child.get("line")}
            raise safe.SafeFailure(code, result.returncode)
        return child

    def maintenance(command):
        result = json.loads(
            safe.checked(
                [
                    sys.executable,
                    "-m",
                    "vayujit_api.maintenance_cli",
                    command,
                    "--confirm",
                ],
                env=process_env,
            )
        )
        require(result.get("status") == "PASS", "canonical_maintenance_command_failed")
        return result

    try:
        witness = audit.load_file(
            ROOT / "scripts/preflight-local-database.py", "source_preflight"
        ).run()
        require(
            witness["status"] == "READ_ONLY_PREFLIGHT_COMPLETE"
            and witness["database_revision"] == [repair.LEGACY],
            "legacy_preflight_required",
        )
        require(not cfg.publishing_worker_enabled, "enabled_worker_requires_review")
        marker = maintenance_marker()
        require(not marker.exists(), "maintenance_already_enabled_preserve_state")
        private = Path(
            json.loads(
                safe.checked(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(ROOT / "scripts/local-reconciliation-private.ps1"),
                        "-Token",
                        token,
                    ]
                )
            )["stage"]
        )
        report["api_before"] = process_action("Inspect")
        engine = source_engine(readonly=True)
        with engine.connect() as db:
            db_oid = db.scalar(
                sa.text("SELECT oid FROM pg_database WHERE datname=current_database()")
            )
            for table, expected in repair.expected_contracts().items():
                repair.reject_hidden_drift(db, table)
                repair.validate_legacy(
                    expected,
                    audit.actual_contract(sa.inspect(db), table),
                    db.scalar(sa.text(f'SELECT count(*) FROM public."{table}"')),
                )
        engine.dispose()
        approved = json.loads(
            (ROOT / "tmp/local-reconciliation-3830d7929ed9bb2f.json").read_text()
        )
        require(
            approved["status"] == "COPY_ONLY_PASSED"
            and approved["copy_upgrade"].get(
                "late_failure_full_transaction_rollback_verified"
            )
            is True,
            "approved_atomic_rehearsal_missing",
        )
        expected_operations = approved["copy_upgrade"]["operations"]
        require(exact_plan(expected_operations), "approved_repair_plan_mismatch")
        stage = "maintenance_enable_and_verify"
        require(
            maintenance("maintenance-on").get("maintenance") is True,
            "maintenance_enable_failed",
        )
        marker_owned = True
        # Prove the running API sees the same canonical marker without credentials.
        request = urllib.request.Request(
            "http://127.0.0.1:8000/api/v1/auth/login",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=15).close()
            raise safe.SafeFailure("maintenance_gate_did_not_block")
        except urllib.error.HTTPError as error:
            require(
                error.code == 503
                and json.load(error).get("code") == "maintenance_mode",
                "maintenance_gate_not_verified",
            )
        stage = "exact_api_tree_pause"
        pause_armed = True
        report["api_pause"] = process_action("Pause")
        stage = "fresh_encrypted_backup_restore_copy_and_rollback_proof"
        backup_result = {}
        preservation = {}
        backup_exit = safe.main(
            Path(r"C:\vayujit-os db encr bkp"),
            checked_reconciliation=True,
            quiesced_witness=witness,
            result_sink=backup_result,
            preservation_sink=preservation,
        )
        report["fresh_backup_result"] = {
            k: backup_result.get(k)
            for k in (
                "token",
                "status",
                "failure_stage",
                "failure_code",
                "native_exit_code",
                "cleanup",
            )
        }
        persist()
        require(backup_exit == 0, "fresh_backup_rehearsal_not_passed")
        require(
            backup_result.get("status") == "PASS" and preservation,
            "fresh_preservation_missing",
        )
        require(
            backup_result["checked_copy_upgrade"]["operations"] == expected_operations,
            "fresh_copy_repair_differs_from_approved_plan",
        )
        report["fresh_backup"] = {
            k: backup_result[k]
            for k in (
                "token",
                "backup_directory",
                "recovery_key_file",
                "status",
                "backup_restore",
                "migration_rehearsal",
                "database_ciphertext_sha256",
                "media_file_count",
            )
        }
        state = {"token": token, "database_oid": db_oid, "preservation": preservation}
        state_path = private / "source-state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        persist()
        stage = "atomic_source_reconciliation_and_upgrade"
        engine = source_engine()
        with engine.begin() as db:
            require(
                db.scalar(
                    sa.text(
                        "SELECT count(*) FROM pg_stat_activity WHERE "
                        "datname=current_database() AND pid<>pg_backend_pid()"
                    )
                )
                == 0,
                "unexpected_source_database_session",
            )
            require(
                db.scalar(sa.text("SELECT pg_try_advisory_xact_lock(762021, 16031)"))
                is True,
                "source_migration_already_active",
            )
            verify_records(db, state, migrated=False)
            config = Config(str(ROOT / "apps/api/alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
            script = ScriptDirectory.from_config(config)
            operations, adopted, count = repair.upgrade_connection(
                db, repair.expected_contracts(), config, script
            )
            require(
                operations == expected_operations
                and exact_plan(operations)
                and count == 16
                and len(adopted) == 3,
                "source_plan_differs_from_approved_rehearsal",
            )
            verify_records(db, state, migrated=True)
            report.update(
                operations=operations,
                adopted=adopted,
                migrations=count,
                all_original_rows_and_precision_preserved_before_commit=True,
            )
        committed = True
        report.update(
            source_database_modified=True,
            source_transaction_committed=True,
            current_revision=repair.HEAD,
        )
        persist()
        engine.dispose()
        stage = "fresh_source_process_verification"
        verified = json.loads(
            safe.checked(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--verify-only",
                    str(state_path),
                ],
                env=process_env,
            )
        )
        require(
            verified.get("status") == "FRESH_SOURCE_PROCESS_VERIFIED",
            "fresh_source_verify_failed",
        )
        report["fresh_process"] = verified
        report["status"] = "SOURCE_MIGRATED_VERIFIED"
    except Exception as error:  # noqa: BLE001 - never expose SQL/native exceptions
        report.update(
            status="FAIL",
            failure_stage=stage,
            failure_code=getattr(error, "code", "source_migration_operation_failed"),
            exception_type=type(error).__name__,
            native_exit_code=getattr(error, "exit_code", None),
        )
    finally:
        if engine is not None:
            engine.dispose()
        if pause_armed:
            try:
                process_env["VAYUJIT_EXPECTED_MIGRATION_REVISION"] = (
                    repair.HEAD if committed else cfg.expected_migration_revision
                )
                report["recovery"]["api_resume"] = process_action("Resume")
                for _ in range(50):
                    try:
                        with urllib.request.urlopen(
                            "http://127.0.0.1:8000/health/ready", timeout=5
                        ) as response:
                            health = json.load(response)
                        if health.get("current_migration") == (
                            repair.HEAD if committed else repair.LEGACY
                        ):
                            break
                    except (OSError, ValueError):
                        time.sleep(0.5)
                else:
                    raise safe.SafeFailure("api_recovery_health_timeout")
                report["recovery"]["api_health"] = {
                    "current_migration": health["current_migration"],
                    "expected_migration": health.get("expected_migration"),
                }
                require(
                    not committed or health.get("expected_migration") == repair.HEAD,
                    "api_expected_revision_not_aligned",
                )
                # On post-commit verification failure, keep writes blocked for review.
                require(
                    not committed or report["status"] == "SOURCE_MIGRATED_VERIFIED",
                    "post_commit_failure_keep_maintenance",
                )
                if marker_owned:
                    require(
                        maintenance("maintenance-off").get("maintenance") is False,
                        "maintenance_restore_failed",
                    )
                    marker_owned = False
                    report["recovery"]["maintenance"] = "RESTORED_OFF"
            # Recovery failures must not replace the original operation failure.
            except Exception as error:  # noqa: BLE001
                report["recovery"]["failure"] = getattr(
                    error, "code", "api_recovery_failed"
                )
                report["status"] = "FAIL"
        elif marker_owned:
            try:
                require(
                    maintenance("maintenance-off").get("maintenance") is False,
                    "maintenance_restore_failed",
                )
                marker_owned = False
            except Exception:  # noqa: BLE001 - preserve marker if recovery is uncertain
                report["recovery"]["failure"] = "maintenance_restore_failed"
        report["maintenance_marker_retained"] = marker_owned
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        # Retain protected recovery state if source committed or recovery needs review.
        report["protected_state_retained"] = str(private) if private else None
        persist()
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "token": token,
                    "source_transaction_committed": committed,
                    "failure_stage": report.get("failure_stage"),
                    "report": str(report_path),
                }
            )
        )
    return 0 if report["status"] == "SOURCE_MIGRATED_VERIFIED" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--confirm-exact-approved-source-upgrade", action="store_true")
    group.add_argument("--verify-only", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.verify_only:
            fresh_verify(arguments.verify_only)
        else:
            raise SystemExit(main())
    # Redact errors before any native/SQL details reach the console.
    except Exception as error:  # noqa: BLE001
        print(json.dumps({"status": "BLOCKED", "exception_type": type(error).__name__}))
        raise SystemExit(1) from None
