"""Recover one abandoned QA database; exact token/marker and no active sessions.

Does not terminate processes or PostgreSQL sessions, and refuses any other name.
"""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from qa.fixture_server import require_target


def cleanup(token: str) -> dict[str, object]:
    name = f"vayujit_qa{token}_test"
    require_target(name, token)
    url = make_url(os.environ["QA_DATABASE_ADMIN_URL"])
    if url.host != "127.0.0.1" or url.database != "postgres":
        raise ValueError("QA_CLEANUP_ADMIN_DENIED")
    admin = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    target = create_engine(url.set(database=name), poolclass=NullPool)
    from vayujit_api.core.test_database import PROJECT_MARKER

    with admin.connect() as connection:
        exists = connection.scalar(
            text("select 1 from pg_database where datname=:name"), {"name": name}
        )
    if exists:
        with target.connect() as connection:
            row = connection.execute(
                text(
                    "select project_identifier,suite_token from test_database_marker "
                    "where marker_id=1"
                )
            ).one()
            if row != (PROJECT_MARKER, token):
                raise ValueError("QA_CLEANUP_MARKER_DENIED")
        target.dispose()
        with admin.connect() as connection:
            active = connection.scalar(
                text("select count(*) from pg_stat_activity where datname=:name"), {"name": name}
            )
            if active:
                raise ValueError("QA_CLEANUP_ACTIVE_SESSIONS_DENIED")
            connection.execute(text(f'DROP DATABASE "{name}"'))
    with admin.connect() as connection:
        assert not connection.scalar(
            text("select 1 from pg_database where datname=:name"), {"name": name}
        )
    target.dispose()
    admin.dispose()
    result = {
        "status": "PASS",
        "database": name,
        "database_absent": True,
        "marker_verified_before_drop": bool(exists),
        "session_termination_used": False,
    }
    destination = Path("tmp/qa-agent") / token / "recovery-cleanup.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    print(json.dumps(cleanup(parser.parse_args().token)))
