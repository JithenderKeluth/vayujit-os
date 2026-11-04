"""Explicitly approved local encrypted backup/isolated restore; NEVER migrates source.

No QA instance, source container lifecycle, source DDL, application authentication,
external provider, permanent-profile initialization or raw-output persistence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
LABEL = "vayujit.local-migration-rehearsal"
SOURCE = "infrastructure-postgres-1"
API_IMAGE = "vayujit-pc-cert-829102f460-api:latest"
RENAMED = {"storyboardversion": "storyboard_version", "styleversion": "style_version"}


class SafeFailure(RuntimeError):
    def __init__(self, code: str, exit_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


def native_failure_code(stderr: bytes) -> str:
    value = stderr.decode("utf-8", errors="replace")
    guard = re.search(r"\bWP6[A-Z]_[A-Z0-9_]+\b", value)
    if guard:
        return guard.group(0)
    for name in (
        "DuplicateTable",
        "UndefinedTable",
        "UndefinedColumn",
        "ForeignKeyViolation",
        "NotNullViolation",
        "UniqueViolation",
        "InsufficientPrivilege",
    ):
        if name in value:
            return "native_" + name
    return "native_operation_failed"


def checked(args, *, env=None, input_data=None, timeout=90):
    result = subprocess.run(
        args,
        input=input_data,
        capture_output=True,
        env=env,
        timeout=timeout,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        # Raw output can contain credentials, SQL or business records. Never emit it.
        raise SafeFailure(native_failure_code(result.stderr), result.returncode)
    return result.stdout


def no_reparse(path: Path) -> None:
    for value in (path, *path.parents):
        if value.exists() and (
            value.is_symlink() or value.stat().st_file_attributes & 0x400
        ):
            raise SafeFailure("reparse_path_denied")


def outside(path: Path, forbidden: list[Path]) -> bool:
    return not any(
        path == other or path.is_relative_to(other) or other.is_relative_to(path)
        for other in forbidden
    )


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def owned_container(meta: dict, token: str, expected_id: str | None) -> bool:
    return bool(
        expected_id
        and meta.get("id") == expected_id
        and meta.get("label", {}).get(LABEL) == token
    )


def fingerprint_sql(table: str, columns: list[str], *, migrated: bool = False) -> str:
    selected = []
    for column in columns:
        actual = (
            RENAMED.get(column, column)
            if migrated and table == "video_generations"
            else column
        )
        selected.append(f"{quote(actual)} AS {quote(column)}")
    return (
        "SELECT jsonb_build_object('rows',count(*),'digest',"
        "md5(coalesce(string_agg(md5(to_jsonb(r)::text),'' ORDER BY md5(to_jsonb(r)::text)),''))) "
        f"FROM (SELECT {','.join(selected)} FROM public.{quote(table)}) r"
    )


def transfer(
    source_args,
    target_args,
    *,
    env=None,
    output_file=None,
    timeout=180,
    classify_failures=False,
):
    """Binary-safe pipeline with drained/discarded stderr and bounded owned clients."""
    processes = []
    readers = []
    timed_out = threading.Event()
    diagnostics = []
    digest = hashlib.sha256()
    size = 0

    def drain(stream, diagnostic):
        while block := stream.read(65536):
            if classify_failures and len(diagnostic) < 65536:
                diagnostic.extend(block[: 65536 - len(diagnostic)])

    def expire():
        timed_out.set()
        for process in processes:
            if process.poll() is None:
                process.kill()  # Only the exact native clients this call created.

    timer = threading.Timer(timeout, expire)
    try:
        producer = subprocess.Popen(
            source_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes.append(producer)
        consumer = None
        if target_args:
            consumer = subprocess.Popen(
                target_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            processes.append(consumer)
        for process in processes:
            diagnostic = bytearray()
            diagnostics.append(diagnostic)
            thread = threading.Thread(
                target=drain, args=(process.stderr, diagnostic), daemon=True
            )
            thread.start()
            readers.append(thread)
        timer.start()
        target = consumer.stdin if consumer else output_file
        while block := producer.stdout.read(1024 * 1024):
            digest.update(block)
            size += len(block)
            if target is not None:
                target.write(block)
        if consumer:
            consumer.stdin.close()
        for process in processes:
            process.wait(timeout=timeout)
        for thread in readers:
            thread.join(timeout=5)
        if timed_out.is_set():
            raise SafeFailure("binary_transfer_timeout")
        for index, process in enumerate(processes):
            if process.returncode:
                code = "binary_transfer_failed"
                if classify_failures:
                    code = binary_failure_code(index, bytes(diagnostics[index]))
                raise SafeFailure(code, process.returncode)
        return {"bytes": size, "sha256": digest.hexdigest()}
    finally:
        timer.cancel()
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def binary_failure_code(index: int, diagnostic: bytes) -> str:
    """Allowlisted classifications only; never return native output or paths."""
    if index == 0:
        return "binary_producer_failed"
    if re.search(rb"database [^\r\n]{0,200} does not exist", diagnostic):
        return "restore_database_unavailable"
    if (
        b"server closed the connection" in diagnostic
        or b"Connection refused" in diagnostic
    ):
        return "restore_connection_unavailable"
    if b"unsupported version" in diagnostic:
        return "restore_dump_version_unsupported"
    return "binary_consumer_failed"


def main(
    destination: Path,
    *,
    checked_reconciliation=False,
    quiesced_witness=None,
    result_sink=None,
    preservation_sink=None,
) -> int:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool
    from vayujit_api.core.config import Settings
    from vayujit_api.operations.media_backup import (
        create_media_backup,
        restore_media_backup,
    )

    token = secrets.token_hex(8)
    container = "vayujit-migration-restore-" + token
    volume = container
    runner = "vayujit-migration-runner-" + token
    report = {
        "token": token,
        "status": "RUNNING",
        "source_database_modified": False,
        "source_migration": "NOT_RUN",
        "raw_output_persisted": False,
        "destination_independence": "UNVERIFIED_LOCAL_PC",
        "checks": [],
        "cleanup": {},
        "key_custody": "LOCAL_PROTECTED_OFFLINE_COPY_REQUIRED",
    }
    report_path = ROOT / f"tmp/local-migration-rehearsal-{token}.json"
    stage = "target_preflight"
    started = time.monotonic()
    private = None
    container_id = None
    runner_id = None
    volume_created = False
    engine = None
    docker = shutil.which("docker")
    age = shutil.which("age")

    def persist():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if private:
            (Path(private["backup"]) / "verification.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )

    def require(value, code):
        if not value:
            raise SafeFailure(code)
        report["checks"].append(code)

    def docker_json(kind, name, template):
        return json.loads(
            checked([docker, kind, "inspect", "--format", template, name])
        )

    def restored(sql):
        return json.loads(
            checked(
                [
                    docker,
                    "exec",
                    "-e",
                    "PGOPTIONS=-c TimeZone=UTC",
                    container_id,
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
        )

    try:
        require(bool(docker and age), "tools_available")
        spec = importlib.util.spec_from_file_location(
            "migration_preflight", ROOT / "scripts/preflight-local-database.py"
        )
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)
        witness = quiesced_witness or preflight.run()
        if quiesced_witness is not None:
            with socket.socket() as probe:
                probe.settimeout(2)
                require(
                    probe.connect_ex(("127.0.0.1", 8000)) != 0,
                    "quiesced_api_port_absent",
                )
        require(
            witness["status"] == "READ_ONLY_PREFLIGHT_COMPLETE",
            "exact_source_revalidated",
        )
        require(
            witness["owner_rows"] == 1 and witness["single_owner_constraint_present"],
            "owner_constraint_confirmed",
        )
        cfg = Settings()
        url = make_url(cfg.database_url)
        require(
            preflight.allowed_target(url.host, url.port, url.database),
            "source_url_pinned",
        )
        info = json.loads(
            checked(
                [
                    docker,
                    "inspect",
                    "--format",
                    '{"id":{{json .Id}},"image":{{json .Image}},"mounts":{{json .Mounts}},"ports":{{json .NetworkSettings.Ports}},"started":{{json .State.StartedAt}}}',
                    SOURCE,
                ]
            )
        )
        require(
            info["id"].startswith("9082e894b5af"), "source_container_identity_matches"
        )
        qa_before = json.loads(
            checked(
                [
                    docker,
                    "inspect",
                    "--format",
                    '{"id":{{json .Id}},"started":{{json .State.StartedAt}}}',
                    "vayujit-qa-postgres",
                ]
            )
        )
        require(
            info["ports"].get("5432/tcp")
            == [{"HostIp": "127.0.0.1", "HostPort": "5432"}],
            "source_loopback_binding_matches",
        )
        image_id = json.loads(
            checked([docker, "image", "inspect", "--format", "{{json .Id}}", API_IMAGE])
        )
        media_candidates = list(
            {
                (base / cfg.media_storage_directory).resolve()
                for base in (ROOT, ROOT / "apps/api")
            }
        )
        destination = destination.absolute()
        no_reparse(destination)
        forbidden = [
            ROOT,
            *media_candidates,
            Path(os.environ["LOCALAPPDATA"]) / "Docker",
        ]
        forbidden += [
            Path(m["Source"]).resolve()
            for m in info["mounts"]
            if re.match(r"^[A-Za-z]:", m["Source"])
        ]
        require(
            destination.is_dir() and outside(destination.resolve(), forbidden),
            "destination_separated_from_source_storage",
        )
        engine = create_engine(
            url,
            poolclass=NullPool,
            isolation_level="REPEATABLE READ",
            connect_args={
                "options": "-c default_transaction_read_only=on -c statement_timeout=60000 -c TimeZone=UTC",
                "application_name": "vayujit_authorized_encrypted_backup_readonly",
            },
        )
        with engine.connect() as source:
            require(
                source.scalar(text("SHOW transaction_read_only")) == "on",
                "source_readonly_transaction",
            )
            require(
                list(source.scalars(text("SELECT version_num FROM alembic_version")))
                == witness["database_revision"],
                "source_revision_revalidated",
            )
            if quiesced_witness is not None:
                require(
                    source.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE "
                            "datname=current_database() AND pid<>pg_backend_pid()"
                        )
                    )
                    == 0,
                    "source_has_no_other_database_sessions",
                )
            size = source.scalar(text("SELECT pg_database_size(current_database())"))
            require(
                shutil.disk_usage(destination).free > max(size * 5, 2 * 1024**3),
                "destination_free_space_sufficient",
            )
            stage = "private_paths_and_key"
            private = json.loads(
                checked(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(ROOT / "scripts/local-migration-private.ps1"),
                        "-Action",
                        "Prepare",
                        "-Token",
                        token,
                        "-Destination",
                        str(destination),
                    ]
                )
            )
            work = Path(private["stage"])
            backup = Path(private["backup"])
            require(
                private["acl"] == "owner_and_SYSTEM_only",
                "key_and_staging_acl_verified",
            )
            probe = backup / "writable.probe"
            with probe.open("xb") as stream:
                stream.write(b"probe")
            probe.unlink()
            report.update(
                backup_directory=str(backup),
                recovery_key_file=private["identity"],
                source_container_id=info["id"],
                source_revision=witness["database_revision"],
                target_revision=witness["repository_heads"],
                backup_directory_writable=True,
            )
            persist()
            stage = "source_snapshot"
            schema = inspect(source)
            tables = sorted(schema.get_table_names())
            contract = {
                table: [c["name"] for c in schema.get_columns(table)]
                for table in tables
            }
            fingerprints = {
                table: source.scalar(text(fingerprint_sql(table, cols)))
                for table, cols in contract.items()
            }
            snapshot = source.scalar(text("SELECT pg_export_snapshot()"))
            media = list(
                source.execute(
                    text(
                        "SELECT storage_key,checksum_sha256,size_bytes FROM media_assets"
                    )
                ).mappings()
            )
            roots = [
                candidate
                for candidate in media_candidates
                if candidate.is_dir()
                and all(
                    (candidate / r["storage_key"]).is_file()
                    and (candidate / r["storage_key"]).stat().st_size == r["size_bytes"]
                    for r in media
                )
            ]
            if not media and not roots:
                empty = work / "empty-media"
                empty.mkdir()
                roots = [empty]
            require(len(roots) == 1, "media_source_unambiguous")
            media_root = roots[0]
            for row in media:
                path = (media_root / row["storage_key"]).resolve()
                require(
                    path.is_relative_to(media_root) and not path.is_symlink(),
                    "media_path_scoped",
                )
                require(
                    file_hash(path) == row["checksum_sha256"],
                    "source_media_checksum_matches",
                )
            stage = "encrypted_database_backup"
            encrypted_db = backup / "database.dump.age"
            client_env = os.environ.copy()
            client_env["PGPASSWORD"] = url.password or ""
            client_env["PGOPTIONS"] = "-c default_transaction_read_only=on"
            dump = [
                docker,
                "exec",
                "-e",
                "PGPASSWORD",
                "-e",
                "PGOPTIONS",
                info["id"],
                "pg_dump",
                "-h",
                "127.0.0.1",
                "-U",
                url.username,
                "-d",
                url.database,
                "-Fc",
                "--no-owner",
                "--no-privileges",
                "--lock-wait-timeout=10000",
                "--snapshot=" + snapshot,
            ]
            plain = transfer(
                dump,
                [age, "--encrypt", "-r", private["recipient"], "-o", str(encrypted_db)],
                env=client_env,
            )
            require(plain["bytes"] > 5, "nonempty_database_backup")
            with encrypted_db.open("rb") as stream:
                require(
                    stream.read(21).startswith(b"age-encryption.org/v1"),
                    "ciphertext_header_verified",
                )
            report["database_ciphertext_sha256"] = file_hash(encrypted_db)
            recovery_config = json.dumps(
                {
                    name: getattr(cfg, name)
                    for name in (
                        "credential_encryption_key",
                        "credential_encryption_key_id",
                        "credential_encryption_previous_keys",
                        "session_secret",
                    )
                }
            ).encode()
            checked(
                [
                    age,
                    "--encrypt",
                    "-r",
                    private["recipient"],
                    "-o",
                    str(backup / "recovery-configuration.json.age"),
                ],
                input_data=recovery_config,
            )
            config_roundtrip = checked(
                [
                    age,
                    "--decrypt",
                    "-i",
                    private["identity"],
                    str(backup / "recovery-configuration.json.age"),
                ]
            )
            require(
                hashlib.sha256(config_roundtrip).digest()
                == hashlib.sha256(recovery_config).digest(),
                "configuration_recovery_material_encrypted_and_verified",
            )
            del recovery_config, config_roundtrip
            stage = "encrypted_media_backup"
            archive, manifest = create_media_backup(
                media_root,
                work,
                lineage={"migration_run": token, "source": "existing_local_database"},
            )
            report["media_file_count"] = len(json.loads(manifest.read_text())["files"])
            for original, filename in (
                (archive, "media.zip.age"),
                (manifest, "media.json.age"),
            ):
                checked(
                    [
                        age,
                        "--encrypt",
                        "-r",
                        private["recipient"],
                        "-o",
                        str(backup / filename),
                        str(original),
                    ]
                )
            require(
                transfer(
                    [age, "--decrypt", "-i", private["identity"], str(encrypted_db)],
                    None,
                )
                == plain,
                "database_decryption_hash_matches",
            )
            stage = "negative_decryption_tests"
            wrong = subprocess.run(
                [age, "--decrypt", "-i", private["wrong"], str(encrypted_db)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            require(wrong.returncode != 0, "wrong_key_rejected")
            corrupt = work / "corrupt.age"
            shutil.copyfile(encrypted_db, corrupt)
            with corrupt.open("r+b") as stream:
                stream.seek(-1, 2)
                value = stream.read(1)[0]
                stream.seek(-1, 2)
                stream.write(bytes([value ^ 1]))
            bad = subprocess.run(
                [age, "--decrypt", "-i", private["identity"], str(corrupt)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            require(bad.returncode != 0, "corrupted_ciphertext_rejected")
            stage = "isolated_restore_creation"
            for kind in ("container", "volume"):
                found = subprocess.run(
                    [docker, kind, "inspect", volume],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                require(found.returncode != 0, "restore_name_unused_" + kind)
            checked([docker, "volume", "create", "--label", f"{LABEL}={token}", volume])
            volume_created = True
            restore_password = secrets.token_hex(32)
            env = os.environ.copy()
            env["POSTGRES_PASSWORD"] = restore_password
            container_id = (
                checked(
                    [
                        docker,
                        "run",
                        "--detach",
                        "--pull=never",
                        "--name",
                        container,
                        "--label",
                        f"{LABEL}={token}",
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
                        info["image"],
                    ],
                    env=env,
                )
                .decode()
                .strip()
            )
            isolated = json.loads(
                checked(
                    [
                        docker,
                        "inspect",
                        "--format",
                        '{"network":{{json .HostConfig.NetworkMode}},"ports":{{json .HostConfig.PortBindings}}}',
                        container_id,
                    ]
                )
            )
            require(
                isolated["network"] == "none" and not isolated["ports"],
                "restore_has_no_network_or_ports",
            )
            for _ in range(40):
                ready = subprocess.run(
                    [
                        docker,
                        "exec",
                        container_id,
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
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if ready.returncode == 0:
                    break
                time.sleep(0.5)
            require(ready.returncode == 0, "isolated_postgres_ready")
            stage = "database_restore"
            decrypt = [age, "--decrypt", "-i", private["identity"], str(encrypted_db)]
            transfer(
                decrypt, [docker, "exec", "-i", container_id, "pg_restore", "--list"]
            )
            transfer(
                decrypt,
                [
                    docker,
                    "exec",
                    "-i",
                    container_id,
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
            )
            require(
                all(
                    restored(fingerprint_sql(t, cols)) == fingerprints[t]
                    for t, cols in contract.items()
                ),
                "all_original_tables_and_decimal_values_restored",
            )
            require(
                restored("SELECT to_jsonb(version_num) FROM alembic_version")
                in witness["database_revision"],
                "restored_revision_matches",
            )
            require(
                restored(
                    "SELECT to_jsonb(count(*)) FROM pg_constraint WHERE conname='ck_users_single_owner'"
                )
                == 1,
                "restored_single_owner_constraint",
            )
            stage = "media_restore"
            for filename, target in (
                ("media.zip.age", "verified-media.zip"),
                ("media.json.age", "verified-media.json"),
            ):
                checked(
                    [
                        age,
                        "--decrypt",
                        "-i",
                        private["identity"],
                        "-o",
                        str(work / target),
                        str(backup / filename),
                    ]
                )
            media_result = restore_media_backup(
                work / "verified-media.zip",
                work / "verified-media.json",
                work / "restored-media",
            )
            require(
                media_result["files"] == report["media_file_count"],
                "independent_media_restore_verified",
            )
            stage = "copy_only_migration_rehearsal"
            # No original credentials or inherited real-provider configuration enter this runner.
            clean_env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("VAYUJIT_")
                and k not in {"OPENAI_API_KEY", "PGPASSWORD"}
            }
            clean_env["VAYUJIT_DATABASE_URL"] = (
                f"postgresql+psycopg://postgres:{restore_password}@127.0.0.1:5432/vayujit_restore"
            )
            command = (
                "from vayujit_api.core.config import Settings; Settings.model_config['env_file']=None;"
                "from alembic.config import Config; from alembic import command;"
                "c=Config('/app/alembic.ini'); c.set_main_option('script_location','/app/alembic'); command.upgrade(c,'head')"
            )
            additional = []
            if checked_reconciliation:
                checked(
                    [
                        docker,
                        "exec",
                        container_id,
                        "psql",
                        "-X",
                        "-U",
                        "postgres",
                        "-d",
                        "vayujit_restore",
                        "-v",
                        "ON_ERROR_STOP=1",
                        "-c",
                        f"COMMENT ON DATABASE vayujit_restore IS 'vayujit-copy-reconcile:{token}'",
                    ]
                )
                command = (
                    "import sys,runpy; sys.path.insert(0,'/tools');"
                    "runpy.run_path('/tools/local_reconciliation_copy.py',run_name='__main__')"
                )
                clean_env["LOCAL_RECON_COPY_TOKEN"] = token
                additional = [
                    "--mount",
                    f"type=bind,source={ROOT / 'scripts'},target=/tools,readonly",
                    "--mount",
                    f"type=bind,source={work},target=/private",
                    "-e",
                    "LOCAL_RECON_COPY_TOKEN",
                ]
            unused = subprocess.run(
                [docker, "container", "inspect", runner],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            require(unused.returncode != 0, "migration_runner_name_unused")
            runner_id = (
                checked(
                    [
                        docker,
                        "create",
                        "--pull=never",
                        "--name",
                        runner,
                        "--label",
                        f"{LABEL}={token}",
                        "--network",
                        "container:" + container_id,
                        "--no-healthcheck",
                        "--entrypoint",
                        "python",
                        "--workdir",
                        "/app",
                        "--mount",
                        f"type=bind,source={ROOT / 'apps/api/vayujit_api'},target=/app/vayujit_api,readonly",
                        "--mount",
                        f"type=bind,source={ROOT / 'apps/api/alembic'},target=/app/alembic,readonly",
                        "--mount",
                        f"type=bind,source={ROOT / 'apps/api/alembic.ini'},target=/app/alembic.ini,readonly",
                        "-e",
                        "VAYUJIT_DATABASE_URL",
                        "-e",
                        "VAYUJIT_ENVIRONMENT=test",
                        "-e",
                        "VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP=true",
                        "-e",
                        "VAYUJIT_LIVE_MUTATIONS_ENABLED=false",
                        *additional,
                        image_id,
                        "-c",
                        command,
                    ],
                    env=clean_env,
                )
                .decode()
                .strip()
            )
            child_output = checked(
                [docker, "start", "--attach", runner_id], timeout=240
            )
            if checked_reconciliation:
                child = json.loads(child_output)
                require(
                    child.get("status") == "COPY_UPGRADE_PASSED"
                    and child.get("late_failure_full_transaction_rollback_verified")
                    is True,
                    "atomic_copy_upgrade_and_rollback_proof_passed",
                )
                report["checked_copy_upgrade"] = child
            exit_code = json.loads(
                checked(
                    [
                        docker,
                        "inspect",
                        "--format",
                        "{{json .State.ExitCode}}",
                        runner_id,
                    ]
                )
            )
            require(exit_code == 0, "migration_runner_exit_successful")
            require(
                restored("SELECT to_jsonb(version_num) FROM alembic_version")
                in witness["repository_heads"],
                "copy_migrated_to_exact_head",
            )
            require(
                all(
                    restored(fingerprint_sql(t, cols, migrated=True)) == fingerprints[t]
                    for t, cols in contract.items()
                    if t != "alembic_version"
                ),
                "copy_migration_preserved_all_original_rows_and_precision",
            )
            require(
                restored("SELECT to_jsonb(count(*)) FROM users") == 1
                and restored(
                    "SELECT to_jsonb(count(*)) FROM pg_constraint WHERE conname='ck_users_single_owner'"
                )
                == 1,
                "migrated_copy_single_owner_intact",
            )
            require(
                all(
                    source.scalar(text(fingerprint_sql(t, cols))) == fingerprints[t]
                    for t, cols in contract.items()
                ),
                "source_snapshot_unchanged",
            )
            source.rollback()
        stage = "fresh_source_comparison"
        with engine.connect() as fresh:
            changes = [
                t
                for t, cols in contract.items()
                if fresh.scalar(text(fingerprint_sql(t, cols))) != fingerprints[t]
            ]
            report["source_concurrently_changed_tables"] = changes
            require(not changes, "fresh_source_unchanged_since_backup")
            fresh.rollback()
        source_after = json.loads(
            checked(
                [
                    docker,
                    "inspect",
                    "--format",
                    '{"id":{{json .Id}},"started":{{json .State.StartedAt}}}',
                    SOURCE,
                ]
            )
        )
        qa_after = json.loads(
            checked(
                [
                    docker,
                    "inspect",
                    "--format",
                    '{"id":{{json .Id}},"started":{{json .State.StartedAt}}}',
                    "vayujit-qa-postgres",
                ]
            )
        )
        require(
            source_after == {"id": info["id"], "started": info["started"]}
            and qa_after == qa_before,
            "source_and_qa_container_identity_and_start_time_unchanged",
        )
        report.update(
            status="PASS",
            backup_restore="VERIFIED",
            migration_rehearsal="COPY_ONLY_PASSED",
            original_table_count=len(contract),
            original_row_count=sum(r["rows"] for r in fingerprints.values()),
        )
        if preservation_sink is not None:
            preservation_sink.update(columns=contract, fingerprints=fingerprints)
    # Redact sensitive native/SQL exceptions at this reporting boundary.
    except Exception as error:  # noqa: BLE001
        report.update(
            status="FAIL",
            failure_stage=stage,
            failure_code=getattr(error, "code", "rehearsal_exception"),
            native_exit_code=getattr(error, "exit_code", None),
            exception_type=type(error).__name__,
        )
    finally:
        if report["status"] == "RUNNING":
            report.update(status="FAIL", failure_code="rehearsal_incomplete")
        required_backup_checks = {
            "nonempty_database_backup",
            "ciphertext_header_verified",
            "database_decryption_hash_matches",
            "wrong_key_rejected",
            "corrupted_ciphertext_rejected",
            "all_original_tables_and_decimal_values_restored",
            "restored_revision_matches",
            "restored_single_owner_constraint",
            "independent_media_restore_verified",
            "configuration_recovery_material_encrypted_and_verified",
        }
        report["backup_restore"] = (
            "VERIFIED"
            if required_backup_checks.issubset(report["checks"])
            else "NOT_VERIFIED"
        )
        report["migration_rehearsal"] = (
            "COPY_ONLY_PASSED" if report["status"] == "PASS" else "NOT_PASSED"
        )
        if engine is not None:
            engine.dispose()
        for name, expected_id in ((runner, runner_id), (container, container_id)):
            if expected_id is None:
                report["cleanup"][name] = "NOT_CREATED"
                continue
            try:
                raw = subprocess.run(
                    [
                        docker,
                        "inspect",
                        "--format",
                        '{"id":{{json .Id}},"label":{{json .Config.Labels}}}',
                        name,
                    ],
                    capture_output=True,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if raw.returncode == 0:
                    meta = json.loads(raw.stdout)
                    if not owned_container(meta, token, expected_id):
                        raise SafeFailure("cleanup_container_identity_mismatch")
                    checked([docker, "rm", "--force", meta["id"]])
                remains = checked(
                    [
                        docker,
                        "container",
                        "ls",
                        "--all",
                        "--quiet",
                        "--filter",
                        "id=" + expected_id,
                    ]
                )
                require(not remains.strip(), "temporary_container_absent")
                report["cleanup"][name] = "ABSENT"
            # Preserve the first failure while reporting cleanup separately.
            except Exception:  # noqa: BLE001
                report["cleanup"][name] = "FAILED"
        if volume_created:
            try:
                meta = docker_json("volume", volume, "{{json .Labels}}")
                if meta.get(LABEL) != token:
                    raise SafeFailure("cleanup_volume_identity_mismatch")
                checked([docker, "volume", "rm", volume])
                remaining = (
                    checked([docker, "volume", "ls", "--quiet"]).decode().splitlines()
                )
                require(volume not in remaining, "temporary_volume_absent")
                report["cleanup"][volume + "-volume"] = "ABSENT"
            except Exception:  # noqa: BLE001 - never remove an unverified resource
                report["cleanup"][volume + "-volume"] = "FAILED"
        if private:
            work = Path(private["stage"])
            expected = (
                Path(os.environ["LOCALAPPDATA"]) / "VAYUJIT OS/migration-stage" / token
            )
            try:
                require(
                    work.resolve() == expected.resolve()
                    and (work / "migration-run.marker").read_text() == token,
                    "private_stage_cleanup_scoped",
                )
                no_reparse(work)
                shutil.rmtree(work)
                report["cleanup"]["plaintext_stage"] = "REMOVED"
                Path(private["wrong"]).unlink(missing_ok=True)
            # Preserve private data when cleanup cannot be verified safely.
            except Exception:  # noqa: BLE001
                report["cleanup"]["plaintext_stage"] = "FAILED"
        if "FAILED" in report["cleanup"].values():
            report["status"] = "FAIL"
            report["cleanup_failure"] = True
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        persist()
        if result_sink is not None:
            result_sink.update(report)
        print(
            json.dumps(
                {
                    "token": token,
                    "status": report["status"],
                    "stage": report.get("failure_stage"),
                    "failure_code": report.get("failure_code"),
                    "source_database_modified": False,
                    "report": str(report_path),
                }
            )
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--confirm-backup-and-rehearsal", action="store_true", required=True
    )
    args = parser.parse_args()
    raise SystemExit(main(args.destination))
