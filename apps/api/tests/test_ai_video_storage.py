from vayujit_api.video.inspection import inspect_video
from vayujit_api.video.provider import video_provider


def test_video_storage_metadata_matches_inspection():
    data, _ = video_provider.generate(seed="storage", width=320, height=240, duration=2)
    inspection = inspect_video(data)
    assert inspection.container == "mp4"
    assert inspection.width > 0
    assert inspection.height > 0
    assert inspection.size_bytes == len(data)
