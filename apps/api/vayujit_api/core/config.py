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
    database_url: str = (
        "postgresql+psycopg://vayujit:vayujit_dev@127.0.0.1:5432/vayujit"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
