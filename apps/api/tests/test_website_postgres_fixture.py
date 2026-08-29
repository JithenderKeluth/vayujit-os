# mypy: ignore-errors
from __future__ import annotations

import pytest

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_postgres_fixture_is_guarded(client) -> None:
    assert client.get("/api/v1/auth/setup-status").status_code == 200
