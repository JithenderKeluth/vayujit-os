"""Deterministic provider adapter and transport used for 14A certification."""

from __future__ import annotations

from enum import StrEnum

from vayujit_api.providers.contracts import (
    ProviderConfig,
    ProviderPage,
    ProviderRequest,
    ProviderResponse,
)


class FixtureScenario(StrEnum):
    SUCCESS = "success"
    PAGINATED = "paginated"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    TRANSIENT_5XX = "transient_5xx"
    PERMANENT_4XX = "permanent_4xx"
    MALFORMED = "malformed"


class FixtureTransportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class FixtureTransport:
    """No-network transport with deterministic failure injection."""

    def __init__(self) -> None:
        self.calls = 0
        self._attempts: dict[str, int] = {}

    def request(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse:
        del timeout_seconds
        self.calls += 1
        scenario = request.params.get("scenario", FixtureScenario.SUCCESS.value)
        key = f"{scenario}:{request.page_token or 'first'}"
        attempt = self._attempts.get(key, 0) + 1
        self._attempts[key] = attempt
        if scenario == FixtureScenario.TIMEOUT:
            raise FixtureTransportError("TIMEOUT", "fixture timeout")
        if scenario == FixtureScenario.RATE_LIMITED and attempt == 1:
            return ProviderResponse(429, {"retry-after": "0"}, {})
        if scenario == FixtureScenario.TRANSIENT_5XX and attempt == 1:
            return ProviderResponse(503, {"retry-after": "0"}, {})
        if scenario == FixtureScenario.PERMANENT_4XX:
            return ProviderResponse(401, {}, {})
        if scenario == FixtureScenario.MALFORMED:
            return ProviderResponse(200, {}, {"unexpected": True})
        page = int(request.page_token or "0")
        items = [
            {
                "provider_result_id": f"fixture-{page}-{index}",
                "supplier_name": f"Fixture Supplier {index}",
                "listing_name": "Disposable fixture offering",
                "source_url": "https://fixture.invalid/supplier",
                "verification": "UNVERIFIED",
            }
            for index in range(1, 4)
        ]
        next_token = str(page + 1) if scenario == FixtureScenario.PAGINATED and page == 0 else None
        return ProviderResponse(
            200, {"x-fixture-quota-remaining": "99"}, {"items": items, "next": next_token}
        )


class LocalFixtureAdapter:
    adapter_id = "local_fixture"

    def build_request(
        self, operation: str, config: ProviderConfig, credential: str | None, page_token: str | None
    ) -> ProviderRequest:
        del credential
        scenario = config.values.get("fixture_scenario", FixtureScenario.SUCCESS.value)
        return ProviderRequest(
            method="GET",
            url="fixture://local/suppliers",
            operation=operation,
            params={"scenario": scenario, "page_size": config.values.get("page_size", "3")},
            page_token=page_token,
        )

    def validate_response(self, response: ProviderResponse) -> None:
        if not isinstance(response.body, dict) or not isinstance(response.body.get("items"), list):
            raise ValueError("Fixture response schema is invalid.")

    def normalize(self, response: ProviderResponse) -> ProviderPage:
        self.validate_response(response)
        body = response.body
        assert isinstance(body, dict)
        items = tuple(item for item in body["items"] if isinstance(item, dict))
        if len(items) != len(body["items"]):
            raise ValueError("Fixture response item schema is invalid.")
        next_token = body.get("next")
        return ProviderPage(
            items=items, next_token=next_token if isinstance(next_token, str) else None
        )
