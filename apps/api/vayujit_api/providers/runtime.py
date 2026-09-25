"""Shared bounded execution runtime for provider adapters."""

from __future__ import annotations

import ipaddress
import time
import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import BoundedSemaphore, Lock
from typing import Protocol
from urllib.parse import urlparse

import httpx

from vayujit_api.operations.staging import record_provider_metric
from vayujit_api.providers.contracts import (
    CapabilityKind,
    CredentialReference,
    CredentialRequirement,
    ProviderAdapter,
    ProviderCapability,
    ProviderConfig,
    ProviderEnvironment,
    ProviderErrorCode,
    ProviderExecutionContext,
    ProviderPage,
    ProviderRequest,
    ProviderResponse,
)
from vayujit_api.providers.credentials import (
    EnvironmentSecretResolver,
    ResolvedCredential,
    SecretResolver,
)
from vayujit_api.providers.redaction import redact, safe_error_message
from vayujit_api.providers.registry import ProviderRegistry, provider_registry


class ProviderRuntimeError(RuntimeError):
    def __init__(
        self,
        code: ProviderErrorCode,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
        status_code: int | None = None,
    ) -> None:
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code
        super().__init__(message)

    def safe_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "retryable": self.retryable,
            "retry_after_seconds": self.retry_after_seconds,
            "status_code": self.status_code,
            "message": safe_error_message(self),
        }


