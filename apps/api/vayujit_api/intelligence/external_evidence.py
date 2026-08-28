"""Deterministic safety helpers for external evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class FreshnessPolicy:
    fresh_seconds: int = 86_400
    aging_seconds: int = 172_800
    stale_seconds: int = 604_800
    expires_seconds: int = 2_592_000


DEFAULT_FRESHNESS_POLICY = FreshnessPolicy()


@dataclass(frozen=True)
class FreshnessResult:
    state: str
    retrieved_at: datetime
    fresh_until: datetime | None
    stale_at: datetime | None
    expires_at: datetime | None
    refresh_due: bool
    usable_for_verification: bool
    usable_for_scoring: bool


def derive_freshness(
    retrieved_at: datetime | None,
    *,
    now: datetime | None = None,
    policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY,
) -> FreshnessResult:
    if retrieved_at is None:
        stamp = now or datetime.now(UTC)
        return FreshnessResult("UNKNOWN", stamp, None, None, None, True, False, False)
    stamp = retrieved_at.astimezone(UTC)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    fresh_until = stamp + timedelta(seconds=policy.fresh_seconds)
    stale_at = stamp + timedelta(seconds=policy.aging_seconds)
    expires_at = stamp + timedelta(seconds=policy.expires_seconds)
    if current < fresh_until:
        state = "FRESH"
    elif current < stale_at:
        state = "AGING"
    elif current < expires_at:
        state = "STALE"
    else:
        state = "EXPIRED"
    return FreshnessResult(
        state,
        stamp,
        fresh_until,
        stale_at,
        expires_at,
        state in {"AGING", "STALE", "EXPIRED"},
        state in {"FRESH", "AGING"},
        state in {"FRESH", "AGING"},
    )


def verify_external_candidate(
    candidate: Mapping[str, object],
    *,
    owner_id: object,
    expected_owner_id: object,
) -> str:
    if owner_id != expected_owner_id:
        return "REJECTED"
    if not candidate.get("source_reference") or not candidate.get("retrieval_identity"):
        return "REJECTED"
    if candidate.get("is_untrusted_external_data") is not True:
        return "REJECTED"
    if candidate.get("source_class") == "SEARCH_DISCOVERY_RESULT":
        return "UNVERIFIED"
    if candidate.get("prompt_injection_detected") is True:
        return "REJECTED"
    return "SUPPORTED"


def claim_is_eligible(verification_status: str, source_class: str) -> bool:
    if source_class == "SEARCH_DISCOVERY_RESULT":
        return False
    return verification_status in {"SUPPORTED", "VERIFIED"}
