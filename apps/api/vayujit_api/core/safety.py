from dataclasses import dataclass

from vayujit_api.core.config import Settings


class SafetyBoundaryError(RuntimeError):
    """Raised when an external mutation is not explicitly enabled."""


@dataclass(frozen=True)
class ProviderQuota:
    requests_per_minute: int
    requests_per_day: int
    max_concurrent_jobs: int
    max_upload_bytes: int
    max_video_duration_seconds: int
    max_tokens: int


def quota_for(settings: Settings) -> ProviderQuota:
    return ProviderQuota(
        requests_per_minute=settings.provider_requests_per_minute,
        requests_per_day=settings.provider_requests_per_day,
        max_concurrent_jobs=settings.provider_max_concurrent_jobs,
        max_upload_bytes=settings.media_max_size_bytes,
        max_video_duration_seconds=settings.provider_max_video_duration_seconds,
        max_tokens=settings.provider_max_tokens,
    )


def require_live_provider(settings: Settings, domain: str) -> None:
    switches = {
        "ai": settings.live_ai_enabled,
        "social": settings.live_social_publishing_enabled,
        "marketplace": settings.live_marketplace_mutations_enabled,
        "ads": settings.live_ads_mutations_enabled,
    }
    if settings.environment not in {"staging", "production"} or not switches.get(domain, False):
        raise SafetyBoundaryError("Live provider execution is disabled by configuration.")


def require_ads_spend(
    settings: Settings,
    *,
    owner_opt_in: bool,
    account_opt_in: bool,
    daily_spend: float,
    campaign_spend: float,
    plan_spend: float,
    delta: float,
    currency: str,
) -> None:
    if not settings.live_ads_mutations_enabled or not settings.ads_live_spend_enabled:
        raise SafetyBoundaryError("Live Ads spend is disabled by configuration.")
    if settings.ads_owner_opt_in_required and not owner_opt_in:
        raise SafetyBoundaryError("Owner opt-in is required before Ads spend.")
    if not account_opt_in or currency not in {"INR", "USD", "EUR", "GBP"}:
        raise SafetyBoundaryError("Ads account opt-in and a supported currency are required.")
    if (
        daily_spend + delta > settings.ads_daily_spend_cap
        or campaign_spend + delta > settings.ads_campaign_spend_cap
        or plan_spend + delta > settings.ads_marketing_plan_spend_cap
    ):
        raise SafetyBoundaryError("The configured Ads spend cap would be exceeded.")
