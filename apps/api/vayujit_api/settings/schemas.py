import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


class OwnerProfile(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    created_at: datetime
    last_login_at: datetime | None


class OwnerPreferences(BaseModel):
    timezone: str
    date_format: str
    default_page_size: int
    execution_history_page_size: int
    default_brand_id: uuid.UUID | None
    default_prompt_template_id: uuid.UUID | None
    default_publishing_destination_id: uuid.UUID | None
    confirm_before_publish: bool
    confirm_before_retry: bool
    theme_preference: str
    density_preference: str


class SettingsResponse(BaseModel):
    profile: OwnerProfile
    preferences: OwnerPreferences


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)


class PreferencesUpdate(BaseModel):
    timezone: str = Field(max_length=100)
    date_format: Literal["medium", "short", "iso"]
    default_page_size: Literal[10, 25, 50, 100]
    execution_history_page_size: Literal[10, 25, 50, 100]
    default_brand_id: uuid.UUID | None = None
    default_prompt_template_id: uuid.UUID | None = None
    default_publishing_destination_id: uuid.UUID | None = None
    confirm_before_publish: bool
    confirm_before_retry: bool
    theme_preference: Literal["system", "light", "dark"]
    density_preference: Literal["comfortable", "compact"]

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Unsupported IANA timezone.") from error
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
    confirmation: str = Field(min_length=12, max_length=256)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChange":
        if self.new_password != self.confirmation:
            raise ValueError("Password confirmation does not match.")
        if self.new_password == self.current_password:
            raise ValueError("New password must differ from current password.")
        return self


class SessionSummary(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    current: bool


class SystemStatus(BaseModel):
    application_version: str
    environment: str
    api_status: str
    database_status: str
    migration_revision: str
    expected_revision: str
    server_time: datetime
    python_version: str
    providers: list[str]
    connectors: list[str]
