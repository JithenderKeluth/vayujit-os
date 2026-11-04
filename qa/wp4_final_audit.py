"""Read-only WP4 lifecycle/evidence audit; no automatic repair or deletion."""

import json
import zipfile

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name
from qa.validate_postgres_instance import secret_scan, unchanged


def main(package="wp4", *, docker_audit=unchanged):
    if package not in {
        "wp4",
        "wp5",
        "wp6",
        "wp6a",
        "wp6b",
        "wp7",
        "wp7a",
        "wp7a2",
        "wp7a3",
        "wp7a4",
        "wp7a5",
        "wp7a6",
        "wp7a7",
    }:
        raise ValueError("QA_AUDIT_SCOPE_DENIED")
    instance = QaInstance()
    instance.verify_server()
    browsers = [
        folder
        for folder in (ROOT / "tmp/qa-seller-browser").iterdir()
        if any(folder.glob(f"{package}-*.json"))
    ]
    backend_root = ROOT / f"tmp/qa-{package}-backend"
    backends = list(backend_root.iterdir()) if backend_root.exists() else []
    tokens = sorted({folder.name for folder in browsers + backends})
    databases = []
    engine = instance.engine()
    try:
        with engine.connect() as connection:
            for token in tokens:
                record = instance.load(token)
                absent = (
                    connection.scalar(
                        text("SELECT count(*) FROM pg_database WHERE datname=:n"),
                        {"n": database_name(token)},
                    )
                    == 0
                )
                databases.append(
                    {
                        "token": token,
                        "state": record["state"],
                        "absent": absent,
                        "guarded_recovery": record.get(
                            "invalid_tombstone_recovery", False
                        ),
                        "recovery_statement_timeout_ms": record.get(
                            "recovery_statement_timeout_ms"
                        ),
                    }
                )
    finally:
        engine.dispose()
    traces = []
    for folder in browsers:
        for archive in folder.rglob("trace.zip"):
            with zipfile.ZipFile(archive) as opened:
                assert opened.testzip() is None
            traces.append({"path": archive.relative_to(ROOT).as_posix(), "crc": "PASS"})
    result = {
        "status": (
            "PASS"
            if databases
            and all(d["state"] == "DROPPED" and d["absent"] for d in databases)
            else "CLEANUP_PENDING"
        ),
        "read_only": True,
        "databases": databases,
        "traces": traces,
        "docker_preservation": docker_audit(instance),
        "secret_scan": secret_scan(instance),
    }
    (ROOT / f"tmp/qa-{package}-final-audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
