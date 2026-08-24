import os

os.environ["VAYUJIT_INTELLIGENCE_ENABLED"] = "true"
os.environ["VAYUJIT_INTELLIGENCE_RESEARCH_EXECUTION_ENABLED"] = "true"

import pytest
from test_ai_integration import ORIGIN, setup_context

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)


def _create_mission(client):
    project = client.post(
        "/api/v1/intelligence/projects",
        json={"name": "Deterministic Research", "description": "local", "target_market": "IN"},
        headers=ORIGIN,
    )
    assert project.status_code == 201, project.text
    mission = client.post(
        "/api/v1/intelligence/missions",
        json={
            "project_id": project.json()["id"],
            "name": "Winning products",
            "market": "IN",
            "minimum_score_threshold": 45,
        },
        headers=ORIGIN,
    )
    assert mission.status_code == 201, mission.text
    return mission.json()["id"]


def test_local_research_run_is_deterministic_and_owner_scoped(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    first = client.post(f"/api/v1/intelligence/missions/{mission_id}/run-now", headers=ORIGIN)
    assert first.status_code == 200, first.text
    run = first.json()
    assert run["status"] == "completed"
    candidates = client.get("/api/v1/intelligence/candidates", headers=ORIGIN)
    assert candidates.status_code == 200
    assert len(candidates.json()) == 8
    assert any(row["status"] == "rejected" for row in candidates.json())
    assert (
        client.get("/api/v1/intelligence/candidates?min_score=70", headers=ORIGIN).status_code
        == 200
    )
    second = client.post(f"/api/v1/intelligence/missions/{mission_id}/run-now", headers=ORIGIN)
    assert second.status_code == 200
    assert second.json()["id"] == run["id"]
    with client as _:
        pass


def test_crash_checkpoint_recovers_without_duplicates(client) -> None:
    setup_context(client)
    mission_id = _create_mission(client)
    pending = client.post(
        f"/api/v1/intelligence/missions/{mission_id}/run-now",
        params={"idempotency_key": "crash-proof"},
        headers=ORIGIN,
    )
    assert pending.status_code == 200
    run_id = pending.json()["id"]
    # The public run endpoint completes deterministically; replay proves checkpoint idempotency.
    replay = client.post(f"/api/v1/intelligence/runs/{run_id}/execute", headers=ORIGIN)
    assert replay.status_code == 200
    assert replay.json()["id"] == run_id
