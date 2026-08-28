"""Fail-closed provider-neutral search and approved-fetch transports."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlparse, urlunparse

import httpx

from vayujit_api.core.config import Settings
from vayujit_api.intelligence.policy import UnsafeURL, validate_source_url

INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal secrets",
    "reveal api key",
    "call tools",
    "send email",
    "change score",
    "approve supplier",
    "verify certification",
    "execute shell",
    "change configuration",
    "make a payment",
)
ALLOWED_MIME = {"text/html", "text/plain", "application/json"}


def canonical_url(value: str) -> str:
    safe = validate_source_url(value)
    if safe is None or urlparse(safe).scheme != "https":
        raise UnsafeURL("HTTPS is required for approved external fetches.")
    parsed = urlparse(safe)
    return urlunparse(
        ("https", (parsed.hostname or "").lower(), parsed.path or "/", "", parsed.query, "")
    )


def host_of(value: str) -> str:
    return (urlparse(value).hostname or "").lower().rstrip(".")


def _resolved_addresses(host: str) -> list[Any]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        try:
            return [
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            ]
        except OSError as exc:
            raise UnsafeURL("Unable to resolve external source host safely.") from exc


def validate_external_url(
    value: str, *, allowed_domains: tuple[str, ...] = (), blocked_domains: tuple[str, ...] = ()
) -> str:
    result = canonical_url(value)
    host = host_of(result)
    if blocked_domains and any(host == d or host.endswith("." + d) for d in blocked_domains):
        raise UnsafeURL("Source domain is blocked.")
    if allowed_domains and not any(host == d or host.endswith("." + d) for d in allowed_domains):
        raise UnsafeURL("Source domain is not allowlisted.")
    for address in _resolved_addresses(host):
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            raise UnsafeURL(
                "Private, loopback, link-local, and reserved addresses are not allowed."
            )
    return result


def classify_prompt_injection(value: str) -> dict[str, object]:
    lowered = value.lower()
    markers = [marker for marker in INJECTION_MARKERS if marker in lowered]
    return {
        "classification": "UNTRUSTED_EXTERNAL_DATA",
        "prompt_injection_detected": bool(markers),
        "markers": markers,
        "instructions_executable": False,
    }


def sanitize_text(value: str, *, max_length: int = 20_000) -> str:
    if len(value) > max_length:
        raise ValueError("response_too_large")
    value = re.sub(r"(?is)<(script|style|iframe|form)[^>]*>.*?</\1>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:max_length]


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    domain: str
    snippet: str
    published_at: datetime | None
    retrieved_at: datetime
    provider: str
    provider_result_id: str
    rank: int
    metadata: dict[str, object]
    raw_payload_reference: str | None
    source_classification: str = "SEARCH_DISCOVERY_RESULT"


class SearchProvider:
    name = "provider-neutral"

    def search(
        self,
        *,
        query: str,
        market: str,
        language: str,
        max_results: int,
        safe_search: bool,
        source_categories: tuple[str, ...],
        allowed_domains: tuple[str, ...],
        excluded_domains: tuple[str, ...],
        correlation_id: str,
    ) -> list[SearchResult]:
        raise NotImplementedError


class SearchProviderError(RuntimeError):
    """Safe provider failure with optional server-advertised backoff."""

    def __init__(self, code: str, *, retry_after: float | None = None) -> None:
        super().__init__(code)
        self.retry_after = retry_after


class LocalFixtureSearchProvider(SearchProvider):
    name = "local-fixture"

    def search(self, **kwargs: object) -> list[SearchResult]:
        now = datetime.now(UTC)
        query = str(kwargs["query"])
        return [
            SearchResult(
                "Local external research fixture",
                "https://example.org/research/" + hashlib.sha256(query.encode()).hexdigest()[:12],
                "example.org",
                "Fixture discovery result; verify by fetching the approved page.",
                None,
                now,
                self.name,
                "fixture-" + hashlib.sha256(query.encode()).hexdigest()[:16],
                1,
                {"safe_search": True},
                None,
            )
        ]


class HttpSearchProvider(SearchProvider):
    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(0.0, min(float(value), 60.0))
        except (TypeError, ValueError):
            return None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.name = settings.intelligence_search_provider

    def search(self, **kwargs: object) -> list[SearchResult]:
        if (
            not self.settings.intelligence_search_provider_base_url
            or not self.settings.intelligence_search_provider_api_key
        ):
            raise SearchProviderError("search_auth_failed")
        try:
            with httpx.Client(
                timeout=self.settings.intelligence_search_timeout_seconds, follow_redirects=False
            ) as client:
                response = client.get(
                    self.settings.intelligence_search_provider_base_url,
                    params={
                        "q": str(kwargs["query"]),
                        "limit": int(cast(Any, kwargs["max_results"])),
                    },
                    headers={"X-API-Key": self.settings.intelligence_search_provider_api_key},
                )
            if response.status_code == 429:
                raise SearchProviderError(
                    "search_rate_limited", retry_after=self._retry_after(response)
                )
            if response.status_code in {401, 403}:
                raise SearchProviderError("search_auth_failed")
            if response.status_code >= 500:
                raise SearchProviderError("search_provider_unavailable")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise SearchProviderError("search_invalid_response")
            now = datetime.now(UTC)
            return [
                SearchResult(
                    str(item["title"]),
                    validate_external_url(
                        str(item["url"]),
                        allowed_domains=cast(tuple[str, ...], kwargs.get("allowed_domains", ())),
                    ),
                    host_of(str(item["url"])),
                    str(item.get("snippet", ""))[:2000],
                    None,
                    now,
                    self.name,
                    str(item.get("id", index)),
                    index + 1,
                    {},
                    None,
                )
                for index, item in enumerate(payload)
            ]
        except httpx.TimeoutException as exc:
            raise SearchProviderError("search_timeout") from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError("search_network_failed") from exc
        except (TypeError, ValueError, KeyError) as exc:
            raise SearchProviderError("search_invalid_response") from exc


class BraveSearchProvider(SearchProvider):
    """Official Brave Web Search API adapter with a read-only contract."""

    name = "brave"
    default_base_url = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(0.0, min(float(value), 60.0))
        except (TypeError, ValueError):
            return None

    def preflight(self) -> dict[str, object]:
        """Perform a bounded, non-persisting read-only readiness check."""
        api_key = self.settings.intelligence_search_provider_api_key
        endpoint = self.settings.intelligence_search_provider_base_url or self.default_base_url
        if not api_key:
            return {
                "status": "BLOCKED_BY_EXTERNAL_CREDENTIALS",
                "credential_status": "NOT_CONFIGURED",
                "provider": self.name,
                "mode": "LIVE_READ_ONLY",
                "live": False,
            }
        try:
            started = datetime.now(UTC)
            timeout = httpx.Timeout(
                self.settings.intelligence_search_timeout_seconds,
                connect=min(self.settings.intelligence_search_timeout_seconds, 10.0),
            )
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.get(
                    endpoint,
                    params={
                        "q": "VAYUJIT provider preflight",
                        "count": 1,
                        "country": self.settings.intelligence_search_provider_country[:2],
                        "search_lang": self.settings.intelligence_search_provider_language,
                        "safesearch": "strict",
                    },
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
                    },
                )
            latency_ms = max(0, int((datetime.now(UTC) - started).total_seconds() * 1000))
            base = {
                "provider": self.name,
                "mode": "LIVE_READ_ONLY",
                "live": True,
                "latency_ms": latency_ms,
            }
            if response.status_code in {401, 403}:
                return base | {
                    "status": "AUTH_ERROR",
                    "credential_status": "INVALID",
                    "http_status": response.status_code,
                }
            if response.status_code == 429:
                result = base | {
                    "status": "RATE_LIMITED",
                    "credential_status": "CONFIGURED",
                    "http_status": response.status_code,
                }
                retry_after = self._retry_after(response)
                return result | (
                    {"retry_after_seconds": retry_after} if retry_after is not None else {}
                )
            if response.status_code >= 500:
                return base | {
                    "status": "UNAVAILABLE",
                    "credential_status": "CONFIGURED",
                    "http_status": response.status_code,
                }
            response.raise_for_status()
            if not isinstance(response.json(), dict):
                return base | {"status": "INVALID_RESPONSE", "credential_status": "CONFIGURED"}
            return base | {"status": "VALIDATED", "credential_status": "CONFIGURED"}
        except httpx.TimeoutException:
            return {
                "status": "TIMEOUT",
                "credential_status": "CONFIGURED",
                "provider": self.name,
                "mode": "LIVE_READ_ONLY",
                "live": True,
            }
        except httpx.HTTPError:
            return {
                "status": "UNAVAILABLE",
                "credential_status": "CONFIGURED",
                "provider": self.name,
                "mode": "LIVE_READ_ONLY",
                "live": True,
            }
        except (TypeError, ValueError, KeyError):
            return {
                "status": "INVALID_RESPONSE",
                "credential_status": "CONFIGURED",
                "provider": self.name,
                "mode": "LIVE_READ_ONLY",
                "live": True,
            }

    def search(self, **kwargs: object) -> list[SearchResult]:
        api_key = self.settings.intelligence_search_provider_api_key
        endpoint = self.settings.intelligence_search_provider_base_url or self.default_base_url
        if not api_key or not endpoint:
            raise SearchProviderError("search_auth_failed")
        query = str(kwargs["query"])
        max_results = int(cast(Any, kwargs["max_results"]))
        language = str(
            kwargs.get("language") or self.settings.intelligence_search_provider_language
        )
        country = str(
            kwargs.get("market") or self.settings.intelligence_search_provider_country
        ).upper()
        params: dict[str, str | int] = {
            "q": query,
            "count": max_results,
            "country": country[:2],
            "search_lang": language,
            "safesearch": "strict" if bool(kwargs.get("safe_search", True)) else "off",
        }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    self.settings.intelligence_search_timeout_seconds,
                    connect=min(self.settings.intelligence_search_timeout_seconds, 10.0),
                ),
                follow_redirects=False,
            ) as client:
                response = client.get(
                    endpoint,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
                    },
                )
            if response.status_code in {401, 403}:
                raise SearchProviderError("search_auth_failed")
            if response.status_code == 429:
                raise SearchProviderError(
                    "search_rate_limited", retry_after=self._retry_after(response)
                )
            if response.status_code >= 500:
                raise SearchProviderError("search_provider_unavailable")
            response.raise_for_status()
            payload = response.json()
            web = payload.get("web") if isinstance(payload, dict) else None
            raw_results = web.get("results") if isinstance(web, dict) else None
            if not isinstance(raw_results, list):
                raise SearchProviderError("search_invalid_response")
            now = datetime.now(UTC)
            normalized: list[SearchResult] = []
            allowed = cast(tuple[str, ...], kwargs.get("allowed_domains", ()))
            for index, item in enumerate(raw_results[:max_results], start=1):
                if not isinstance(item, dict) or not item.get("url"):
                    continue
                try:
                    safe_url = validate_external_url(str(item["url"]), allowed_domains=allowed)
                except UnsafeURL:
                    continue
                title = sanitize_text(str(item.get("title", "")), max_length=500)
                snippet = sanitize_text(str(item.get("description", "")), max_length=2000)
                if not title or not snippet:
                    continue
                normalized.append(
                    SearchResult(
                        title=title,
                        url=safe_url,
                        domain=host_of(safe_url),
                        snippet=snippet,
                        published_at=None,
                        retrieved_at=now,
                        provider=self.name,
                        provider_result_id=str(item.get("url", index)),
                        rank=index,
                        metadata={
                            "country": country[:2],
                            "language": language,
                            "safe_search": bool(kwargs.get("safe_search", True)),
                        },
                        raw_payload_reference=None,
                    )
                )
            return normalized
        except httpx.TimeoutException as exc:
            raise SearchProviderError("search_timeout") from exc
        except httpx.HTTPError as exc:
            raise SearchProviderError("search_network_failed") from exc
        except (TypeError, ValueError, KeyError) as exc:
            raise SearchProviderError("search_invalid_response") from exc


class ApprovedWebFetcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch(
        self, url: str, *, allowed_domains: tuple[str, ...], blocked_domains: tuple[str, ...] = ()
    ) -> dict[str, object]:
        requested = validate_external_url(
            url, allowed_domains=allowed_domains, blocked_domains=blocked_domains
        )
        try:
            with httpx.Client(
                timeout=self.settings.intelligence_fetch_timeout_seconds,
                follow_redirects=True,
                max_redirects=self.settings.intelligence_fetch_max_redirects,
            ) as client:
                response = client.get(
                    requested, headers={"Accept": "text/html,text/plain,application/json"}
                )
            final_url = validate_external_url(
                str(response.url), allowed_domains=allowed_domains, blocked_domains=blocked_domains
            )
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type not in ALLOWED_MIME:
                raise RuntimeError("mime_blocked")
            raw = response.content
            if len(raw) > self.settings.intelligence_fetch_max_bytes:
                raise RuntimeError("response_too_large")
            text = raw.decode(response.encoding or "utf-8", errors="replace")
            extracted = {
                "title": "",
                "meta_description": "",
                "text": sanitize_text(text, max_length=self.settings.intelligence_fetch_max_bytes),
                "canonical_url": final_url,
                "prompt_injection": classify_prompt_injection(text),
            }
            digest = hashlib.sha256(raw).hexdigest()
            return {
                "requested_url": requested,
                "final_url": final_url,
                "domain": host_of(final_url),
                "status": "COMPLETED",
                "http_status": response.status_code,
                "content_type": content_type,
                "content_length": len(raw),
                "content_hash": digest,
                "redirect_count": len(response.history),
                "extracted": extracted,
                "classification": "UNTRUSTED_EXTERNAL_DATA",
            }
        except httpx.TimeoutException as exc:
            raise RuntimeError("fetch_timeout") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("fetch_network_failed") from exc
