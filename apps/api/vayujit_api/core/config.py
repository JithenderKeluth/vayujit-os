from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_prefix="VAYUJIT_", extra="ignore"
    )

    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    web_origin: str = "http://127.0.0.1:4200"
    allowed_origins: str = "http://127.0.0.1:4200,app://vayujit"
    allow_missing_origin: bool = False
    trusted_proxy_ips: str = ""
    require_https: bool = False
    content_security_policy: str = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    database_url: str = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit"
    database_pool_size: int = Field(default=5, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=200)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    database_statement_timeout_ms: int = Field(default=30000, ge=100, le=600000)
    session_cookie_name: str = "vayujit_session"
    session_secret: str | None = None
    session_lifetime_hours: int = Field(default=24, ge=1, le=8760)
    session_secure_cookie: bool = False
    session_same_site: Literal["lax", "strict", "none"] = "lax"
    revoked_session_retention_hours: int = Field(default=24, ge=1, le=720)
    backup_directory: str = "../../var/backups"
    pg_dump_path: str | None = None
    backup_retention_count: int = Field(default=10, ge=1, le=100)
    backup_retention_days: int = Field(default=30, ge=1, le=3650)
    export_retention_hours: int = Field(default=24, ge=1, le=720)
    maintenance_marker: str = "../../var/maintenance/enabled"
    restore_enabled: bool = False
    build_identifier: str = "development"
    git_commit: str = "unknown"
    build_timestamp: str = "unknown"
    node_version: str = "22-or-24"
    electron_version: str = "43.2.0"
    angular_build_version: str = "22"
    credential_encryption_key: str | None = None
    credential_encryption_key_id: str = "current"
    credential_encryption_previous_keys: str = ""
    openai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("VAYUJIT_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    ai_real_provider_required: bool = False
    ai_model_cache_seconds: int = Field(default=900, ge=60, le=3600)
    wordpress_site_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAYUJIT_WORDPRESS_SITE_URL", "WORDPRESS_SITE_URL"),
    )
    wordpress_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAYUJIT_WORDPRESS_USERNAME", "WORDPRESS_USERNAME"),
    )
    wordpress_application_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VAYUJIT_WORDPRESS_APPLICATION_PASSWORD", "WORDPRESS_APPLICATION_PASSWORD"
        ),
    )
    wordpress_required: bool = False
    media_storage_directory: str = "../../var/media"
    storage_provider: Literal["filesystem", "s3", "gcs", "azure"] = "filesystem"
    storage_bucket: str | None = None
    media_max_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    media_max_dimension: int = Field(default=10000, ge=256, le=50000)
    media_min_free_bytes: int = Field(default=100 * 1024 * 1024, ge=1024 * 1024)
    wordpress_taxonomy_cache_seconds: int = Field(default=900, ge=60, le=3600)
    shopify_shop_domain: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VAYUJIT_SHOPIFY_SHOP_DOMAIN",
            "SHOPIFY_SHOP_DOMAIN",
            "VAYUJIT_SHOPIFY_STORE_DOMAIN",
            "SHOPIFY_STORE_DOMAIN",
        ),
    )
    shopify_admin_api_access_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VAYUJIT_SHOPIFY_ADMIN_API_ACCESS_TOKEN",
            "SHOPIFY_ADMIN_API_ACCESS_TOKEN",
            "VAYUJIT_SHOPIFY_ACCESS_TOKEN",
            "SHOPIFY_ACCESS_TOKEN",
        ),
    )
    shopify_api_version: str = Field(
        default="2026-07",
        validation_alias=AliasChoices("VAYUJIT_SHOPIFY_API_VERSION", "SHOPIFY_API_VERSION"),
    )
    shopify_mode: Literal["fake", "sandbox", "live"] = Field(
        default="fake",
        validation_alias=AliasChoices("VAYUJIT_SHOPIFY_MODE", "SHOPIFY_MODE"),
    )
    shopify_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAYUJIT_SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_ID"),
    )
    shopify_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAYUJIT_SHOPIFY_CLIENT_SECRET", "SHOPIFY_CLIENT_SECRET"),
    )
    shopify_timeout_seconds: int = Field(
        default=45,
        ge=10,
        le=120,
        validation_alias=AliasChoices("VAYUJIT_SHOPIFY_TIMEOUT", "SHOPIFY_TIMEOUT"),
    )
    shopify_live_mutation_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "VAYUJIT_SHOPIFY_LIVE_MUTATION_ENABLED", "SHOPIFY_LIVE_MUTATION_ENABLED"
        ),
    )
    shopify_discovery_cache_seconds: int = Field(default=900, ge=60, le=3600)
    publishing_worker_enabled: bool = False
    publishing_worker_concurrency: int = Field(default=2, ge=1, le=32)
    publishing_worker_poll_seconds: float = Field(default=2.0, ge=0.1, le=60)
    publishing_job_lease_seconds: int = Field(default=60, ge=15, le=3600)
    publishing_worker_heartbeat_seconds: int = Field(default=20, ge=5, le=300)
    publishing_schedule_horizon_days: int = Field(default=30, ge=1, le=366)
    publishing_schedule_max_per_owner: int = Field(default=1000, ge=1, le=100000)
    publishing_job_max_attempts: int = Field(default=5, ge=1, le=10)
    publishing_worker_id: str | None = None
    campaign_max_active_per_owner: int = Field(default=100, ge=1, le=10000)
    campaign_max_activities: int = Field(default=500, ge=1, le=5000)
    campaign_max_dependencies: int = Field(default=1000, ge=1, le=10000)
    campaign_calendar_max_days: int = Field(default=90, ge=1, le=366)
    campaign_bulk_schedule_max: int = Field(default=100, ge=1, le=500)
    campaign_max_duration_days: int = Field(default=365, ge=1, le=3660)
    request_max_body_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    request_rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1, le=1000)
    ai_rate_limit_per_minute: int = Field(default=30, ge=1, le=1000)
    upload_rate_limit_per_minute: int = Field(default=20, ge=1, le=1000)
    provider_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    provider_requests_per_day: int = Field(default=10000, ge=1, le=1000000)
    provider_max_concurrent_jobs: int = Field(default=4, ge=1, le=1000)
    provider_max_video_duration_seconds: int = Field(default=300, ge=1, le=86400)
    provider_max_tokens: int = Field(default=8192, ge=1, le=1000000)
    ads_live_spend_enabled: bool = False
    ads_owner_opt_in_required: bool = True
    ads_daily_spend_cap: float = Field(default=0, ge=0)
    ads_campaign_spend_cap: float = Field(default=0, ge=0)
    ads_marketing_plan_spend_cap: float = Field(default=0, ge=0)
    live_ai_enabled: bool = False
    live_social_publishing_enabled: bool = False
    live_marketplace_mutations_enabled: bool = False
    live_ads_mutations_enabled: bool = False
    metrics_enabled: bool = True
    external_mutations_emergency_stop: bool = False
    provider_runtime_mode: Literal["fake", "sandbox", "live"] = "fake"
    provider_connect_timeout_seconds: float = Field(default=5.0, ge=0.1, le=60)
    provider_read_timeout_seconds: float = Field(default=30.0, ge=0.1, le=300)
    provider_total_timeout_seconds: float = Field(default=45.0, ge=0.1, le=600)
    provider_retry_max_attempts: int = Field(default=3, ge=1, le=5)
    provider_retry_backoff_seconds: float = Field(default=1.0, ge=0.1, le=60)
    intelligence_enabled: bool = False
    intelligence_research_execution_enabled: bool = False
    intelligence_external_research_enabled: bool = False
    intelligence_autonomous_research_enabled: bool = False
    intelligence_web_fetch_enabled: bool = False
    intelligence_search_provider_enabled: bool = False
    intelligence_external_provider_mode: Literal[
        "DISABLED", "LOCAL_FIXTURE", "SANDBOX", "LIVE_READ_ONLY"
    ] = "DISABLED"
    intelligence_search_provider: str = "deterministic"
    intelligence_search_provider_base_url: str | None = None
    intelligence_search_provider_api_key: str | None = None
    intelligence_search_timeout_seconds: float = Field(default=15.0, ge=0.1, le=120)
    intelligence_external_max_retries: int = Field(default=2, ge=0, le=5)
    intelligence_external_retry_backoff_seconds: float = Field(default=0.25, ge=0, le=5)
    intelligence_search_max_results: int = Field(default=10, ge=1, le=50)
    intelligence_search_requests_per_minute: int = Field(default=10, ge=1, le=1000)
    intelligence_search_requests_per_hour: int = Field(default=100, ge=1, le=10000)
    intelligence_search_daily_cap: int = Field(default=500, ge=1, le=100000)
    intelligence_fetch_max_bytes: int = Field(default=1_000_000, ge=1024, le=20_000_000)
    intelligence_fetch_max_redirects: int = Field(default=3, ge=0, le=10)
    intelligence_fetch_timeout_seconds: float = Field(default=15.0, ge=0.1, le=120)
    intelligence_external_approved_domains: str = ""
    intelligence_external_blocked_domains: str = ""
    intelligence_external_kill_switch: bool = False
    intelligence_search_provider_kill_switch: bool = False

    @field_validator("environment")
    @classmethod
    def recognized_environment(cls, value: str) -> str:
        if value not in {"local", "test", "development", "staging", "production"}:
            raise ValueError("environment must be local, test, development, staging, or production")
        return value

    @model_validator(mode="after")
    def production_security(self) -> "Settings":
        if self.environment in {"staging", "production"}:
            if not self.session_secure_cookie:
                raise ValueError("staging and production require secure session cookies")
            if not self.allow_missing_origin:
                pass
            if self.require_https is False:
                raise ValueError("staging and production require HTTPS")
        if self.environment == "production":
            if self.allow_missing_origin:
                raise ValueError("production cannot allow missing Origin headers")
            if not self.credential_encryption_key:
                raise ValueError("production requires credential encryption keys")
            if not self.session_secret or len(self.session_secret) < 32:
                raise ValueError("production requires a 32-character session secret")
            if self.storage_provider != "filesystem" and not self.storage_bucket:
                raise ValueError("production object storage requires a bucket")
            if any(
                origin.startswith(("http://127.0.0.1", "http://localhost", "app://"))
                for origin in self.allowed_origin_set
            ):
                raise ValueError("production trusted origins cannot be local origins")
            if self.debug:
                raise ValueError("production cannot enable debug mode")
            if self.live_ads_mutations_enabled and not self.ads_live_spend_enabled:
                raise ValueError("live Ads mutations require the spend switch")
        if self.environment in {"local", "test", "development"} and self.require_https:
            raise ValueError("HTTPS is only required for staging or production")
        if not self.allowed_origin_set:
            raise ValueError("at least one allowed Origin is required")
        if "*" in self.allowed_origin_set:
            raise ValueError("wildcard origins are not allowed with credentialed CORS")
        return self

    @property
    def allowed_origin_set(self) -> set[str]:
        return {origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()}

    @property
    def is_live_environment(self) -> bool:
        return self.environment in {"staging", "production"}

    @property
    def live_mutations_enabled(self) -> bool:
        return any(
            (
                self.live_ai_enabled,
                self.live_social_publishing_enabled,
                self.live_marketplace_mutations_enabled,
                self.live_ads_mutations_enabled,
            )
        )

    def configuration_report(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "database_configured": bool(self.database_url),
            "encryption_configured": bool(self.credential_encryption_key),
            "session_secret_configured": bool(self.session_secret),
            "storage_provider": self.storage_provider,
            "storage_configured": bool(
                self.storage_bucket or self.storage_provider == "filesystem"
            ),
            "trusted_origins": sorted(self.allowed_origin_set),
            "live_mutations_enabled": self.live_mutations_enabled,
            "ads_spend_enabled": self.ads_live_spend_enabled,
            "debug": self.debug,
            "shopify_mode": self.shopify_mode,
            "shopify_configured": bool(
                self.shopify_shop_domain and self.shopify_admin_api_access_token
            ),
            "shopify_api_version": self.shopify_api_version,
            "shopify_timeout_seconds": self.shopify_timeout_seconds,
            "shopify_live_mutation_enabled": self.shopify_live_mutation_enabled,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
