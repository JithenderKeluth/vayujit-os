"""Read-only preflight for the already-approved normal development app resume.

Not a fixture, migration, lifecycle or repair tool. Never prints configuration.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))


def main():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from vayujit_api.core.config import get_settings

    url = make_url(str(get_settings().database_url))
    if (
        url.host != "127.0.0.1"
        or (url.port or 5432) != 5432
        or url.database != "vayujit"
    ):
        raise ValueError("EXACT_PREVIOUSLY_RUNNING_APP_TARGET_REQUIRED")
    engine = create_engine(
        url, connect_args={"options": "-c default_transaction_read_only=on"}
    )
    try:
        with engine.connect() as db:
            if db.scalar(text("SHOW transaction_read_only")) != "on":
                raise ValueError("READ_ONLY_REQUIRED")
            count = db.scalar(
                text(
                    "SELECT count(*) FROM campaign_workflow_waits WHERE completed_at IS NULL"
                )
            )
            if count != 0:
                raise ValueError("PENDING_STARTUP_WRITES_REQUIRE_REVIEW")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "read_only": True,
                    "incomplete_campaign_waits": 0,
                    "database_modified": False,
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    # Sanitize the CLI boundary; never expose a database URL.
    except Exception:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "database_modified": False,
                    "raw_error_persisted": False,
                }
            )
        )
        raise SystemExit(1) from None
