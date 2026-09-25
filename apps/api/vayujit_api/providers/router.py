"""Minimal authenticated provider registry and explicit fixture validation API."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.providers.service import provider_summaries, safe_health, validate_local_fixture

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])
CurrentUser = Annotated[User, Depends(current_user)]


class FixtureValidationRequest(BaseModel):
    scenario: Literal[
        "success",
        "paginated",
        "rate_limited",
        "timeout",
        "transient_5xx",
        "permanent_4xx",
        "malformed",
    ] = "success"
    page_size: int = Field(default=3, ge=1, le=50)


@router.get("")
def list_providers(_user: CurrentUser) -> list[dict[str, object]]:
    return provider_summaries()


@router.get("/{provider_id}")
def provider_detail(provider_id: str, _user: CurrentUser) -> dict[str, object]:
    from vayujit_api.providers.registry import provider_registry

    try:
        definition = provider_registry.get(provider_id)
    except KeyError:
        raise HTTPException(404, "Provider is not registered.") from None
    return {**definition.safe_dict(), "health": safe_health(definition.provider_id)}


@router.post("/local_fixture/validate")
def validate_fixture(data: FixtureValidationRequest, _user: CurrentUser) -> dict[str, object]:
    try:
        result = validate_local_fixture(scenario=data.scenario, page_size=data.page_size)
    except Exception as error:
        detail = getattr(error, "safe_dict", lambda: {"message": "Provider validation failed."})()
        raise HTTPException(422, detail) from None
    return {
        "status": "SUCCESS",
        "environment": "LOCAL_FIXTURE",
        "execution": result.execution.safe_dict(),
        "items": list(result.items),
    }
