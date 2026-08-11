"""Typed, safe failure taxonomy for durable AI Studio execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class StudioFailureSpec:
    code: str
    retryable: bool
    safe_message: str
    recovery_actions: tuple[str, ...]
    retry_provider: bool
    context_refresh_required: bool = False


class StudioProviderFailure(RuntimeError):
    """Typed provider/test-adapter failure with no raw provider payload."""

    def __init__(self, code: str, *, retry_after: float | None = None) -> None:
        self.spec = failure_spec(code)
        self.retry_after = retry_after
        super().__init__(self.spec.safe_message)


_RETRY: Final[tuple[str, ...]] = ("retry_generation", "review_failure")
_PERMANENT: Final[tuple[str, ...]] = ("review_failure",)

FAILURE_TAXONOMY: Final[dict[str, StudioFailureSpec]] = {
    "provider_unavailable": StudioFailureSpec(
        "provider_unavailable", True, "The AI provider is temporarily unavailable.", _RETRY, True
    ),
    "provider_timeout": StudioFailureSpec(
        "provider_timeout",
        True,
        "The AI provider timed out; the generation can be retried.",
        _RETRY,
        True,
    ),
    "provider_throttled": StudioFailureSpec(
        "provider_throttled",
        True,
        "The AI provider is throttling requests; retry timing has been applied.",
        _RETRY,
        True,
    ),
    "provider_5xx": StudioFailureSpec(
        "provider_5xx", True, "The AI provider returned a temporary server error.", _RETRY, True
    ),
    "invalid_credentials": StudioFailureSpec(
        "invalid_credentials",
        False,
        "The AI provider credentials need attention.",
        ("open_provider_settings", "review_failure"),
        False,
    ),
    "unsupported_provider": StudioFailureSpec(
        "unsupported_provider", False, "This AI provider is not supported.", _PERMANENT, False
    ),
    "unsupported_model": StudioFailureSpec(
        "unsupported_model",
        False,
        "The selected AI model is not supported.",
        ("choose_another_model", "open_provider_settings", "review_failure"),
        False,
    ),
    "policy_refusal": StudioFailureSpec(
        "policy_refusal",
        False,
        "The provider declined this request under its safety policy.",
        ("review_failure", "edit_instructions"),
        False,
    ),
    "context_too_large": StudioFailureSpec(
        "context_too_large",
        False,
        "The generation context is too large for the selected provider.",
        ("refresh_context", "open_product", "review_failure"),
        False,
        True,
    ),
    "malformed_output": StudioFailureSpec(
        "malformed_output",
        False,
        "The provider returned malformed structured output.",
        ("retry_generation", "regenerate", "review_failure"),
        False,
    ),
    "output_too_large": StudioFailureSpec(
        "output_too_large",
        False,
        "The provider output exceeded the safe size limit.",
        _PERMANENT,
        False,
    ),
    "structured_validation_failed": StudioFailureSpec(
        "structured_validation_failed",
        False,
        "The provider output failed structured validation.",
        ("retry_generation", "regenerate", "review_failure"),
        False,
    ),
    "unsafe_input": StudioFailureSpec(
        "unsafe_input",
        False,
        "The request contains input that cannot be processed safely.",
        _PERMANENT,
        False,
    ),
    "stale_context": StudioFailureSpec(
        "stale_context",
        False,
        "The Product or Brand Voice context changed before execution.",
        ("refresh_context", "open_product", "review_failure"),
        False,
        True,
    ),
    "cancelled": StudioFailureSpec(
        "cancelled", False, "The AI generation was cancelled.", _PERMANENT, False
    ),
    "unknown_transient": StudioFailureSpec(
        "unknown_transient", True, "The AI provider returned a temporary error.", _RETRY, True
    ),
    "unknown_permanent": StudioFailureSpec(
        "unknown_permanent", False, "The AI generation failed safely.", _PERMANENT, False
    ),
}


IMAGE_FAILURE_TAXONOMY: Final[dict[str, StudioFailureSpec]] = {
    "checkpoint_invalid": StudioFailureSpec(
        "checkpoint_invalid",
        False,
        "The saved AI checkpoint is invalid and must be reviewed.",
        ("review_failure", "regenerate"),
        False,
    ),
}


def failure_spec(code: str) -> StudioFailureSpec:
    return IMAGE_FAILURE_TAXONOMY.get(
        code, FAILURE_TAXONOMY.get(code, FAILURE_TAXONOMY["unknown_permanent"])
    )


def validate_failure_scenario(name: str | None) -> str:
    allowed = {
        "success",
        "throttle_once",
        "throttle_twice",
        "throttle_exhausted",
        "timeout_once",
        "timeout_twice",
        "transient_5xx_once",
        "transient_5xx_exhausted",
        "invalid_credentials",
        "unsupported_model",
        "policy_refusal",
        "context_too_large",
        "malformed_json_once",
        "malformed_json_twice",
        "missing_required_field",
        "wrong_field_type",
        "truncated_output",
        "oversized_output",
        "provider_unavailable_once",
        "unknown_transient",
        "unknown_permanent",
        "unsupported_provider",
        "unsafe_input",
    }
    value = (name or "success").strip().casefold()
    if value not in allowed:
        raise ValueError("Unknown deterministic AI failure scenario.")
    return value


def scenario_failure(scenario: str, attempt_number: int) -> StudioProviderFailure | None:
    if scenario in {"throttle_once", "throttle_twice", "throttle_exhausted"}:
        limit = {"throttle_once": 1, "throttle_twice": 2, "throttle_exhausted": 99}[scenario]
        if attempt_number <= limit:
            return StudioProviderFailure("provider_throttled", retry_after=2.0)
    if scenario in {"timeout_once", "timeout_twice"} and attempt_number <= (
        1 if scenario.endswith("once") else 2
    ):
        return StudioProviderFailure("provider_timeout")
    if scenario in {"transient_5xx_once", "transient_5xx_exhausted"} and attempt_number <= (
        1 if scenario.endswith("once") else 99
    ):
        return StudioProviderFailure("provider_5xx")
    if scenario == "provider_unavailable_once" and attempt_number == 1:
        return StudioProviderFailure("provider_unavailable")
    permanent = {
        "invalid_credentials": "invalid_credentials",
        "unsupported_model": "unsupported_model",
        "unsupported_provider": "unsupported_provider",
        "policy_refusal": "policy_refusal",
        "context_too_large": "context_too_large",
        "unsafe_input": "unsafe_input",
        "unknown_permanent": "unknown_permanent",
        "unknown_transient": "unknown_transient",
    }
    if scenario in permanent:
        return StudioProviderFailure(permanent[scenario])
    return None


def validate_structured_output(
    content: object, *, content_type: str | None = None, max_bytes: int = 100_000
) -> dict[str, object]:
    """Validate the typed structured shape for the requested output type."""
    import json

    if not isinstance(content, dict):
        raise StudioProviderFailure("structured_validation_failed")
    if len(json.dumps(content, ensure_ascii=False, default=str).encode()) > max_bytes:
        raise StudioProviderFailure("output_too_large")
    required: dict[str, tuple[str, ...]] = {
        "product_title": ("title",),
        "product_description": ("title", "description"),
        "bullet_points": ("title", "bullets"),
        "seo_metadata": ("seo", "keywords"),
        "social_caption": ("caption", "tags"),
        "blog_content": ("title", "description", "headings"),
    }
    for key in required.get(content_type or "", ("title", "description")):
        value = content.get(key)
        if key == "seo":
            valid = isinstance(value, dict)
        elif key in {"bullets", "keywords", "search_terms", "tags", "headings"}:
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        else:
            valid = isinstance(value, str) and bool(value.strip())
        if not valid:
            raise StudioProviderFailure("structured_validation_failed")
        if isinstance(value, str) and len(value) > 10_000:
            raise StudioProviderFailure("output_too_large")
    for key in ("bullets", "keywords", "search_terms", "tags", "headings"):
        value = content.get(key)
        if value is not None and (
            not isinstance(value, list)
            or len(value) > 100
            or any(not isinstance(item, str) for item in value)
        ):
            raise StudioProviderFailure("structured_validation_failed")
    metadata = content.get("seo")
    if metadata is not None and not isinstance(metadata, dict):
        raise StudioProviderFailure("structured_validation_failed")
    return content
