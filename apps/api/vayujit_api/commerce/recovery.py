"""Bridge commerce failures into the existing Recovery projection.

This module deliberately has no queue or action registry of its own. Callers
can attach the returned safe failure context to the platform Recovery record
that owns the campaign/workflow operation.
"""

from dataclasses import dataclass
from typing import Literal

CommerceFailureKind = Literal[
    "listing_submission_failed",
    "listing_rejected",
    "authentication_expired",
    "ambiguous_remote_result",
    "inventory_write_failed",
    "order_sync_failed",
    "settlement_import_failed",
    "amazon_throttled",
    "amazon_policy_rejection",
    "amazon_ambiguous_result",
]


@dataclass(frozen=True)
class CommerceFailureProjection:
    kind: CommerceFailureKind
    safe_reason_code: str
    retryable: bool
    suggested_recovery: str


def project_failure(kind: CommerceFailureKind) -> CommerceFailureProjection:
    retryable = kind not in {
        "listing_rejected",
        "authentication_expired",
        "amazon_policy_rejection",
    }
    return CommerceFailureProjection(
        kind=kind,
        safe_reason_code=f"commerce.{kind}",
        retryable=retryable,
        suggested_recovery="retry" if retryable else "review",
    )
