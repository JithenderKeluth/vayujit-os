from __future__ import annotations

import uuid

import pytest

from vayujit_api.providers.contracts import (
    CredentialReference,
    ProviderCapability,
    ProviderConfig,
    ProviderEnvironment,
    ProviderRequest,
)
from vayujit_api.providers.credentials import StaticSecretResolver
from vayujit_api.providers.fixture import FixtureTransport
from vayujit_api.providers.runtime import (
    HttpProviderTransport,
    ProviderRuntime,
    ProviderRuntimeError,
    RequestBudget,
    RetryPolicy,
)
from vayujit_api.providers.service import create_runtime, provider_summaries


def test_registry_is_safe_and_declares_fixture_capabilities() -> None:
    fixture = next(item for item in provider_summaries() if item["provider_id"] == "local_fixture")
    assert fixture["category"] == "SUPPLIER"
    assert "SUPPLIER_SEARCH" in fixture["capabilities"]
    assert fixture["environments"] == ["LOCAL_FIXTURE"]
    assert "VAYUJIT_FIXTURE_PROVIDER_API_KEY" not in str(fixture)


def test_fixture_success_pagination_and_correlation() -> None:
    runtime = create_runtime()
    result = runtime.execute(
        "local_fixture",
        ProviderCapability.SUPPLIER_SEARCH,
        operation="supplier_search",
        config=ProviderConfig(
            "local_fixture",
            ProviderEnvironment.LOCAL_FIXTURE,
            {"fixture_scenario": "paginated", "page_size": "3"},
        ),
        owner_id=uuid.uuid4(),
        correlation_id="test-correlation",
        budget=RequestBudget(max_pages=2, max_items=10),
    )
    assert len(result.items) == 6
    assert result.context.correlation_id == "test-correlation"
    assert result.execution.status == "SUCCEEDED"
    assert result.execution.environment == "LOCAL_FIXTURE"


@pytest.mark.parametrize("scenario", ["rate_limited", "transient_5xx"])
def test_fixture_retries_transient_failures_without_sleep(scenario: str) -> None:
    runtime = create_runtime()
    result = runtime.execute(
        "local_fixture",
        ProviderCapability.SUPPLIER_SEARCH,
        operation="supplier_search",
        config=ProviderConfig(
            "local_fixture", ProviderEnvironment.LOCAL_FIXTURE, {"fixture_scenario": scenario}
        ),
        retry=RetryPolicy(max_attempts=3, maximum_delay_seconds=0),
    )
    assert result.execution.status == "SUCCEEDED"
    assert result.execution.attempts == 2


def test_fixture_errors_are_structured_and_non_retryable_auth_is_not_retried() -> None:
    runtime = create_runtime()
    with pytest.raises(ProviderRuntimeError) as caught:
        runtime.execute(
            "local_fixture",
            ProviderCapability.SUPPLIER_SEARCH,
            operation="supplier_search",
            config=ProviderConfig(
                "local_fixture",
                ProviderEnvironment.LOCAL_FIXTURE,
                {"fixture_scenario": "permanent_4xx"},
            ),
        )
    assert caught.value.code.value == "AUTHENTICATION"
    assert caught.value.retryable is False
    assert runtime.records[-1].attempts == 1


def test_fixture_timeout_is_retryable_but_bounded() -> None:
    runtime = create_runtime()
    with pytest.raises(ProviderRuntimeError) as caught:
        runtime.execute(
            "local_fixture",
            ProviderCapability.SUPPLIER_SEARCH,
            operation="supplier_search",
            config=ProviderConfig(
                "local_fixture", ProviderEnvironment.LOCAL_FIXTURE, {"fixture_scenario": "timeout"}
            ),
            retry=RetryPolicy(max_attempts=2, maximum_delay_seconds=0),
        )
    assert caught.value.code.value == "TIMEOUT"
    assert caught.value.retryable is True
    assert runtime.records[-1].attempts == 2


def test_malformed_response_is_schema_error_and_budget_is_bounded() -> None:
    runtime = create_runtime()
    with pytest.raises(ProviderRuntimeError, match="schema"):
        runtime.execute(
            "local_fixture",
            ProviderCapability.SUPPLIER_SEARCH,
            operation="supplier_search",
            config=ProviderConfig(
                "local_fixture",
                ProviderEnvironment.LOCAL_FIXTURE,
                {"fixture_scenario": "malformed"},
            ),
        )
    with pytest.raises(ProviderRuntimeError, match="page budget"):
        runtime.execute(
            "local_fixture",
            ProviderCapability.SUPPLIER_SEARCH,
            operation="supplier_search",
            config=ProviderConfig(
                "local_fixture",
                ProviderEnvironment.LOCAL_FIXTURE,
                {"fixture_scenario": "paginated"},
            ),
            budget=RequestBudget(max_pages=1, max_items=10),
        )


def test_credential_reference_is_resolved_without_safe_record_leak() -> None:
    secret = "fixture-super-secret-token"
    runtime = ProviderRuntime(
        resolver=StaticSecretResolver({"FIXTURE_TOKEN": secret}),
        adapters={
            "local_fixture": __import__(
                "vayujit_api.providers.fixture", fromlist=["LocalFixtureAdapter"]
            ).LocalFixtureAdapter()
        },
        transport=FixtureTransport(),
        sleeper=lambda _seconds: None,
    )
    result = runtime.execute(
        "local_fixture",
        ProviderCapability.SUPPLIER_SEARCH,
        operation="supplier_search",
        config=ProviderConfig("local_fixture", ProviderEnvironment.LOCAL_FIXTURE),
        credential_reference=CredentialReference("environment", "FIXTURE_TOKEN"),
    )
    assert secret not in str(result.execution.safe_dict())


def test_provider_config_rejects_secret_like_values_and_writes() -> None:
    with pytest.raises(ValueError, match="Secrets"):
        ProviderConfig(
            "local_fixture", ProviderEnvironment.LOCAL_FIXTURE, {"api_key": "secret"}
        ).validate()
    runtime = create_runtime()
    with pytest.raises(ProviderRuntimeError, match="capability"):
        runtime.execute(
            "local_fixture",
            ProviderCapability.LISTING_WRITE,
            operation="listing_write",
            config=ProviderConfig("local_fixture", ProviderEnvironment.LOCAL_FIXTURE),
        )


@pytest.mark.parametrize(
    "url", ["http://example.com", "https://127.0.0.1", "https://user:pass@example.com"]
)
def test_http_transport_rejects_unsafe_outbound_urls(url: str) -> None:
    with pytest.raises(ProviderRuntimeError, match="HTTPS|private|embedded"):
        HttpProviderTransport().request(ProviderRequest("GET", url, "health"), timeout_seconds=1.0)
