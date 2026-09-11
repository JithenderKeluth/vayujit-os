"""Test-only deterministic owner harness for due-diligence isolation proofs."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.identity.service import hasher, normalize_email, now

OWNER_A = uuid.UUID("a8c5d5a7-2d0c-4b6e-8d33-9f6d0a5c1001")
OWNER_B = uuid.UUID("b8c5d5a7-2d0c-4b6e-8d33-9f6d0a5c1002")


def create_test_owner(db: Session, *, owner_id: uuid.UUID, email: str) -> User:
    """Create a second owner in disposable test DBs without changing runtime auth.

    Local-owner production authentication intentionally has a singleton constraint.  The
    constraint is removed only for this test transaction's disposable schema so owner-scoped
    rows can be persisted and exercised through the normal dependency override.
    """
    db.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_singleton_key_key"))
    existing = db.get(User, owner_id)
    if existing is not None:
        return existing
    user = User(
        id=owner_id,
        singleton_key=1,
        full_name=f"Due Diligence {email.split('@', maxsplit=1)[0]}",
        email=email,
        normalized_email=normalize_email(email),
        password_hash=hasher.hash("test-only-password"),
        created_at=now(),
        updated_at=now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
