"""Read-only per-item index/nullability classification in an attested QA database."""

import json
import sys

from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, Float, inspect, text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from vayujit_api.ads import models as ads
from vayujit_api.video import bulk_models
from vayujit_api.video import models as video

from qa.postgres_instance import ROOT, QaInstance, database_name
from qa.wp6a_schema_probe import main as inventory


def main(token):
    # Existing probe verifies instance, signed ACTIVE lifecycle, owner/OID and marker.
    inventory(token)
    folder = ROOT / "tmp/qa-seller-browser" / token
    source = json.loads((folder / "wp6a-schema-inventory.json").read_text(encoding="utf-8"))
    q = QaInstance()
    engine = q.engine(database_name(token))
    rows = []
    nulls = []
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        inspector = inspect(conn)
        aliases = not MigrationContext.configure(conn).impl.compare_type(
            Column("n", DOUBLE_PRECISION()), Column("n", Float())
        )
        for module in (video, bulk_models, ads):
            for model in vars(module).values():
                if (
                    not isinstance(model, type)
                    or model.__module__ != module.__name__
                    or not hasattr(model, "__table__")
                ):
                    continue
                table = model.__table__
                actual = inspector.get_indexes(table.name)
                candidates = [
                    i["column_names"]
                    for i in actual
                    if not i.get("dialect_options", {}).get("postgresql_where")
                ]
                candidates += [
                    i["column_names"] for i in inspector.get_unique_constraints(table.name)
                ]
                candidates.append(inspector.get_pk_constraint(table.name)["constrained_columns"])
                for idx in table.indexes:
                    if idx.name in {i["name"] for i in actual}:
                        continue
                    cols = [c.name for c in idx.columns]
                    covered = any(c[: len(cols)] == cols for c in candidates)
                    rows.append(
                        {
                            "table": table.name,
                            "index": idx.name,
                            "columns": cols,
                            "prefix_access_path_present": covered,
                            "classification": (
                                "MAINTAINABILITY_NAMING_DEBT"
                                if covered
                                else "RELIABILITY_PERFORMANCE_RISK"
                            ),
                            "reason": (
                                "No missing columns or demonstrated incorrect read; "
                                "workload/load plan not certified."
                            ),
                        }
                    )
                for col in inspector.get_columns(table.name):
                    if col["nullable"] != table.c[col["name"]].nullable:
                        # Both identifiers are trusted SQLAlchemy metadata, not user-provided names.
                        count = conn.scalar(
                            text(
                                f'SELECT count(*) FROM "{table.name}" WHERE "{col["name"]}" IS NULL'
                            )
                        )
                        nulls.append(
                            {
                                "table": table.name,
                                "column": col["name"],
                                "database_nullable": col["nullable"],
                                "orm_nullable": table.c[col["name"]].nullable,
                                "null_rows": count,
                                "classification": "NON_BLOCKING_HISTORICAL_CONSTRAINT_RISK",
                                "limitation": (
                                    "Fresh synthetic state is not proof legacy rows are non-NULL; "
                                    "no unsafe backfill or tightening."
                                ),
                            }
                        )
    engine.dispose()
    result = {
        "token": token,
        "read_only": True,
        "migration_heads": source["migration_heads"],
        "inventory_tables": len(source["tables"]),
        "index_debt": rows,
        "nullable_debt": nulls,
        "float_double_precision_alembic_types_equivalent": aliases,
        "missing_orm_columns": [t["table"] for t in source["tables"] if t["missing_orm_columns"]],
    }
    (folder / "wp6b-schema-review.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "index_items": len(rows),
                "covered_by_prefix": sum(r["prefix_access_path_present"] for r in rows),
                "nullable_items": len(nulls),
                "types_equivalent": aliases,
                "read_only": True,
            }
        )
    )


if __name__ == "__main__":
    main(sys.argv[1])
