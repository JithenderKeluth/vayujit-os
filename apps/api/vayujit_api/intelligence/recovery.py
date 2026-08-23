from __future__ import annotations

from typing import Final

FAILURE_CLASSIFICATIONS: Final[tuple[str, ...]] = (
    "source_unavailable",
    "source_rate_limited",
    "source_authentication_failed",
    "unsafe_url",
    "invalid_evidence",
    "stale_evidence",
    "parsing_failed",
    "verification_failed",
)

RECOVERY_ACTIONS: Final[dict[str, dict[str, str]]] = {
    "source_unavailable": {
        "action": "retry_after_backoff",
        "safety": "no_external_call_in_foundation",
    },
    "source_rate_limited": {
        "action": "wait_for_retry_window",
        "safety": "no_external_call_in_foundation",
    },
    "source_authentication_failed": {
        "action": "pause_source_and_require_operator",
        "safety": "never_log_credentials",
    },
    "unsafe_url": {
        "action": "reject_and_require_operator",
        "safety": "never_fetch_for_recovery",
    },
    "invalid_evidence": {
        "action": "quarantine_evidence",
        "safety": "append_only",
    },
    "stale_evidence": {
        "action": "mark_for_refresh",
        "safety": "external_refresh_disabled",
    },
    "parsing_failed": {
        "action": "quarantine_and_require_operator",
        "safety": "no_untrusted_execution",
    },
    "verification_failed": {
        "action": "require_human_review",
        "safety": "no_auto_approval",
    },
}
