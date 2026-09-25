"""Secret-reference resolution without secret persistence or API exposure."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from vayujit_api.providers.contracts import CredentialReference


class CredentialResolutionError(RuntimeError):
    """Raised when a referenced credential cannot be resolved safely."""


@dataclass(frozen=True)
class ResolvedCredential:
    reference: CredentialReference | None
    value: str | None

    @property
    def configured(self) -> bool:
        return bool(self.value)

    def safe_dict(self) -> dict[str, object]:
        return {
            "source": self.reference.source if self.reference else None,
            "key": self.reference.key if self.reference else None,
            "version": self.reference.version if self.reference else None,
            "configured": self.configured,
        }


class SecretResolver(Protocol):
    def resolve(self, reference: CredentialReference) -> ResolvedCredential: ...


class EnvironmentSecretResolver:
    """Resolve only from an explicitly named environment variable."""

    def resolve(self, reference: CredentialReference) -> ResolvedCredential:
        if reference.source != "environment":
            raise CredentialResolutionError(
                "This deployment supports environment-managed credentials only."
            )
        value = os.environ.get(reference.key)
        return ResolvedCredential(reference, value if value else None)


class StaticSecretResolver:
    """Test-only resolver; it never exposes values in safe projections."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = dict(values)

    def resolve(self, reference: CredentialReference) -> ResolvedCredential:
        if reference.source != "environment":
            raise CredentialResolutionError("Static test credentials use environment references.")
        return ResolvedCredential(reference, self._values.get(reference.key))
