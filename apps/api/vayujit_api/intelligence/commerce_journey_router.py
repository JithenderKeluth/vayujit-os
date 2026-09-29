from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.business_agent_models import BusinessAgentGoal, agent_now
from vayujit_api.intelligence.commerce_journey import project_journey
from vayujit_api.intelligence.economic_integration_service import record_journey_decision

router = APIRouter(prefix="/api/v1/commerce-journeys", tags=["commerce-journeys"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


class JourneyDecision(BaseModel):
    opportunity_id: uuid.UUID
    action: str = Field(min_length=3, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    economic_context_id: uuid.UUID | None = None
    scenario_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=160)


class ContextConfirmation(BaseModel):
    confirmed: bool = False
    marketplace: str | None = Field(default=None, max_length=120)
    budget_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    risk_preference: str | None = Field(default=None, max_length=80)
    constraints: list[str] = Field(default_factory=list, max_length=30)


@router.get("/active")
def active_journey(db: DB, owner: Owner) -> dict[str, object]:
    return {"journey": project_journey(db, owner)}


@router.get("/{journey_id}")
def get_journey(journey_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    journey = project_journey(db, owner, journey_id)
    if journey is None:
        raise HTTPException(404, "Commerce journey not found.")
    return {"journey": journey}


@router.get("/{journey_id}/next-action")
def next_action(journey_id: uuid.UUID, db: DB, owner: Owner) -> dict[str, object]:
    journey = project_journey(db, owner, journey_id)
    if journey is None:
        raise HTTPException(404, "Commerce journey not found.")
    return {
        "journey_id": journey_id,
        "next_action": journey["next_action"],
        "human_controlled": True,
    }


@router.post("/{journey_id}/context-confirmation")
def confirm_context(
    journey_id: uuid.UUID, data: ContextConfirmation, db: DB, owner: Owner
) -> dict[str, object]:
    goal = db.scalar(
        select(BusinessAgentGoal).where(
            BusinessAgentGoal.id == journey_id, BusinessAgentGoal.owner_id == owner.id
        )
    )
    if goal is None:
        raise HTTPException(404, "Commerce journey not found.")
    if not data.confirmed:
        return {"confirmed": False, "journey": project_journey(db, owner, journey_id)}
    values = {
        key: value
        for key, value in data.model_dump().items()
        if key not in {"confirmed", "constraints"} and value is not None
    }
    values["constraints"] = data.constraints
    structured = dict(goal.structured_goal or {})
    structured["commerce_context"] = values
    provenance = dict(goal.provenance or {})
    provenance["commerce_context_confirmed"] = True
    provenance["commerce_context_source"] = "USER_CONFIRMED"
    goal.structured_goal = structured
    goal.provenance = provenance
    goal.updated_at = agent_now()
    db.commit()
    return {"confirmed": True, "journey": project_journey(db, owner, journey_id)}


@router.get("/{journey_id}/decision-brief")
def journey_decision_brief(
    journey_id: uuid.UUID,
    db: DB,
    owner: Owner,
    opportunity_id: uuid.UUID,
    economic_context_id: uuid.UUID | None = None,
) -> dict[str, object]:
    from vayujit_api.intelligence.economic_integration_service import decision_brief_for_opportunity

    journey = project_journey(db, owner, journey_id)
    if journey is None:
        raise HTTPException(404, "Commerce journey not found.")
    return decision_brief_for_opportunity(
        db, owner, opportunity_id, economic_context_id=economic_context_id
    )


@router.post("/{journey_id}/decision")
def journey_decision(
    journey_id: uuid.UUID, data: JourneyDecision, db: DB, owner: Owner
) -> dict[str, object]:
    return record_journey_decision(
        db,
        owner,
        journey_id,
        opportunity_id=data.opportunity_id,
        action=data.action,
        note=data.note,
        economic_context_id=data.economic_context_id,
        scenario_id=data.scenario_id,
        idempotency_key=data.idempotency_key,
    )
