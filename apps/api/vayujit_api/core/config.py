from functools import lru_cache

from pydantic import Field
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

    @property
    def allowed_origin_set(self) -> set[str]:
        return {origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
