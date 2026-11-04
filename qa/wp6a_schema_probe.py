"""Read-only schema inventory in an exact signed disposable WP6A installation."""

import json
import sys

from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from vayujit_api.ads import models as ads
from vayujit_api.core.test_database import PROJECT_MARKER
from vayujit_api.video import bulk_models
from vayujit_api.video import models as video

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
            row = c.execute(
                text(
                    "SELECT d.oid::bigint,r.rolname FROM pg_database d JOIN pg_roles r "
                    "ON r.oid=d.datdba WHERE d.datname=:n"
                ),
                {"n": name},
            ).one()
            assert tuple(row) == (record["oid"], ROLE)
    finally:
        admin.dispose()
    engine = q.engine(name)
    try:
        with engine.connect() as c:
            c.exec_driver_sql("SET TRANSACTION READ ONLY")
            marker = c.execute(
                text(
                    "SELECT project_identifier,suite_token FROM test_database_marker "
                    "WHERE marker_id=1"
                )
            ).one()
            assert tuple(marker) == (PROJECT_MARKER, token)
            inspector = inspect(c)
            tables = []
            for module in (video, bulk_models, ads):
                for model in vars(module).values():
                    if (
                        not isinstance(model, type)
                        or model.__module__ != module.__name__
                        or not hasattr(model, "__table__")
                    ):
                        continue
                    table = model.__table__
                    actual = {v["name"]: v for v in inspector.get_columns(table.name)}
                    expected = {v.name: v for v in table.columns}
                    tables.append(
                        {
                            "table": table.name,
                            "missing_orm_columns": sorted(expected.keys() - actual.keys()),
                            "extra_database_columns": sorted(actual.keys() - expected.keys()),
                            "missing_orm_indexes": sorted(
                                {i.name for i in table.indexes}
                                - {i["name"] for i in inspector.get_indexes(table.name)}
                            ),
                            "columns": [
                                {
                                    "name": k,
                                    "database_type": str(
                                        v["type"].compile(dialect=postgresql.dialect())
                                    ),
                                    "nullable": v["nullable"],
                                    "server_default": v["default"],
                                    "orm_type": (
                                        str(expected[k].type.compile(dialect=postgresql.dialect()))
                                        if k in expected
                                        else None
                                    ),
                                    "orm_nullable": expected[k].nullable if k in expected else None,
                                }
                                for k, v in actual.items()
                            ],
                            "indexes": inspector.get_indexes(table.name),
                            "foreign_keys": inspector.get_foreign_keys(table.name),
                            "checks": inspector.get_check_constraints(table.name),
                        }
                    )
            version = c.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        value = {
            "token": token,
            "read_only": True,
            "marker_verified": True,
            "migration_heads": version,
            "tables": tables,
        }
        (ROOT / "tmp/qa-seller-browser" / token / "wp6a-schema-inventory.json").write_text(
            json.dumps(value, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "token": token,
                    "heads": version,
                    "tables": len(tables),
                    "column_drift": [
                        {
                            k: v
                            for k, v in t.items()
                            if k in {"table", "missing_orm_columns", "extra_database_columns"}
                        }
                        for t in tables
                        if t["missing_orm_columns"] or t["extra_database_columns"]
                    ],
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1])
