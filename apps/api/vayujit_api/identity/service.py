import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import AuthSession, User, UserStatus

hasher = PasswordHasher()


def now() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def cleanup_sessions(db: Session) -> int:
    cutoff = now() - timedelta(hours=get_settings().revoked_session_retention_hours)
    result = cast(
        CursorResult[tuple[()]],
        db.execute(
            delete(AuthSession).where(
                or_(
                    AuthSession.expires_at <= now(),
                    AuthSession.revoked_at.is_not(None) & (AuthSession.revoked_at <= cutoff),
                )
            ),
        ),
    )
    return result.rowcount or 0


def new_session(db: Session, user: User) -> str:
    cleanup_sessions(db)
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=now() + timedelta(hours=get_settings().session_lifetime_hours),
            created_at=now(),
        )
    )
    return token


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    if user is None or not user.is_active or user.status == UserStatus.DISABLED:
        return None
    try:
        hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        return None
    user.last_login_at = user.updated_at = now()
    return user


def resolve(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    item = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    if item is None or item.revoked_at is not None or item.expires_at <= now():
        return None
    user = db.get(User, item.user_id)
    return user if user and user.is_active and user.status != UserStatus.DISABLED else None
