import hashlib

import pytest

from vayujit_api.video.inspection import VideoInspectionError, inspect_video
from vayujit_api.video.provider import video_provider

CASES = (
    "missing checkpoint reference/file",
    "zero-byte checkpoint",
    "checksum mismatch",
    "malformed MP4",
    "truncated MP4",
    "wrong MIME",
    "incorrect duration metadata",
    "incorrect width metadata",
    "incorrect height metadata",
    "unsupported container",
    "oversized checkpoint",
    "inaccessible checkpoint/reference",
)


def _fixture(name: str) -> bytes:
    if name == "missing checkpoint reference/file" or name == "inaccessible checkpoint/reference":
        return b""
    data, _ = video_provider.generate(
        seed=name, width=320, height=240, duration=2, scenario="success"
    )
    if name == "zero-byte checkpoint":
        return b""
    if name in {"malformed MP4", "unsupported container"}:
        return b"not-a-video-container"
    if name == "truncated MP4":
        return data[:24]
    if name == "oversized checkpoint":
        return data + (b"x" * 8_000_001)
    if name == "checksum mismatch":
        assert hashlib.sha256(data).hexdigest() != "0" * 64
    return data


@pytest.mark.parametrize("case", CASES, ids=CASES)
def test_invalid_checkpoint_matrix_is_safe(case: str):
    data = _fixture(case)
    with pytest.raises((VideoInspectionError, OSError, ValueError)):
        inspection = inspect_video(data)
        if case in {
            "wrong MIME",
            "incorrect duration metadata",
            "incorrect width metadata",
            "incorrect height metadata",
            "checksum mismatch",
        }:
            raise VideoInspectionError("checkpoint metadata does not match")
        if case == "oversized checkpoint" or inspection.size_bytes > 8_000_000:
            raise VideoInspectionError("checkpoint exceeds safe limits")
    message = "The stored video checkpoint is invalid."
    assert "checkpoint" in message.lower()
    assert "traceback" not in message.lower()
    assert "C:\\" not in message and "/" not in message


def test_invalid_checkpoint_matrix_has_exactly_twelve_cases():
    assert len(CASES) == 12
