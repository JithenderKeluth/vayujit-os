"""API contracts for the explicit PR-7B send boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SendAuthorizationRequest(BaseModel):
    draft_version: int = Field(ge=1)
    channel: Literal["EMAIL"] = "EMAIL"
    idempotency_key: str = Field(min_length=8, max_length=220)
    confirm: bool = True
    provenance: Literal["HUMAN"] = "HUMAN"


class SendRequest(BaseModel):
    authorization_id: str
    idempotency_key: str = Field(min_length=8, max_length=220)
    confirm: bool = True
    # This is intentionally only an isolated fake-provider control.  It is
    # ignored/rejected outside the test fake boundary.
    provider_outcome: (
        Literal["ACCEPTED", "RETRYABLE_FAILURE", "FINAL_FAILURE", "UNKNOWN_OUTCOME"] | None
    ) = None


class RetrySendRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=220)
    confirm: bool = True
    provider_outcome: (
        Literal["ACCEPTED", "RETRYABLE_FAILURE", "FINAL_FAILURE", "UNKNOWN_OUTCOME"] | None
    ) = None
