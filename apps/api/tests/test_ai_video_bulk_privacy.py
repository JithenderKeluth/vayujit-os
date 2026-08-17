import uuid

from vayujit_api.video.bulk import VideoBulkRequest, _json


def test_bulk_snapshot_serialization_contains_only_bounded_identifiers():
    data = VideoBulkRequest(
        product_ids=[uuid.uuid4()],
        video_types=["youtube_video"],
        targets=["youtube"],
        idempotency_key="privacy",
    )
    encoded = _json(
        {"products": [str(value) for value in data.product_ids], "targets": data.targets}
    )
    assert "token" not in encoded.lower()
    assert "password" not in encoded.lower()
    assert "database" not in encoded.lower()
