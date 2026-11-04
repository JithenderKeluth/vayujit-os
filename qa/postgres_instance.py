"""WP0A approved-instance and signed lifecycle authority; no production imports."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "tmp" / "qa-postgres-private"
MANIFEST = PRIVATE / "instance.json"
ROLE = "vayujit_qa_admin"
CONTAINER = "vayujit-qa-postgres"
VOLUME = "vayujit-qa-postgres-data"
NETWORK = "vayujit-qa-postgres-net"
HOST_NETWORK = "vayujit-qa-postgres-host"
MARKER = "vayujit-os-disposable-test-database-v1"


class GuardDenied(RuntimeError):
    pass


def deny(code: str) -> None:
    raise GuardDenied(code)


def database_name(token: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{16}", token):
        deny("QA_TOKEN_DENIED")
    return f"vayujit_qa{token}_test"


def signed(payload: dict, key: bytes) -> dict:
    value = {k: v for k, v in payload.items() if k != "signature"}
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return {**value, "signature": hmac.new(key, encoded, hashlib.sha256).hexdigest()}


def verified(payload: dict, key: bytes) -> dict:
    if not hmac.compare_digest(
        str(payload.get("signature", "")), signed(payload, key)["signature"]
    ):
        deny("QA_SIGNATURE_DENIED")
    return payload


class QaInstance:
    def __init__(self, *, bootstrap: bool = False, allow_stopped: bool = False):
        self.verify_private_acl()
        for path in (PRIVATE, MANIFEST, PRIVATE / "guard-key", PRIVATE / "qa-password"):
            if path.is_symlink() or path.is_junction():
                deny("QA_PRIVATE_PATH_DENIED")
        self.key = (PRIVATE / "guard-key").read_bytes().strip()
        self.manifest = json.loads(MANIFEST.read_text())
        if not bootstrap:
            verified(self.manifest, self.key)
        m = self.manifest
        if (
            m.get("container_name"),
            m.get("host"),
            m.get("port"),
            m.get("role"),
            m.get("scope"),
        ) != (CONTAINER, "127.0.0.1", 55432, ROLE, "disposable-only"):
            deny("QA_APPROVED_TARGET_DENIED")
        uuid.UUID(m["instance_id"])
        self.url = URL.create(
            "postgresql+psycopg",
            username=ROLE,
            password=(PRIVATE / "qa-password").read_text().strip(),
            host="127.0.0.1",
            port=55432,
            database="postgres",
        )
        self.verify_docker(allow_stopped=allow_stopped)

    @staticmethod
    def verify_private_acl() -> None:
        if os.name != "nt":
            deny("QA_WINDOWS_ACL_REQUIRED")
        module = str(ROOT / "scripts" / "pc-first-key-security.psm1").replace("'", "''")
        folder = str(PRIVATE).replace("'", "''")
        script = (
            "$ErrorActionPreference='Stop'; Import-Module '" + module + "'; "
            "Assert-VayujitPrivateAcl -Path '" + folder + "' -Kind Directory | Out-Null; "
            "foreach($n in @('instance.json','guard-key','qa-password',"
            "'bootstrap-password','instance-id'))"
            "{Assert-VayujitPrivateAcl -Path (Join-Path '" + folder + "' $n) -Kind File | Out-Null}"
        )
        result = subprocess.run(
            [
                str(
                    Path(os.environ["SYSTEMROOT"])
                    / "System32/WindowsPowerShell/v1.0/powershell.exe"
                ),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                base64.b64encode(script.encode("utf-16-le")).decode(),
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
        if result.returncode:
            deny("QA_PRIVATE_ACL_DENIED")

    def docker(self, *args: str) -> str:
        try:
            result = subprocess.run(
                [self.manifest["docker_executable"], *args],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            deny("QA_DOCKER_UNAVAILABLE")
        if result.returncode:
            deny("QA_DOCKER_COMMAND_FAILED")
        return result.stdout.strip()

    def verify_docker(self, *, allow_stopped: bool = False) -> dict:
        m = self.manifest
        if self.docker("info", "--format", "{{.ID}}") != m["engine_id"]:
            deny("QA_ENGINE_ID_DENIED")
        c = json.loads(self.docker("inspect", CONTAINER))[0]
        if c["Id"] != m["container_id"] or c["Image"] != m["image_id"]:
            deny("QA_CONTAINER_ID_DENIED")
        labels = c["Config"]["Labels"]
        if (
            labels.get("io.vayujit.qa.instance") != m["instance_id"]
            or labels.get("io.vayujit.qa.scope") != "disposable-only"
        ):
            deny("QA_CONTAINER_LABEL_DENIED")
        if c["HostConfig"]["PortBindings"] != {
            "5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55432"}]
        }:
            deny("QA_PORT_BINDING_DENIED")
        stopped_control = allow_stopped and c["State"]["Status"] == "exited"
        if not stopped_control and c["NetworkSettings"]["Ports"].get("5432/tcp") != [
            {"HostIp": "127.0.0.1", "HostPort": "55432"}
        ]:
            deny("QA_EFFECTIVE_PORT_DENIED")
        if set(c["NetworkSettings"]["Networks"]) != {NETWORK, HOST_NETWORK}:
            deny("QA_NETWORK_DENIED")
        net = json.loads(self.docker("network", "inspect", NETWORK))[0]
        host_net = json.loads(self.docker("network", "inspect", HOST_NETWORK))[0]
        vol = json.loads(self.docker("volume", "inspect", VOLUME))[0]
        if not net["Internal"] or set(net.get("Containers", {})) - {c["Id"]}:
            deny("QA_NETWORK_MEMBERSHIP_DENIED")
        if (
            host_net["Internal"]
            or set(host_net.get("Containers", {})) - {c["Id"]}
            or host_net["Options"].get("com.docker.network.bridge.enable_ip_masquerade") != "false"
        ):
            deny("QA_HOST_NETWORK_DENIED")
        for resource in (net, host_net, vol):
            if resource["Labels"].get("io.vayujit.qa.instance") != m["instance_id"]:
                deny("QA_STORAGE_LABEL_DENIED")
        volumes = [x for x in c["Mounts"] if x["Type"] == "volume"]
        if (
            len(volumes) != 1
            or volumes[0]["Name"] != VOLUME
            or volumes[0]["Destination"] != "/var/lib/postgresql/data"
        ):
            deny("QA_DATA_VOLUME_DENIED")
        allowed_binds = {
            str((ROOT / "infrastructure" / "qa-postgres-init.sh").resolve()).lower(),
            *(
                str((PRIVATE / name).resolve()).lower()
                for name in ("bootstrap-password", "qa-password", "instance-id")
            ),
        }
        for mount in c["Mounts"]:
            if mount["Type"] == "bind":
                # Docker Desktop may expose C:/... as /run/desktop/mnt/host/c/...
                source = mount["Source"].replace("\\", "/").lower()
                normalized = {x.replace("\\", "/") for x in allowed_binds}
                for item in list(normalized):
                    if len(item) > 2 and item[1] == ":":
                        normalized.add("/run/desktop/mnt/host/" + item[0] + item[2:])
                if source not in normalized or mount["RW"]:
                    deny("QA_BIND_MOUNT_DENIED")
        if any(x.startswith("POSTGRES_PASSWORD=") for x in c["Config"]["Env"]):
            deny("QA_INLINE_CREDENTIAL_DENIED")
        return c

    def engine(self, database: str = "postgres"):
        return create_engine(
            self.url.set(database=database),
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 5,
                "options": "-c statement_timeout=15000",
            },
        )

    def verify_server(self) -> None:
        self.verify_docker()
        engine = self.engine()
        try:
            with engine.connect() as c:
                row = c.execute(
                    text(
                        "SELECT current_database(), current_user, "
                        "current_setting('server_version_num')::int"
                    )
                ).one()
                role = c.execute(
                    text(
                        "SELECT rolcreatedb,rolsuper,rolcreaterole,rolreplication,rolbypassrls "
                        "FROM pg_roles WHERE rolname=current_user"
                    )
                ).one()
                marker = c.execute(
                    text("SELECT instance_id,qa_role,scope FROM vayujit_qa_guard.instance_identity")
                ).one()
                memberships = c.scalar(
                    text(
                        "SELECT count(*) FROM pg_auth_members WHERE "
                        "member=(SELECT oid FROM pg_roles WHERE rolname=current_user)"
                    )
                )
                if (
                    row[0] != "postgres"
                    or row[1] != ROLE
                    or row[2] // 10000 != 17
                    or tuple(role) != (True, False, False, False, False)
                    or memberships
                ):
                    deny("QA_SERVER_ROLE_DENIED")
                if tuple(marker) != (
                    self.manifest["instance_id"],
                    ROLE,
                    "disposable-only",
                ):
                    deny("QA_SERVER_INSTANCE_DENIED")
        finally:
            engine.dispose()

    def ledger_path(self, token: str) -> Path:
        database_name(token)
        folder = PRIVATE / "lifecycles"
        if folder.is_symlink() or folder.is_junction():
            deny("QA_LIFECYCLE_PATH_DENIED")
        folder.mkdir(exist_ok=True)
        path = folder / (token + ".json")
        if path.is_symlink() or path.is_junction():
            deny("QA_LIFECYCLE_PATH_DENIED")
        return path

    def save(self, token: str, record: dict, *, new: bool = False) -> None:
        p = self.ledger_path(token)
        value = json.dumps(signed(record, self.key), sort_keys=True)
        if new:
            with p.open("x") as file:
                file.write(value)
        else:
            temp = p.with_suffix(".pending")
            temp.write_text(value)
            temp.replace(p)

    def load(self, token: str) -> dict:
        record = verified(json.loads(self.ledger_path(token).read_text()), self.key)
        if (
            record["instance_id"],
            record["container_id"],
            record["database"],
            record["owner"],
            record["token"],
        ) != (
            self.manifest["instance_id"],
            self.manifest["container_id"],
            database_name(token),
            ROLE,
            token,
        ):
            deny("QA_LIFECYCLE_ID_DENIED")
        return record

    @contextmanager
    def lease(self, token: str):
        lock = self.ledger_path(token).with_suffix(".lock")
        try:
            file = lock.open("x")
        except FileExistsError:
            deny("QA_LIFECYCLE_BUSY")
        try:
            file.write("owned-lifecycle-operation")
            file.close()
            yield
        finally:
            lock.unlink()

    def create(self, token: str) -> str:
        with self.lease(token):
            return self._create(token)

    def _create(self, token: str) -> str:
        name = database_name(token)
        self.verify_server()
        record = {
            "instance_id": self.manifest["instance_id"],
            "container_id": self.manifest["container_id"],
            "database": name,
            "owner": ROLE,
            "token": token,
            "creation_id": str(uuid.uuid4()),
            "state": "CREATING",
        }
        admin = self.engine()
        try:
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
                if c.scalar(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": name}):
                    deny("QA_DATABASE_ALREADY_EXISTS")
                self.save(token, record, new=True)
                c.execute(text(f'CREATE DATABASE "{name}"'))
                record["oid"] = c.scalar(
                    text("SELECT oid::bigint FROM pg_database WHERE datname=:n"),
                    {"n": name},
                )
            target = self.engine(name)
            try:
                with target.begin() as c:
                    c.execute(
                        text(
                            "CREATE TABLE test_database_marker(marker_id integer PRIMARY KEY, "
                            "project_identifier text NOT NULL, suite_token text NOT NULL, "
                            "creation_id text NOT NULL)"
                        )
                    )
                    c.execute(
                        text("INSERT INTO test_database_marker VALUES(1,:p,:t,:i)"),
                        {"p": MARKER, "t": token, "i": record["creation_id"]},
                    )
            finally:
                target.dispose()
            record["state"] = "ACTIVE"
            self.save(token, record)
        finally:
            admin.dispose()
        return name

    def drop(
        self, token: str, *, requested_name: str | None = None, timeout_ms: int = 15000
    ) -> None:
        if type(timeout_ms) is not int or not 15000 <= timeout_ms <= 90000:
            deny("QA_DELETE_TIMEOUT_DENIED")
        if requested_name is not None and requested_name != database_name(token):
            deny("QA_DELETE_NAME_DENIED")
        with self.lease(token):
            self._drop(token, requested_name=requested_name, timeout_ms=timeout_ms)

    def resume_drop(self, token: str, *, timeout_ms: int = 15000) -> None:
        """Explicit retry of an interrupted owned deletion; all SQL guards rerun.

        Normal drop still rejects DROPPING. No lifecycle reset, FORCE, absent-DB
        inference, prefix deletion or session termination is permitted here.
        """
        if type(timeout_ms) is not int or not 15000 <= timeout_ms <= 90000:
            deny("QA_RECOVERY_TIMEOUT_DENIED")
        with self.lease(token):
            self._drop(token, resume=True, timeout_ms=timeout_ms)

    def _drop(
        self,
        token: str,
        *,
        requested_name: str | None = None,
        resume: bool = False,
        timeout_ms: int = 15000,
    ) -> None:
        name = database_name(token)
        if requested_name is not None and requested_name != name:
            deny("QA_DELETE_NAME_DENIED")
        record = self.load(token)
        if record["state"] != ("DROPPING" if resume else "ACTIVE"):
            deny("QA_DELETE_STATE_DENIED")
        self.verify_server()
        admin = self.engine()
        try:
            with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
                row = c.execute(
                    text(
                        "SELECT d.oid::bigint,r.rolname,d.datconnlimit FROM pg_database d "
                        "JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:n"
                    ),
                    {"n": name},
                ).one()
                if tuple(row[:2]) != (record["oid"], ROLE):
                    deny("QA_DELETE_OWNER_OID_DENIED")
                invalid = row[2] == -2
                if invalid and not resume:
                    deny("QA_DELETE_INVALID_REQUIRES_EXPLICIT_RESUME")
                if invalid:
                    # PostgreSQL disallows connections to an interrupted-DROP
                    # tombstone. The signed DROPPING stage was persisted only
                    # after marker validation; same instance + owner + OID must
                    # still match. Never recreate, alter or mark it valid.
                    record["invalid_tombstone_recovery"] = True
                else:
                    target = self.engine(name)
                    try:
                        with target.connect() as t:
                            marker = t.execute(
                                text(
                                    "SELECT project_identifier,suite_token,creation_id "
                                    "FROM test_database_marker WHERE marker_id=1"
                                )
                            ).one()
                            if tuple(marker) != (MARKER, token, record["creation_id"]):
                                deny("QA_DELETE_MARKER_DENIED")
                    finally:
                        target.dispose()
                if c.scalar(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": name},
                ):
                    deny("QA_DELETE_ACTIVE_SESSIONS")
                record["state"] = "DROPPING"
                if timeout_ms != 15000:
                    # Only this guarded recovery connection; never alter the role/server.
                    c.execute(
                        text("SELECT set_config('statement_timeout', :ms, false)"),
                        {"ms": str(timeout_ms)},
                    )
                    record[
                        "recovery_statement_timeout_ms" if resume else "drop_statement_timeout_ms"
                    ] = timeout_ms
                self.save(token, record)
                # No FORCE or session termination. Never delete by prefix.
                c.execute(text(f'DROP DATABASE "{name}"'))
                if c.scalar(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": name}):
                    deny("QA_DELETE_DATABASE_REMAINS")
                record["state"] = "DROPPED"
                self.save(token, record)
        finally:
            admin.dispose()


def attest() -> None:
    instance = QaInstance(bootstrap=True)
    if "signature" in instance.manifest:
        deny("QA_REATTEST_DENIED")
    instance.verify_server()
    MANIFEST.write_text(json.dumps(signed(instance.manifest, instance.key), indent=2))


def approved_guard(admin_url: URL) -> QaInstance | None:
    """Dedicated role must never fall back to the historical unguarded harness."""
    path = os.environ.get("QA_POSTGRES_INSTANCE_MANIFEST")
    if admin_url.username != ROLE and not path:
        return None
    if not path or Path(path).resolve() != MANIFEST.resolve():
        deny("QA_MANIFEST_REQUIRED")
    instance = QaInstance()
    if make_url(admin_url) != instance.url:
        deny("QA_ADMIN_URL_DENIED")
    instance.verify_server()
    return instance


if __name__ == "__main__":
    import sys

    try:
        if sys.argv[1:] == ["attest"]:
            attest()
        else:
            instance = QaInstance(allow_stopped=sys.argv[1:] == ["identity"])
            if sys.argv[1:] != ["identity"]:
                instance.verify_server()
            print(
                json.dumps(
                    {
                        "container_id": instance.manifest["container_id"],
                        "instance_id": instance.manifest["instance_id"],
                        "endpoint": "127.0.0.1:55432",
                        "role": ROLE,
                        "scope": "vayujit_qa<16-hex>_test",
                    }
                )
            )
    # Security boundary: unknown CLI exceptions must never print credentials.
    except Exception as error:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "safe_code": (
                        str(error) if isinstance(error, GuardDenied) else "QA_INSTANCE_CHECK_FAILED"
                    ),
                    "exception_type": type(error).__name__,
                }
            )
        )
        raise SystemExit(1) from None
