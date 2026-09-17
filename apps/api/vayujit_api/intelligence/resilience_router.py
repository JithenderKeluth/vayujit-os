"""Owner-scoped 8E.3 resilience and recommendation projections."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.portfolio_service import portfolio_or_404
from vayujit_api.intelligence.resilience_analysis import calculate_resilience

router = APIRouter(
    prefix="/api/v1/intelligence/supplier-portfolios", tags=["supplier-portfolio-resilience"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _bundle(
    portfolio_id: uuid.UUID, db: Session, owner: User, assessment_version_id: uuid.UUID | None
):
    return calculate_resilience(
        db, owner, portfolio_or_404(db, owner, portfolio_id), assessment_version_id
    )


@router.get("/{portfolio_id}/resilience")
def resilience(
    portfolio_id: uuid.UUID, db: DB, owner: Owner, assessment_version_id: uuid.UUID | None = None
):
    return _bundle(portfolio_id, db, owner, assessment_version_id)


@router.get("/{portfolio_id}/resilience/dimensions")
def dimensions(
    portfolio_id: uuid.UUID, db: DB, owner: Owner, assessment_version_id: uuid.UUID | None = None
):
    return _bundle(portfolio_id, db, owner, assessment_version_id)["dimensions"]


@router.get("/{portfolio_id}/recommendations")
def recommendations(
    portfolio_id: uuid.UUID, db: DB, owner: Owner, assessment_version_id: uuid.UUID | None = None
):
    return _bundle(portfolio_id, db, owner, assessment_version_id)["recommendations"]


@router.get("/{portfolio_id}/risk")
def risk(
    portfolio_id: uuid.UUID, db: DB, owner: Owner, assessment_version_id: uuid.UUID | None = None
):
    return _bundle(portfolio_id, db, owner, assessment_version_id)["risk"]


@router.get("/{portfolio_id}/confidence")
def confidence(
    portfolio_id: uuid.UUID, db: DB, owner: Owner, assessment_version_id: uuid.UUID | None = None
):
    return _bundle(portfolio_id, db, owner, assessment_version_id)["confidence"]
