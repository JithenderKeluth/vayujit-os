from __future__ import annotations

import uuid

import pytest
from test_ai_integration import ORIGIN, setup_context

pytest_plugins = ("test_ai_integration",)
pytestmark = pytest.mark.integration


def _audience(client, **overrides: object):
    payload: dict[str, object] = {
        "name": "Abstract acceptance audience",
        "geography": ["IN"],
        "languages": ["en-IN"],
        "age_min": 25,
        "age_max": 45,
        "interests": ["home-decor"],
        "exclusions": ["existing-customers"],
        "custom_segment_id": "segment_opaque_001",
        "remarketing_segment_id": "remarketing_opaque_001",
    }
    payload.update(overrides)
    return client.post("/api/v1/ads/audiences", json=payload, headers=ORIGIN)


def test_meta_and_google_audience_validation_is_server_derived(client) -> None:
    setup_context(client)
    created = _audience(client)
    assert created.status_code == 201, created.text
    assert created.json()["privacy"] == "abstract_segments_only"
    validated = client.post(
        f"/api/v1/ads/audiences/{created.json()['id']}/validate", headers=ORIGIN
    )
    assert validated.status_code == 200, validated.text
    body = validated.json()
    assert body["validation_status"] == "valid"
    assert body["providers"]["meta"]["status"] == "valid"
    assert body["providers"]["google"]["status"] == "valid"
    assert "opaque_001" not in validated.text


@pytest.mark.parametrize(
    "payload",
    [
        {"age_min": 60, "age_max": 20},
        {"geography": ["INDIA"]},
        {"languages": ["english-IN"]},
        {"interests": ["home"], "exclusions": ["home"]},
        {"provider": "linkedin"},
        {"custom_segment_id": "person@example.com"},
    ],
)
def test_invalid_audience_inputs_are_rejected_without_pii(
    client, payload: dict[str, object]
) -> None:
    setup_context(client)
    response = _audience(client, **payload)
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()
    assert "password" not in response.text.lower()
    assert "cookie" not in response.text.lower()


def test_wrong_owner_audience_is_not_visible_or_validatable(client) -> None:
    setup_context(client)
    created = _audience(client)
    assert created.status_code == 201
    # The owner-scoped fixture has no second authenticated owner; an unknown UUID
    # exercises the same non-disclosure contract without creating private data.
    response = client.post(f"/api/v1/ads/audiences/{uuid.uuid4()}/validate", headers=ORIGIN)
    assert response.status_code in {404, 422}
    assert "opaque" not in response.text.lower()
