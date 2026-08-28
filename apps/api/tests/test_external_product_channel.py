from __future__ import annotations

from typing import Any

import pytest
import test_ai_integration as integration

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
SAFE_MARKERS = (
    "password",
    "authorization",
    "cookie",
    "postgresql://",
    "traceback",
    "file://",
)


def test_external_product_channel_projection_and_owner_safety(client: Any) -> None:
    context = integration.setup_context(client)
    product_id = context["product"]["id"]
    response = client.get(
        f"/api/v1/intelligence/external/products/{product_id}/channel",
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    required = {
        "external_research_status",
        "last_external_research_at",
        "external_evidence_count",
        "verified_external_evidence_count",
        "supported_external_evidence_count",
        "stale_external_evidence_count",
        "expired_external_evidence_count",
        "external_conflict_count",
        "external_confidence",
        "last_material_change_at",
        "follow_up_required",
    }
    assert required <= body.keys()
    assert set(body["actions"]) <= {
        "view_external_research",
        "refresh_external_research",
        "review_conflicts",
        "review_evidence",
    }
    assert not any(marker in response.text.lower() for marker in SAFE_MARKERS)
    forged = client.get(
        "/api/v1/intelligence/external/products/00000000-0000-4000-8000-000000000001/channel",
        headers=ORIGIN,
    )
    assert forged.status_code == 404
