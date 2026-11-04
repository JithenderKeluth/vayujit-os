"""Read-only bounded diagnostics for exact signed WP7 fixture targets. No SQL text."""

import json
import sys
import uuid

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name


def main(tokens):
    instance = QaInstance()
    instance.verify_server()
    rows = []
    engine = instance.engine()
    try:
        with engine.connect() as connection:
            for token in tokens:
                record = instance.load(token)
                activities = connection.execute(
                    text(
                        "SELECT state, wait_event_type, wait_event, "
                        "extract(epoch from now()-query_start)::integer AS seconds, "
                        "CASE WHEN query ~* '^DROP DATABASE' THEN 'DROP_DATABASE' "
                        "WHEN query ~* '^DROP TABLE' THEN 'DROP_TABLE' "
                        "WHEN query ~* '^CREATE TABLE' THEN 'CREATE_TABLE' "
                        "WHEN query ~* '^SELECT' THEN 'SELECT' ELSE 'OTHER' END operation "
                        "FROM pg_stat_activity WHERE (datname=:name OR "
                        "(datname='postgres' AND query LIKE :pattern)) AND usename=current_user"
                    ),
                    {"name": database_name(token), "pattern": f'%"{database_name(token)}"%'},
                ).mappings()
                stats = (
                    connection.execute(
                        text(
                            "SELECT xact_commit, xact_rollback, tup_inserted, tup_updated "
                            "FROM pg_stat_database WHERE datname=:name"
                        ),
                        {"name": database_name(token)},
                    )
                    .mappings()
                    .first()
                )
                rows.append(
                    {
                        "token": token,
                        "state": record["state"],
                        "database_absent": not bool(
                            connection.scalar(
                                text(
                                    "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"
                                ),
                                {"name": database_name(token)},
                            )
                        ),
                        "activities": [dict(a) for a in activities],
                        "progress_counters": dict(stats) if stats else None,
                    }
                )
    finally:
        engine.dispose()
    result = {"read_only": True, "rows": rows, "raw_sql_or_output_persisted": False}
    (ROOT / f"tmp/qa-wp7/probe-{uuid.uuid4().hex}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1:])
