"""WP3 read-only lifecycle and evidence audit; never repairs or deletes state."""

import json
import zipfile

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name
from qa.validate_postgres_instance import secret_scan, unchanged


def main():
    instance = QaInstance()
    instance.verify_server()
    browsers = [
        folder
        for folder in (ROOT / "tmp/qa-seller-browser").iterdir()
        if any(folder.glob("wp3-*.json"))
    ]
    backends = list((ROOT / "tmp/qa-wp3-backend").iterdir())
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
                assert record["state"] == "DROPPED" and absent
                databases.append(
                    {
                        "token": token,
                        "state": record["state"],
                        "absent": absent,
                        "guarded_recovery": record.get("invalid_tombstone_recovery", False),
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
        "status": "PASS",
        "read_only": True,
        "databases": databases,
        "traces": traces,
        "docker_preservation": unchanged(instance),
        "secret_scan": secret_scan(instance),
    }
    (ROOT / "tmp/qa-wp3-final-audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
