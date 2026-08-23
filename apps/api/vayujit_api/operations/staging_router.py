"""Authenticated staging diagnostics; values are status-only and redacted."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.operations.staging import (
    ProviderAccountRegistry,
    ProviderAccountState,
    ProviderAccountStatus,
    provider_metrics_snapshot,
    staging_configuration_errors,
)

router = APIRouter(prefix="/api/v1/system/staging", tags=["staging"])
CurrentUser = Annotated[User, Depends(current_user)]
registry = ProviderAccountRegistry()


def _refresh_registry() -> None:
    settings = get_settings()
    configured = {
        "openai-compatible": bool(settings.openai_api_key),
        "shopify": bool(settings.shopify_admin_api_access_token),
        "wordpress": bool(settings.wordpress_application_password),
    }
    for provider, has_credentials in configured.items():
        state = "CONFIGURED" if has_credentials else "NOT_CONFIGURED"
        registry.set(
            ProviderAccountStatus(
                provider=provider,
                account_id=None,
                state=cast(ProviderAccountState, state),
                mode=settings.provider_runtime_mode,
                capability="read_only_validation",
                safe_message=(
                    "Credential is loaded from deployment configuration."
                    if has_credentials
                    else "Provider credential is not configured."
                ),
            )
        )


@router.get("/providers")
def provider_status(_user: CurrentUser) -> dict[str, object]:
    _refresh_registry()
    settings = get_settings()
    return {
        "environment": settings.environment,
        "emergency_stop": settings.external_mutations_emergency_stop,
        "live_mutations_enabled": settings.live_mutations_enabled,
        "ads_spend_enabled": settings.ads_live_spend_enabled,
        "configuration_errors": staging_configuration_errors(settings),
        "providers": registry.safe_list(),
    }


@router.get("/metrics")
def provider_metrics(_user: CurrentUser) -> dict[str, object]:
    return {"metrics": provider_metrics_snapshot()}


@router.get("/contract")
def staging_contract(_user: CurrentUser) -> dict[str, object]:
    settings = get_settings()
    return {
        "mode": settings.provider_runtime_mode,
        "connect_timeout_seconds": settings.provider_connect_timeout_seconds,
        "read_timeout_seconds": settings.provider_read_timeout_seconds,
        "total_timeout_seconds": settings.provider_total_timeout_seconds,
        "retry_max_attempts": settings.provider_retry_max_attempts,
        "retry_backoff_seconds": settings.provider_retry_backoff_seconds,
        "external_mutation_emergency_stop": settings.external_mutations_emergency_stop,
        "ads_spend_enabled": settings.ads_live_spend_enabled,
    }
