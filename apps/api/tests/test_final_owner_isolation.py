from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
import test_ai_integration as ai_fixture

pytestmark = pytest.mark.integration
pytest_plugins = ("test_ai_integration",)
ORIGIN = {"Origin": "http://127.0.0.1:4200"}


def test_single_owner_installation_boundary_and_forged_context_matrix(client: Any) -> None:
    context = ai_fixture.setup_context(client)
    forged = str(uuid4())

    second_owner = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Second Owner",
            "email": "second@example.com",
            "password": ai_fixture.PASSWORD,
            "password_confirmation": ai_fixture.PASSWORD,
        },
        headers=ORIGIN,
    )
    assert second_owner.status_code == 409

    cases: list[tuple[str, str, str, dict[str, object] | None]] = [
        ("brand read", "GET", f"/api/v1/brands/{forged}", None),
        ("product read", "GET", f"/api/v1/products/{forged}", None),
        ("media read", "GET", f"/api/v1/media/{forged}", None),
        ("content read", "GET", f"/api/v1/ai/artifacts/{forged}", None),
        ("image read", "GET", f"/api/v1/ai/images/outputs/{forged}", None),
        ("video read", "GET", f"/api/v1/ai/video/generations/{forged}", None),
        ("bulk video read", "GET", f"/api/v1/ai/video/bulk/{forged}", None),
        ("social read", "GET", f"/api/v1/social/posts/{forged}", None),
        ("marketplace read", "GET", f"/api/v1/marketplaces/listings/{forged}", None),
        ("campaign read", "GET", f"/api/v1/campaigns/{forged}", None),
        ("ads account read", "GET", f"/api/v1/ads/accounts/{forged}", None),
        ("ads campaign read", "GET", f"/api/v1/ads/campaigns/{forged}", None),
        ("marketing plan read", "GET", f"/api/v1/ads/plans/{forged}", None),
        ("product channel read", "GET", f"/api/v1/ads/product-channel/{forged}", None),
        ("campaign action", "POST", f"/api/v1/campaigns/{forged}/validate", {}),
        ("ads reconcile", "POST", f"/api/v1/ads/campaigns/{forged}/reconcile", {}),
        (
            "ads recovery",
            "POST",
            "/api/v1/ads/recovery",
            {
                "action": "reconcile",
                "entity_type": "campaign",
                "entity_id": forged,
                "confirm": True,
            },
        ),
        (
            "campaign recovery",
            "POST",
            "/api/v1/campaigns/recovery/actions",
            {
                "action": "retry_activity",
                "campaign_id": forged,
                "activity_id": forged,
                "confirm": True,
            },
        ),
        (
            "video recovery",
            "GET",
            f"/api/v1/ai/video/generations/{forged}/recovery",
            None,
        ),
        (
            "marketing plan action",
            "POST",
            f"/api/v1/ads/plans/{forged}/actions",
            {"action": "pause", "confirm": True},
        ),
    ]
    assert len(cases) == 20
    for label, method, path, payload in cases:
        response = client.request(method, path, json=payload, headers=ORIGIN)
        allowed = {200, 404, 405, 422} if label == "product channel read" else {404, 405, 422}
        assert response.status_code in allowed, f"{label}: {response.text}"
        assert all(
            marker not in response.text.lower()
            for marker in (
                "traceback",
                "postgresql://",
                "password",
                "cookie",
                "token",
                "file://",
            )
        ), label

    assert context["brand"]["id"] != forged
    assert context["product"]["id"] != forged
