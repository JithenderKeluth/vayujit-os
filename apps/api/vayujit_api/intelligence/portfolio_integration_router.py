"""Authenticated routes for Slice 8E.5 portfolio operational integration."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.portfolio_integration import (
    calendar,
    human_action,
    operations,
    portfolio_integrity,
    portfolio_product_channel,
    recover,
)
from vayujit_api.intelligence.portfolio_integration_schemas import (
    PortfolioActionRequest,
    PortfolioRecoveryRequest,
)
from vayujit_api.intelligence.portfolio_service import portfolio_or_404

router = APIRouter(
    prefix="/api/v1/intelligence/supplier-portfolios",
    tags=["supplier-portfolio-operational-integration"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/operations")
def portfolio_operations(db: DB, owner: Owner) -> dict[str, Any]:
    return operations(db, owner)


@router.get("/calendar")
def portfolio_calendar(db: DB, owner: Owner) -> list[dict[str, Any]]:
    return calendar(db, owner)


@router.get("/system-doctor")
def portfolio_system_doctor(db: DB, owner: Owner) -> dict[str, Any]:
    counters = portfolio_integrity(db, owner)
    return {
        "status": "PASS" if not any(counters.values()) else "INTEGRITY_FAILURE",
        "severity": "product_integrity_problem" if any(counters.values()) else "none",
        "integrity": counters,
        "configuration_warnings": [],
        "external_limitations": ["Supplier contact and procurement dispatch are disabled."],
    }


@router.get("/{portfolio_id}/product-channel")
def product_channel(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, Any]:
    return portfolio_product_channel(db, owner, portfolio_or_404(db, owner, portfolio_id))


@router.get("/{portfolio_id}/events")
def events(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, Any]]:
    return portfolio_product_channel(db, owner, portfolio_or_404(db, owner, portfolio_id))["events"]


@router.post("/{portfolio_id}/actions")
def action(
    portfolio_id: uuid.UUID, data: PortfolioActionRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    return human_action(db, owner, portfolio_or_404(db, owner, portfolio_id), data)


@router.post("/{portfolio_id}/recovery")
def recovery(
    portfolio_id: uuid.UUID, data: PortfolioRecoveryRequest, db: DB, owner: Owner
) -> dict[str, Any]:
    return recover(db, owner, portfolio_or_404(db, owner, portfolio_id), data)


@router.get("/{portfolio_id}/integrity")
def integrity(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, int]:
    portfolio_or_404(db, owner, portfolio_id)
    all_values = portfolio_integrity(db, owner)
    return {key: value for key, value in all_values.items()}
