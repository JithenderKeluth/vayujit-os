# mypy: ignore-errors
from __future__ import annotations

import pytest
from sqlalchemy import select
from website_postgres_fixture import run_website_research

from vayujit_api.intelligence.autonomous_models import AutonomousResearchContradiction
from vayujit_api.intelligence.website_models import WebsiteClaim

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def test_capability_contradiction_remains_reviewable_and_owner_scoped(client, db_session) -> None:
    run_website_research(
        client,
        content="Company Name: Capability Fixture. Product: Fixture Tray. OEM private label.",
    )
    run_website_research(
        client,
        content="Company Name: Capability Fixture. Product: Fixture Tray. Custom design only.",
    )
    claims = list(db_session.scalars(select(WebsiteClaim)))
    capabilities = [item for item in claims if item.claim_type == "CAPABILITY"]
    assert {item.claim_value["capability"] for item in capabilities} == {
        "OEM",
        "PRIVATE_LABEL",
        "CUSTOM_DESIGN",
    }
    assert all(item.status in {"CLAIMED", "NO_LONGER_OBSERVED"} for item in capabilities)
    mission_response = client.post(
        "/api/v1/intelligence/autonomous/missions",
        json={
            "mission_type": "PRICING_RESEARCH",
            "goal": "Contradiction fixture",
            "scope": {"provider_scenario": "conflicting"},
            "idempotency_key": "capability-contradiction",
        },
        headers={"Origin": "http://127.0.0.1:4200"},
    )
    assert mission_response.status_code == 201, mission_response.text
    mission_id = mission_response.json()["id"]
    run_response = client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
        json={"confirm": True},
        headers={"Origin": "http://127.0.0.1:4200"},
    )
    assert run_response.status_code == 200, run_response.text
    contradictions = list(db_session.scalars(select(AutonomousResearchContradiction)))
    assert len(contradictions) == 1
    assert contradictions[0].status == "UNRESOLVED"
    client.post(
        f"/api/v1/intelligence/autonomous/missions/{mission_id}/run",
        json={"confirm": True},
        headers={"Origin": "http://127.0.0.1:4200"},
    )
    assert len(list(db_session.scalars(select(AutonomousResearchContradiction)))) == 1
