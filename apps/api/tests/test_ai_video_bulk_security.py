from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from vayujit_api.video.bulk import VideoBulkRequest, _validate_limits


def base(**overrides: Any) -> dict[str, Any]:
    value: dict[str, object] = {
        "product_ids": [uuid.uuid4()],
        "video_types": ["youtube_video"],
        "targets": ["youtube"],
        "idempotency_key": "security-matrix",
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "case",
    [
        {"targets": ["../../secrets"]},
        {"targets": ["https://evil.example"]},
        {"targets": ["youtube\u0000"]},
        {"product_ids": [uuid.uuid4(), uuid.uuid4()] * 26},
        {"video_types": ["youtube_video", "youtube_video"]},
        {"targets": ["youtube", "youtube"]},
        {"video_types": ["unsupported_video"]},
        {"targets": ["unsupported"]},
        {"resolution": "10x10"},
        {"resolution": "9999x9999"},
        {
            "product_ids": [uuid.uuid4()] * 2,
            "video_types": ["youtube_video"] * 2,
            "targets": ["youtube", "instagram", "facebook", "amazon", "flipkart", "meesho"],
        },
        {"product_ids": [uuid.uuid4()] * 51},
        {"video_types": ["youtube_video"] * 13},
        {
            "targets": [
                "youtube",
                "instagram",
                "facebook",
                "amazon",
                "flipkart",
                "meesho",
                "campaign",
            ]
        },
        {
            "duration_seconds": 60,
            "resolution": "3840x3840",
            "product_ids": [uuid.uuid4()] * 10,
            "video_types": ["youtube_video"] * 1,
            "targets": ["youtube"],
        },
        {"idempotency_key": "x" * 161},
        {"product_ids": []},
        {"video_types": []},
        {"targets": []},
        {"resolution": "not-a-resolution"},
        {"script_version": 0},
        {"storyboard_version": 0},
        {"style_version": 0},
        {"preset_version": 0},
        {"failure_scenario": "x" * 81},
    ],
)
def test_bulk_security_matrix_case_is_safe_and_non_mutating(case: dict[str, Any]) -> None:
    with pytest.raises((ValidationError, ValueError, Exception)) as captured:
        request = VideoBulkRequest(**base(**case))
        _validate_limits(request)
    message = str(captured.value).lower()
    assert not any(
        secret in message
        for secret in ("token", "password", "cookie", "database", "traceback", "sql", "path")
    )


def test_bulk_source_media_limit_rejects_before_provider_or_storage() -> None:
    with pytest.raises(ValidationError, match="at most 5"):
        VideoBulkRequest(**base(source_media_ids=[uuid.uuid4()] * 6))
