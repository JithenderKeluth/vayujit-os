"""Rehearse ONLY an isolated restore of the retained, owner-approved ciphertext.

Never opens a source/QA database connection, never changes historical migrations,
never initializes business data. No option exists to migrate the source.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import local_migration_rehearsal as safe

ROOT = Path(__file__).resolve().parents[1]
BACKUP_TOKEN = "c2bd95c186adede5"
BACKUP = Path(r"C:\vayujit-os db encr bkp") / ("migration-" + BACKUP_TOKEN)


def main():
    token = secrets.token_hex(8)
    name = "vayujit-copy-reconcile-" + token
    volume = name
    report_path = ROOT / f"tmp/local-reconciliation-{token}.json"
    report = {
        "token": token,
        "backup_token": BACKUP_TOKEN,
        "status": "RUNNING",
        "source_database_modified": False,
        "source_migration": "NOT_RUN",
        "raw_output_persisted": False,
        "checks": [],
        "cleanup": {},
    }
    docker = shutil.which("docker")
    age = shutil.which("age")
    stage = "retained_backup_validation"
    started = time.monotonic()
    containers = {}
    volume_created = False
    private = None

    def persist():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def require(value, code):
        if not value:
            raise safe.SafeFailure(code)
        report["checks"].append(code)

    def inspect(name, template):
        return json.loads(safe.checked([docker, "inspect", "--format", template, name]))

    def psql(sql):
        return safe.checked(
            [
                docker,
                "exec",
                containers[name],
                "psql",
                "-X",
                "-U",
                "postgres",
                "-d",
                "vayujit_restore",
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                sql,
            ]
        )

    def absent(kind, resource):
        result = subprocess.run(
            [docker, kind, "inspect", resource],
            capture_output=True,
            check=False,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        require(result.returncode != 0, "fresh_name_required_" + kind)

    def runner(suffix, verify=False):
        runner_name = name + suffix
        absent("container", runner_name)
        args = [
            docker,
            "create",
            "--pull=never",
            "--name",
            runner_name,
            "--label",
            f"{safe.LABEL}={token}",
            "--network",
            "container:" + containers[name],
            "--no-healthcheck",
            "--security-opt",
            "no-new-privileges=true",
            "--entrypoint",
            "python",
            "--workdir",
            "/app",
        ]
        for source, target in (
            (ROOT / "apps/api/vayujit_api", "/app/vayujit_api"),
            (ROOT / "apps/api/alembic", "/app/alembic"),
            (ROOT / "apps/api/alembic.ini", "/app/alembic.ini"),
            (ROOT / "scripts", "/tools"),
        ):
            args += ["--mount", f"type=bind,source={source},target={target},readonly"]
        args += [
            "--mount",
            f"type=bind,source={private},target=/private",
            "-e",
            "VAYUJIT_DATABASE_URL",
            "-e",
            "LOCAL_RECON_COPY_TOKEN",
            "-e",
            "PYTHONPATH=/app:/tools",
            "-e",
            "VAYUJIT_ENVIRONMENT=test",
            "-e",
            "VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true",
            "-e",
            "VAYUJIT_LIVE_MUTATIONS_ENABLED=false",
            image_id,
            "/tools/local_reconciliation_copy.py",
        ]
        if verify:
            args += ["--verify-only"]
        containers[runner_name] = safe.checked(args, env=runner_env).decode().strip()
        result = subprocess.run(
            [docker, "start", "--attach", containers[runner_name]],
            capture_output=True,
            check=False,
            timeout=240,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Only our child's structured JSON is retained. Never persist raw output.
        try:
            child = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise safe.SafeFailure(
                "copy_child_report_invalid", result.returncode
            ) from None
        require(
            child.get("status")
            in {"COPY_UPGRADE_PASSED", "FRESH_PROCESS_VERIFIED", "FAIL"},
            "copy_child_report_schema_valid",
        )
        report["fresh_process" if verify else "copy_upgrade"] = child
        persist()
        exit_code = inspect(containers[runner_name], "{{json .State.ExitCode}}")
        require(
            result.returncode == 0 and exit_code == 0 and child["status"] != "FAIL",
            "fresh_process_passed" if verify else "copy_upgrade_passed",
        )

    try:
        require(bool(docker and age), "tools_available")
        original = json.loads(
            (ROOT / f"tmp/local-migration-rehearsal-{BACKUP_TOKEN}.json").read_text()
        )
        summary = json.loads((BACKUP / "backup-verification-summary.json").read_text())
        require(
            safe.file_hash(ROOT / f"tmp/local-migration-rehearsal-{BACKUP_TOKEN}.json")
            == summary["original_report_sha256"],
            "original_evidence_hash_matches",
        )
        require(
            summary["backup_restore"] == "VERIFIED"
            and original["source_database_modified"] is False,
            "previous_backup_restore_verified",
        )
        safe.no_reparse(BACKUP)
        require(
            (BACKUP / "migration-run.marker").read_text() == BACKUP_TOKEN,
            "retained_backup_marker_matches",
        )
        require(
            {a["name"] for a in summary["artifacts"]}
            == {
                "database.dump.age",
                "media.zip.age",
                "media.json.age",
                "recovery-configuration.json.age",
            }
            and len(summary["artifacts"]) == 4,
            "complete_artifact_set_required",
        )
        for artifact in summary["artifacts"]:
            require(
                artifact["name"]
                in {
                    "database.dump.age",
                    "media.zip.age",
                    "media.json.age",
                    "recovery-configuration.json.age",
                },
                "artifact_allowlisted",
            )
            require(
                safe.file_hash(BACKUP / artifact["name"]) == artifact["sha256"],
                "retained_ciphertext_hash_matches",
            )
        private_info = json.loads(
            safe.checked(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts/local-migration-private.ps1"),
                    "-Action",
                    "Check",
                    "-Token",
                    BACKUP_TOKEN,
                    "-Destination",
                    str(BACKUP.parent),
                ]
            )
        )
        require(
            private_info["acl"] == "owner_and_SYSTEM_only", "retained_key_acl_verified"
        )
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
        witnesses = {
            n: inspect(n, '{"id":{{json .Id}},"started":{{json .State.StartedAt}}}')
            for n in (safe.SOURCE, "vayujit-qa-postgres")
        }
        require(
            witnesses[safe.SOURCE]["id"] == original["source_container_id"],
            "source_container_witness_unchanged",
        )
        pg_image = inspect(safe.SOURCE, "{{json .Image}}")
        image_id = json.loads(
            safe.checked(
                [docker, "image", "inspect", "--format", "{{json .Id}}", safe.API_IMAGE]
            )
        )
        stage = "isolated_restore_creation"
        absent("container", name)
        absent("volume", volume)
        safe.checked(
            [docker, "volume", "create", "--label", f"{safe.LABEL}={token}", volume]
        )
        volume_created = True
        password = secrets.token_hex(32)
        env = os.environ.copy()
        env["POSTGRES_PASSWORD"] = password
        containers[name] = (
            safe.checked(
                [
                    docker,
                    "run",
                    "--detach",
                    "--pull=never",
                    "--name",
                    name,
                    "--label",
                    f"{safe.LABEL}={token}",
                    "--network",
                    "none",
                    "--no-healthcheck",
                    "--security-opt",
                    "no-new-privileges=true",
                    "--mount",
                    f"type=volume,source={volume},target=/var/lib/postgresql/data",
                    "-e",
                    "POSTGRES_PASSWORD",
                    "-e",
                    "POSTGRES_USER=postgres",
                    "-e",
                    "POSTGRES_DB=vayujit_restore",
                    pg_image,
                ],
                env=env,
            )
            .decode()
            .strip()
        )
        meta = inspect(
            containers[name],
            '{"network":{{json .HostConfig.NetworkMode}},"ports":{{json .HostConfig.PortBindings}}}',
        )
        require(
            meta["network"] == "none" and not meta["ports"],
            "no_network_no_published_ports",
        )
        for _ in range(40):
            ready = subprocess.run(
                [
                    docker,
                    "exec",
                    containers[name],
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    "-d",
                    "vayujit_restore",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        require(ready.returncode == 0, "isolated_postgres_ready")
        stage = "retained_ciphertext_restore"
        safe.transfer(
            [
                age,
                "--decrypt",
                "-i",
                private_info["identity"],
                str(BACKUP / "database.dump.age"),
            ],
            [
                docker,
                "exec",
                "-i",
                containers[name],
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-privileges",
                "-U",
                "postgres",
                "-d",
                "vayujit_restore",
            ],
            classify_failures=True,
        )
        require(
            json.loads(psql("SELECT to_jsonb(version_num) FROM alembic_version"))
            == "20261010_0151",
            "restored_legacy_revision",
        )
        psql(f"COMMENT ON DATABASE vayujit_restore IS 'vayujit-copy-reconcile:{token}'")
        # Only explicitly passed ephemeral values enter the disconnected runner.
        runner_env = os.environ.copy()
        runner_env["VAYUJIT_DATABASE_URL"] = (
            f"postgresql+psycopg://postgres:{password}@127.0.0.1:5432/vayujit_restore"
        )
        runner_env["LOCAL_RECON_COPY_TOKEN"] = token
        stage = "checked_reconciliation_and_sixteen_upgrades"
        runner("-upgrade")
        stage = "fresh_process_preservation_verification"
        runner("-verify", verify=True)
        for resource, before in witnesses.items():
            require(
                inspect(
                    resource, '{"id":{{json .Id}},"started":{{json .State.StartedAt}}}'
                )
                == before,
                "unrelated_runtime_identity_and_start_time_unchanged",
            )
        report["status"] = "COPY_ONLY_PASSED"
    except Exception as error:  # noqa: BLE001 - redact sensitive native/SQL failures
        report.update(
            status="FAIL",
            failure_stage=stage,
            failure_code=getattr(error, "code", "copy_rehearsal_exception"),
            native_exit_code=getattr(error, "exit_code", None),
            exception_type=type(error).__name__,
        )
    finally:
        # Only this run's created ID + marker pair can be removed.
        for resource, expected_id in reversed(list(containers.items())):
            try:
                meta = inspect(
                    resource, '{"id":{{json .Id}},"label":{{json .Config.Labels}}}'
                )
                require(
                    safe.owned_container(meta, token, expected_id),
                    "cleanup_exact_container_verified",
                )
                safe.checked([docker, "rm", "--force", expected_id])
                require(
                    not safe.checked(
                        [docker, "ps", "-aq", "--filter", "id=" + expected_id]
                    ).strip(),
                    "temporary_container_absent",
                )
                report["cleanup"][resource] = "ABSENT"
            # Preserve the original failure; report cleanup independently.
            except Exception:  # noqa: BLE001
                report["cleanup"][resource] = "FAILED"
        if volume_created:
            try:
                labels = json.loads(
                    safe.checked(
                        [
                            docker,
                            "volume",
                            "inspect",
                            "--format",
                            "{{json .Labels}}",
                            volume,
                        ]
                    )
                )
                require(
                    labels.get(safe.LABEL) == token, "cleanup_volume_marker_verified"
                )
                safe.checked([docker, "volume", "rm", volume])
                report["cleanup"][volume + "-volume"] = "REMOVED"
            except Exception:  # noqa: BLE001 - never remove unverified resources
                report["cleanup"][volume + "-volume"] = "FAILED"
        if private is not None:
            try:
                expected = (
                    Path(os.environ["LOCALAPPDATA"])
                    / "VAYUJIT OS/migration-stage"
                    / token
                )
                safe.no_reparse(private)
                require(
                    private.resolve() == expected.resolve()
                    and (private / "migration-run.marker").read_text() == token,
                    "private_stage_cleanup_verified",
                )
                shutil.rmtree(private)
                report["cleanup"]["private_stage"] = "REMOVED"
            except Exception:  # noqa: BLE001 - preserve private data on ambiguity
                report["cleanup"]["private_stage"] = "FAILED"
        if "FAILED" in report["cleanup"].values():
            report["status"] = "FAIL"
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        persist()
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "token": token,
                    "report": str(report_path),
                    "source_database_modified": False,
                    "failure_stage": report.get("failure_stage"),
                }
            )
        )
    return 0 if report["status"] == "COPY_ONLY_PASSED" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-isolated-copy-only", action="store_true", required=True
    )
    parser.parse_args()
    raise SystemExit(main())
