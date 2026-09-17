"""HTTP contracts for the bounded 8E.5 operational integration."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PortfolioAction = Literal[
    "ACKNOWLEDGE_RISK",
    "REQUEST_MORE_RESEARCH",
    "REQUEST_DUE_DILIGENCE",
    "CREATE_BACKUP_SCENARIO",
    "KEEP_UNDER_REVIEW",
    "ACCEPT_CONCENTRATION",
    "ARCHIVE_RECOMMENDATION",
]


class PortfolioActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: PortfolioAction
    idempotency_key: str = Field(min_length=3, max_length=180)
    rationale: str = Field(default="", max_length=2000)
    assessment_version_id: uuid.UUID | None = None
    recommendation_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None


class PortfolioRecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "RECALCULATE_STALE_PORTFOLIO_ASSESSMENT",
        "RETRY_FAILED_PORTFOLIO_SIMULATION",
        "REBUILD_PORTFOLIO_OPERATIONAL_PROJECTION",
    ]
    idempotency_key: str = Field(min_length=3, max_length=180)
    reason: str = Field(min_length=1, max_length=2000)
    assessment_version_id: uuid.UUID | None = None
    simulation_id: uuid.UUID | None = None
    confirm: bool = False
