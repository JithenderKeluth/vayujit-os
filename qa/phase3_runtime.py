"""QA-only fresh API process attached to a supervisor-owned marked database.

No database creation/deletion or worker startup. Parent owns exact-resource cleanup.
"""

import argparse
import os

from sqlalchemy import text
from sqlalchemy.engine import make_url

from qa.fixture_server import require_target


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    name = f"vayujit_qa{args.token}_test"
    require_target(name, args.token)
    url = make_url(os.environ["VAYUJIT_DATABASE_URL"])
    if url.host != "127.0.0.1" or url.database != name or os.environ["QA_PHASE"] != "3":
        raise ValueError("QA_RUNTIME_TARGET_DENIED")
    from qa.network_guard import restrict_egress

    restrict_egress(url.port or 5432, local_supplier_fixture=True)
    from vayujit_api.core.config import Settings

    Settings.model_config["env_file"] = None
    from vayujit_api.core.config import get_settings
    from vayujit_api.core.database import engine
    from vayujit_api.main import app

    settings = get_settings()
    if settings.live_mutations_enabled or not settings.external_mutations_emergency_stop:
        raise ValueError("QA_RUNTIME_SAFETY_DENIED")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("select suite_token from test_database_marker where marker_id=1")
            )
            == args.token
        )

    @app.get("/__qa/witness", include_in_schema=False)
    def witness() -> dict[str, object]:
        return {
            "token": args.token,
            "disposable": True,
            "process_id": os.getpid(),
            "schema": "ORM_METADATA_NOT_MIGRATION_CERTIFICATION",
        }

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="error", access_log=False)
    engine.dispose()


if __name__ == "__main__":
    run()
