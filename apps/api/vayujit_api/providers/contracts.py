"""Provider-neutral contracts shared by adapters and the runtime."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ProviderCategory(StrEnum):
    SUPPLIER = "SUPPLIER"
    MARKETPLACE = "MARKETPLACE"
    RESEARCH = "RESEARCH"
    FX = "FX"
    FREIGHT = "FREIGHT"
    CUSTOMS = "CUSTOMS"
    CONTENT = "CONTENT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    SOCIAL = "SOCIAL"
    ADVERTISING = "ADVERTISING"
    COMMERCE = "COMMERCE"
    OTHER = "OTHER"


class ProviderEnvironment(StrEnum):
    LOCAL_FIXTURE = "LOCAL_FIXTURE"
    SANDBOX = "SANDBOX"
    TEST = "TEST"
    STAGING = "STAGING"
    LIVE = "LIVE"


class CredentialType(StrEnum):
    NONE = "NONE"
    API_KEY = "API_KEY"
    BEARER_TOKEN = "BEARER_TOKEN"
    BASIC_AUTH = "BASIC_AUTH"
    OAUTH2_CLIENT = "OAUTH2_CLIENT"
    OAUTH2_TOKEN = "OAUTH2_TOKEN"
    SIGNED_REQUEST = "SIGNED_REQUEST"
    CUSTOM = "CUSTOM"


class CapabilityKind(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    FINANCIAL = "FINANCIAL"


class ProviderCapability(StrEnum):
    SUPPLIER_SEARCH = "SUPPLIER_SEARCH"
    SUPPLIER_DETAIL = "SUPPLIER_DETAIL"
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    ORDER_READ = "ORDER_READ"
    INVENTORY_READ = "INVENTORY_READ"
    INVENTORY_WRITE = "INVENTORY_WRITE"
    LISTING_READ = "LISTING_READ"
    LISTING_WRITE = "LISTING_WRITE"
    FX_RATE_READ = "FX_RATE_READ"
    FREIGHT_QUOTE_READ = "FREIGHT_QUOTE_READ"
    CUSTOMS_RATE_READ = "CUSTOMS_RATE_READ"
    CONTENT_GENERATE = "CONTENT_GENERATE"
    IMAGE_GENERATE = "IMAGE_GENERATE"
    VIDEO_GENERATE = "VIDEO_GENERATE"
    SOCIAL_PUBLISH = "SOCIAL_PUBLISH"
    AD_CAMPAIGN_READ = "AD_CAMPAIGN_READ"


class ProviderErrorCode(StrEnum):
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    CONFIGURATION = "CONFIGURATION"
    QUOTA = "QUOTA"
    UNKNOWN = "UNKNOWN"


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_:-]{1,63}$")
_SECRET_PARTS = ("secret", "token", "password", "api_key", "authorization", "credential")


@dataclass(frozen=True)
class CredentialReference:
    """A pointer to a secret; never the secret itself."""

    source: str
    key: str
    version: str | None = None

    def __post_init__(self) -> None:
        if self.source not in {"environment", "deployment", "encrypted_store"}:
            raise ValueError("Unsupported credential source.")
        if not self.key or len(self.key) > 160:
            raise ValueError("Credential reference key is invalid.")

    def safe_dict(self) -> dict[str, str | None]:
        return {"source": self.source, "key": self.key, "version": self.version}


@dataclass(frozen=True)
class CredentialRequirement:
    name: str
    credential_type: CredentialType
    environment_key: str | None = None
    required: bool = True

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 64:
            raise ValueError("Credential requirement name is invalid.")
        if self.credential_type is not CredentialType.NONE and not self.environment_key:
            raise ValueError("Secret-backed credentials require an environment key.")

    def safe_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.credential_type.value,
            "configured_by": "environment" if self.environment_key else None,
            "required": self.required,
        }


@dataclass(frozen=True)
class ProviderDefinition:
    provider_id: str
    stable_key: str
    display_name: str
    category: ProviderCategory
    adapter_id: str
    capabilities: frozenset[ProviderCapability]
    capability_kinds: Mapping[ProviderCapability, CapabilityKind] = field(default_factory=dict)
    authentication: CredentialType = CredentialType.NONE
    environments: frozenset[ProviderEnvironment] = frozenset({ProviderEnvironment.LOCAL_FIXTURE})
    credential_requirements: tuple[CredentialRequirement, ...] = ()
    configuration_requirements: tuple[str, ...] = ()
    enabled: bool = True
    live_capable: bool = False

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.provider_id) or not _IDENTIFIER.fullmatch(
            self.stable_key
        ):
            raise ValueError("Provider identity is invalid.")
        if self.live_capable and ProviderEnvironment.LIVE not in self.environments:
            raise ValueError("A live-capable provider must declare LIVE support.")
        if any(capability not in self.capabilities for capability in self.capability_kinds):
            raise ValueError("Capability kind declared for an unsupported capability.")

    def supports(self, capability: ProviderCapability, environment: ProviderEnvironment) -> bool:
        return capability in self.capabilities and environment in self.environments

    def kind_for(self, capability: ProviderCapability) -> CapabilityKind:
        return self.capability_kinds.get(capability, CapabilityKind.READ)

    def safe_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "stable_key": self.stable_key,
            "display_name": self.display_name,
            "category": self.category.value,
            "adapter_id": self.adapter_id,
            "capabilities": sorted(item.value for item in self.capabilities),
            "capability_kinds": {key.value: self.kind_for(key).value for key in self.capabilities},
            "authentication": self.authentication.value,
            "environments": sorted(item.value for item in self.environments),
            "credential_requirements": [item.safe_dict() for item in self.credential_requirements],
            "configuration_requirements": list(self.configuration_requirements),
            "enabled": self.enabled,
            "live_capable": self.live_capable,
        }


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    environment: ProviderEnvironment
    values: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not _IDENTIFIER.fullmatch(self.provider_id):
            raise ValueError("Provider configuration identity is invalid.")
        if len(self.values) > 32:
            raise ValueError("Provider configuration has too many values.")
        for key, value in self.values.items():
            folded = key.casefold()
            if any(part in folded for part in _SECRET_PARTS):
                raise ValueError("Secrets must be supplied by credential reference.")
            if not key or len(key) > 80 or len(value) > 2000:
                raise ValueError("Provider configuration value is invalid.")


@dataclass(frozen=True)
class ProviderRequest:
    method: str
    url: str
    operation: str
    params: Mapping[str, str] = field(default_factory=dict)
    json_body: Mapping[str, Any] | None = None
    page_token: str | None = None


@dataclass(frozen=True)
class ProviderResponse:
    status_code: int
    headers: Mapping[str, str]
    body: object


@dataclass(frozen=True)
class ProviderPage:
    items: tuple[Mapping[str, object], ...]
    next_token: str | None = None


class ProviderAdapter(Protocol):
    adapter_id: str

    def build_request(
        self, operation: str, config: ProviderConfig, credential: str | None, page_token: str | None
    ) -> ProviderRequest: ...

    def validate_response(self, response: ProviderResponse) -> None: ...

    def normalize(self, response: ProviderResponse) -> ProviderPage: ...


@dataclass(frozen=True)
class ProviderExecutionContext:
    provider_id: str
    owner_id: uuid.UUID | None
    correlation_id: str
    request_id: str
    provider_execution_id: str
    capability: ProviderCapability
    environment: ProviderEnvironment


def is_secret_key(value: str) -> bool:
    folded = value.casefold()
    return any(part in folded for part in _SECRET_PARTS)
