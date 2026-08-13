from vayujit_api.video.provider import video_provider


def test_video_provider_context_is_local_and_minimal():
    health = video_provider.health()
    assert health["local"] is True
    assert health["live_provider_supported"] is False
    assert health["workflow_supported"] is True
