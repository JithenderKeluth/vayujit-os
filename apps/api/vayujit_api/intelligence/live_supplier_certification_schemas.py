"""API contracts for the PR-9A controlled certification harness."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LiveSupplierApprovalCreate(BaseModel):
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    source_url: str = Field(min_length=1, max_length=2_000)
    candidate_category: str = Field(default="supplier_website", min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=500)
    path_scope: str | None = Field(default=None, max_length=2_000)
    expires_at: datetime | None = None
    actor_provenance: str = Field(default="HUMAN", max_length=16)

    @field_validator("source_url", "purpose", "candidate_category", "actor_provenance")
    @classmethod
    def clean_text(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError("control characters are not allowed")
        return value.strip()


class LiveSupplierCertificationCreate(BaseModel):
    approval_id: uuid.UUID
    source_url: str | None = Field(default=None, max_length=2_000)
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    correlation_id: str = Field(default="", max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=180)
    refresh: bool = False


class LiveSupplierApprovalAction(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    actor_provenance: str = Field(default="HUMAN", max_length=16)
    # Optional PR-9B review fields keep the original PR-9A review route
    # backward-compatible while exposing the canonical append-only review
    # contract at the same execution resource.
    action: str | None = Field(default=None, max_length=32)
    rationale: str | None = Field(default=None, max_length=2_000)
    evidence_hash: str = Field(default="", max_length=128)
    evidence_version: int = Field(default=1, ge=1)

    @field_validator("reason", "actor_provenance")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError("control characters are not allowed")
        return value.strip()


class LiveSupplierExecutionAuthorizationCreate(BaseModel):
    approval_id: uuid.UUID
    source_url: str | None = Field(default=None, max_length=2_000)
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    provider: str = Field(default="approved_web_fetch", max_length=64)
    expires_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=180)
    actor_provenance: str = Field(default="HUMAN", max_length=16)


class LiveSupplierExecutionAuthorizationAction(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    actor_provenance: str = Field(default="HUMAN", max_length=16)

    @field_validator("reason", "actor_provenance")
    @classmethod
    def clean_action_text(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError("control characters are not allowed")
        return value.strip()


class LiveSupplierExecutionAction(BaseModel):
    actor_provenance: str = Field(default="HUMAN", max_length=16)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @field_validator("actor_provenance")
    @classmethod
    def clean_execution_actor(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError("control characters are not allowed")
        return value.strip()


class LiveSupplierExecutionEligibilityRequest(BaseModel):
    approval_id: uuid.UUID
    source_url: str | None = Field(default=None, max_length=2_000)
    goal_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    provider: str = Field(default="approved_web_fetch", max_length=64)


class LiveSupplierEvidenceReviewCreate(BaseModel):
    action: str = Field(min_length=1, max_length=32)
    rationale: str = Field(min_length=1, max_length=2_000)
    evidence_hash: str = Field(default="", max_length=128)
    evidence_version: int = Field(default=1, ge=1)
    actor_provenance: str = Field(default="HUMAN", max_length=16)

    @field_validator("action", "rationale", "evidence_hash", "actor_provenance")
    @classmethod
    def clean_review_text(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\t" for char in value):
            raise ValueError("control characters are not allowed")
        return value.strip()
