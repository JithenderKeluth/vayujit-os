from __future__ import annotations

import copy
import uuid
from typing import Any

import pytest
import test_ai_integration as ai_fixture
import test_ai_video_slice3_channels as video_fixture
from sqlalchemy import func, select
from test_campaign_video_execution import ORIGIN, _approved_lineage, _campaign, _factory, _request

from vayujit_api.publishing.models import PublishingJob, PublishingSchedule
from vayujit_api.social.connectors import FAKE_CONNECTOR_CALLS

client = ai_fixture.client
pytestmark = pytest.mark.integration


def _safe(response: Any) -> None:
    text = response.text.lower()
    assert response.status_code < 500, response.text
    for forbidden in (
        "traceback",
        "sqlalchemy",
        "postgresql://",
        "c:\\\\users",
        "site-packages",
        "secret-token-value",
        "cookie-value",
    ):
        assert forbidden not in text


def test_campaign_video_security_matrix_20_cases_has_no_execution_side_effects(
    client: Any,
) -> None:
    FAKE_CONNECTOR_CALLS.clear()
    context = ai_fixture.setup_context(client)
    campaign = _campaign(client, context)
    lineage = _approved_lineage(client, context, "youtube_video", "youtube")
    account_id = video_fixture._account(client, "youtube", "-security")
    disabled = client.post(
        "/api/v1/social/accounts",
        json={
            "platform": "youtube",
            "display_name": "Disabled local account",
            "remote_account_id": "disabled-security-account",
            "capabilities": {"supported_content_types": ["youtube_video"]},
        },
        headers=ORIGIN,
    )
    assert disabled.status_code == 201, disabled.text
    base = _request(context, lineage, account_id, "youtube_video")

    def random_id() -> str:
        return str(uuid.uuid4())

    preview_cases: list[tuple[str, dict[str, object]]] = [
        ("wrong_product", {"product_id": random_id()}),
        ("wrong_video", {"video_generation_id": random_id()}),
        ("unapproved_video", {"metadata_artifact_id": random_id()}),
        ("stale_video", {"video_version": 99}),
        ("wrong_social_account", {"target_account_id": random_id()}),
        (
            "wrong_marketplace_account",
            {
                "video_channel": "amazon",
                "target_account_id": random_id(),
                "target_listing_id": random_id(),
            },
        ),
        (
            "wrong_listing",
            {
                "video_channel": "amazon",
                "target_account_id": random_id(),
                "target_listing_id": random_id(),
            },
        ),
        ("disabled_account", {"target_account_id": disabled.json()["id"]}),
        ("invalid_schedule", {"timezone_name": "Invalid/Local/Zone"}),
        ("hostile_metadata", {"metadata": {"prompt": "secret-token-value"}}),
        ("unsafe_url", {"metadata": {"description": "file://C:/private/value"}}),
        (
            "cross_owner_thumbnail",
            {
                "thumbnail_output_id": random_id(),
                "thumbnail_media_id": random_id(),
                "thumbnail_version": 1,
            },
        ),
        ("cross_owner_caption", {"caption_track_id": random_id(), "caption_version": 1}),
    ]
    outcomes: dict[str, int] = {}
    for name, overrides in preview_cases:
        payload = copy.deepcopy(base)
        payload.update(overrides)
        response = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
            json=payload,
            headers=ORIGIN,
        )
        _safe(response)
        assert response.status_code == 200 and response.json()["ready"] is False
        outcomes[name] = response.status_code

    wrong_campaign = client.post(
        f"/api/v1/campaigns/{random_id()}/video/activities/preview", json=base, headers=ORIGIN
    )
    _safe(wrong_campaign)
    assert wrong_campaign.status_code == 404
    outcomes["wrong_owner_campaign"] = 404
    wrong_activity = client.get(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{random_id()}/detail"
    )
    _safe(wrong_activity)
    assert wrong_activity.status_code == 404
    outcomes["wrong_owner_activity"] = 404
    for name in ("invalid_dependency", "cross_owner_dependency"):
        dependency = client.post(
            f"/api/v1/campaigns/{campaign['id']}/dependencies",
            json={
                "predecessor_activity_id": random_id(),
                "successor_activity_id": random_id(),
                "dependency_type": "success_required",
            },
            headers=ORIGIN,
        )
        _safe(dependency)
        assert dependency.status_code in {404, 409, 422}
        outcomes[name] = dependency.status_code

    valid_preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/preview",
        json=base,
        headers=ORIGIN,
    )
    assert valid_preview.status_code == 200 and valid_preview.json()["ready"] is True
    stale_payload = {**base, "metadata": {"title": "Changed after preview"}}
    stale_payload.update(
        {"preview_fingerprint": valid_preview.json()["fingerprint"], "confirm": True}
    )
    stale = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json=stale_payload,
        headers=ORIGIN,
    )
    _safe(stale)
    assert stale.status_code == 409
    outcomes["stale_preview"] = 409

    create_payload = dict(base)
    create_payload.update(
        {"preview_fingerprint": valid_preview.json()["fingerprint"], "confirm": True}
    )
    created = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities",
        json=create_payload,
        headers=ORIGIN,
    )
    assert created.status_code == 200, created.text
    activity = created.json()["activity"]
    replacement_payload = dict(base)
    replacement_payload.update(
        {
            "activity_id": activity["id"],
            "expected_activity_row_version": activity["row_version"],
            "idempotency_key": "security-stale-replacement",
        }
    )
    replacement_preview = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/replacement/preview",
        json=replacement_payload,
        headers=ORIGIN,
    )
    assert replacement_preview.status_code == 200, replacement_preview.text
    replacement_payload.update(
        {"preview_fingerprint": "0" * 64, "confirm": True, "reason": "Safe stale test."}
    )
    stale_replacement = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/replacement",
        json=replacement_payload,
        headers=ORIGIN,
    )
    _safe(stale_replacement)
    assert stale_replacement.status_code == 409
    outcomes["stale_replacement_fingerprint"] = 409

    cancelled = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activities/{activity['id']}/cancel", headers=ORIGIN
    )
    assert cancelled.status_code == 200, cancelled.text
    replay = client.post(
        f"/api/v1/campaigns/{campaign['id']}/video/activities/{activity['id']}/materialize",
        json={
            "preview_fingerprint": valid_preview.json()["fingerprint"],
            "expected_activity_row_version": activity["row_version"],
            "confirm": True,
        },
        headers=ORIGIN,
    )
    _safe(replay)
    assert replay.status_code == 409
    outcomes["cancelled_activity_replay"] = 409

    assert len(outcomes) == 20
    assert set(outcomes) == {
        "wrong_owner_campaign",
        "wrong_owner_activity",
        "wrong_product",
        "wrong_video",
        "unapproved_video",
        "stale_video",
        "wrong_social_account",
        "wrong_marketplace_account",
        "wrong_listing",
        "disabled_account",
        "stale_preview",
        "stale_replacement_fingerprint",
        "invalid_dependency",
        "cross_owner_dependency",
        "invalid_schedule",
        "hostile_metadata",
        "unsafe_url",
        "cross_owner_thumbnail",
        "cross_owner_caption",
        "cancelled_activity_replay",
    }
    assert not FAKE_CONNECTOR_CALLS
    with _factory() as db:
        assert db.scalar(select(func.count()).select_from(PublishingSchedule)) == 0
        assert db.scalar(select(func.count()).select_from(PublishingJob)) == 0
