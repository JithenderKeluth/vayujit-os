import hashlib
import sys
from datetime import UTC, datetime
from typing import Annotated

from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from vayujit_api.ai.models import PromptTemplate
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.core.config import get_settings as application_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import AuthSession, User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import hasher, now
from vayujit_api.publishing.models import PublishingDestination
from vayujit_api.settings.models import OwnerPreference
from vayujit_api.settings.schemas import (
    OwnerPreferences,
    OwnerProfile,
    PasswordChange,
    PreferencesUpdate,
    ProfileUpdate,
    SessionSummary,
    SettingsResponse,
    SystemStatus,
)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
system_router = APIRouter(prefix="/api/v1/system", tags=["system"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]
SessionCookie = Annotated[str | None, Cookie(alias="vayujit_session")]


def preference(db: Session, user: User) -> OwnerPreference:
    value = db.scalar(select(OwnerPreference).where(OwnerPreference.owner_id == user.id))
    if value:
        return value
    stamp = now()
    value = OwnerPreference(owner_id=user.id, timezone="UTC", created_at=stamp, updated_at=stamp)
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def present(db: Session, user: User) -> SettingsResponse:
    value = preference(db, user)
    effective = OwnerPreferences.model_validate(value, from_attributes=True)
    if value.default_brand_id is not None:
        brand = db.scalar(
            select(Brand).where(
                Brand.id == value.default_brand_id,
                Brand.owner_id == user.id,
                Brand.status == "active",
            )
        )
        if brand is None:
            effective.default_brand_id = None
    if value.default_prompt_template_id is not None:
        template = db.scalar(
            select(PromptTemplate).where(
                PromptTemplate.id == value.default_prompt_template_id,
                PromptTemplate.status == "enabled",
            )
        )
        if template is None:
            effective.default_prompt_template_id = None
    if value.default_publishing_destination_id is not None:
        destination = db.scalar(
            select(PublishingDestination).where(
                PublishingDestination.id == value.default_publishing_destination_id,
                PublishingDestination.owner_id == user.id,
                PublishingDestination.status == "active",
            )
        )
        if destination is None:
            effective.default_publishing_destination_id = None
    return SettingsResponse(
        profile=OwnerProfile.model_validate(user, from_attributes=True),
        preferences=effective,
    )


@router.get("", response_model=SettingsResponse)
def read_settings(db: DatabaseSession, user: CurrentUser) -> SettingsResponse:
    return present(db, user)


@router.patch("/profile", response_model=SettingsResponse)
def update_profile(data: ProfileUpdate, db: DatabaseSession, user: CurrentUser) -> SettingsResponse:
    user.full_name = data.full_name.strip()
    user.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="settings.profile_updated",
        entity_type="user",
        entity_id=user.id,
        metadata={"field": "full_name"},
    )
    db.commit()
    return present(db, user)


@router.patch("/preferences", response_model=SettingsResponse)
def update_preferences(
    data: PreferencesUpdate, db: DatabaseSession, user: CurrentUser
) -> SettingsResponse:
    references = (
        (
            data.default_brand_id,
            select(Brand.id).where(
                Brand.id == data.default_brand_id,
                Brand.owner_id == user.id,
                Brand.status == "active",
            ),
        ),
        (
            data.default_prompt_template_id,
            select(PromptTemplate.id).where(
                PromptTemplate.id == data.default_prompt_template_id,
                PromptTemplate.status == "enabled",
            ),
        ),
        (
            data.default_publishing_destination_id,
            select(PublishingDestination.id).where(
                PublishingDestination.id == data.default_publishing_destination_id,
                PublishingDestination.owner_id == user.id,
                PublishingDestination.status == "active",
            ),
        ),
    )
    for identifier, query in references:
        if identifier is not None and db.scalar(query) is None:
            raise HTTPException(404, "Selected default is unavailable.")
    value = preference(db, user)
    for field, item in data.model_dump().items():
        setattr(value, field, item)
    value.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="settings.preferences_updated",
        entity_type="owner_preference",
        entity_id=value.id,
        metadata={"fields": sorted(data.model_fields_set)},
    )
    db.commit()
    return present(db, user)


@router.post("/change-password", status_code=204)
def change_password(data: PasswordChange, db: DatabaseSession, user: CurrentUser) -> None:
    try:
        hasher.verify(user.password_hash, data.current_password)
    except VerifyMismatchError:
        raise HTTPException(400, "Current password is incorrect.") from None
    user.password_hash = hasher.hash(data.new_password)
    user.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="settings.password_changed",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()


def token_hash(token: str | None) -> str:
    return hashlib.sha256((token or "").encode()).hexdigest()


@router.get("/sessions", response_model=list[SessionSummary])
def sessions(
    db: DatabaseSession, user: CurrentUser, token: SessionCookie = None
) -> list[SessionSummary]:
    current_hash = token_hash(token)
    values = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .order_by(AuthSession.created_at.desc())
    ).all()
    return [
        SessionSummary(
            id=item.id,
            created_at=item.created_at,
            expires_at=item.expires_at,
            current=item.token_hash == current_hash,
        )
        for item in values
    ]


@router.post("/sessions/revoke-others", status_code=204)
def revoke_others(db: DatabaseSession, user: CurrentUser, token: SessionCookie = None) -> None:
    current_hash = token_hash(token)
    stamp = now()
    for item in db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.token_hash != current_hash,
        )
    ):
        item.revoked_at = stamp
    record_event(
        db,
        actor_id=user.id,
        action="settings.sessions_revoked",
        entity_type="user",
        entity_id=user.id,
        metadata={"scope": "others"},
    )
    db.commit()


@router.post("/sessions/revoke-all", status_code=204)
def revoke_all(response: Response, db: DatabaseSession, user: CurrentUser) -> None:
    stamp = now()
    for item in db.scalars(
        select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
    ):
        item.revoked_at = stamp
    record_event(
        db,
        actor_id=user.id,
        action="settings.sessions_revoked",
        entity_type="user",
        entity_id=user.id,
        metadata={"scope": "all"},
    )
    db.commit()
    response.delete_cookie(application_settings().session_cookie_name, path="/")


@system_router.get("/status", response_model=SystemStatus)
def system_status(db: DatabaseSession, _user: CurrentUser) -> SystemStatus:
    database_status = "ok"
    try:
        db.execute(text("select 1"))
    except Exception:
        database_status = "unavailable"
    revision = (
        db.scalar(text("select version_num from alembic_version"))
        if inspect(db.get_bind()).has_table("alembic_version")
        else "unmanaged-test-schema"
    )
    return SystemStatus(
        application_version="0.1.0",
        environment=application_settings().environment,
        api_status="ok",
        database_status=database_status,
        migration_revision=str(revision),
        expected_revision="20260728_0008",
        server_time=datetime.now(UTC),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        providers=["mock-deterministic"],
        connectors=["mock-publishing"],
    )
