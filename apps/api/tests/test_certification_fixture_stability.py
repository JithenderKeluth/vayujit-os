from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.certification_infrastructure


@pytest.mark.parametrize("run_number", range(1, 21))
def test_disposable_fixture_lifecycle_is_stable(
    client: TestClient,
    run_number: int,
) -> None:
    del run_number
    response = client.get("/health")
    assert response.status_code == 200
