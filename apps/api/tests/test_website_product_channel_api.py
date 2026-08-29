from __future__ import annotations

import uuid

import pytest
from website_postgres_fixture import ORIGIN, run_website_research

from vayujit_api.intelligence.autonomous_models import AutonomousResearchMission

pytest_plugins = ("website_postgres_fixture",)
pytestmark = pytest.mark.integration


def create_product(client, suffix: str = "") -> dict[str, object]:
    brand = client.post(
        "/api/v1/brands",
        json={"name": f"Channel Brand {suffix}"},
        headers=ORIGIN,
    )
    assert brand.status_code == 201, brand.text
    response = client.post(
        "/api/v1/products",
        json={
            "name": f"Channel Product {suffix}",
            "product_type": "physical",
            "short_description": "Disposable channel fixture",
            "description": "A bounded Product Channel fixture.",
            "category": "Fixtures",
            "tags": ["fixture"],
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_product_channel_owner_safety_rejects_foreign_product_reference(client) -> None:
    response = client.get(
        f"/api/v1/intelligence/websites/product-channel/{uuid.uuid4()}",
        headers=ORIGIN,
    )
    assert response.status_code == 404
    assert "traceback" not in response.text.lower()
    assert "sql" not in response.text.lower()


def test_product_channel_no_research_is_unknown_and_zeroed(client) -> None:
    product = create_product(client, "empty")
    response = client.get(
        f"/api/v1/intelligence/websites/product-channel/{product['id']}",
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["website_research_status"] == "not_started"
    assert value["manufacturer_candidate_count"] == 0
    assert value["supplier_website_candidate_count"] == 0
    assert value["offering_count"] == 0
    assert value["freshness"] == "UNKNOWN"
    assert value["confidence"] == 0
    assert value["risk"] == []
    assert value["verification"] == "UNKNOWN"
    assert value["follow_up_required"] is False


def test_product_channel_projection_uses_persisted_website_data(client, db_session) -> None:
    product = create_product(client, "researched")
    seeded = run_website_research(
        client,
        content=(
            "Company Name: Channel Fixture Manufacturer. Product: Channel Fixture. "
            "MOQ: 100 units Lead time: 20 days OEM ISO certificate."
        ),
    )
    mission = db_session.get(AutonomousResearchMission, seeded["mission_id"])
    assert mission is not None
    mission.product_id = uuid.UUID(str(product["id"]))
    mission.scope = {**(mission.scope or {}), "candidate_id": str(product["id"])}
    db_session.commit()
    response = client.get(
        f"/api/v1/intelligence/websites/product-channel/{product['id']}",
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["website_research_status"] == "available"
    assert value["offering_count"] >= 0
    assert value["confidence"] != "UNKNOWN"
    assert "risk" in value
    assert "verification" in value
    assert value["product_id"] == str(product["id"])
