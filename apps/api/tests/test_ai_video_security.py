import pytest

from vayujit_api.video.provider import video_provider


def test_video_security_boundaries_are_network_free() -> None:
    assert video_provider.health()["live_provider_supported"] is False
    for scenario in ("provider_unavailable", "unsupported_operation", "policy_rejection"):
        with pytest.raises((RuntimeError, ValueError, PermissionError)):
            video_provider.generate(
                seed=scenario, width=320, height=240, duration=2, scenario=scenario
            )
    invalid, _ = video_provider.generate(
        seed="invalid", width=320, height=240, duration=2, scenario="invalid_video"
    )
    truncated, _ = video_provider.generate(
        seed="truncated", width=320, height=240, duration=2, scenario="truncated_output"
    )
    oversized, _ = video_provider.generate(
        seed="oversized", width=320, height=240, duration=2, scenario="oversized_video"
    )
    assert not invalid.startswith(b"\x00\x00\x00\x18ftyp")
    assert truncated.startswith(b"\x00\x00\x00\x18ftyp")
    assert len(oversized) > 8_000_000
