"""Read-only checks for exact WP7A5 databases; never repairs or deletes resources."""

import json

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name


def main():
    instance = QaInstance()
    instance.verify_server()
    tokens = {
        p.parent.name
        for p in (ROOT / "tmp/qa-seller-browser").glob("*/wp7a5-browser.json")
    }
    tokens.update(
        p.name for p in (ROOT / "tmp/qa-wp7a5-backend").iterdir() if p.is_dir()
    )
    rows = []
    engine = instance.engine()
    try:
        with engine.connect() as db:
            for token in sorted(tokens):
                record = instance.load(token)
                found = db.execute(
                    text(
                        "SELECT d.oid::bigint, r.rolname, d.datconnlimit FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=:name"
                    ),
                    {"name": database_name(token)},
                ).one_or_none()
                row = {
                    "token": token,
                    "signed_state": record["state"],
                    "recorded_oid": record.get("oid"),
                    "database_absent": found is None,
                }
                if found:
                    row.update(
                        actual_oid=found[0], owner=found[1], connection_limit=found[2]
                    )
                row["sessions"] = [
                    dict(s)
                    for s in db.execute(
                        text(
                            "SELECT state, wait_event_type, wait_event FROM pg_stat_activity WHERE datname=:name"
                        ),
                        {"name": database_name(token)},
                    ).mappings()
                ]
                rows.append(row)
    finally:
        engine.dispose()
    result = {"read_only": True, "runs": rows}
    (ROOT / "tmp/qa-wp7a5/lifecycle-status.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
