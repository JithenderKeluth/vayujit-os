"""Strict request contracts for bounded 8E.4 simulations."""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SimulationType = Literal[
    "SUPPLIER_UNAVAILABLE",
    "SUPPLIER_CAPACITY_REDUCTION",
    "COUNTRY_DISRUPTION",
    "REGION_DISRUPTION",
    "LEAD_TIME_INCREASE",
    "LANDED_COST_INCREASE",
    "FX_SHOCK",
    "MOQ_INCREASE",
    "AVAILABILITY_REDUCTION",
    "MULTI_SUPPLIER_DISRUPTION",
    "CUSTOM",
]

Provenance = Literal["OBSERVED", "VERIFIED", "DERIVED", "HUMAN_ENTERED", "SIMULATION_ASSUMPTION"]


class SimulationAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: object
    provenance: Provenance = "SIMULATION_ASSUMPTION"


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_type: SimulationType
    assessment_version_id: uuid.UUID | None = None
    assumptions: dict[str, object] = Field(default_factory=dict)
    idempotency_key: Annotated[str, Field(min_length=3, max_length=180)]

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, value: dict[str, object]) -> dict[str, object]:
        if len(value) > 32:
            raise ValueError("At most 32 bounded simulation assumptions are supported.")
        for key, item in value.items():
            if len(key) > 80:
                raise ValueError("Simulation assumption names are too long.")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Simulation assumptions must be finite.")
        return value
