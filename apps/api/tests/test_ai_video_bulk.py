import uuid

import pytest

from vayujit_api.video.bulk import VideoBulkRequest, _validate_limits

pytestmark = pytest.mark.integration


def test_video_bulk_scope_is_explicitly_bounded() -> None:
    request = VideoBulkRequest(
        product_ids=[uuid.uuid4()],
        video_types=["youtube_video"],
        targets=["youtube"],
        idempotency_key="bulk-scope",
    )
    _validate_limits(request)
