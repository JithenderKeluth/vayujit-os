import pytest

from vayujit_api.video.inspection import VideoInspectionError, inspect_video
from vayujit_api.video.provider import video_provider


def test_local_video_provider_is_deterministic_and_parseable() -> None:
    first, metadata = video_provider.generate(seed="same", width=320, height=240, duration=2)
    second, second_metadata = video_provider.generate(
        seed="same", width=320, height=240, duration=2
    )
    assert first == second
    assert metadata == second_metadata
    inspection = inspect_video(first)
    assert inspection.container == "mp4"
    assert inspection.mime_type == "video/mp4"
    assert inspection.video_stream_count == 1
    assert inspection.audio_stream_count == 0
    assert inspection.duration_seconds > 0
    assert inspection.width > 0 and inspection.height > 0
    assert inspection.frame_rate and inspection.frame_rate > 0
    assert inspection.size_bytes == len(first)
    health = video_provider.health()
    assert health["local"] is True
    assert health["live_provider_supported"] is False
    assert health["visual_effect_simulated"] is True
    assert health["workflow_supported"] is True


def test_local_provider_failure_scenarios_are_explicit() -> None:
    for scenario in ("provider_unavailable", "unsupported_operation", "policy_rejection"):
        try:
            video_provider.generate(
                seed=scenario, width=320, height=240, duration=2, scenario=scenario
            )
        except (RuntimeError, ValueError, PermissionError) as error:
            assert scenario.split("_")[0] in str(error).lower() or scenario in str(error).lower()
        else:
            raise AssertionError(f"scenario {scenario} did not fail")
    invalid, _ = video_provider.generate(
        seed="invalid", width=320, height=240, duration=2, scenario="invalid_video"
    )
    truncated, _ = video_provider.generate(
        seed="truncated", width=320, height=240, duration=2, scenario="truncated_output"
    )
    oversized, _ = video_provider.generate(
        seed="oversized", width=320, height=240, duration=2, scenario="oversized_video"
    )
    with pytest.raises(VideoInspectionError):
        inspect_video(invalid)
    with pytest.raises(VideoInspectionError):
        inspect_video(truncated)
    assert len(oversized) > 8_000_000
