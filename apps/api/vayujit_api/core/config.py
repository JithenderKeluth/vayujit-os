from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_prefix="VAYUJIT_",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    web_origin: str = "http://127.0.0.1:4200"
    allowed_origins: str = "http://127.0.0.1:4200,app://vayujit"
    allow_missing_origin: bool = False
    database_url: str = "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit"
    session_cookie_name: str = "vayujit_session"
    session_lifetime_hours: int = 24
    session_secure_cookie: bool = False
    revoked_session_retention_hours: int = 24
    backup_directory: str = "../../var/backups"
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
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAYUJIT_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    ai_real_provider_required: bool = False
    ai_model_cache_seconds: int = Field(default=900, ge=60, le=3600)

    @field_validator("environment")
    @classmethod
    def recognized_environment(cls, value: str) -> str:
        if value not in {"development", "test", "production"}:
            raise ValueError("environment must be development, test, or production")
        return value

    @model_validator(mode="after")
    def production_security(self) -> "Settings":
        if self.environment == "production":
            if not self.session_secure_cookie:
                raise ValueError("production requires secure session cookies")
            if self.allow_missing_origin:
                raise ValueError("production cannot allow missing Origin headers")
        if not self.allowed_origin_set:
            raise ValueError("at least one allowed Origin is required")
        return self

    @property
    def allowed_origin_set(self) -> set[str]:
        return {origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
