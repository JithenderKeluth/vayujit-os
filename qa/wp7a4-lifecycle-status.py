"""Read-only status of exact WP7A4 runs; no repair, DROP, session termination or state rewrite."""

import json

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name


def main():
    instance = QaInstance()
    instance.verify_server()
    tokens = ["16866647c1ffa6ee", "ecbda835383b31a3", "412436d33a219d5f", "a909d1776a7048ef"]
    engine = instance.engine()
    rows = []
    try:
        with engine.connect() as db:
            for token in tokens:
                row = {"token": token}
                try:
                    record = instance.load(token)
                    row.update(
                        state=record["state"], recorded_oid=record["oid"], signed_identity=True
                    )
                except Exception as error:
                    row.update(
                        state="UNREADABLE", error_type=type(error).__name__, signed_identity=False
                    )
                found = db.execute(
                    text(
                        "SELECT d.oid::bigint, r.rolname, d.datconnlimit FROM pg_database d "
                        "JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:name"
                    ),
                    {"name": database_name(token)},
                ).one_or_none()
                row["database_absent"] = found is None
                if found:
                    row.update(actual_oid=found[0], owner=found[1], connection_limit=found[2])
                row["sessions"] = (
                    db.execute(
                        text(
                            "SELECT state, wait_event_type, wait_event FROM pg_stat_activity "
                            "WHERE datname=:name"
                        ),
                        {"name": database_name(token)},
                    )
                    .mappings()
                    .all()
                )
                row["sessions"] = [dict(s) for s in row["sessions"]]
                rows.append(row)
    finally:
        engine.dispose()
    report = {"read_only": True, "runs": rows}
    (ROOT / "tmp/qa-wp7a4/lifecycle-status.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
