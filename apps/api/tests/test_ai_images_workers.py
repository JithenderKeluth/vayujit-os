from vayujit_api.ai.image_provider import image_provider
from vayujit_api.ai.studio_worker import calculate_backoff


def test_image_retry_backoff_uses_shared_runtime_rules() -> None:
    assert calculate_backoff(1) == (1, 1)
    assert calculate_backoff(3, retry_after=5)[1] >= 5


def test_crash_after_result_scenario_is_deterministic() -> None:
    image, metadata = image_provider.generate(
        operation="generate_product_image",
        width=64,
        height=64,
        seed="crash",
        scenario="crash_after_result",
    )
    assert image.startswith(b"\x89PNG")
    assert metadata["scenario"] == "crash_after_result"
