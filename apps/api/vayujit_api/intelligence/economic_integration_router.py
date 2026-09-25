"""Product Opportunity read-only sourcing economics projection endpoints (13G)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.economic_integration_service import (
    project_economics_for_opportunity,
)

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities",
    tags=["product-opportunity-sourcing-economics"],
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/{opportunity_id}/sourcing-economics")
def sourcing_economics_projection(
    opportunity_id: uuid.UUID,
    db: DB,
    owner: Owner,
    economic_context_id: uuid.UUID | None = None,
) -> dict[str, object]:
    return project_economics_for_opportunity(
        db, owner, opportunity_id, economic_context_id=economic_context_id
    )
