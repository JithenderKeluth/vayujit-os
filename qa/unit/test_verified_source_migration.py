"""Source-operation guards only. Never opens a database or stops any process."""

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(scope="module")
def module():
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "source_migration", scripts / "apply_verified_local_migration.py"
        )
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        return loaded
    finally:
        sys.path.remove(str(scripts))


def test_only_exact_owner_approved_source_is_allowed(module):
    assert module.source_url_allowed(
        make_url("postgresql+psycopg://vayujit@127.0.0.1:5432/vayujit")
    )


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://vayujit@localhost:5432/vayujit",
        "postgresql://vayujit@127.0.0.1:55432/vayujit",
        "postgresql://postgres@127.0.0.1:5432/vayujit",
        "postgresql://vayujit@127.0.0.1:5432/vayujit_golden_test",
        "postgresql://vayujit@127.0.0.1:5432/postgres",
        "postgresql://vayujit@127.0.0.1:5432/vayujit_qa0123456789abcdef_test",
        "postgresql://vayujit@192.168.1.2:5432/vayujit",
        "sqlite:///vayujit",
    ],
)
def test_unapproved_targets_roles_and_instances_are_denied(module, url):
    assert not module.source_url_allowed(make_url(url))


def test_exact_repair_count_contract_cannot_include_extra_operations(module):
    operations = [{"operation": "set_canonical_default"}] * 31 + [
        {"operation": "add_canonical_index"}
    ] * 24
    assert module.exact_plan(operations)
    assert not module.exact_plan(operations + [{"operation": "drop_table"}])
    assert not module.exact_plan(operations[:-1])


def test_empty_preservation_contract_is_rejected_before_any_query(module):
    class NeverConnect:
        def scalar(self, statement):
            pytest.fail("No query is allowed for an empty preservation contract")

    with pytest.raises(module.safe.SafeFailure, match="preservation_contract_missing"):
        module.verify_records(
            NeverConnect(),
            {"preservation": {"columns": {}, "fingerprints": {}}},
            migrated=False,
        )
