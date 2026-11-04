"""Checked reconciliation for a marked, network-isolated restored COPY only.

No CLI accepts a source URL. Historical Alembic files are unmodified. Only the
three observed, EMPTY legacy tables may be reconciled; unknown drift is rejected.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from audit_local_migration_contract import actual_contract, expected_contracts
from local_migration_rehearsal import fingerprint_sql
from sqlalchemy.engine import make_url

LEGACY = "20261010_0151"
HEAD = "20261207_0150"
PREFIX = "vayujit-copy-reconcile:"
stage = "initialization"


def require(value, code):
    if not value:
        raise RuntimeError("LOCAL_RECON_" + code)


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def default_sql(column):
    value = column["default"]
    if value is None:
        return None
    if column["type"] == "JSONB":
        require(value in {"'[]'::jsonb", "'{}'::jsonb"}, "DEFAULT_UNSUPPORTED")
        return value
    if column["type"] == "INTEGER":
        require(bool(re.fullmatch(r"[0-9]+", value)), "DEFAULT_UNSUPPORTED")
        return value
    require(
        column["type"].startswith("VARCHAR(") or column["type"] == "TEXT",
        "DEFAULT_UNSUPPORTED",
    )
    return "'" + value.replace("'", "''") + "'"


def default_matches(column, actual):
    expected = default_sql(column)
    if actual == expected:
        return True
    if expected is None or actual is None:
        return False
    # Only PostgreSQL's explicit casts for canonical string/integer literals.
    casts = (
        ("::character varying", "::text")
        if column["type"] != "INTEGER"
        else ("::integer",)
    )
    return actual in {expected + cast for cast in casts}


def validate_legacy(expected, actual, rows):
    require(rows == 0, "NONEMPTY_LEGACY_TABLE")
    require(not actual["check_constraints"], "UNEXPECTED_CHECK_CONSTRAINT")
    require(
        expected["columns"].keys() == actual["columns"].keys(), "COLUMN_SET_CHANGED"
    )
    for name, column in expected["columns"].items():
        current = actual["columns"][name]
        require(column["nullable"] == current["nullable"], "NULLABILITY_CHANGED")
        legacy_time = (
            name == "created_at"
            and current["type"] in {"TIMESTAMP", "TIMESTAMP WITHOUT TIME ZONE"}
            and column["type"] == "TIMESTAMP WITH TIME ZONE"
        )
        require(column["type"] == current["type"] or legacy_time, "TYPE_UNSUPPORTED")
        require(
            current["default"] is None or default_matches(column, current["default"]),
            "DEFAULT_CONFLICT",
        )
    for key in ("primary_key", "unique_constraints", "foreign_keys"):
        require(expected[key] == actual[key], "CONSTRAINT_CONFLICT")
    for name, index in expected["indexes"].items():
        if name in actual["indexes"]:
            require(index == actual["indexes"][name], "INDEX_CONFLICT")
    for index in actual["indexes"].values():
        require(
            not index["unique"]
            and bool(index["columns"])
            and all(c in expected["columns"] for c in index["columns"]),
            "UNEXPECTED_INDEX",
        )


def verify_canonical(expected, actual):
    require(
        expected["columns"].keys() == actual["columns"].keys(), "COLUMN_SET_CHANGED"
    )
    for name, column in expected["columns"].items():
        current = actual["columns"][name]
        require(
            column["type"] == current["type"]
            and column["nullable"] == current["nullable"]
            and default_matches(column, current["default"]),
            "CANONICAL_COLUMN_MISMATCH",
        )
    for key in ("primary_key", "unique_constraints", "foreign_keys"):
        require(expected[key] == actual[key], "CONSTRAINT_CONFLICT")
    for name, index in expected["indexes"].items():
        require(index == actual["indexes"].get(name), "CANONICAL_INDEX_MISSING")


def identity(db, token):
    require(bool(re.fullmatch(r"[a-f0-9]{16}", token)), "TOKEN_INVALID")
    require(
        db.scalar(sa.text("SELECT current_database()")) == "vayujit_restore",
        "COPY_DATABASE_REQUIRED",
    )
    require(
        db.scalar(sa.text("SELECT current_user")) == "postgres", "COPY_ROLE_REQUIRED"
    )
    require(
        db.scalar(
            sa.text(
                "SELECT shobj_description(oid,'pg_database') FROM pg_database "
                "WHERE datname=current_database()"
            )
        )
        == PREFIX + token,
        "COPY_MARKER_MISMATCH",
    )


def reject_hidden_drift(db, table):
    schema = sa.inspect(db)
    for column in schema.get_columns(table):
        require(
            not column.get("computed") and not column.get("identity"),
            "GENERATED_COLUMN",
        )
    for fk in schema.get_foreign_keys(table):
        require(fk.get("referred_schema") in {None, "public"}, "FK_SCHEMA_UNSUPPORTED")
        require(set(fk["options"]) <= {"ondelete"}, "FK_OPTIONS_UNSUPPORTED")
    for index in schema.get_indexes(table):
        if index.get("duplicates_constraint"):
            continue
        require(not index.get("include_columns"), "INDEX_OPTIONS_UNSUPPORTED")
        require(not index.get("column_sorting"), "INDEX_OPTIONS_UNSUPPORTED")
        require(
            all(not v for v in index.get("dialect_options", {}).values()),
            "INDEX_OPTIONS_UNSUPPORTED",
        )
    require(
        not db.scalar(
            sa.text(
                "SELECT c.relrowsecurity OR c.relforcerowsecurity OR EXISTS "
                "(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname=:table"
            ),
            {"table": table},
        ),
        "RLS_OR_CUSTOM_TRIGGER",
    )
    require(
        not db.scalar(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_class x ON x.oid=i.indexrelid "
                "JOIN pg_am a ON a.oid=x.relam WHERE n.nspname='public' AND t.relname=:table "
                "AND (NOT i.indisvalid OR NOT i.indisready OR a.amname<>'btree' "
                "OR i.indpred IS NOT NULL OR i.indexprs IS NOT NULL)) "
                "OR EXISTS (SELECT 1 FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' "
                "AND t.relname=:table AND NOT c.convalidated)"
            ),
            {"table": table},
        ),
        "INVALID_OR_UNSUPPORTED_INDEX_CONSTRAINT",
    )


def reconcile(engine, contracts, token):
    with engine.begin() as db:
        identity(db, token)
        return reconcile_connection(db, contracts)


def reconcile_connection(db, contracts):
    """Shared SQL core; callers must verify identity and own the transaction."""
    operations = []
    # Keep all locks and DDL within the caller's existing transaction.
    if db.in_transaction():
        require(
            db.scalar(sa.text("SELECT version_num FROM alembic_version")) == LEGACY,
            "LEGACY_REVISION_REQUIRED",
        )
        db.execute(sa.text("SET LOCAL lock_timeout='5s'"))
        for table in contracts:
            db.execute(
                sa.text(
                    f"LOCK TABLE public.{quote(table)} IN ACCESS EXCLUSIVE MODE NOWAIT"
                )
            )
        # Validate ALL tables before issuing any schema change.
        for table, expected in contracts.items():
            reject_hidden_drift(db, table)
            validate_legacy(
                expected,
                actual_contract(sa.inspect(db), table),
                db.scalar(sa.text(f"SELECT count(*) FROM public.{quote(table)}")),
            )
        for table, expected in contracts.items():
            current = actual_contract(sa.inspect(db), table)
            for name, column in expected["columns"].items():
                if current["columns"][name]["type"] != column["type"]:
                    db.execute(
                        sa.text(
                            f"ALTER TABLE public.{quote(table)} ALTER COLUMN {quote(name)} "
                            "TYPE TIMESTAMP WITH TIME ZONE "
                            f"USING {quote(name)} AT TIME ZONE 'UTC'"
                        )
                    )
                    operations.append(
                        {"operation": "empty_timestamp_to_timestamptz", "table": table}
                    )
                if (
                    column["default"] is not None
                    and current["columns"][name]["default"] is None
                ):
                    db.execute(
                        sa.text(
                            f"ALTER TABLE public.{quote(table)} ALTER COLUMN {quote(name)} "
                            f"SET DEFAULT {default_sql(column)}"
                        )
                    )
                    operations.append(
                        {
                            "operation": "set_canonical_default",
                            "table": table,
                            "column": name,
                        }
                    )
            for name, index in expected["indexes"].items():
                if name not in current["indexes"]:
                    db.execute(
                        sa.text(
                            f"CREATE INDEX {quote(name)} ON public.{quote(table)} "
                            f"({','.join(quote(c) for c in index['columns'])})"
                        )
                    )
                    operations.append(
                        {
                            "operation": "add_canonical_index",
                            "table": table,
                            "index": name,
                        }
                    )
            verify_canonical(expected, actual_contract(sa.inspect(db), table))
    else:
        require(False, "TRANSACTION_REQUIRED")
    return operations


def upgrade_connection(db, contracts, cfg, script):
    """Original Alembic steps on the same caller-owned transaction, no stamp."""
    require(db.in_transaction(), "TRANSACTION_REQUIRED")
    revisions = list(script.iterate_revisions(HEAD, LEGACY))
    require(
        len(revisions) == 16 and script.get_heads() == [HEAD], "MIGRATION_GRAPH_CHANGED"
    )
    for revision in revisions:
        require(
            "autocommit_block" not in Path(revision.path).read_text(),
            "AUTOCOMMIT_MIGRATION_NOT_ALLOWED",
        )
    operations = reconcile_connection(db, contracts)
    adopted = []
    for revision in revisions:
        if revision.revision in {"20261011_0152", "20261012_0153"}:
            revision.module.op = CheckedOperations(contracts, adopted)
    with EnvironmentContext(
        cfg,
        script,
        fn=lambda rev, context: script._upgrade_revs(HEAD, rev),
        destination_rev=HEAD,
    ) as context:
        context.configure(connection=db, transaction_per_migration=False)
        with context.begin_transaction():
            context.run_migrations()
    return operations, adopted, len(revisions)


class CheckedOperations:
    def __init__(self, contracts, adopted):
        self.contracts = contracts
        self.adopted = adopted

    def __getattr__(self, name):
        return getattr(op, name)

    def create_table(self, table, *args, **kwargs):
        require(table in self.contracts and not kwargs, "ADOPTION_NOT_ALLOWLISTED")
        db = op.get_bind()
        verify_canonical(self.contracts[table], actual_contract(sa.inspect(db), table))
        require(
            db.scalar(sa.text(f"SELECT count(*) FROM public.{quote(table)}")) == 0,
            "NONEMPTY_LEGACY_TABLE",
        )
        self.adopted.append({"table": table, "contract_verified": True})
        return sa.Table(table, sa.MetaData(), autoload_with=db)

    def create_index(self, name, table, columns, *args, **kwargs):
        if table in self.contracts:
            expected = self.contracts[table]["indexes"].get(name)
            require(
                not args
                and not kwargs
                and expected == {"columns": columns, "unique": False},
                "INDEX_ADOPTION_NOT_ALLOWLISTED",
            )
            actual = actual_contract(sa.inspect(op.get_bind()), table)
            require(actual["indexes"].get(name) == expected, "INDEX_ADOPTION_MISMATCH")
            return None
        return op.create_index(name, table, columns, *args, **kwargs)


def main():
    global stage
    from vayujit_api.core.config import Settings

    Settings.model_config["env_file"] = None
    token = os.environ.get("LOCAL_RECON_COPY_TOKEN", "")
    url = make_url(os.environ["VAYUJIT_DATABASE_URL"])
    require(
        url.host == "127.0.0.1"
        and url.port == 5432
        and url.database == "vayujit_restore"
        and url.username == "postgres",
        "COPY_URL_REQUIRED",
    )
    cfg = Config("/app/alembic.ini")
    cfg.set_main_option("script_location", "/app/alembic")
    script = ScriptDirectory.from_config(cfg)
    contracts = expected_contracts(Path("/app/alembic/versions"))
    engine = sa.create_engine(
        url, connect_args={"options": "-c TimeZone=UTC -c statement_timeout=60000"}
    )
    try:
        if sys.argv[1:] == ["--verify-only"]:
            stage = "fresh_process_reconstruction"
            preserved = json.loads(Path("/private/preservation.json").read_text())
            with engine.connect() as db:
                identity(db, token)
                require(
                    db.scalar(sa.text("SELECT version_num FROM alembic_version"))
                    == HEAD,
                    "HEAD_NOT_REACHED",
                )
                for table, cols in preserved["columns"].items():
                    if table != "alembic_version":
                        require(
                            db.scalar(
                                sa.text(fingerprint_sql(table, cols, migrated=True))
                            )
                            == preserved["fingerprints"][table],
                            "ORIGINAL_ROWS_CHANGED",
                        )
                schema = sa.inspect(db)
                for table, expected in contracts.items():
                    verify_canonical(expected, actual_contract(schema, table))
                linkage = schema.get_foreign_keys(
                    "intelligence_supplier_shortlist_decisions"
                )
                require(
                    any(
                        c["constrained_columns"] == ["comparison_snapshot_id"]
                        and c["referred_table"]
                        == "intelligence_supplier_comparison_snapshots"
                        and c["options"].get("ondelete") == "SET NULL"
                        for c in linkage
                    ),
                    "SHORTLIST_LINKAGE_MISSING",
                )
                require(
                    db.scalar(sa.text("SELECT count(*) FROM users")) == 1
                    and db.scalar(
                        sa.text(
                            "SELECT count(*) FROM pg_constraint WHERE "
                            "conname='ck_users_single_owner' AND convalidated"
                        )
                    )
                    == 1,
                    "SINGLE_OWNER_CHANGED",
                )
                require(
                    {
                        "catalog_product_lineages",
                        "catalog_product_variants",
                        "inventory_items",
                        "inventory_movements",
                        "channel_sku_mappings",
                        "operational_signals",
                    }
                    <= set(schema.get_table_names()),
                    "REQUIRED_TABLES_MISSING",
                )
            print(
                json.dumps(
                    {
                        "status": "FRESH_PROCESS_VERIFIED",
                        "head": HEAD,
                        "all_original_rows_and_precision_preserved": True,
                        "single_owner_preserved": True,
                        "shortlist_linkage_present": True,
                        "required_application_tables_present": True,
                    }
                )
            )
            return
        require(not sys.argv[1:], "ARGUMENT_NOT_SUPPORTED")
        stage = "baseline_preservation_snapshot"
        with engine.connect() as db:
            identity(db, token)
            schema = sa.inspect(db)
            columns = {
                t: [c["name"] for c in schema.get_columns(t)]
                for t in schema.get_table_names()
            }
            baseline = {
                t: db.scalar(sa.text(fingerprint_sql(t, cols)))
                for t, cols in columns.items()
            }
            legacy_contracts = {t: actual_contract(schema, t) for t in contracts}
        Path("/private/preservation.json").write_text(
            json.dumps({"columns": columns, "fingerprints": baseline}), encoding="utf-8"
        )

        class RollbackProof(Exception):
            pass

        stage = "late_failure_atomic_rollback_proof"
        try:
            with engine.begin() as db:
                identity(db, token)
                upgrade_connection(db, contracts, cfg, script)
                raise RollbackProof()
        except RollbackProof:
            pass
        with engine.connect() as db:
            require(
                set(sa.inspect(db).get_table_names()) == set(columns),
                "ROLLBACK_TABLE_SET_CHANGED",
            )
            require(
                all(
                    actual_contract(sa.inspect(db), t) == old
                    for t, old in legacy_contracts.items()
                ),
                "ROLLBACK_SCHEMA_CHANGED",
            )
            require(
                all(
                    db.scalar(sa.text(fingerprint_sql(t, cols))) == baseline[t]
                    for t, cols in columns.items()
                ),
                "ROLLBACK_ROWS_OR_REVISION_CHANGED",
            )
        stage = "atomic_reconciliation_and_sixteen_upgrades"
        with engine.begin() as db:
            identity(db, token)
            operations, adopted, migration_count = upgrade_connection(
                db, contracts, cfg, script
            )
            require(
                db.scalar(sa.text("SELECT version_num FROM alembic_version")) == HEAD,
                "HEAD_NOT_REACHED",
            )
            for table, expected in contracts.items():
                verify_canonical(expected, actual_contract(sa.inspect(db), table))
            for table, cols in columns.items():
                if table != "alembic_version":
                    require(
                        db.scalar(sa.text(fingerprint_sql(table, cols, migrated=True)))
                        == baseline[table],
                        "ORIGINAL_ROWS_CHANGED",
                    )
            require(
                db.scalar(sa.text("SELECT count(*) FROM users")) == 1
                and db.scalar(
                    sa.text(
                        "SELECT count(*) FROM pg_constraint WHERE "
                        "conname='ck_users_single_owner' AND convalidated"
                    )
                )
                == 1,
                "SINGLE_OWNER_CHANGED",
            )
        print(
            json.dumps(
                {
                    "status": "COPY_UPGRADE_PASSED",
                    "operations": operations,
                    "adopted": adopted,
                    "migrations": migration_count,
                    "head": HEAD,
                    "all_original_rows_and_precision_preserved": True,
                    "original_tables": len(columns),
                    "late_failure_full_transaction_rollback_verified": True,
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - never emit SQL or business data
        guard = str(error) if type(error) is RuntimeError else ""
        code = (
            guard
            if re.fullmatch(r"LOCAL_RECON_[A-Z_]+", guard)
            else "COPY_OPERATION_FAILED"
        )
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "stage": stage,
                    "failure_code": code,
                    "exception_type": type(error).__name__,
                }
            )
        )
        raise SystemExit(1) from None
