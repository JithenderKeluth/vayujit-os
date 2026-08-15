from __future__ import annotations

import uuid
from typing import Any, cast

from vayujit_api.commerce.marketplace_video import (
    MARKETPLACE_VIDEO_CAPABILITIES,
    VIDEO_FAILURE_ACTIONS,
    fake_video_connector_state,
    video_connector_for,
)


def test_marketplace_video_capabilities_are_normalized_and_local_only() -> None:
    assert set(MARKETPLACE_VIDEO_CAPABILITIES) == {"amazon", "flipkart", "meesho"}
    for raw_capability in MARKETPLACE_VIDEO_CAPABILITIES.values():
        capability = cast(Any, raw_capability)
        assert capability["supports_video"] is True
        assert capability["ruleset"] == "LOCAL FAKE-CERTIFIED RULESET"
        assert "video/mp4" in capability["mime_types"]
        assert capability["attachment_support"] is True
        assert capability["reconciliation_support"] is True


def test_fake_marketplace_connectors_are_deterministic_and_idempotent() -> None:
    listing_id = uuid.uuid4()
    product_id = uuid.uuid4()
    output_id = uuid.uuid4()
    for marketplace in ("amazon", "flipkart", "meesho"):
        connector = video_connector_for(marketplace)
        before = connector.mutations
        first = connector.attach(
            listing_id=listing_id,
            product_id=product_id,
            output_id=output_id,
            version=2,
            operation="attach",
        )
        second = connector.attach(
            listing_id=listing_id,
            product_id=product_id,
            output_id=output_id,
            version=2,
            operation="attach",
        )
        assert first["remote_video_id"] == second["remote_video_id"]
        assert connector.mutations == before + 1
        assert connector.lookup(str(first["remote_video_id"]))["state"] == "active"
    assert all(
        cast(Any, value)["remote_count"] >= 1 for value in fake_video_connector_state().values()
    )


def test_video_recovery_matrix_has_twelve_server_actions() -> None:
    assert len(VIDEO_FAILURE_ACTIONS) == 12
    ambiguous = cast(Any, VIDEO_FAILURE_ACTIONS["commerce.video.ambiguous_result"])
    assert ambiguous == ["reconcile", "review_failure"]
    stale = cast(Any, VIDEO_FAILURE_ACTIONS["commerce.video.stale_video"])
    assert "replace_video" in stale
