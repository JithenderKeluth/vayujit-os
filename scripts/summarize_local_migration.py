"""Summarize actual backup checks without changing the original failed run record."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "c2bd95c186adede5"


def main():
    original = ROOT / f"tmp/local-migration-rehearsal-{TOKEN}.json"
    raw = original.read_bytes()
    run = json.loads(raw)
    required = {
        "source_readonly_transaction",
        "key_and_staging_acl_verified",
        "ciphertext_header_verified",
        "configuration_recovery_material_encrypted_and_verified",
        "database_decryption_hash_matches",
        "wrong_key_rejected",
        "corrupted_ciphertext_rejected",
        "all_original_tables_and_decimal_values_restored",
        "restored_revision_matches",
        "restored_single_owner_constraint",
        "independent_media_restore_verified",
    }
    assert required.issubset(run["checks"])
    assert run["token"] == TOKEN and run["source_database_modified"] is False
    assert run["cleanup"]["plaintext_stage"] == "REMOVED"
    backup = Path(run["backup_directory"])
    assert backup == Path(r"C:\vayujit-os db encr bkp") / ("migration-" + TOKEN)
    assert (backup / "migration-run.marker").read_text() == TOKEN
    spec = importlib.util.spec_from_file_location(
        "rehearsal", ROOT / "scripts/local_migration_rehearsal.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.no_reparse(backup)
    artifacts = []
    for name in (
        "database.dump.age",
        "media.zip.age",
        "media.json.age",
        "recovery-configuration.json.age",
    ):
        file = backup / name
        assert file.stat().st_size > 22
        with file.open("rb") as stream:
            assert stream.read(21) == b"age-encryption.org/v1"
        artifacts.append(
            {
                "name": name,
                "bytes": file.stat().st_size,
                "sha256": helper.file_hash(file),
            }
        )
    assert artifacts[0]["sha256"] == run["database_ciphertext_sha256"]
    preflight = json.loads(
        (ROOT / "tmp/local-database-migration-preflight.json").read_text()
    )
    result = {
        "token": TOKEN,
        "derived_from_actual_checks": True,
        "original_report_sha256": hashlib.sha256(raw).hexdigest(),
        "original_overall_status": run["status"],
        "backup_restore": "VERIFIED",
        "migration_rehearsal": "BLOCKED_DUPLICATE_SCHEMA_OBJECTS",
        "source_migration": "NOT_RUN",
        "source_database_modified_by_rehearsal": False,
        "source_revision_after_readonly_recheck": preflight["database_revision"],
        "backup_directory": str(backup),
        "recovery_key_file": run["recovery_key_file"],
        "media_tree_files_restored_and_checksum_verified": run["media_file_count"],
        "all_original_table_rows_and_financial_values_restored": True,
        "wrong_key_rejected": True,
        "corrupted_ciphertext_rejected": True,
        "private_plaintext_stage_removed": True,
        "cleanup": run["cleanup"],
        "destination_independence": "UNVERIFIED_LOCAL_PC_NOT_OFF_DEVICE",
        "recovery_key_custody": "OWNER_OFFLINE_COPY_REQUIRED",
        "migration_failure_stage": run["failure_stage"],
        "migration_failure_code": run["failure_code"],
        "pending_create_collisions": preflight["pending_create_collisions"],
        "duration_seconds": run["duration_seconds"],
        "per_stage_durations": "NOT_RECORDED_IN_THIS_RUN",
        "fresh_source_row_comparison_after_rehearsal": "NOT_EXECUTED_AFTER_EARLY_MIGRATION_FAILURE",
        "artifacts": artifacts,
    }
    for target in (
        ROOT / f"tmp/local-migration-backup-verification-{TOKEN}.json",
        backup / "backup-verification-summary.json",
    ):
        with target.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
    print(
        json.dumps(
            {
                "backup_restore": result["backup_restore"],
                "migration_rehearsal": result["migration_rehearsal"],
                "source_migration": result["source_migration"],
                "encrypted_artifacts": len(artifacts),
            }
        )
    )


if __name__ == "__main__":
    main()
