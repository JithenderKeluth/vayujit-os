"""Read-only wait-state inspection for this package's signed database only."""

import json
import sys

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name


def main():
    token = sys.argv[1]
    name = database_name(token)
    if not (ROOT / "tmp/qa-wp7a7-backend" / token / "openapi.json").is_file():
        raise ValueError("EXACT_TASK_RUN_REQUIRED")
    instance = QaInstance()
    instance.verify_server()
    record = instance.load(token)
    engine = instance.engine()
    try:
        with engine.connect() as db:
            rows = db.execute(
                text("SELECT state,wait_event_type,wait_event,EXTRACT(EPOCH FROM (now()-query_start))::int AS seconds FROM pg_stat_activity WHERE datname=:name"),
                {"name": name},
            ).mappings()
            print(json.dumps({"token": token, "lifecycle": record["state"], "sessions": [dict(row) for row in rows]}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "READ_ONLY_DIAGNOSTIC_FAILED", "raw_output_persisted": False}))
        raise SystemExit(1) from None
