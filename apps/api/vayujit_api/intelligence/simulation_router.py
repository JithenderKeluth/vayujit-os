"""Owner-scoped supplier portfolio resilience simulation API (8E.4)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.portfolio_service import portfolio_or_404
from vayujit_api.intelligence.simulation_schemas import SimulationRequest
from vayujit_api.intelligence.simulation_service import (
    create_simulation,
    get_simulation,
    list_simulations,
)

router = APIRouter(
    prefix="/api/v1/intelligence/supplier-portfolios",
    tags=["supplier-portfolio-simulations"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.post("/{portfolio_id}/simulations", status_code=status.HTTP_201_CREATED)
def create(
    portfolio_id: uuid.UUID, data: SimulationRequest, db: DB, owner: Owner
) -> dict[str, object]:
    portfolio = portfolio_or_404(db, owner, portfolio_id)
    payload, reused = create_simulation(db, owner, portfolio, data)
    return {**payload, "reused": reused}


@router.get("/{portfolio_id}/simulations")
def list_all(portfolio_id: uuid.UUID, db: DB, owner: Owner) -> list[dict[str, object]]:
    portfolio = portfolio_or_404(db, owner, portfolio_id)
    return list_simulations(db, owner, portfolio)


@router.get("/{portfolio_id}/simulations/{simulation_id}")
def detail(
    portfolio_id: uuid.UUID, simulation_id: uuid.UUID, db: DB, owner: Owner
) -> dict[str, object]:
    portfolio = portfolio_or_404(db, owner, portfolio_id)
    return get_simulation(db, owner, portfolio, simulation_id)
