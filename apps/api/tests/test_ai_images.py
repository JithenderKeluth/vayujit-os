import pytest

from vayujit_api.ai.failures import StudioProviderFailure
from vayujit_api.ai.image_provider import deterministic_png, image_provider
from vayujit_api.media.service import image_dimensions


def test_deterministic_png_is_valid_and_repeatable() -> None:
    first = deterministic_png(32, 24, "stable")
    assert first == deterministic_png(32, 24, "stable")
    assert image_dimensions(first, "image/png") == (32, 24)


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("throttle", "provider_throttled"),
        ("timeout", "provider_timeout"),
        ("provider_error", "provider_unavailable"),
        ("policy_refusal", "policy_refusal"),
        ("unsupported_operation", "unsupported_provider"),
        ("oversized_output", "output_too_large"),
    ],
)
def test_image_provider_failure_scenarios_are_typed(scenario: str, code: str) -> None:
    with pytest.raises(StudioProviderFailure) as error:
        image_provider.generate(
            operation="generate_product_image", width=64, height=64, seed="test", scenario=scenario
        )
    assert error.value.spec.code == code


def test_invalid_fixture_is_not_presented_as_an_image() -> None:
    value, metadata = image_provider.generate(
        operation="generate_product_image",
        width=64,
        height=64,
        seed="test",
        scenario="invalid_image",
    )
    assert value == b"not-an-image"
    assert metadata["scenario"] == "invalid_image"
