"""Read-only signed WP7A database activity; no SQL text or connection secrets."""

import json
import sys

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name


def main(token):
    if not (ROOT / "tmp/qa-wp7a-backend" / token).is_dir():
        raise ValueError("WP7A_OWNED_RUN_REQUIRED")
    instance = QaInstance()
    record = instance.load(token)
    instance.verify_server()
    engine = instance.engine()
    try:
        with engine.connect() as c:
            activities = [
                dict(row)
                for row in c.execute(
                    text(
                        "SELECT state, wait_event_type, wait_event, "
                        "extract(epoch from now()-query_start)::integer AS seconds "
                        "FROM pg_stat_activity WHERE datname=:name"
                    ),
                    {"name": database_name(token)},
                ).mappings()
            ]
        result = {
            "token": token,
            "lifecycle": record["state"],
            "activities": activities,
            "read_only": True,
        }
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1])
