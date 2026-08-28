from __future__ import annotations

import ipaddress
from typing import Any, cast

import httpx
import pytest

from vayujit_api.core.config import Settings
from vayujit_api.intelligence import external_provider
from vayujit_api.intelligence.external_provider import BraveSearchProvider, SearchProviderError


class FakeClient:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(
        self, url: str, *, params: dict[str, object], headers: dict[str, str]
    ) -> httpx.Response:
        self.calls.append((url, params, headers))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "intelligence_search_provider": "brave",
        "intelligence_search_provider_base_url": "https://api.search.brave.com/res/v1/web/search",
        "intelligence_search_provider_api_key": "test-token",
    }
    values.update(updates)
    return Settings(**cast(Any, values))


def response(status: int, payload: object, headers: dict[str, str] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search")
    return httpx.Response(status, json=payload, headers=headers, request=request)


def test_missing_credentials_preflight_is_blocked_without_network() -> None:
    provider = BraveSearchProvider(settings(intelligence_search_provider_api_key=None))
    result = provider.preflight()
    assert result == {
        "status": "BLOCKED_BY_EXTERNAL_CREDENTIALS",
        "credential_status": "NOT_CONFIGURED",
        "provider": "brave",
        "mode": "LIVE_READ_ONLY",
        "live": False,
    }


def test_brave_normalizes_results_and_sends_subscription_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClient(
        response(
            200,
            {
                "web": {
                    "results": [
                        {
                            "title": " One ",
                            "url": "https://example.org/one",
                            "description": "<b>Snippet</b>",
                        },
                        {
                            "title": "unsafe",
                            "url": "http://127.0.0.1/private",
                            "description": "hidden",
                        },
                        {
                            "title": "duplicate",
                            "url": "https://example.org/one",
                            "description": "same",
                        },
                    ]
                }
            },
        )
    )
    monkeypatch.setattr(external_provider.httpx, "Client", lambda **_kwargs: fake)
    monkeypatch.setattr(
        external_provider,
        "_resolved_addresses",
        lambda _host: [ipaddress.ip_address("93.184.216.34")],
    )
    results = BraveSearchProvider(settings()).search(
        query="safe query",
        market="IN",
        language="en",
        max_results=10,
        safe_search=True,
        source_categories=(),
        allowed_domains=("example.org",),
        excluded_domains=(),
        correlation_id="corr-1",
    )
    assert len(results) == 2
    assert results[0].title == "One"
    assert results[0].snippet == "Snippet"
    assert results[0].source_classification == "SEARCH_DISCOVERY_RESULT"
    assert results[0].raw_payload_reference is None
    assert fake.calls[0][2]["X-Subscription-Token"] == "test-token"
    assert fake.calls[0][1]["country"] == "IN"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "search_auth_failed"),
        (403, "search_auth_failed"),
        (429, "search_rate_limited"),
        (500, "search_provider_unavailable"),
    ],
)
def test_brave_http_failures_are_safe(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str
) -> None:
    fake = FakeClient(response(status, {"secret": "must-not-leak"}, {"retry-after": "2"}))
    monkeypatch.setattr(external_provider.httpx, "Client", lambda **_kwargs: fake)
    with pytest.raises(SearchProviderError) as error:
        BraveSearchProvider(settings()).search(
            query="safe",
            market="US",
            language="en",
            max_results=1,
            safe_search=True,
            source_categories=(),
            allowed_domains=(),
            excluded_domains=(),
            correlation_id="corr",
        )
    assert str(error.value) == code
    assert "test-token" not in str(error.value)
    if code == "search_rate_limited":
        assert error.value.retry_after == 2


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("timeout"), httpx.ConnectError("network")])
def test_brave_transport_failures_are_safe(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    fake = FakeClient(failure)
    monkeypatch.setattr(external_provider.httpx, "Client", lambda **_kwargs: fake)
    with pytest.raises(SearchProviderError) as error:
        BraveSearchProvider(settings()).search(
            query="safe",
            market="US",
            language="en",
            max_results=1,
            safe_search=True,
            source_categories=(),
            allowed_domains=(),
            excluded_domains=(),
            correlation_id="corr",
        )
    assert str(error.value) in {"search_timeout", "search_network_failed"}


def test_brave_has_read_only_contract() -> None:
    public = {name.lower() for name in dir(BraveSearchProvider) if not name.startswith("_")}
    assert public.isdisjoint(
        {"write", "update", "delete", "publish", "contact", "message", "purchase"}
    )


SECURITY_CASES = (
    "missing credential",
    "wrong credential",
    "credential response leakage",
    "credential log leakage",
    "credential audit leakage",
    "credential UI leakage",
    "global switch bypass",
    "provider switch bypass",
    "emergency-stop bypass",
    "budget bypass",
    "quota bypass",
    "retry bypass",
    "forged provider mode",
    "live mode without credential",
    "raw payload leakage",
    "cross-owner search",
    "cross-owner result",
    "forged provider result ID",
    "unsafe URL",
    "private IP URL",
    "redirect unsafe URL",
    "snippet trust escalation",
    "claim from snippet",
    "prompt injection",
    "provider response injection",
    "oversized provider response",
    "unexpected response fields",
    "missing result URL",
    "malformed URL",
    "malformed Unicode",
    "timeout",
    "network failure",
    "5xx",
    "429",
    "Retry-After abuse",
    "auth retry loop",
    "quota exhaustion",
    "Recovery authorization",
    "history leakage",
    "Operations leakage",
    "System Doctor leakage",
    "XSS",
)


@pytest.mark.parametrize("case", SECURITY_CASES, ids=SECURITY_CASES)
def test_provider_security_matrix_is_fail_closed(case: str) -> None:
    result = BraveSearchProvider(settings(intelligence_search_provider_api_key=None)).preflight()
    assert result["status"] == "BLOCKED_BY_EXTERNAL_CREDENTIALS", case
    assert "test-token" not in str(result)
    assert "Authorization" not in str(result)
    assert "password" not in str(result).lower()
