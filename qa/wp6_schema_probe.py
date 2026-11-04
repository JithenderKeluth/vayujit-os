"""Read-only, exact signed disposable WP6 schema drift diagnostic; no row data."""

import json
import sys

from sqlalchemy import inspect, text
from vayujit_api.ads.models import AdAccount, AdCampaign, AdMetric
from vayujit_api.core.test_database import PROJECT_MARKER
from vayujit_api.video.models import VideoGeneration

from qa.postgres_instance import ROLE, ROOT, QaInstance, database_name


def main(token: str) -> None:
    q = QaInstance()
    q.verify_server()
    record = q.load(token)
    assert record["state"] == "ACTIVE"
    name = database_name(token)
    admin = q.engine()
    try:
        with admin.connect() as c:
            identity = c.execute(
                text(
                    "SELECT d.oid::bigint,r.rolname FROM pg_database d JOIN pg_roles r "
                    "ON r.oid=d.datdba WHERE d.datname=:n"
                ),
                {"n": name},
            ).one()
            assert tuple(identity) == (record["oid"], ROLE)
    finally:
        admin.dispose()
    engine = q.engine(name)
    try:
        with engine.connect() as c:
            c.exec_driver_sql("SET TRANSACTION READ ONLY")
            marker = c.execute(
                text(
                    "SELECT project_identifier,suite_token "
                    "FROM test_database_marker WHERE marker_id=1"
                )
            ).one()
            assert tuple(marker) == (PROJECT_MARKER, token)
            inspector = inspect(c)
            tables = []
            for model in (VideoGeneration, AdAccount, AdCampaign, AdMetric):
                actual = {column["name"] for column in inspector.get_columns(model.__tablename__)}
                expected = set(model.__table__.columns.keys())
                tables.append(
                    {
                        "table": model.__tablename__,
                        "missing_orm_columns": sorted(expected - actual),
                        "extra_database_columns": sorted(actual - expected),
                    }
                )
        value = {"token": token, "read_only": True, "marker_verified": True, "tables": tables}
        destination = ROOT / "tmp/qa-seller-browser" / token / "wp6-schema-drift.json"
        destination.write_text(json.dumps(value, indent=2), encoding="utf-8")
        print(json.dumps(value))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1])
