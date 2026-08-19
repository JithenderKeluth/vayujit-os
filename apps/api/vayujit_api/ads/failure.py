from __future__ import annotations

from typing import Final

ADS_FAILURE_TAXONOMY: Final[dict[str, dict[str, object]]] = {
    "ads.account_disabled": {
        "safe_message": "The Ads account is disabled.",
        "retryable": False,
        "recovery_actions": ["change_account", "review_failure"],
    },
    "ads.invalid_credentials": {
        "safe_message": "The Ads account credentials are invalid.",
        "retryable": False,
        "recovery_actions": ["change_account", "review_failure"],
    },
    "ads.unsupported_objective": {
        "safe_message": "The selected Ads objective is unsupported.",
        "retryable": False,
        "recovery_actions": ["review_failure"],
    },
    "ads.invalid_budget": {
        "safe_message": "The Ads budget is invalid.",
        "retryable": False,
        "recovery_actions": ["change_budget", "review_failure"],
    },
    "ads.invalid_audience": {
        "safe_message": "The Ads audience is invalid or unavailable.",
        "retryable": False,
        "recovery_actions": ["review_failure"],
    },
    "ads.invalid_creative": {
        "safe_message": "The Ads creative is invalid or unavailable.",
        "retryable": False,
        "recovery_actions": ["replace_creative", "review_failure"],
    },
    "ads.invalid_destination": {
        "safe_message": "The Ads destination is invalid.",
        "retryable": False,
        "recovery_actions": ["review_failure"],
    },
    "ads.policy_rejection": {
        "safe_message": "The Ads provider rejected this content under policy.",
        "retryable": False,
        "recovery_actions": ["review_policy", "replace_creative", "cancel"],
    },
    "ads.throttled": {
        "safe_message": "The Ads provider is throttling requests.",
        "retryable": True,
        "recovery_actions": ["retry", "review_failure"],
    },
    "ads.timeout": {
        "safe_message": "The Ads provider timed out.",
        "retryable": True,
        "recovery_actions": ["retry", "review_failure"],
    },
    "ads.connector_unavailable": {
        "safe_message": "The Ads provider is temporarily unavailable.",
        "retryable": True,
        "recovery_actions": ["retry", "review_failure"],
    },
    "ads.ambiguous_result": {
        "safe_message": "The Ads result is ambiguous; reconcile before retrying.",
        "retryable": False,
        "recovery_actions": ["reconcile", "review_failure"],
    },
    "ads.stale_campaign": {
        "safe_message": "The Ads campaign changed; refresh and preview again.",
        "retryable": False,
        "recovery_actions": ["reconcile", "review_failure"],
    },
    "ads.stale_creative": {
        "safe_message": "The Ads creative changed; preview the exact version again.",
        "retryable": False,
        "recovery_actions": ["replace_creative", "review_failure"],
    },
    "ads.stale_budget": {
        "safe_message": "The Ads budget changed; preview the current version again.",
        "retryable": False,
        "recovery_actions": ["change_budget", "review_failure"],
    },
    "ads.remote_not_found": {
        "safe_message": "The remote Ads entity was not found.",
        "retryable": False,
        "recovery_actions": ["reconcile", "review_failure"],
    },
}


def failure_spec(code: str) -> dict[str, object]:
    return dict(
        ADS_FAILURE_TAXONOMY.get(
            code,
            {
                "safe_message": "The Ads operation failed safely.",
                "retryable": False,
                "recovery_actions": ["review_failure"],
            },
        )
    )
