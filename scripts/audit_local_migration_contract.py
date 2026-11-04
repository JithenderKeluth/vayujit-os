"""Read-only contracts for the two observed legacy migration collisions.

Migration functions execute against an in-memory recorder, never a live Alembic
operation context. No schema repair, stamping or source migration is provided.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
MIGRATIONS = (
    "20261011_0152_supplier_comparison_snapshot.py",
    "20261012_0153_procurement_readiness.py",
)


def load_file(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("audit_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_contracts(migration_directory: Path | None = None) -> dict:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    dialect = postgresql.dialect()
    contracts = {}

    class Recorder:
        def create_table(self, name, *items):
            table = sa.Table(name, sa.MetaData(), *items)
            contracts[name] = {
                "columns": {
                    c.name: {
                        "type": c.type.compile(dialect=dialect),
                        "nullable": c.nullable,
                        "default": (
                            str(c.server_default.arg) if c.server_default else None
                        ),
                    }
                    for c in table.columns
                },
                "primary_key": list(table.primary_key.columns.keys()),
                "unique_constraints": sorted(
                    [
                        list(c.columns.keys())
                        for c in table.constraints
                        if isinstance(c, sa.UniqueConstraint)
                    ]
                ),
                "foreign_keys": sorted(
                    [
                        {
                            "columns": [e.parent.name for e in c.elements],
                            "targets": [e.target_fullname for e in c.elements],
                            "ondelete": c.ondelete,
                        }
                        for c in table.foreign_key_constraints
                    ],
                    key=lambda value: value["columns"],
                ),
                "indexes": {},
            }

        def create_index(self, name, table, columns):
            if table in contracts:
                contracts[table]["indexes"][name] = {
                    "columns": columns,
                    "unique": False,
                }

        def add_column(self, table, column):
            # Separately audited below; never execute this operation.
            if table != "intelligence_supplier_shortlist_decisions":
                raise RuntimeError("unexpected_recorded_operation")

        def create_foreign_key(self, *args, **kwargs):
            if args[0] != "fk_shortlist_decision_comparison_snapshot":
                raise RuntimeError("unexpected_recorded_operation")

    for filename in MIGRATIONS:
        module = load_file(
            (migration_directory or ROOT / "apps/api/alembic/versions") / filename,
            filename,
        )
        module.op = Recorder()
        module.upgrade()
    return contracts


def actual_contract(schema, table: str) -> dict:
    from sqlalchemy.dialects import postgresql

    return {
        "columns": {
            c["name"]: {
                "type": c["type"].compile(dialect=postgresql.dialect()),
                "nullable": c["nullable"],
                "default": c["default"],
            }
            for c in schema.get_columns(table)
        },
        "primary_key": schema.get_pk_constraint(table)["constrained_columns"],
        "unique_constraints": sorted(
            [c["column_names"] for c in schema.get_unique_constraints(table)]
        ),
        "foreign_keys": sorted(
            [
                {
                    "columns": c["constrained_columns"],
                    "targets": [
                        f"{c['referred_table']}.{column}"
                        for column in c["referred_columns"]
                    ],
                    "ondelete": c["options"].get("ondelete"),
                }
                for c in schema.get_foreign_keys(table)
            ],
            key=lambda value: value["columns"],
        ),
        "indexes": {
            c["name"]: {"columns": c["column_names"], "unique": c["unique"]}
            for c in schema.get_indexes(table)
            if not c.get("duplicates_constraint")
        },
        "check_constraints": schema.get_check_constraints(table),
    }


def differences(expected: dict, actual: dict) -> dict:
    # Raw default representations are intentionally NOT normalized into a claim
    # of equivalence. Any difference requires review; this never authorizes DDL.
    return {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if value != actual.get(key)
    }


def run() -> dict:
    preflight = load_file(ROOT / "scripts/preflight-local-database.py", "preflight")
    witness = preflight.run()
    if witness["status"] != "READ_ONLY_PREFLIGHT_COMPLETE":
        raise RuntimeError("exact_target_preflight_not_complete")
    if (
        witness["database_revision"] != ["20261010_0151"]
        or witness["role"] != "vayujit"
    ):
        raise RuntimeError("legacy_revision_or_role_changed")
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.pool import NullPool
    from vayujit_api.core.config import Settings

    engine = create_engine(
        Settings().database_url,
        poolclass=NullPool,
        connect_args={
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000"
        },
    )
    try:
        with engine.connect() as db:
            if db.scalar(text("SHOW transaction_read_only")) != "on":
                raise RuntimeError("readonly_not_enforced")
            if db.scalar(text("SELECT current_database()")) != "vayujit":
                raise RuntimeError("database_identity_changed")
            schema = inspect(db)
            tables = {}
            for table, expected in expected_contracts().items():
                actual = actual_contract(schema, table)
                tables[table] = {
                    "expected": expected,
                    "actual": actual,
                    "differences": differences(expected, actual),
                    "rows": db.scalar(text(f'SELECT count(*) FROM public."{table}"')),
                }
            shortlist = "intelligence_supplier_shortlist_decisions"
            result = {
                "status": "READ_ONLY_CONTRACT_AUDIT_COMPLETE",
                "source_database_modified": False,
                "source_migration_authorization": "CONDITIONAL_ALL_PREREQUISITES_MUST_PASS",
                "source_migration": "NOT_RUN",
                "tables": tables,
                "shortlist_comparison_column": [
                    {
                        "name": c["name"],
                        "type": str(c["type"]),
                        "nullable": c["nullable"],
                        "default": c["default"],
                    }
                    for c in schema.get_columns(shortlist)
                    if c["name"] == "comparison_snapshot_id"
                ],
                "shortlist_comparison_index": [
                    c["name"]
                    for c in schema.get_indexes(shortlist)
                    if c["name"] == "ix_shortlist_decision_comparison_snapshot"
                ],
                "shortlist_comparison_fk": [
                    c
                    for c in schema.get_foreign_keys(shortlist)
                    if c["constrained_columns"] == ["comparison_snapshot_id"]
                ],
                "equivalence_or_adoption_authorized_by_this_report": False,
            }
            db.rollback()
            return result
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        result = run()
    except Exception as error:  # noqa: BLE001 - redact SQL/configuration exceptions
        result = {
            "status": "BLOCKED",
            "exception_type": type(error).__name__,
            "source_database_modified": False,
        }
    target = ROOT / "tmp/local-migration-contract-audit.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "source_database_modified": False}))
    raise SystemExit(
        0 if result["status"] == "READ_ONLY_CONTRACT_AUDIT_COMPLETE" else 1
    )
