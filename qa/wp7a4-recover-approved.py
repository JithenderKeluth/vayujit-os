"""One exact HUMAN-approved WP7A4 interrupted-DROP recovery, never a general cleanup command."""

import json
import time

from sqlalchemy import text

from qa.postgres_instance import ROLE, ROOT, QaInstance, database_name


def main():
    token = "412436d33a219d5f"
    instance = QaInstance()
    instance.verify_server()
    assert instance.manifest["instance_id"] == "389b97d2-a4cd-4d9b-972e-6bb2bf5785eb"
    assert (
        instance.manifest["container_id"]
        == "a06480a4e71135da13f225685c8809b0d30255cf53209d93bb0123097b1fec23"
    )
    record = instance.load(token)
    assert record["state"] == "DROPPING" and record["oid"] == 10930268
    engine = instance.engine()
    try:
        with engine.connect() as db:
            found = db.execute(
                text(
                    "SELECT d.oid::bigint,r.rolname,d.datconnlimit FROM pg_database d "
                    "JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:n"
                ),
                {"n": database_name(token)},
            ).one()
            assert tuple(found) == (10930268, ROLE, -2)
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
        "human_approval": "Exact WP7A4 recovery approved in conversation",
        "state": record["state"],
        "oid": record["oid"],
        "non_force": True,
        "seconds": round(time.monotonic() - started, 3),
    }
    (ROOT / "tmp/qa-wp7a4/recovery-412436d33a219d5f.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
