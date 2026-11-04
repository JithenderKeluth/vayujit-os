"""Read-only diagnosis of exact signed WP7A6 resources; never SQL text or secrets."""

import json

from sqlalchemy import text

from qa.postgres_instance import ROOT, QaInstance, database_name


def main():
    instance = QaInstance()
    instance.verify_server()
    roots = [ROOT / "tmp/qa-wp7a6-backend"]
    folders = list(roots[0].iterdir())
    folders += [
        p
        for p in (ROOT / "tmp/qa-seller-browser").iterdir()
        if (p / "wp7a6-session.json").is_file()
    ]
    result = []
    engine = instance.engine()
    try:
        with engine.connect() as db:
            for folder in folders:
                token = folder.name
                record = instance.load(token)
                row = db.execute(
                    text(
                        "SELECT d.oid::bigint, d.datconnlimit, r.rolname FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE datname=:n"
                    ),
                    {"n": database_name(token)},
                ).first()
                sessions = list(
                    db.execute(
                        text(
                            "SELECT state,wait_event_type,wait_event FROM pg_stat_activity WHERE datname=:n"
                        ),
                        {"n": database_name(token)},
                    ).mappings()
                )
                result.append(
                    {
                        "token": token,
                        "state": record["state"],
                        "database": list(row) if row else None,
                        "sessions": [dict(r) for r in sessions],
                    }
                )
    finally:
        engine.dispose()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
