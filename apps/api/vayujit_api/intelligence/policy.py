from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException


class UnsafeURL(ValueError):
    """Raised when a URL is outside the approved external-content boundary."""


def validate_source_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("Only http and https source URLs are supported.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Source URLs may not contain embedded credentials.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURL("A source URL hostname is required.")
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith(
        ".localhost"
    ):
        raise UnsafeURL("Local and metadata hosts are not allowed.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    ):
        raise UnsafeURL("Private, loopback, link-local, and reserved addresses are not allowed.")
    if parsed.port and parsed.port not in {80, 443}:
        raise UnsafeURL("Non-standard source URL ports are not allowed.")
    return value.strip()


def enforce_access_method(method: str) -> str:
    if method not in {
        "api",
        "approved_web_fetch",
        "manual_import",
        "manual_entry",
        "internal",
        "provider_connector",
    }:
        raise HTTPException(422, "Unsupported source access method.")
    return method


@dataclass(frozen=True)
class FreshnessPolicy:
    fresh_seconds: int
    aging_seconds: int
    stale_seconds: int


DEFAULT_FRESHNESS_POLICIES: dict[str, FreshnessPolicy] = {
    "marketplace": FreshnessPolicy(6 * 3600, 24 * 3600, 7 * 86400),
    "trend_source": FreshnessPolicy(3600, 6 * 3600, 24 * 3600),
    "supplier_directory": FreshnessPolicy(7 * 86400, 30 * 86400, 90 * 86400),
    "document": FreshnessPolicy(30 * 86400, 90 * 86400, 365 * 86400),
    "manual": FreshnessPolicy(7 * 86400, 30 * 86400, 90 * 86400),
}


def freshness_status(
    observed_at: datetime,
    *,
    policy: FreshnessPolicy | None = None,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> str:
    if observed_at.tzinfo is None:
        return "unknown"
    current = now or datetime.now(observed_at.tzinfo)
    age = max(0, int((current - observed_at).total_seconds()))
    if ttl_seconds is not None and ttl_seconds <= 0:
        return "expired"
    selected = policy or FreshnessPolicy(86400, 7 * 86400, 30 * 86400)
    if ttl_seconds is not None:
        selected = FreshnessPolicy(ttl_seconds, ttl_seconds * 2, ttl_seconds * 4)
    if age <= selected.fresh_seconds:
        return "fresh"
    if age <= selected.aging_seconds:
        return "aging"
    if age <= selected.stale_seconds:
        return "stale"
    return "expired"


def normalize_quantity(value: float, unit: str) -> tuple[float, str]:
    """Normalize common physical units for deterministic rule inputs."""
    conversions = {
        "g": (0.001, "kg"),
        "kg": (1.0, "kg"),
        "mm": (0.001, "m"),
        "cm": (0.01, "m"),
        "m": (1.0, "m"),
        "ml": (0.001, "l"),
        "l": (1.0, "l"),
    }
    normalized = conversions.get(unit.lower())
    if normalized is None:
        raise HTTPException(422, "Unsupported measurement unit.")
    factor, canonical = normalized
    return value * factor, canonical


def normalize_status(value: str, allowed: tuple[str, ...], field: str) -> str:
    if value not in allowed:
        raise HTTPException(422, f"Invalid {field}.")
    return value


def safe_external_content(value: str, *, max_length: int = 20_000) -> str:
    if len(value) > max_length:
        raise HTTPException(413, "Evidence content exceeds the safe size limit.")
    return value


UNTRUSTED_EXTERNAL_DATA = "untrusted_external_data"


def validate_metadata(value: dict[str, object]) -> dict[str, object]:
    blocked = ("password", "secret", "token", "credential", "api_key", "cookie", "authorization")

    def walk(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if any(part in str(key).lower() for part in blocked):
                    raise HTTPException(
                        422, "Sensitive credentials are not accepted in Intelligence metadata."
                    )
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return value
