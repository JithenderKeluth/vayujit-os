import hashlib
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import AuthSession, User
from vayujit_api.identity.schemas import (
    AuthenticatedUserResponse,
    LoginRequest,
    OwnerSetupRequest,
    SetupStatusResponse,
)
from vayujit_api.identity.service import (
    authenticate,
    hasher,
    new_session,
    normalize_email,
    now,
    resolve,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
attempts: dict[str, list[float]] = {}
DatabaseSession = Annotated[Session, Depends(get_session)]
SessionCookie = Annotated[str | None, Cookie(alias="vayujit_session")]


def present(user: User) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(
        id=str(user.id), full_name=user.full_name, email=user.email, role=user.role.value
    )


def set_cookie(response: Response, token: str) -> None:
    cfg = get_settings()
    response.set_cookie(
        cfg.session_cookie_name,
        token,
        httponly=True,
        secure=cfg.session_secure_cookie,
        samesite="strict",
        max_age=cfg.session_lifetime_hours * 3600,
        path="/",
    )


def current_user(
    db: DatabaseSession,
    token: SessionCookie = None,
) -> User:
    user = resolve(db, token)
    if not user:
        raise HTTPException(401, "Authentication required.")
    return user


@router.get("/setup-status", response_model=SetupStatusResponse)
def setup_status(db: DatabaseSession) -> SetupStatusResponse:
    return SetupStatusResponse(owner_exists=(db.scalar(select(func.count(User.id))) or 0) > 0)


@router.post("/setup-owner", response_model=AuthenticatedUserResponse, status_code=201)
def setup_owner(
    data: OwnerSetupRequest, response: Response, db: DatabaseSession
) -> AuthenticatedUserResponse:
    stamp = now()
    user = User(
        full_name=data.full_name.strip(),
        email=data.email.strip(),
        normalized_email=normalize_email(data.email),
        password_hash=hasher.hash(data.password),
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Owner setup is already complete.") from error
    token = new_session(db, user)
    db.commit()
    set_cookie(response, token)
    return present(user)


@router.post("/login", response_model=AuthenticatedUserResponse)
def login(
    data: LoginRequest, request: Request, response: Response, db: DatabaseSession
) -> AuthenticatedUserResponse:
    key = request.client.host if request.client else "local"
    recent = [x for x in attempts.get(key, []) if monotonic() - x < 60]
    if len(recent) >= 5:
        raise HTTPException(429, "Too many login attempts. Try again shortly.")
    user = authenticate(db, data.email, data.password)
    if not user:
        attempts[key] = [*recent, monotonic()]
        raise HTTPException(401, "Invalid email or password.")
    attempts.pop(key, None)
    token = new_session(db, user)
    db.commit()
    set_cookie(response, token)
    return present(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DatabaseSession,
    token: SessionCookie = None,
) -> None:
    if token:
        item = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
        if item and item.revoked_at is None:
            item.revoked_at = now()
            db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@router.get("/me", response_model=AuthenticatedUserResponse)
def me(user: Annotated[User, Depends(current_user)]) -> AuthenticatedUserResponse:
    return present(user)
