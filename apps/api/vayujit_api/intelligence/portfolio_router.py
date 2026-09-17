"""Authenticated owner-scoped supplier portfolio foundation API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.portfolio_analysis import (
    calculate_concentration,
    calculate_dependencies,
    calculate_readiness,
)
from vayujit_api.intelligence.portfolio_schemas import (
    AssessmentCreate,
    PortfolioCreate,
    PortfolioMemberCreate,
    PortfolioPatch,
)
from vayujit_api.intelligence.portfolio_service import (
    add_member,
    assessment_history,
    create_assessment,
    create_portfolio,
    current_assessment,
    list_members,
    list_portfolios,
    portfolio_detail,
    portfolio_or_404,
    update_portfolio,
)

router = APIRouter(prefix="/api/v1/intelligence/supplier-portfolios", tags=["supplier-portfolios"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create(data: PortfolioCreate, db: DB, owner: Owner) -> dict[str, object]:
    payload, reused = create_portfolio(db, owner, data)
    return {**payload, "reused": reused}


@router.get("")
def list_all(db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_portfolios(db, owner)


@router.get("/{portfolio_id}")
def detail(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = portfolio_or_404(db, owner, portfolio_id)
    return portfolio_detail(row)


@router.patch("/{portfolio_id}")
def patch(portfolio_id: uuid.UUID, data: PortfolioPatch, db: DB, owner: Owner) -> dict[str, object]:
    return update_portfolio(db, owner, portfolio_or_404(db, owner, portfolio_id), data)


@router.post("/{portfolio_id}/members", status_code=status.HTTP_201_CREATED)
def member(
    portfolio_id: uuid.UUID, data: PortfolioMemberCreate, db: DB, owner: Owner
) -> dict[str, object]:
    return add_member(db, owner, portfolio_or_404(db, owner, portfolio_id), data)


@router.get("/{portfolio_id}/members")
def members(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return list_members(db, owner, portfolio_or_404(db, owner, portfolio_id))


@router.post("/{portfolio_id}/assess", status_code=status.HTTP_201_CREATED)
def assess(
    portfolio_id: uuid.UUID, data: AssessmentCreate, db: DB, owner: Owner
) -> dict[str, object]:
    payload, reused = create_assessment(db, owner, portfolio_or_404(db, owner, portfolio_id), data)
    return {**payload, "reused": reused}


@router.get("/{portfolio_id}/assessment")
def assessment(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    row = portfolio_or_404(db, owner, portfolio_id)
    value = current_assessment(db, owner, row)
    return value or {"status": "not_assessed"}


@router.get("/{portfolio_id}/history")
def history(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    return assessment_history(db, owner, portfolio_or_404(db, owner, portfolio_id))


@router.get("/{portfolio_id}/concentration")
def concentration(
    portfolio_id: uuid.UUID,
    db: DB,
    owner: Owner,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, object]:
    row = portfolio_or_404(db, owner, portfolio_id)
    return calculate_concentration(db, owner, row, assessment_version_id)


@router.get("/{portfolio_id}/dependencies")
def dependencies(
    portfolio_id: uuid.UUID,
    db: DB,
    owner: Owner,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, object]:
    row = portfolio_or_404(db, owner, portfolio_id)
    return calculate_dependencies(db, owner, row, assessment_version_id)


@router.get("/{portfolio_id}/alternates")
def alternates(
    portfolio_id: uuid.UUID,
    db: DB,
    owner: Owner,
    assessment_version_id: uuid.UUID | None = None,
) -> dict[str, object]:
    row = portfolio_or_404(db, owner, portfolio_id)
    return calculate_readiness(db, owner, row, assessment_version_id)
