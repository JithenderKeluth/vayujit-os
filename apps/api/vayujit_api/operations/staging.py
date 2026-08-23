"""Provider-neutral staging controls and certification helpers.

The staging boundary is deliberately small: connectors continue to own provider
protocol details, while this module owns mode, safety, status, privacy, and
failure taxonomy shared by every connector.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Literal

from vayujit_api.core.config import Settings
from vayujit_api.core.observability import maintenance_enabled
from vayujit_api.publishing.shopify_connector import validate_api_version, validate_shop_domain

ProviderMode = Literal["fake", "sandbox", "live"]
ProviderAccountState = Literal[
    "NOT_CONFIGURED", "CONFIGURED", "VALIDATING", "VALID", "INVALID", "DISABLED"
]


class StagingSafetyError(RuntimeError):
    """Raised when a staging provider operation is not safe to execute."""


@dataclass(frozen=True)
class ProviderRuntimeLineage:
    provider: str
    mode: ProviderMode
    account_id: str | None = None
    job_id: str | None = None
    attempt_id: str | None = None
    mapping_id: str | None = None
    correlation_id: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderAccountStatus:
    provider: str
    account_id: str | None
    state: ProviderAccountState
    mode: ProviderMode
    capability: str
    safe_message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def safe_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "account_id": self.account_id,
            "state": self.state,
            "mode": self.mode,
            "capability": self.capability,
            "safe_message": self.safe_message,
            "checked_at": self.checked_at.isoformat(),
        }


class ProviderAccountRegistry:
    """In-memory status registry used by diagnostics and staging drills.

    Persisted provider configurations remain the source of truth. This registry
    intentionally contains status only; it never stores credentials or payloads.
    """

    def __init__(self) -> None:
        self._items: dict[tuple[str, str | None], ProviderAccountStatus] = {}

    def set(self, status: ProviderAccountStatus) -> ProviderAccountStatus:
        self._items[(status.provider, status.account_id)] = status
        return status

    def get(self, provider: str, account_id: str | None = None) -> ProviderAccountStatus:
        return self._items.get(
            (provider, account_id),
            ProviderAccountStatus(
                provider=provider,
                account_id=account_id,
                state="NOT_CONFIGURED",
                mode="fake",
                capability="unknown",
                safe_message="Provider account is not configured.",
            ),
        )

    def safe_list(self) -> list[dict[str, object]]:
        return [item.safe_dict() for item in self._items.values()]


class IdempotencyLedger:
    """Small durable-operation seam used by adapters and deterministic drills."""

    def __init__(self) -> None:
        self._results: dict[str, object] = {}
        self._lock = Lock()

    def execute(self, key: str, operation: Any) -> tuple[object, bool]:
        if not key or len(key) > 200:
            raise StagingSafetyError("A bounded idempotency key is required.")
        with self._lock:
            if key in self._results:
                return self._results[key], True
            result = operation()
            self._results[key] = result
            return result, False

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return dict(self._results)


_metrics: Counter[str] = Counter()
_metrics_lock = Lock()


def record_provider_metric(provider: str, metric: str) -> None:
    with _metrics_lock:
        _metrics[f"provider.{provider}.{metric}"] += 1


def provider_metrics_snapshot() -> dict[str, int]:
    with _metrics_lock:
        return dict(_metrics)


def normalize_provider_failure(error: Exception) -> dict[str, object]:
    if all(
        hasattr(error, attribute)
        for attribute in ("code", "retryable", "ambiguous", "safe_message", "retry_after")
    ):
        values = vars(error)
        code = values["code"]
        retryable = values["retryable"]
        ambiguous = values["ambiguous"]
        safe_message = values["safe_message"]
        retry_after = values["retry_after"]
    else:
        code = "provider_unavailable"
        retryable = True
        ambiguous = False
        retry_after = None
        safe_message = "The provider could not be reached safely."
    record_provider_metric("unknown", code)
    return {
        "code": code,
        "retryable": retryable,
        "ambiguous": ambiguous,
        "retry_after": retry_after,
        "safe_message": safe_message,
    }


def require_staging_mutation(
    settings: Settings,
    *,
    domain: Literal["ai", "social", "marketplace", "ads"],
    mode: ProviderMode,
    account_state: ProviderAccountState,
    confirmation: bool,
    idempotency_key: str | None,
    account_opt_in: bool = False,
) -> None:
    """Apply the shared kill-switch contract before a remote mutation."""
    if settings.external_mutations_emergency_stop or maintenance_enabled():
        raise StagingSafetyError("External provider mutations are stopped by the operator.")
    if settings.environment not in {"staging", "production"}:
        raise StagingSafetyError("Provider mutations are available only in staging or production.")
    if mode not in {"sandbox", "live"}:
        raise StagingSafetyError("A remote sandbox or live provider mode is required.")
    switches = {
        "ai": settings.live_ai_enabled,
        "social": settings.live_social_publishing_enabled,
        "marketplace": settings.live_marketplace_mutations_enabled,
        "ads": settings.live_ads_mutations_enabled,
    }
    if domain not in switches or not switches[domain]:
        raise StagingSafetyError("The provider domain is disabled by configuration.")
    if (
        domain == "marketplace"
        and settings.shopify_mode in {"sandbox", "live"}
        and not settings.shopify_live_mutation_enabled
    ):
        raise StagingSafetyError("Shopify remote mutations are disabled by configuration.")
    if account_state != "VALID" or not account_opt_in:
        raise StagingSafetyError("A validated, explicitly opted-in provider account is required.")
    if not confirmation:
        raise StagingSafetyError("Explicit operator confirmation is required.")
    if not idempotency_key or len(idempotency_key) > 200:
        raise StagingSafetyError("A bounded idempotency key is required.")
    if domain == "ads" and not settings.ads_live_spend_enabled:
        raise StagingSafetyError("Live Ads spend is disabled by configuration.")


def staging_configuration_errors(settings: Settings) -> list[str]:
    """Return safe fail-closed validation errors for a staging deployment."""
    errors: list[str] = []
    if settings.environment != "staging":
        errors.append("environment must be staging")
    if not settings.database_url:
        errors.append("database URL is required")
    if not settings.credential_encryption_key:
        errors.append("credential encryption key is required")
    if not settings.session_secret or len(settings.session_secret) < 32:
        errors.append("a 32-character session secret is required")
    if not settings.session_secure_cookie or not settings.require_https:
        errors.append("secure cookies and HTTPS are required")
    if not settings.allowed_origin_set or any(
        not origin.startswith("https://") for origin in settings.allowed_origin_set
    ):
        errors.append("trusted staging origins must use HTTPS")
    if settings.live_ads_mutations_enabled and not settings.ads_live_spend_enabled:
        errors.append("live Ads mutation cannot be enabled while Ads spend is disabled")
    provider_credentials = {
        "ai": settings.openai_api_key,
        "social": settings.wordpress_application_password,
        "marketplace": settings.shopify_admin_api_access_token,
    }
    for domain, enabled in (
        ("ai", settings.live_ai_enabled),
        ("social", settings.live_social_publishing_enabled),
        ("marketplace", settings.live_marketplace_mutations_enabled),
    ):
        if enabled and not provider_credentials[domain]:
            errors.append(f"{domain} provider is enabled without credentials")
    errors.extend(shopify_configuration_errors(settings))
    return errors


def shopify_configuration_errors(settings: Settings) -> list[str]:
    """Validate Shopify deployment configuration without contacting the store."""
    if settings.shopify_mode == "fake":
        return []
    errors: list[str] = []
    if settings.environment != "staging":
        errors.append("Shopify sandbox mode requires a staging environment")
    if not settings.shopify_shop_domain:
        errors.append("Shopify store domain is required")
    else:
        try:
            validate_shop_domain(settings.shopify_shop_domain, resolve_dns=False)
        except ValueError:
            errors.append("Shopify store domain must be a valid myshopify.com domain")
    if not settings.shopify_admin_api_access_token:
        errors.append("Shopify access token is required")
    try:
        validate_api_version(settings.shopify_api_version)
    except ValueError:
        errors.append("Shopify API version must use the YYYY-MM quarterly format")
    if settings.shopify_mode == "live":
        errors.append("Shopify production mode is not permitted by staging certification")
    if settings.shopify_live_mutation_enabled:
        if settings.shopify_mode not in {"sandbox", "live"}:
            errors.append("Shopify mutations require sandbox or live mode")
        if not settings.live_marketplace_mutations_enabled:
            errors.append("Shopify mutations require the global marketplace switch")
        if settings.external_mutations_emergency_stop:
            errors.append("Shopify mutations cannot be enabled while the emergency stop is active")
    return errors


def webhook_signature(secret: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return digest.hexdigest()


def validate_webhook(
    *,
    secret: str,
    timestamp: str,
    signature: str,
    body: bytes,
    now: float | None = None,
    max_age_seconds: int = 300,
    seen: set[str] | None = None,
) -> None:
    try:
        stamp = int(timestamp)
    except ValueError as error:
        raise StagingSafetyError("Webhook timestamp is invalid.") from error
    current = time.time() if now is None else now
    if abs(current - stamp) > max_age_seconds:
        raise StagingSafetyError("Webhook timestamp is stale.")
    expected = webhook_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, signature):
        raise StagingSafetyError("Webhook signature is invalid.")
    replay_key = f"{timestamp}:{signature}"
    if seen is not None:
        if replay_key in seen:
            raise StagingSafetyError("Webhook replay was rejected.")
        seen.add(replay_key)


def redact_provider_payload(payload: Any) -> dict[str, object]:
    """Return a bounded JSON-safe payload summary with recursive secret redaction."""
    blocked = {
        "token",
        "access_token",
        "api_key",
        "password",
        "secret",
        "authorization",
        "database_url",
        "dsn",
        "path",
        "local_path",
        "environment",
    }

    def safe_value(value: Any, key: str = "") -> object:
        normalized = key.casefold()
        if normalized in blocked or any(part in normalized for part in ("credential", "cookie")):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                str(item_key): safe_value(item_value, str(item_key))
                for item_key, item_value in list(value.items())[:50]
            }
        if isinstance(value, list):
            return [safe_value(item) for item in value[:50]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return {"type": type(value).__name__}

    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    return safe_value(payload)  # type: ignore[return-value]
