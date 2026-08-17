import uuid

import pytest

from vayujit_api.video.bulk import VideoBulkRequest, _child_key, _validate_limits

pytestmark = pytest.mark.integration


def request(**overrides):
    value = {
        "product_ids": [uuid.uuid4()],
        "video_types": ["youtube_video"],
        "targets": ["youtube"],
        "idempotency_key": "core",
    }
    value.update(overrides)
    return VideoBulkRequest(**value)


def test_bulk_limits_are_bounded_and_child_identity_is_deterministic():
    data = request()
    _validate_limits(data)
    parent = uuid.uuid4()
    owner = uuid.uuid4()
    product = data.product_ids[0]
    assert _child_key(owner, parent, product, "youtube_video", "youtube", data, 1) == _child_key(
        owner, parent, product, "youtube_video", "youtube", data, 1
    )
    assert _child_key(owner, parent, product, "youtube_video", "youtube", data, 1) != _child_key(
        owner, parent, product, "youtube_video", "youtube", data, 2
    )


def test_bulk_rejects_excessive_output_matrix():
    with pytest.raises(Exception, match="safe limit"):
        _validate_limits(
            request(
                product_ids=[uuid.uuid4()] * 2,
                video_types=["youtube_video"] * 2,
                targets=["youtube", "instagram", "facebook", "amazon", "flipkart", "meesho"],
            )
        )
