"""One exact HUMAN-approved WP7A5 tombstone recovery; no general deletion authority."""

import json
import subprocess
import time

from sqlalchemy import text

from qa.postgres_instance import ROLE, ROOT, QaInstance, database_name


def main():
    token = "11e7601f51503966"
    instance = QaInstance()
    instance.verify_server()
    assert instance.manifest["instance_id"] == "389b97d2-a4cd-4d9b-972e-6bb2bf5785eb"
    assert (
        instance.manifest["container_id"]
        == "a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23"
    )
    record = instance.load(token)
    assert record["state"] == "DROPPING" and record["oid"] == 11877071
    check = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','node.exe') -and $_.CommandLine -like '*11e7601f51503966*' }).Count",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert (
        check.returncode == 0 and check.stdout.strip() == "0"
    ), "EXACT_QA_PROCESS_CHECK_REQUIRED"
    engine = instance.engine()
    try:
        with engine.connect() as db:
            found = db.execute(
                text(
                    "SELECT d.oid::bigint,r.rolname,d.datconnlimit FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:n"
                ),
                {"n": database_name(token)},
            ).one()
            assert tuple(found) == (11877071, ROLE, -2)
            assert (
                db.scalar(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname=:n"),
                    {"n": database_name(token)},
                )
                == 0
            )
    finally:
        engine.dispose()
    started = time.monotonic()
    instance.resume_drop(token, timeout_ms=90000)
    record = instance.load(token)
    result = {
        "token": token,
        "human_approval": "Exact WP7A5 recovery approved in conversation",
        "state": record["state"],
        "oid": record["oid"],
        "non_force": True,
        "matching_python_node_processes": 0,
        "seconds": round(time.monotonic() - started, 3),
    }
    (ROOT / "tmp/qa-wp7a5/recovery-11e7601f51503966.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
