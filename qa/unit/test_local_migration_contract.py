"""Pure contract recording tests; no engine, Docker or database access."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def module():
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts/audit_local_migration_contract.py"
    )
    spec = importlib.util.spec_from_file_location("contract_audit", source)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_capture_does_not_invoke_real_alembic_operations(module, monkeypatch):
    from alembic import op

    def denied(*args, **kwargs):
        pytest.fail("Live Alembic operation must not be invoked")

    for name in ("create_table", "create_index", "add_column", "create_foreign_key"):
        monkeypatch.setattr(op, name, denied)
    contracts = module.expected_contracts()
    assert len(contracts) == 3
    table = contracts["intelligence_supplier_comparison_snapshots"]
    assert table["primary_key"] == ["id"]
    assert table["columns"]["snapshot_version"] == {
        "type": "INTEGER",
        "nullable": False,
        "default": "1",
    }
    assert ["owner_id", "idempotency_key"] in table["unique_constraints"]
    assert len(table["indexes"]) == 8


def test_human_and_reference_contracts_are_retained(module):
    table = module.expected_contracts()[
        "intelligence_supplier_procurement_readiness_acknowledgements"
    ]
    assert table["columns"]["provenance"]["default"] == "HUMAN"
    assert {
        "columns": ["actor_id"],
        "targets": ["users.id"],
        "ondelete": "RESTRICT",
    } in table["foreign_keys"]
    assert table["indexes"]["ix_pr8c_ack_assessment"] == {
        "columns": ["owner_id", "assessment_id"],
        "unique": False,
    }


@pytest.mark.parametrize("key", ["columns", "primary_key", "foreign_keys", "indexes"])
def test_missing_contract_is_never_silently_equivalent(module, key):
    assert key in module.differences({key: ["required"]}, {})


def test_default_representations_require_review_not_automatic_adoption(module):
    expected = {"columns": {"version": {"default": "1"}}}
    actual = {"columns": {"version": {"default": "'1'::integer"}}}
    assert "columns" in module.differences(expected, actual)


def test_identical_contract_reports_no_differences(module):
    assert module.differences({"primary_key": ["id"]}, {"primary_key": ["id"]}) == {}
