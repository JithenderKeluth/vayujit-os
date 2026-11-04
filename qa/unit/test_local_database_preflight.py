"""Pure guard tests: never connects to the application or any PostgreSQL server."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def module():
    source = Path(__file__).resolve().parents[2] / "scripts/preflight-local-database.py"
    spec = importlib.util.spec_from_file_location("local_db_preflight", source)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_exact_confirmed_local_target_only(module):
    assert module.allowed_target("127.0.0.1", 5432, "vayujit")


@pytest.mark.parametrize(
    ("host", "port", "name"),
    [
        ("localhost", 5432, "vayujit"),
        ("192.168.1.5", 5432, "vayujit"),
        (None, 5432, "vayujit"),
        ("127.0.0.1", 55432, "vayujit"),
        ("127.0.0.1", None, "vayujit"),
        ("127.0.0.1", 5432, "vayujit_golden_test"),
        ("127.0.0.1", 5432, "vayujit_business"),
        ("127.0.0.1", 5432, "postgres"),
        ("127.0.0.1", 5432, "vayujit_qa0123456789abcdef_test"),
        ("127.0.0.1", 5432, None),
        ("127.0.0.1", 5432, "vayujit; DROP DATABASE other"),
    ],
)
def test_other_targets_fail_closed(module, host, port, name):
    assert not module.allowed_target(host, port, name)
