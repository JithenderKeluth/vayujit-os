"""Fresh-process read-only reconstruction, exact existing signed QA lifecycle."""

import json
import os
import sys
import traceback
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from qa.postgres_instance import QaInstance, database_name


def main(token, owner_id):
    database_name(token)
    destination = (
        Path(__file__).resolve().parents[1]
        / f"tmp/qa-seller-browser/{token}/reconstruction-stage.json"
    )

    def stage(name):
        destination.write_text(json.dumps({"token": token, "stage": name}), encoding="utf-8")

    stage("instance_initialization")
    instance = QaInstance()
    stage("signed_lifecycle_load")
    record = instance.load(token)
    stage("instance_verification")
    instance.verify_server()
    if record["state"] != "ACTIVE":
        raise ValueError("ACTIVE_QA_REQUIRED")
    url = instance.url.set(database=database_name(token))
    for key in list(os.environ):
        if key.startswith("VAYUJIT_") or key == "OPENAI_API_KEY":
            del os.environ[key]
    os.environ["VAYUJIT_DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["VAYUJIT_ENV"] = "test"
    os.environ["VAYUJIT_EXTERNAL_MUTATIONS_EMERGENCY_STOP"] = "true"
    os.environ["VAYUJIT_INTELLIGENCE_EXTERNAL_KILL_SWITCH"] = "true"
    os.environ["VAYUJIT_INTELLIGENCE_SEARCH_PROVIDER_KILL_SWITCH"] = "true"
    from vayujit_api.core.config import Settings

    Settings.model_config["env_file"] = None
    from vayujit_api.core.test_database import assert_safe_test_database
    from vayujit_api.identity.models import User

    from qa.network_guard import restrict_egress
    from qa.wp7a2_fixture import snapshot

    restrict_egress(url.port, local_supplier_fixture=True)
    # Register the application's canonical model graph; no startup, workers or
    # migrations run, and the subsequent session is read-only.
    from fastapi.testclient import TestClient
    from vayujit_api.core.database import get_session
    from vayujit_api.main import create_app

    engine = create_engine(url, poolclass=NullPool)
    try:
        stage("database_marker")
        with engine.connect() as c:
            assert_safe_test_database(c, database_url=str(url), environment="test")
        with Session(engine) as db:
            db.execute(__import__("sqlalchemy").text("SET TRANSACTION READ ONLY"))
            stage("owner_reconstruction")
            owner = db.get(User, uuid.UUID(owner_id))
            if owner is None:
                raise ValueError("OWNER_REQUIRED")
            stage("canonical_snapshot")
            result = {"token": token, "fresh_process": True, **snapshot(db, owner)}

        def read_session():
            with Session(engine) as db:
                db.execute(__import__("sqlalchemy").text("SET TRANSACTION READ ONLY"))
                yield db

        # Fresh canonical application instance, genuine persisted browser
        # session authentication. No login shortcut or approval substitution.
        raw_auth = sys.stdin.read()
        result["authenticated_api_process"] = False
        if raw_auth:
            auth = json.loads(raw_auth)
            app = create_app()
            app.dependency_overrides[get_session] = read_session
            client = TestClient(app)
            headers = {"Cookie": auth["cookie"]}
            me = client.get("/api/v1/auth/me", headers=headers)
            campaigns = client.get("/api/v1/ads/campaigns", headers=headers)
            recovery = client.get("/api/v1/ads/recovery", headers=headers)
            if (
                me.status_code != 200
                or str(me.json()["id"]) != owner_id
                or campaigns.status_code != 200
                or recovery.status_code != 200
            ):
                raise ValueError("FRESH_AUTHENTICATED_API_RECONSTRUCTION_FAILED")
            result["authenticated_api_process"] = True
            result["api_campaign_ids"] = [r["id"] for r in campaigns.json()]
            result["api_observed_failures"] = [
                r["failure_code"] for r in recovery.json() if r["observed"]
            ]
            client.close()
        stage("complete")
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main(*sys.argv[1:])
    except Exception as error:
        print(
            json.dumps(
                {
                    "diagnostic": "QA_RECONSTRUCTION_FAILED",
                    "exception_type": type(error).__name__,
                    "frames": [
                        {
                            "file": __import__("pathlib").Path(f.filename).name,
                            "line": f.lineno,
                            "function": f.name,
                        }
                        for f in traceback.extract_tb(error.__traceback__)
                    ],
                }
            )
        )
        raise SystemExit(1) from None
