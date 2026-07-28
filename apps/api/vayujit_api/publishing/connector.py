import hashlib
import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConnectorResult:
    external_reference: str
    external_url: str
    payload: dict[str, object]


class ConnectorFailure(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code, self.safe_message, self.retryable = code, message, retryable


class PublishingConnector(Protocol):
    key: str
    name: str
    connector_type: str

    def available(self) -> bool: ...
    def publish(
        self, destination: dict[str, object], snapshot: dict[str, object]
    ) -> ConnectorResult: ...


class MockPublishingConnector:
    key = "mock_publisher_v1"
    name = "Deterministic Local Mock Publisher"
    connector_type = "mock"

    def available(self) -> bool:
        return True

    def publish(
        self, destination: dict[str, object], snapshot: dict[str, object]
    ) -> ConnectorResult:
        failure = destination.get("simulate_failure")
        if failure:
            retryable = destination.get("failure_type") == "retryable"
            raise ConnectorFailure(
                "mock_retryable_failure" if retryable else "mock_permanent_failure",
                "The local mock publisher deliberately failed.",
                retryable=retryable,
            )
        normalized = json.dumps({"destination": destination, "content": snapshot}, sort_keys=True)
        checksum = hashlib.sha256(normalized.encode()).hexdigest()
        prefix = str(destination.get("publication_prefix") or "PUB").upper()
        reference = f"{prefix}-{checksum[:12]}"
        return ConnectorResult(
            reference,
            f"https://example.invalid/publications/{reference.lower()}",
            {"publication_id": reference, "status": "published", "checksum": checksum},
        )


connector = MockPublishingConnector()
