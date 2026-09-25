"""Application-facing provider platform service and safe status projection."""

from __future__ import annotations

from vayujit_api.providers.contracts import (
    CredentialReference,
    ProviderCapability,
    ProviderConfig,
    ProviderEnvironment,
)
from vayujit_api.providers.credentials import SecretResolver
from vayujit_api.providers.fixture import FixtureTransport, LocalFixtureAdapter
from vayujit_api.providers.registry import provider_registry
from vayujit_api.providers.runtime import ProviderRuntime, RuntimeResult


def create_runtime(resolver: SecretResolver | None = None) -> ProviderRuntime:
    return ProviderRuntime(
        resolver=resolver,
        adapters={"local_fixture": LocalFixtureAdapter()},
        transport=FixtureTransport(),
        sleeper=lambda _seconds: None,
    )


runtime = create_runtime()


def provider_summaries() -> list[dict[str, object]]:
    return [
        {
            **definition.safe_dict(),
            "configuration_status": "NOT_CONFIGURED",
            "credential_status": (
                "REFERENCE_REQUIRED" if definition.credential_requirements else "NOT_REQUIRED"
            ),
            "connectivity_status": "NOT_TESTED",
            "provider_status": "NOT_VERIFIED",
            "health": safe_health(definition.provider_id),
        }
        for definition in provider_registry.definitions()
    ]


def validate_local_fixture(
    *,
    operation: str = "supplier_search",
    scenario: str = "success",
    page_size: int = 3,
    credential_reference: CredentialReference | None = None,
) -> RuntimeResult:
    return runtime.execute(
        "local_fixture",
        ProviderCapability.SUPPLIER_SEARCH,
        operation=operation,
        config=ProviderConfig(
            provider_id="local_fixture",
            environment=ProviderEnvironment.LOCAL_FIXTURE,
            values={"fixture_scenario": scenario, "page_size": str(page_size)},
        ),
        credential_reference=credential_reference,
    )


def safe_health(provider_id: str) -> dict[str, object]:
    return runtime.health(provider_id)
