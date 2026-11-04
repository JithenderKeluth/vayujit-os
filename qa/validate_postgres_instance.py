"""WP0A only: bounded migration/API fixture and signed lifecycle certification."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from qa.postgres_instance import (
    CONTAINER,
    HOST_NETWORK,
    NETWORK,
    PRIVATE,
    ROOT,
    VOLUME,
    GuardDenied,
    QaInstance,
    database_name,
)

EVIDENCE = ROOT / "tmp/qa-postgres-evidence"


class QaMigrationConfig(Config):
    """ConfigParser requires literal URL percent signs escaped, not new credentials."""

    def set_main_option(self, name, value):
        super().set_main_option(
            name, value.replace("%", "%%") if name == "sqlalchemy.url" else value
        )


def fixture(token: str) -> dict:
    """Fresh process: explicitly injected disposable settings, no .env or providers."""
    stage = "fixture_identity"
    app_engine = None
    try:
        instance = QaInstance()
        instance.verify_server()
        record = instance.load(token)
        assert record["state"] == "ACTIVE"
        name = database_name(token)
        for key in list(os.environ):
            if key.startswith("VAYUJIT_"):
                del os.environ[key]
        from vayujit_api.core import config

        config.Settings.model_config["env_file"] = None
        for field in config.Settings.model_fields.values():
            alias = field.validation_alias
            for key in (
                [alias] if isinstance(alias, str) else getattr(alias, "choices", [])
            ):
                if isinstance(key, str):
                    os.environ.pop(key, None)
        cfg = config.Settings(
            _env_file=None,
            environment="test",
            database_url=instance.url.set(database=name).render_as_string(
                hide_password=False
            ),
            external_mutations_emergency_stop=True,
            intelligence_external_kill_switch=True,
            intelligence_search_provider_kill_switch=True,
            intelligence_external_provider_mode="DISABLED",
            media_storage_directory=str(EVIDENCE / "fixture-private-media"),
            maintenance_marker=str(EVIDENCE / "fixture-maintenance-disabled"),
            log_level="ERROR",
        )
        config.get_settings.cache_clear()
        config.get_settings = lambda: cfg
        from qa.network_guard import restrict_egress

        restrict_egress(55432)
        from alembic import command
        from vayujit_api.core.database import engine

        app_engine = engine
        stage = "alembic_upgrade_head"
        alembic_cfg = QaMigrationConfig(str(ROOT / "apps/api/alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
        command.upgrade(alembic_cfg, "head")
        with engine.connect() as c:
            revisions = list(c.scalars(text("SELECT version_num FROM alembic_version")))
        stage = "canonical_owner_fixture"
        from fastapi.testclient import TestClient
        from vayujit_api.main import app

        payload = {
            "full_name": "[QA SYNTHETIC] WP0A Owner",
            "email": "qa-wp0a@example.com",
            "password": "DisposableFixtureOnly739!",
            "password_confirmation": "DisposableFixtureOnly739!",
        }
        with TestClient(app, headers={"Origin": "http://127.0.0.1:4200"}) as client:
            assert (
                client.post("/api/v1/auth/setup-owner", json=payload).status_code == 201
            )
            assert client.get("/api/v1/auth/me").status_code == 200
            assert (
                client.post("/api/v1/auth/setup-owner", json=payload).status_code == 409
            )
        stage = "persisted_owner_constraint"
        with engine.connect() as c:
            assert c.scalar(text("SELECT count(*) FROM users")) == 1
            assert (
                c.scalar(
                    text(
                        "SELECT count(*) FROM pg_constraint WHERE conname='ck_users_single_owner'"
                    )
                )
                == 1
            )
        return {
            "status": "PASS",
            "stage": stage,
            "migration_heads": revisions,
            "owner_created": True,
            "authenticated": True,
            "second_owner_rejected": True,
        }
    except Exception as error:  # noqa: BLE001 - sanitized subprocess failure boundary
        return {
            "status": "FAIL",
            "stage": stage,
            "exception_type": type(error).__name__,
            "sqlstate": getattr(getattr(error, "orig", None), "sqlstate", None),
            "frames": [
                {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                for f in traceback.extract_tb(error.__traceback__)
            ],
            "config_interpolation_failure": isinstance(error, ValueError)
            and "interpolation" in str(error).lower(),
        }
    finally:
        if app_engine is not None:
            app_engine.dispose()


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    instance = QaInstance()
    results = []

    def check(label, action):
        try:
            detail = action()
            results.append({"check": label, "status": "PASS", "evidence": detail})
        # Record check failure without credential-bearing exception messages.
        except Exception as error:  # noqa: BLE001
            results.append(
                {
                    "check": label,
                    "status": "FAIL",
                    "safe_code": (
                        str(error)
                        if isinstance(error, GuardDenied)
                        else type(error).__name__
                    ),
                }
            )

    def denied(action, code):
        try:
            action()
        except GuardDenied as error:
            assert str(error) == code
            return code
        raise AssertionError("guard accepted forbidden operation")

    check("exact_container_endpoint_role_server", instance.verify_server)

    def privileges():
        engine = instance.engine()
        try:
            with engine.connect() as c:
                assert not c.scalar(
                    text(
                        "SELECT has_database_privilege(current_user,'postgres','CREATE')"
                    )
                )
                assert not c.scalar(
                    text("SELECT has_schema_privilege(current_user,'public','CREATE')")
                )
                assert not c.scalar(
                    text(
                        "SELECT has_table_privilege(current_user,'vayujit_qa_guard.instance_identity','UPDATE')"
                    )
                )
                assert not c.scalar(
                    text(
                        "SELECT has_table_privilege(current_user,'vayujit_qa_guard.instance_identity','DELETE')"
                    )
                )
                owners = list(
                    c.scalars(
                        text(
                            "SELECT datname FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user)"
                        )
                    )
                )
                assert not owners
        finally:
            engine.dispose()
        return "No maintenance-database CREATE, public-schema CREATE, identity UPDATE/DELETE, or preexisting database ownership"

    check("minimal_role_maintenance_permissions", privileges)
    token = uuid.uuid4().hex[:16]
    name = instance.create(token)
    results.append(
        {"check": "create_owned_token_database", "status": "PASS", "evidence": name}
    )
    try:
        for forbidden in ("postgres", "vayujit_golden_test", "unrelated_test"):
            check(
                "deny_delete_" + forbidden,
                lambda n=forbidden: denied(
                    lambda: instance.drop(token, requested_name=n),
                    "QA_DELETE_NAME_DENIED",
                ),
            )
        check(
            "deny_existing_database_reuse",
            lambda: denied(
                lambda: instance.create(token), "QA_DATABASE_ALREADY_EXISTS"
            ),
        )
        check("deny_missing_lifecycle", lambda: missing_lifecycle(instance))
        record = instance.load(token)
        original = instance.ledger_path(token).read_text()
        try:
            altered = dict(record, owner="postgres")
            instance.save(token, altered)
            check(
                "deny_wrong_lifecycle_owner",
                lambda: denied(lambda: instance.drop(token), "QA_LIFECYCLE_ID_DENIED"),
            )
            instance.save(token, dict(record, state="DROPPED"))
            check(
                "deny_wrong_lifecycle_state",
                lambda: denied(lambda: instance.drop(token), "QA_DELETE_STATE_DENIED"),
            )
            instance.save(token, dict(record, oid=record["oid"] + 1))
            check(
                "deny_wrong_database_oid",
                lambda: denied(
                    lambda: instance.drop(token), "QA_DELETE_OWNER_OID_DENIED"
                ),
            )
            tampered = dict(record, state="DROPPED")
            instance.ledger_path(token).write_text(json.dumps(tampered))
            check(
                "deny_tampered_lifecycle",
                lambda: denied(lambda: instance.drop(token), "QA_SIGNATURE_DENIED"),
            )
        finally:
            instance.ledger_path(token).write_text(original)
        target = instance.engine(name)
        try:
            with target.begin() as c:
                c.execute(
                    text("UPDATE test_database_marker SET suite_token='not-the-token'")
                )
            check(
                "deny_wrong_database_marker",
                lambda: denied(lambda: instance.drop(token), "QA_DELETE_MARKER_DENIED"),
            )
            with target.begin() as c:
                c.execute(
                    text("UPDATE test_database_marker SET suite_token=:t"), {"t": token}
                )
            with target.connect():
                check(
                    "deny_active_session_cleanup",
                    lambda: denied(
                        lambda: instance.drop(token), "QA_DELETE_ACTIVE_SESSIONS"
                    ),
                )
        finally:
            target.dispose()
        child = subprocess.run(
            [sys.executable, "-m", "qa.validate_postgres_instance", "--fixture", token],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        try:
            outcome = json.loads(child.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            outcome = {
                "status": "FAIL",
                "stage": "fixture_child_report",
                "exit_code": child.returncode,
            }
        results.append(
            {"check": "fresh_process_migrations_canonical_fixture", **outcome}
        )
    finally:
        check("guarded_cleanup", lambda: instance.drop(token))
    engine = instance.engine()
    try:
        with engine.connect() as c:
            check("test_database_absent", lambda: absent(c, name))
            databases = list(
                c.scalars(text("SELECT datname FROM pg_database ORDER BY datname"))
            )
            version = c.scalar(text("SHOW server_version"))
    finally:
        engine.dispose()
    check("existing_fixture_runner_handshake_cleanup", lambda: harness_probe(instance))
    check("unrelated_docker_resources_unchanged", lambda: unchanged(instance))
    check("secrets_absent_from_logs_reports", lambda: secret_scan(instance))
    report = {
        "status": "PASS" if all(x["status"] == "PASS" for x in results) else "FAIL",
        "container_id": instance.manifest["container_id"],
        "instance_id": instance.manifest["instance_id"],
        "endpoint": "127.0.0.1:55432",
        "role": "vayujit_qa_admin",
        "server_version": version,
        "database_scope": "vayujit_qa<16-hex>_test",
        "fixture_token": token,
        "databases_after_cleanup": databases,
        "checks": results,
        "passed": sum(x["status"] == "PASS" for x in results),
        "failed": sum(x["status"] != "PASS" for x in results),
    }
    (EVIDENCE / "validation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


def missing_lifecycle(instance):
    token = uuid.uuid4().hex[:16]
    try:
        instance.drop(token)
    except FileNotFoundError:
        return "missing signed lifecycle refused before SQL deletion"
    raise AssertionError


def absent(connection, name):
    assert not connection.scalar(
        text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": name}
    )
    return True


def harness_probe(instance):
    """Single HTTP witness only, not a seller journey or browser suite."""
    token = uuid.uuid4().hex[:16]
    output = EVIDENCE / ("harness-" + token)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = dict(os.environ)
    env.update(
        QA_DATABASE_ADMIN_URL=instance.url.render_as_string(hide_password=False),
        QA_POSTGRES_INSTANCE_MANIFEST=str(guard_manifest()),
        QA_ORIGIN="http://127.0.0.1:4200",
        QA_PHASE="1",
    )
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "qa.fixture_server",
            "--port",
            str(port),
            "--token",
            token,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ready = False
    try:
        for _ in range(60):
            if child.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/__qa/witness", timeout=1
                ) as response:
                    witness = json.load(response)
                    assert witness["token"] == token and witness["disposable"]
                    ready = True
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
    finally:
        if child.stdin is not None:
            child.stdin.close()
            child.stdin = None
        try:
            child.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            child.terminate()  # Only this owned child, never unrelated processes.
            child.communicate(timeout=10)
    assert ready and child.returncode == 0
    cleanup = json.loads((output / "cleanup.json").read_text())
    assert cleanup["database_absent"] and cleanup["signed_lifecycle"]
    assert instance.load(token)["state"] == "DROPPED"
    return {
        "http_witness": True,
        "child_exit_code": child.returncode,
        "signed_lifecycle_cleanup": True,
        "token": token,
    }


def guard_manifest():
    from qa.postgres_instance import MANIFEST

    return MANIFEST


def unchanged(instance):
    baseline = json.loads((EVIDENCE / "preflight.json").read_text(encoding="utf-8-sig"))
    for expected in baseline["containers"]:
        c = json.loads(instance.docker("inspect", expected["id"]))[0]
        actual = {
            "id": c["Id"],
            "name": c["Name"],
            "image": c["Image"],
            "status": c["State"]["Status"],
            "started": c["State"]["StartedAt"],
            "finished": c["State"]["FinishedAt"],
            "mounts": [
                {k: m.get(k) for k in ("Type", "Name", "Source", "Destination", "RW")}
                for m in c["Mounts"]
            ],
            "networks": list(c["NetworkSettings"]["Networks"]),
        }
        assert actual == expected
    for kind, key, additions in (
        ("network", "networks", {NETWORK, HOST_NETWORK}),
        ("volume", "volumes", {VOLUME}),
    ):
        names = set(instance.docker(kind, "ls", "--format", "{{.Name}}").splitlines())
        assert names == set(baseline[key]) | additions
    return {
        "original_containers": len(baseline["containers"]),
        "original_networks_and_volumes_preserved": True,
    }


def secret_scan(instance):
    secrets = [
        (PRIVATE / n).read_text().strip()
        for n in ("bootstrap-password", "qa-password", "guard-key")
    ]
    log = subprocess.run(
        [instance.manifest["docker_executable"], "logs", CONTAINER],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    contents = [log.stdout, log.stderr]
    for folder in (ROOT / "docs/qa/seller-experience", EVIDENCE):
        contents.extend(
            p.read_text(encoding="utf-8-sig")
            for p in folder.rglob("*")
            if p.is_file() and p.suffix in {".json", ".md"}
        )
    assert not any(secret in content for secret in secrets for content in contents)
    return {"credential_matches": 0, "raw_container_logs_persisted": False}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        result = fixture(sys.argv[2])
        print(json.dumps(result))
        raise SystemExit(0 if result["status"] == "PASS" else 1)
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - redact unanticipated CLI failures
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "safe_code": (
                        str(error)
                        if isinstance(error, GuardDenied)
                        else type(error).__name__
                    ),
                }
            )
        )
        raise SystemExit(1) from None
