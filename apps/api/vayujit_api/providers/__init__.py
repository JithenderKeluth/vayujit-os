"""Provider-neutral runtime foundation for external integrations.

The package deliberately contains no domain semantics and no external-write
capability. Domain adapters register metadata and translate provider payloads;
the shared runtime owns credentials, retries, limits, validation, and safe
execution records.
"""

from vayujit_api.providers.contracts import (
    CapabilityKind,
    CredentialReference,
    CredentialRequirement,
    CredentialType,
    ProviderCapability,
    ProviderCategory,
    ProviderConfig,
    ProviderDefinition,
    ProviderEnvironment,
    ProviderErrorCode,
)
from vayujit_api.providers.registry import provider_registry
from vayujit_api.providers.runtime import ProviderRuntime, RuntimeResult

__all__ = [
    "CapabilityKind",
    "CredentialReference",
    "CredentialRequirement",
    "CredentialType",
    "ProviderCapability",
    "ProviderCategory",
    "ProviderConfig",
    "ProviderDefinition",
    "ProviderEnvironment",
    "ProviderErrorCode",
    "ProviderRuntime",
    "RuntimeResult",
    "provider_registry",
]
