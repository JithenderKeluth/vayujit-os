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
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.name = settings.intelligence_search_provider

    def search(self, **kwargs: object) -> list[SearchResult]:
        if (
            not self.settings.intelligence_search_provider_base_url
            or not self.settings.intelligence_search_provider_api_key
        ):
            raise RuntimeError("search_auth_failed")
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
                raise RuntimeError("search_rate_limited")
            if response.status_code in {401, 403}:
                raise RuntimeError("search_auth_failed")
            if response.status_code >= 500:
                raise RuntimeError("search_provider_unavailable")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise RuntimeError("search_invalid_response")
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
            raise RuntimeError("search_timeout") from exc


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