class ProviderTransport(Protocol):
    def request(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse: ...


class HttpProviderTransport:
    """The sole normal outbound HTTP boundary for future live adapters."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def request(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse:
        _validate_outbound_url(request.url)
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout_seconds),
                follow_redirects=False,
                transport=self._transport,
                headers={"User-Agent": "VAYUJIT-ProviderRuntime/1.0"},
            ) as client:
                response = client.request(
                    request.method,
                    request.url,
                    params=request.params,
                    json=request.json_body,
                )
        except httpx.TimeoutException as error:
            raise ProviderRuntimeError(
                ProviderErrorCode.TIMEOUT, "The provider request timed out.", retryable=True
            ) from error
        except httpx.NetworkError as error:
            raise ProviderRuntimeError(
                ProviderErrorCode.NETWORK, "The provider network request failed.", retryable=True
            ) from error
        except httpx.HTTPError as error:
            raise ProviderRuntimeError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "The provider could not be reached safely.",
                retryable=True,
            ) from error
        return ProviderResponse(
            response.status_code,
            {key.casefold(): value for key, value in response.headers.items()},
            _bounded_json(response),
        )


def _validate_outbound_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ProviderRuntimeError(
            ProviderErrorCode.CONFIGURATION,
            "Provider URL must use HTTPS without embedded credentials or fragments.",
        )
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
        (".local", ".internal")
    ):
        raise ProviderRuntimeError(
            ProviderErrorCode.CONFIGURATION,
            "Provider URL targets a private or local network.",
        )
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ProviderRuntimeError(
            ProviderErrorCode.CONFIGURATION,
            "Provider URL targets a private or local network.",
        )


def _bounded_json(response: httpx.Response) -> object:
    if len(response.content) > 1_000_000:
        raise ProviderRuntimeError(
            ProviderErrorCode.SCHEMA_ERROR, "Provider response was too large."
        )
    try:
        return response.json()
    except ValueError:
        return response.text[:4000]


def parse_retry_after(
    value: object, *, now: datetime | None = None, maximum: int = 3600
) -> int | None:
    if value is None:
        return None
    seconds: float
    try:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            seconds = float(str(value))
        else:
            seconds = float(value)
    except (TypeError, ValueError):
        if not isinstance(value, str):
            return None
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            seconds = (parsed - (now or datetime.now(UTC))).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return min(maximum, max(0, int(seconds + 0.999)))


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    maximum_delay_seconds: int = 8

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5 or self.maximum_delay_seconds < 0:
            raise ValueError("Retry policy is outside the bounded runtime limits.")


@dataclass(frozen=True)
class RequestBudget:
    max_pages: int = 10
    max_items: int = 200

    def __post_init__(self) -> None:
        if not 1 <= self.max_pages <= 100 or not 1 <= self.max_items <= 10_000:
            raise ValueError("Provider request budget is outside the bounded limits.")


@dataclass(frozen=True)
class RateLimitPolicy:
    requests_per_minute: int = 60
    max_concurrent: int = 4

    def __post_init__(self) -> None:
        if not 1 <= self.requests_per_minute <= 10_000 or not 1 <= self.max_concurrent <= 32:
            raise ValueError("Rate-limit policy is outside the bounded limits.")


@dataclass(frozen=True)
class ProviderExecutionRecord:
    provider_id: str
    capability: str
    environment: str
    correlation_id: str
    provider_execution_id: str
    status: str
    attempts: int
    result_count: int
    duration_ms: int
    error: dict[str, object] | None = None
    rate_limit_remaining: int | None = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def safe_dict(self) -> dict[str, object]:
        return redact(
            {
                "provider_id": self.provider_id,
                "capability": self.capability,
                "environment": self.environment,
                "correlation_id": self.correlation_id,
                "provider_execution_id": self.provider_execution_id,
                "status": self.status,
                "attempts": self.attempts,
                "result_count": self.result_count,
                "duration_ms": self.duration_ms,
                "error": self.error,
                "rate_limit_remaining": self.rate_limit_remaining,
                "completed_at": self.completed_at.isoformat(),
            }
        )


@dataclass(frozen=True)
class RuntimeResult:
    context: ProviderExecutionContext
    items: tuple[Mapping[str, object], ...]
    execution: ProviderExecutionRecord
    next_token: str | None = None

    def safe_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.context.provider_id,
            "correlation_id": self.context.correlation_id,
            "provider_execution_id": self.context.provider_execution_id,
            "items": [redact(item) for item in self.items],
            "execution": self.execution.safe_dict(),
            "next_token": self.next_token,
        }


class _Limiter:
    def __init__(self) -> None:
        self._last: dict[tuple[str, str], float] = {}
        self._semaphores: dict[tuple[str, str], BoundedSemaphore] = {}
        self._lock = Lock()

    def slot(
        self, provider_id: str, capability: ProviderCapability, policy: RateLimitPolicy
    ) -> BoundedSemaphore:
        key = (provider_id, capability.value)
        with self._lock:
            return self._semaphores.setdefault(key, BoundedSemaphore(policy.max_concurrent))

    def acquire(
        self,
        provider_id: str,
        capability: ProviderCapability,
        policy: RateLimitPolicy,
        *,
        bypass: bool = False,
    ) -> None:
        if bypass:
            return
        key = (provider_id, capability.value)
        now = time.monotonic()
        interval = 60.0 / policy.requests_per_minute
        previous = self._last.get(key)
        if previous is not None and now - previous < interval:
            raise ProviderRuntimeError(
                ProviderErrorCode.RATE_LIMITED,
                "The provider runtime rate limit was reached.",
                retryable=True,
                retry_after_seconds=max(1, int(interval - (now - previous))),
            )
        self._last[key] = now


class ProviderRuntime:
    """Bounded, observable execution for thin provider adapters."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry = provider_registry,
        resolver: SecretResolver | None = None,
        adapters: Mapping[str, ProviderAdapter] | None = None,
        transport: ProviderTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.registry = registry
        self.resolver = resolver or EnvironmentSecretResolver()
        self.adapters = dict(adapters or {})
        self.transport = transport or HttpProviderTransport()
        self.sleeper = sleeper
        self._limiter = _Limiter()
        self.records: list[ProviderExecutionRecord] = []
        self.counters: defaultdict[str, int] = defaultdict(int)

    def execute(
        self,
        provider_id: str,
        capability: ProviderCapability,
        *,
        operation: str,
        config: ProviderConfig,
        owner_id: uuid.UUID | None = None,
        credential_reference: CredentialReference | None = None,
        correlation_id: str | None = None,
        retry: RetryPolicy | None = None,
        budget: RequestBudget | None = None,
        rate_limit: RateLimitPolicy | None = None,
    ) -> RuntimeResult:
        started = time.perf_counter()
        retry = retry or RetryPolicy()
        budget = budget or RequestBudget()
        rate_limit = rate_limit or RateLimitPolicy()
        definition = self.registry.get(provider_id)
        if config.provider_id != definition.provider_id:
            raise ProviderRuntimeError(
                ProviderErrorCode.CONFIGURATION, "Provider configuration does not match registry."
            )
        config.validate()
        if not definition.enabled:
            raise ProviderRuntimeError(ProviderErrorCode.CONFIGURATION, "Provider is disabled.")
        if not definition.supports(capability, config.environment):
            raise ProviderRuntimeError(
                ProviderErrorCode.CONFIGURATION,
                "Provider capability is unavailable in this environment.",
            )
        if definition.kind_for(capability) is not CapabilityKind.READ:
            raise ProviderRuntimeError(
                ProviderErrorCode.AUTHORIZATION, "External provider writes are disabled in 14A."
            )
        adapter = self.adapters.get(definition.adapter_id)
        if adapter is None:
            raise ProviderRuntimeError(
                ProviderErrorCode.CONFIGURATION, "Provider adapter is not available."
            )
        credential = self._resolve(definition.credential_requirements, credential_reference)
        correlation = correlation_id or str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        context = ProviderExecutionContext(
            provider_id=provider_id,
            owner_id=owner_id,
            correlation_id=correlation,
            request_id=str(uuid.uuid4()),
            provider_execution_id=execution_id,
            capability=capability,
            environment=config.environment,
        )
        page_token: str | None = None
        all_items: list[Mapping[str, object]] = []
        attempts = 0
        remaining: int | None = None
        try:
            for _page in range(budget.max_pages):
                request = adapter.build_request(operation, config, credential.value, page_token)
                response = self._request_with_retry(
                    provider_id,
                    capability,
                    adapter,
                    request,
                    retry,
                    rate_limit,
                )
                attempts += self._last_attempts
                remaining = _quota_remaining(response.headers)
                adapter.validate_response(response)
                page: ProviderPage = adapter.normalize(response)
                all_items.extend(page.items)
                if len(all_items) > budget.max_items:
                    raise ProviderRuntimeError(
                        ProviderErrorCode.QUOTA, "Provider result budget was exceeded."
                    )
                page_token = page.next_token
                if page_token is None:
                    break
            else:
                raise ProviderRuntimeError(
                    ProviderErrorCode.QUOTA, "Provider page budget was exceeded."
                )
            record = self._record(
                provider_id,
                capability,
                config.environment,
                correlation,
                execution_id,
                "SUCCEEDED",
                attempts,
                len(all_items),
                started,
                remaining,
            )
            return RuntimeResult(context, tuple(all_items), record, page_token)
        except ProviderRuntimeError as error:
            record = self._record(
                provider_id,
                capability,
                config.environment,
                correlation,
                execution_id,
                "FAILED",
                max(1, attempts + self._last_attempts),
                len(all_items),
                started,
                remaining,
                error,
            )
            raise
        except ValueError as error:
            normalized = ProviderRuntimeError(
                ProviderErrorCode.SCHEMA_ERROR, "Provider response schema was invalid."
            )
            record = self._record(
                provider_id,
                capability,
                config.environment,
                correlation,
                execution_id,
                "FAILED",
                max(1, attempts),
                len(all_items),
                started,
                remaining,
                normalized,
            )
            raise normalized from error

    def _resolve(
        self, requirements: tuple[CredentialRequirement, ...], reference: CredentialReference | None
    ) -> ResolvedCredential:
        requirement = next(
            (item for item in requirements if getattr(item, "required", False)), None
        )
        if requirement is None and reference is None:
            return ResolvedCredential(None, None)
        if reference is None:
            if requirement is None:
                return ResolvedCredential(None, None)
            reference = CredentialReference("environment", str(requirement.environment_key))
        try:
            resolved = self.resolver.resolve(reference)
        except Exception as error:
            raise ProviderRuntimeError(
                ProviderErrorCode.CONFIGURATION, "Provider credential could not be resolved safely."
            ) from error
        if requirement is not None and requirement.required and not resolved.configured:
            raise ProviderRuntimeError(
                ProviderErrorCode.CONFIGURATION, "A required provider credential is missing."
            )
        return resolved

    _last_attempts: int = 0

    def _request_with_retry(
        self,
        provider_id: str,
        capability: ProviderCapability,
        adapter: ProviderAdapter,
        request: ProviderRequest,
        policy: RetryPolicy,
        rate_limit: RateLimitPolicy,
    ) -> ProviderResponse:
        del adapter
        last: ProviderRuntimeError | None = None
        self._last_attempts = 0
        for attempt in range(1, policy.max_attempts + 1):
            self._last_attempts = attempt
            slot = self._limiter.slot(provider_id, capability, rate_limit)
            slot.acquire()
            try:
                try:
                    self._limiter.acquire(provider_id, capability, rate_limit, bypass=attempt > 1)
                    response = self.transport.request(request, timeout_seconds=30.0)
                    error = _response_error(response)
                    if error is not None:
                        raise error
                    self.counters["provider_requests_total"] += 1
                    return response
                except ProviderRuntimeError as error:
                    last = error
                    self.counters[f"provider_error.{error.code.value}"] += 1
                    if not error.retryable or attempt == policy.max_attempts:
                        break
                    self.counters["provider_retry_total"] += 1
                    delay = min(
                        float(error.retry_after_seconds or 2 ** (attempt - 1)),
                        float(policy.maximum_delay_seconds),
                    )
                    self.sleeper(delay)
                except Exception as error:
                    code = getattr(error, "code", "NETWORK")
                    normalized = (
                        ProviderErrorCode.TIMEOUT
                        if code == "TIMEOUT"
                        else ProviderErrorCode.NETWORK
                    )
                    last = ProviderRuntimeError(
                        normalized,
                        (
                            "The provider request timed out."
                            if normalized is ProviderErrorCode.TIMEOUT
                            else "The provider request failed safely."
                        ),
                        retryable=True,
                    )
                    if attempt == policy.max_attempts:
                        break
                    self.sleeper(
                        min(float(2 ** (attempt - 1)), float(policy.maximum_delay_seconds))
                    )
            finally:
                slot.release()
        assert last is not None
        raise last

    def _record(
        self,
        provider_id: str,
        capability: ProviderCapability,
        environment: ProviderEnvironment,
        correlation_id: str,
        execution_id: str,
        status: str,
        attempts: int,
        result_count: int,
        started: float,
        remaining: int | None,
        error: ProviderRuntimeError | None = None,
    ) -> ProviderExecutionRecord:
        self.counters["provider_executions_total"] += 1
        record = ProviderExecutionRecord(
            provider_id,
            capability.value,
            environment.value,
            correlation_id,
            execution_id,
            status,
            attempts,
            result_count,
            round((time.perf_counter() - started) * 1000),
            error.safe_dict() if error else None,
            remaining,
        )
        if status == "SUCCEEDED":
            self.counters["provider_success_total"] += 1
        else:
            self.counters["provider_failure_total"] += 1
        self.records.append(record)
        record_provider_metric(provider_id, status.casefold())
        return record

    def health(self, provider_id: str) -> dict[str, object]:
        definition = self.registry.get(provider_id)
        records = [item for item in self.records if item.provider_id == provider_id]
        last = records[-1] if records else None
        return {
            "provider_id": provider_id,
            "registered": True,
            "adapter_available": definition.adapter_id in self.adapters,
            "configuration": "STATIC_REGISTRY",
            "credential": (
                "REFERENCE_REQUIRED" if definition.credential_requirements else "NOT_REQUIRED"
            ),
            "connectivity": "NOT_TESTED",
            "provider": "NOT_VERIFIED",
            "last_execution": last.safe_dict() if last else None,
        }


def _quota_remaining(headers: Mapping[str, str]) -> int | None:
    value = headers.get("x-fixture-quota-remaining") or headers.get("x-ratelimit-remaining")
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _response_error(response: ProviderResponse) -> ProviderRuntimeError | None:
    status = response.status_code
    if 200 <= status < 300:
        return None
    retry_after = parse_retry_after(response.headers.get("retry-after"))
    if status == 401:
        return ProviderRuntimeError(
            ProviderErrorCode.AUTHENTICATION, "Provider authentication failed.", status_code=status
        )
    if status == 403:
        return ProviderRuntimeError(
            ProviderErrorCode.AUTHORIZATION, "Provider authorization failed.", status_code=status
        )
    if status == 404:
        return ProviderRuntimeError(
            ProviderErrorCode.NOT_FOUND, "Provider resource was not found.", status_code=status
        )
    if status == 429:
        return ProviderRuntimeError(
            ProviderErrorCode.RATE_LIMITED,
            "The provider rate limit was reached.",
            retryable=True,
            retry_after_seconds=retry_after,
            status_code=status,
        )
    if status >= 500:
        return ProviderRuntimeError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "The provider is temporarily unavailable.",
            retryable=True,
            retry_after_seconds=retry_after,
            status_code=status,
        )
    return ProviderRuntimeError(
        ProviderErrorCode.INVALID_REQUEST, "The provider rejected the request.", status_code=status
    )
