from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

SOCIAL_CONNECTOR_KEY = "social_fake"
FAKE_CONNECTOR_CALLS: dict[str, int] = {}
FAKE_REMOTE_PUBLICATIONS: set[str] = set()
SCENARIOS = {
    "success",
    "processing",
    "published",
    "rejected",
    "throttled",
    "timeout",
    "ambiguous_result",
    "credential_failure",
    "policy_failure",
    "remote_unavailable",
    "remote_missing",
}


class SocialConnectorFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        ambiguous: bool = False,
        retry_after: int | None = None,
        remote_publication_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.ambiguous = ambiguous
        self.retry_after = retry_after
        self.remote_publication_id = remote_publication_id


class SocialConnector(Protocol):
    platform: str

    def validate_account(self, account: dict[str, object]) -> bool: ...
    def publish_post(
        self, account: dict[str, object], post: dict[str, object], idempotency_key: str
    ) -> dict[str, object]: ...
    def fetch_publication_status(
        self, account: dict[str, object], remote_id: str
    ) -> dict[str, object]: ...
    def fetch_metrics(self, account: dict[str, object], remote_id: str) -> dict[str, float]: ...


@dataclass(frozen=True)
class FakeSocialConnector:
    platform: str
    scenario: str = "success"

    def validate_account(self, account: dict[str, object]) -> bool:
        if self.scenario == "credential_failure":
            raise SocialConnectorFailure(
                "social.invalid_credentials", "The social account credentials were rejected."
            )
        return True

    def publish_post(
        self, account: dict[str, object], post: dict[str, object], idempotency_key: str
    ) -> dict[str, object]:
        key = f"{self.platform}:{idempotency_key}"
        FAKE_CONNECTOR_CALLS[key] = FAKE_CONNECTOR_CALLS.get(key, 0) + 1
        if self.scenario in {"rejected", "policy_failure"}:
            raise SocialConnectorFailure(
                "social.policy_rejected", "The local social connector rejected this post by policy."
            )
        if self.scenario == "throttled":
            raise SocialConnectorFailure(
                "social.throttled",
                "The local social connector is throttled.",
                retryable=True,
                retry_after=2,
            )
        if self.scenario == "remote_missing":
            raise SocialConnectorFailure(
                "social.remote_missing",
                "The remote publication could not be found; reconciliation is required.",
                retryable=True,
                ambiguous=True,
            )
        if self.scenario in {"timeout", "remote_unavailable"}:
            raise SocialConnectorFailure(
                "social.provider_unavailable",
                "The local social connector is unavailable.",
                retryable=True,
            )
        remote_id = deterministic_remote_id(self.platform, account, post, idempotency_key)
        FAKE_REMOTE_PUBLICATIONS.add(remote_id)
        if self.scenario == "ambiguous_result":
            raise SocialConnectorFailure(
                "social.ambiguous_result",
                "The publication result was ambiguous; reconciliation is required.",
                ambiguous=True,
                remote_publication_id=remote_id,
            )
        return {
            "remote_publication_id": remote_id,
            "status": "processing" if self.scenario == "processing" else "published",
            "synthetic_test_data": True,
        }

    def fetch_publication_status(
        self, account: dict[str, object], remote_id: str
    ) -> dict[str, object]:
        if self.scenario == "remote_missing":
            raise SocialConnectorFailure(
                "social.remote_missing",
                "The remote publication could not be found; retry is available.",
                retryable=True,
            )
        if self.scenario == "remote_unavailable":
            raise SocialConnectorFailure(
                "social.provider_unavailable",
                "The local social connector is unavailable.",
                retryable=True,
            )
        return {
            "remote_publication_id": remote_id,
            "status": "published",
            "synthetic_test_data": True,
        }

    def fetch_metrics(self, account: dict[str, object], remote_id: str) -> dict[str, float]:
        digest = int(hashlib.sha256(remote_id.encode()).hexdigest()[:8], 16)
        return {
            "impressions": float(digest % 1000),
            "reach": float(digest % 700),
            "likes": float(digest % 100),
            "comments": float(digest % 20),
            "shares": float(digest % 15),
            "clicks": float(digest % 50),
            "views": float(digest % 500),
        }


def deterministic_remote_id(
    platform: str,
    account: dict[str, object],
    post: dict[str, object],
    idempotency_key: str,
) -> str:
    normalized = json.dumps(
        {
            "platform": platform,
            "account": account.get("remote_account_id"),
            "post": post,
            "idempotency_key": idempotency_key,
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:20]
    return f"{platform[:3].upper()}-{digest}"


def connector_for(platform: str, capabilities: dict[str, object]) -> FakeSocialConnector:
    scenario = str(capabilities.get("scenario", "success"))
    if scenario not in SCENARIOS:
        scenario = "success"
    return FakeSocialConnector(platform, scenario)
