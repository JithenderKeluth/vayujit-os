"""Pure fail-closed reconciliation tests. No live engine or Docker access."""

import copy
import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def module():
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "reconciliation_copy", scripts / "local_reconciliation_copy.py"
        )
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        return loaded
    finally:
        sys.path.remove(str(scripts))


@pytest.fixture
def contract(module):
    expected = next(iter(module.expected_contracts().values()))
    actual = copy.deepcopy(expected)
    actual["check_constraints"] = []
    for column in actual["columns"].values():
        column["default"] = None
    actual["columns"]["created_at"]["type"] = "TIMESTAMP WITHOUT TIME ZONE"
    return expected, actual


def test_only_observed_empty_legacy_shape_is_reconcilable(module, contract):
    module.validate_legacy(*contract, rows=0)


def test_nonempty_table_is_not_reinterpreted_or_silently_adopted(module, contract):
    with pytest.raises(RuntimeError, match="NONEMPTY_LEGACY_TABLE"):
        module.validate_legacy(*contract, rows=1)


@pytest.mark.parametrize(
    "change",
    [
        "extra_column",
        "missing_column",
        "nullable",
        "type",
        "default",
        "pk",
        "fk",
        "unique",
        "check",
        "index",
    ],
)
def test_unknown_drift_fails_closed(module, contract, change):
    expected, actual = contract
    if change == "extra_column":
        actual["columns"]["surprise"] = actual["columns"]["id"]
    elif change == "missing_column":
        actual["columns"].pop("owner_id")
    elif change == "nullable":
        actual["columns"]["owner_id"]["nullable"] = True
    elif change == "type":
        actual["columns"]["owner_id"]["type"] = "TEXT"
    elif change == "default":
        actual["columns"]["status"]["default"] = "'VERIFIED'::text"
    elif change == "pk":
        actual["primary_key"] = ["owner_id"]
    elif change == "fk":
        actual["foreign_keys"][0]["ondelete"] = "CASCADE_UNEXPECTED"
    elif change == "unique":
        actual["unique_constraints"] = []
    elif change == "check":
        actual["check_constraints"] = [{"sqltext": "surprise"}]
    else:
        key = next(iter(actual["indexes"]))
        actual["indexes"][key]["unique"] = True
    with pytest.raises(RuntimeError, match="LOCAL_RECON_"):
        module.validate_legacy(expected, actual, rows=0)


@pytest.mark.parametrize(
    "kind,value,actual,matched",
    [
        ("VARCHAR(16)", "HUMAN", "'HUMAN'::character varying", True),
        ("VARCHAR(16)", "HUMAN", "'SYSTEM'::character varying", False),
        ("TEXT", "", "''::text", True),
        ("JSONB", "'[]'::jsonb", "'[]'::jsonb", True),
        ("JSONB", "'[]'::jsonb", "'{}'::jsonb", False),
        ("INTEGER", "1", "1", True),
        ("INTEGER", "1", "0", False),
        ("TEXT", None, None, True),
    ],
)
def test_only_canonical_default_literals_match(module, kind, value, actual, matched):
    assert module.default_matches({"type": kind, "default": value}, actual) is matched


def test_unreconciled_contract_cannot_be_adopted(module, contract):
    with pytest.raises(RuntimeError, match="CANONICAL_COLUMN_MISMATCH"):
        module.verify_canonical(*contract)


def test_canonical_contract_allows_preserved_extra_plain_indexes(module, contract):
    expected, _ = contract
    actual = copy.deepcopy(expected)
    for column in actual["columns"].values():
        column["default"] = module.default_sql(column)
    actual["indexes"]["preserved_old_index"] = {
        "columns": ["owner_id"],
        "unique": False,
    }
    module.verify_canonical(expected, actual)


def test_copy_marker_is_mandatory_before_mutation(module):
    class Connection:
        def scalar(self, statement):
            return (
                "vayujit_restore"
                if "current_database()" in str(statement)
                else "postgres"
            )

    with pytest.raises(RuntimeError, match="COPY_MARKER_MISMATCH"):
        module.identity(Connection(), "0123456789abcdef")


def test_source_database_name_is_rejected(module):
    class Connection:
        def scalar(self, statement):
            return "vayujit"

    with pytest.raises(RuntimeError, match="COPY_DATABASE_REQUIRED"):
        module.identity(Connection(), "0123456789abcdef")


def test_reflected_timestamp_type_keeps_timezone_information(module):
    import sqlalchemy as sa

    class Inspector:
        def get_columns(self, table):
            return [
                {
                    "name": "created_at",
                    "type": sa.DateTime(timezone=True),
                    "nullable": False,
                    "default": None,
                }
            ]

        def get_pk_constraint(self, table):
            return {"constrained_columns": []}

        def get_unique_constraints(self, table):
            return []

        get_foreign_keys = get_unique_constraints
        get_indexes = get_unique_constraints
        get_check_constraints = get_unique_constraints

    actual = module.actual_contract(Inspector(), "sample")
    assert actual["columns"]["created_at"]["type"] == "TIMESTAMP WITH TIME ZONE"
