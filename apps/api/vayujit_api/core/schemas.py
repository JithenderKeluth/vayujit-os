from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    correlation_id: str | None = None
