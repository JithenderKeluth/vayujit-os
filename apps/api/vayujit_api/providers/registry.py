"""Canonical static provider and capability registry."""

from __future__ import annotations

from dataclasses import dataclass

from vayujit_api.providers.contracts import (
    CapabilityKind,
    CredentialRequirement,
    CredentialType,
    ProviderCapability,
    ProviderCategory,
    ProviderDefinition,
    ProviderEnvironment,
)


def _read(*capabilities: ProviderCapability) -> dict[ProviderCapability, CapabilityKind]:
    return {capability: CapabilityKind.READ for capability in capabilities}


@dataclass(frozen=True)
class ProviderRegistry:
    _definitions: tuple[ProviderDefinition, ...]

    def get(self, provider_id: str) -> ProviderDefinition:
        for definition in self._definitions:
            if definition.provider_id == provider_id or definition.stable_key == provider_id:
                return definition
        raise KeyError(f"Unknown provider: {provider_id}")

    def definitions(self) -> tuple[ProviderDefinition, ...]:
        return self._definitions

    def safe_list(self) -> list[dict[str, object]]:
        return [item.safe_dict() for item in self._definitions]


_fixture_credentials = (
    CredentialRequirement(
        name="fixture_token",
        credential_type=CredentialType.API_KEY,
        environment_key="VAYUJIT_FIXTURE_PROVIDER_API_KEY",
        required=False,
    ),
)


def _supplier(provider_id: str, display_name: str) -> ProviderDefinition:
    capabilities = frozenset(
        {ProviderCapability.SUPPLIER_SEARCH, ProviderCapability.SUPPLIER_DETAIL}
    )
    return ProviderDefinition(
        provider_id=provider_id,
        stable_key=provider_id,
        display_name=display_name,
        category=ProviderCategory.SUPPLIER,
        adapter_id=f"{provider_id}_adapter",
        capabilities=capabilities,
        capability_kinds=_read(*capabilities),
        authentication=CredentialType.API_KEY,
        environments=frozenset({ProviderEnvironment.LOCAL_FIXTURE}),
        credential_requirements=_fixture_credentials,
        configuration_requirements=("country_code", "result_limit"),
    )


provider_registry = ProviderRegistry(
    (
        ProviderDefinition(
            provider_id="local_fixture",
            stable_key="local_fixture",
            display_name="Deterministic Local Fixture",
            category=ProviderCategory.SUPPLIER,
            adapter_id="local_fixture",
            capabilities=frozenset(
                {ProviderCapability.SUPPLIER_SEARCH, ProviderCapability.SUPPLIER_DETAIL}
            ),
            capability_kinds=_read(
                ProviderCapability.SUPPLIER_SEARCH, ProviderCapability.SUPPLIER_DETAIL
            ),
            authentication=CredentialType.API_KEY,
            environments=frozenset({ProviderEnvironment.LOCAL_FIXTURE}),
            credential_requirements=_fixture_credentials,
            configuration_requirements=("fixture_scenario", "page_size"),
        ),
        _supplier("indiamart", "IndiaMART"),
        _supplier("alibaba", "Alibaba"),
        _supplier("tradeindia", "TradeIndia"),
        _supplier("global_sources", "Global Sources"),
        ProviderDefinition(
            provider_id="openai_compatible",
            stable_key="openai_compatible",
            display_name="OpenAI-compatible provider",
            category=ProviderCategory.CONTENT,
            adapter_id="openai_compatible",
            capabilities=frozenset({ProviderCapability.CONTENT_GENERATE}),
            capability_kinds=_read(ProviderCapability.CONTENT_GENERATE),
            authentication=CredentialType.API_KEY,
            environments=frozenset({ProviderEnvironment.LOCAL_FIXTURE}),
            credential_requirements=(
                CredentialRequirement(
                    name="api_key",
                    credential_type=CredentialType.API_KEY,
                    environment_key="VAYUJIT_OPENAI_API_KEY",
                ),
            ),
            configuration_requirements=("base_url", "model"),
            live_capable=False,
        ),
    )
)
