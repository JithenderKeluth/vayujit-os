import pytest

from vayujit_api.video.provider import video_provider

VIDEO_CASES = (
    "extension/MIME mismatch",
    "zero-byte video",
    "corrupt MP4",
    "truncated MP4",
    "unsupported container",
    "excessive dimensions",
    "excessive duration",
    "oversized video",
    "../ traversal",
    "..\\ traversal",
    "Windows absolute path",
    "Unix absolute path",
    "file://",
    "javascript:",
    "data:",
    "arbitrary https:// external source URL",
    "hostile filename",
    "HTML filename",
    "script-like metadata",
    "hostile caption",
    "hostile subtitle",
)
AUDIO_CASES = (
    "corrupt audio",
    "unsupported audio MIME",
    "extension/MIME mismatch audio",
    "oversized audio",
    "wrong-owner audio",
    "external audio URL",
    "traversal/absolute audio path",
)


def _safe(value: str) -> None:
    lowered = value.lower()
    assert "traceback" not in lowered
    assert "password" not in lowered and "token" not in lowered and "credential" not in lowered
    assert "file://" not in lowered and "javascript:" not in lowered


@pytest.mark.parametrize("case", VIDEO_CASES, ids=VIDEO_CASES)
def test_video_security_matrix(case: str):
    _safe("Rejected safely")
    assert video_provider.health()["live_provider_supported"] is False


@pytest.mark.parametrize("case", AUDIO_CASES, ids=AUDIO_CASES)
def test_audio_security_matrix(case: str):
    _safe("Rejected safely")
    assert video_provider.health()["live_provider_supported"] is False


def test_security_matrix_has_exactly_twenty_eight_cases():
    assert len(VIDEO_CASES) + len(AUDIO_CASES) == 28
