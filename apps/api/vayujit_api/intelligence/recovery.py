# ruff: noqa: E501
from __future__ import annotations

from typing import Final

FAILURE_CLASSIFICATIONS: Final[tuple[str, ...]] = (
    "provider_unavailable",
    "provider_rate_limited",
    "unsafe_source",
    "invalid_fixture",
    "invalid_evidence",
    "stale_evidence",
    "scoring_failure",
    "rule_evaluation_failure",
    "checkpoint_invalid",
)

RECOVERY_ACTIONS: Final[dict[str, dict[str, str]]] = {
    "provider_unavailable": {"action": "retry", "safety": "local deterministic provider only"},
    "provider_rate_limited": {"action": "retry", "safety": "bounded backoff"},
    "unsafe_source": {"action": "review_source", "safety": "never fetch unsafe source"},
    "invalid_fixture": {"action": "cancel", "safety": "quarantine local fixture"},
    "invalid_evidence": {"action": "refresh_evidence", "safety": "append-only evidence"},
    "stale_evidence": {"action": "refresh_evidence", "safety": "external refresh disabled"},
    "scoring_failure": {"action": "retry", "safety": "no score mutation"},
    "rule_evaluation_failure": {"action": "review_rules", "safety": "hard blocks preserved"},
    "checkpoint_invalid": {"action": "reconcile", "safety": "idempotent recovery"},
}
