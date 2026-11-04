"""The synthetic clock fixture cannot attach outside its exact QA installation."""

from types import SimpleNamespace

import pytest

from qa.wp7a7_fixture import install


@pytest.mark.parametrize(
    ("phase", "database"),
    [
        ("WP7A6", "vayujit_qa0123456789abcdef_test"),
        ("WP7A7", "vayujit"),
        ("WP7A7", "vayujit_golden_test"),
        ("WP7A7", "vayujit_qa1111111111111111_test"),
    ],
)
def test_clock_installation_rejects_wrong_phase_or_target(monkeypatch, phase, database):
    monkeypatch.setenv("QA_BROWSER_PHASE", phase)
    engine = SimpleNamespace(url=SimpleNamespace(database=database))
    with pytest.raises(ValueError, match="EXACT_WP7A7_REQUIRED"):
        install(None, "0123456789abcdef", engine)
