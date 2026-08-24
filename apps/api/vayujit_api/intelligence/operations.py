# ruff: noqa: E501
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.projection import get_operations_projection

router = APIRouter(prefix="/api/v1/operations/intelligence", tags=["operations-intelligence"])
diagnostics_router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/projection")
def projection(db: DB, owner: Owner) -> dict[str, object]:
    return get_operations_projection(db, owner)


@diagnostics_router.get("/system-doctor")
def system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    value = get_operations_projection(db, owner)
    return {
        "status": "healthy" if value["enabled"] else "disabled",
        "checks": {
            "database_readiness": "ready",
            "worker_registration": value["workers"],
            "scheduler_registration": value["scheduler"],
            "source_registry": {
                "enabled": value["enabled_sources"],
                "external_calls": value["external_calls"],
            },
            "unsafe_configuration": {
                "external_research_disabled": not value["external_research_enabled"]
            },
            "freshness_backlog": value["freshness_backlog"],
            "evidence_storage": "ready",
            "supplier_intelligence": {
                "enabled": value["enabled"],
                "provider": "deterministic_local_fixture",
                "worker": "registered",
                "source_registry": "ready",
                "external_connectors": "disabled",
            },
        },
    }
