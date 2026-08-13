import pytest

from vayujit_api.ai.failures import failure_spec

CASES = {
    "ai.video.provider_unavailable": (
        {"retry_generation", "change_provider", "review_failure"},
        {"regenerate"},
    ),
    "ai.video.throttled": ({"retry_generation", "review_failure"}, {"change_provider"}),
    "ai.video.timeout": (
        {"retry_generation", "change_provider", "review_failure"},
        {"remove_audio"},
    ),
    "ai.video.invalid_output": (
        {"regenerate", "change_provider", "change_model", "review_failure"},
        {"retry_generation"},
    ),
    "ai.video.output_too_large": (
        {"edit_script", "open_storyboard", "regenerate", "review_failure"},
        {"retry_generation"},
    ),
    "ai.video.unsupported_operation": (
        {"change_provider", "change_model", "open_storyboard", "edit_script", "review_failure"},
        {"retry_generation"},
    ),
    "ai.video.source_missing": (
        {"open_source_media", "replace_media", "review_failure"},
        {"retry_generation"},
    ),
    "ai.video.source_changed": (
        {"open_source_media", "replace_media", "regenerate", "review_failure"},
        {"retry_generation"},
    ),
    "ai.video.checkpoint_invalid": (
        {"retry_generation", "regenerate", "review_failure"},
        {"remove_audio"},
    ),
    "ai.video.render_failed": (
        {"retry_generation", "change_provider", "change_model", "review_failure"},
        {"remove_audio"},
    ),
    "ai.video.audio_failed": (
        {"remove_audio", "replace_media", "retry_generation", "review_failure"},
        {"change_model"},
    ),
    "ai.video.caption_failed": (
        {"edit_script", "review_failure", "retry_generation", "regenerate"},
        {"remove_audio"},
    ),
}


@pytest.mark.parametrize("code,expected_forbidden", CASES.items())
def test_video_recovery_action_matrix(code, expected_forbidden):
    expected, forbidden = expected_forbidden
    spec = failure_spec(code)
    actions = set(spec.recovery_actions)
    assert expected <= actions
    assert forbidden.isdisjoint(actions)
    assert spec.safe_message
    assert all("retry" not in action or spec.retryable for action in actions)


def test_video_recovery_taxonomy_has_exactly_twelve_failure_codes():
    assert len(CASES) == 12
