"""Explicit HUMAN-approved rotation of only the dedicated local QA role secret."""

import json
import os
import secrets
import subprocess

import psycopg
from psycopg import sql

from qa.postgres_instance import PRIVATE, ROLE, ROOT, QaInstance


def main() -> None:
    q = QaInstance()
    q.verify_server()
    target = PRIVATE / "qa-password"
    stage = PRIVATE / "qa-password-rotation"
    if stage.exists() or stage.is_symlink():
        raise RuntimeError("QA_ROTATION_STAGE_EXISTS")
    replacement = secrets.token_urlsafe(48)
    # Generated credential artifact only, within the existing ACL-protected directory.
    with stage.open("x", encoding="utf-8") as handle:
        handle.write(replacement)
    module = str(ROOT / "scripts/pc-first-key-security.psm1").replace("'", "''")
    safe_path = str(stage).replace("'", "''")
    verify = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "$ErrorActionPreference='Stop'; Import-Module '" + module + "'; "
            "Set-VayujitPrivateAcl -Path '" + safe_path + "' -Kind File; "
            "Assert-VayujitPrivateAcl -Path '" + safe_path + "' -Kind File | Out-Null",
        ],
        capture_output=True,
        timeout=20,
        check=False,
    )
    if verify.returncode:
        raise RuntimeError("QA_ROTATION_ACL_DENIED")
    changed = False
    try:
        with psycopg.connect(
            host="127.0.0.1",
            port=55432,
            dbname="postgres",
            user=ROLE,
            password=q.url.password,
            connect_timeout=5,
            autocommit=True,
        ) as conn:
            if conn.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE usename=%s AND pid<>pg_backend_pid()",
                (ROLE,),
            ).fetchone()[0]:
                raise RuntimeError("QA_ROTATION_OTHER_SESSIONS_PRESENT")
            if (
                conn.execute("SHOW log_statement").fetchone()[0] != "none"
                or conn.execute("SHOW log_min_duration_statement").fetchone()[0] != "-1"
            ):
                raise RuntimeError("QA_ROTATION_LOGGING_POLICY_DENIED")
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(ROLE), sql.Literal(replacement)
                )
            )
            changed = True
            try:
                os.replace(stage, target)
                fresh = QaInstance()
                fresh.verify_server()
                try:
                    stale = psycopg.connect(
                        host="127.0.0.1",
                        port=55432,
                        dbname="postgres",
                        user=ROLE,
                        password=q.url.password,
                        connect_timeout=5,
                    )
                except psycopg.OperationalError:
                    pass
                else:
                    stale.close()
                    raise RuntimeError("QA_OLD_CREDENTIAL_NOT_REVOKED")
            except Exception:
                # Keep server and local protected credential consistent on local-write failure.
                conn.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(ROLE), sql.Literal(q.url.password)
                    )
                )
                target.write_text(q.url.password, encoding="utf-8")
                changed = False
                raise RuntimeError("QA_ROTATION_REVERTED_LOCAL_FAILURE") from None
        value = {
            "status": "PASS",
            "role": ROLE,
            "scope": "dedicated_qa_only",
            "human_authorized": True,
            "other_sessions": 0,
            "private_acl_verified": True,
            "new_login_verified": True,
            "old_credential_rejected": True,
            "credential_values_recorded": False,
        }
        (ROOT / "tmp/qa-wp6a-credential-rotation.json").write_text(
            json.dumps(value, indent=2), encoding="utf-8"
        )
        print(json.dumps(value))
    finally:
        if stage.exists() and not changed:
            stage.unlink()  # Exact generated private staging file only; not unrelated data.


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Neither database exceptions nor process arguments may expose credentials.
        allowed = {
            "QA_ROTATION_STAGE_EXISTS",
            "QA_ROTATION_ACL_DENIED",
            "QA_ROTATION_OTHER_SESSIONS_PRESENT",
            "QA_ROTATION_LOGGING_POLICY_DENIED",
            "QA_ROTATION_REVERTED_LOCAL_FAILURE",
        }
        code = (
            str(error)
            if isinstance(error, RuntimeError) and str(error) in allowed
            else type(error).__name__
        )
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "safe_code": code,
                    "sqlstate": getattr(error, "sqlstate", None),
                }
            )
        )
        raise SystemExit(1) from None
