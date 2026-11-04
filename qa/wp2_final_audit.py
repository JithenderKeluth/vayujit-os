"""Read-only audit of WP2 disposable lifecycle and retained browser evidence."""

import json
import zipfile

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name
from qa.validate_postgres_instance import secret_scan, unchanged


def main():
    instance = QaInstance()
    instance.verify_server()
    backend = list((ROOT / "tmp/qa-wp2-backend").iterdir())
    browsers = []
    for folder in (ROOT / "tmp/qa-seller-browser").iterdir():
        marker = folder / "stop.request"
        if (
            (folder / "wp2-browser.json").exists()
            or (folder / "wp2-before.json").exists()
            or (marker.exists() and "WP2" in marker.read_text(encoding="utf-8"))
        ):
            browsers.append(folder)
    tokens = sorted({folder.name for folder in backend + browsers})
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
                assert record["state"] == "DROPPED" and absent
                databases.append(
                    {
                        "token": token,
                        "state": record["state"],
                        "absent": absent,
                        "invalid_tombstone_recovery": record.get(
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
    reports = []
    for folder in browsers:
        report = folder / "wp2-browser.json"
        if report.exists():
            result = json.loads(report.read_text(encoding="utf-8"))
            reports.append(
                {
                    "token": folder.name,
                    "status": result["status"],
                    "passed": sum(row["status"] == "PASS" for row in result["checks"]),
                    "failed": sum(row["status"] == "FAIL" for row in result["checks"]),
                    "axe_violations": sum(
                        len(scan["violations"]) for scan in result["axe"]
                    ),
                    "axe_incomplete_nodes": sum(
                        len(item["nodes"])
                        for scan in result["axe"]
                        for item in scan["incomplete"]
                    ),
                }
            )
    result = {
        "status": "PASS",
        "read_only": True,
        "databases": databases,
        "traces": traces,
        "browser_reports": reports,
        "docker_preservation": unchanged(instance),
        "secret_scan": secret_scan(instance),
    }
    destination = ROOT / "tmp/qa-wp2-final-audit.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
