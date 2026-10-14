"""Provider adapter boundary for PR-7B.

There is intentionally no SMTP/HTTP implementation here.  The fake provider
is deterministic, in-memory, and only callable from the test environment.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock
from typing import Literal

ProviderOutcome = Literal["ACCEPTED", "RETRYABLE_FAILURE", "FINAL_FAILURE", "UNKNOWN_OUTCOME"]


@dataclass(frozen=True)
class ProviderResult:
    outcome: ProviderOutcome
    provider: str = "fake"
    provider_reference: str | None = None
    error_category: str | None = None
    retryable: bool = False
    receipt_metadata: dict[str, object] | None = None


class FakeEmailProvider:
    """A no-network provider used by deterministic certification only."""

    _lock = Lock()
    _calls: list[dict[str, object]] = []

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._calls.clear()

    @classmethod
    def calls(cls) -> list[dict[str, object]]:
        with cls._lock:
            return list(cls._calls)

    @classmethod
    def send(
        cls,
        *,
        recipient: str,
        subject: str,
        message_body: str,
        logical_message_id: uuid.UUID,
        payload_fingerprint: str,
        outcome: ProviderOutcome = "ACCEPTED",
    ) -> ProviderResult:
        # Keep the record intentionally redacted: no body/secret/headers are
        # retained in process diagnostics or returned to the API.
        with cls._lock:
            cls._calls.append(
                {
                    "logical_message_id": str(logical_message_id),
                    "recipient": recipient,
                    "subject_fingerprint": payload_fingerprint,
                }
            )
        if outcome == "ACCEPTED":
            return ProviderResult(
                outcome=outcome,
                provider_reference=f"fake-{logical_message_id.hex[:20]}",
                receipt_metadata={"accepted": True, "network": False},
            )
        if outcome == "RETRYABLE_FAILURE":
            return ProviderResult(
                outcome=outcome,
                error_category="TEMPORARY_PROVIDER_FAILURE",
                retryable=True,
                receipt_metadata={"accepted": False, "network": False},
            )
        if outcome == "FINAL_FAILURE":
            return ProviderResult(
                outcome=outcome,
                error_category="PERMANENT_PROVIDER_FAILURE",
                retryable=False,
                receipt_metadata={"accepted": False, "network": False},
            )
        return ProviderResult(
            outcome="UNKNOWN_OUTCOME",
            error_category="UNKNOWN_PROVIDER_OUTCOME",
            retryable=False,
            receipt_metadata={"accepted": None, "network": False},
        )


def reset_fake_provider() -> None:
    FakeEmailProvider.reset()


def fake_provider_calls() -> list[dict[str, object]]:
    return FakeEmailProvider.calls()
