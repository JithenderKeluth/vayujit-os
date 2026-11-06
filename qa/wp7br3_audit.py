"""Read-only exact R3 receipt/absence/process/evidence audit; no lifecycle mutation."""
from __future__ import annotations

import hashlib
import json
import subprocess
import traceback
from pathlib import Path

from sqlalchemy import text

from qa.postgres_instance import QaInstance, database_name


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tmp/qa-wp7br3/session-control.json").read_text())
    if receipt["package"] != "WP7B-R3":
        raise ValueError("R3_RECEIPT_REQUIRED")
    token = receipt["session"]["token"]
    instance = QaInstance()
    instance.verify_server()
    state = instance.load(token)
    engine = instance.engine()
    try:
        with engine.connect() as connection:
            absent = connection.scalar(
                text("SELECT count(*) FROM pg_database WHERE datname=:name"),
                {"name": database_name(token)},
            ) == 0
    finally:
        engine.dispose()
    ps = (
        "Get-NetTCPConnection -State Listen | Where-Object {$_.LocalPort -in @(4200,8000)} | "
        "ForEach-Object {$p=Get-Process -Id $_.OwningProcess; "
        "[pscustomobject]@{port=$_.LocalPort;address=$_.LocalAddress;pid=$p.Id;"
        "start=$p.StartTime.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress"
    )
    current = json.loads(subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout or "[]")
    expected = receipt["preflight"]["development_listeners"]
    order = lambda rows: sorted(rows, key=lambda r: (r["port"], r["pid"]))
    containers_unchanged = None
    if "containers" in receipt["preflight"]:
        observed = []
        for old in receipt["preflight"]["containers"]:
            c = json.loads(instance.docker("inspect", old["id"]))[0]
            observed.append({
                "id": c["Id"], "name": c["Name"], "image": c["Image"],
                "status": c["State"]["Status"], "started": c["State"]["StartedAt"],
                "finished": c["State"]["FinishedAt"],
                "mounts": [{k: m.get(k) for k in ("Type", "Name", "Destination", "RW")} for m in c["Mounts"]],
                "networks": list(c["NetworkSettings"]["Networks"]),
            })
        containers_unchanged = observed == receipt["preflight"]["containers"]
    preserved = all(
        hashlib.sha256((root / file).read_bytes()).hexdigest() == digest
        for file, digest in receipt["preserved_reports"].items()
    )
    app_preserved = all(
        hashlib.sha256((root / file).read_bytes()).hexdigest() == digest
        for file, digest in receipt["source_before"].items()
        if file.startswith(("apps/", "dist/"))
    )
    result = {
        "package": "WP7B-R3", "token": token, "read_only": True,
        "signed_state": state["state"], "database_absent": absent,
        "normal_listeners_unchanged": order(current) == order(expected),
        "containers_unchanged": containers_unchanged,
        "prior_reports_unchanged": preserved, "application_and_build_unchanged": app_preserved,
        "permanent_database_accessed": False, "raw_output_persisted": False,
    }
    (root / f"tmp/qa-wp7br3/audit-{token}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not absent or state["state"] != "DROPPED" or not preserved or not app_preserved or order(current) != order(expected) or containers_unchanged is False:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "BLOCKED", "safe_code": "R3_AUDIT_NOT_ESTABLISHED", "exception_type": type(error).__name__, "source_lines": [f.lineno for f in traceback.extract_tb(error.__traceback__) if Path(f.filename).name == "wp7br3_audit.py"], "raw_output_persisted": False}))
        raise SystemExit(1) from None
