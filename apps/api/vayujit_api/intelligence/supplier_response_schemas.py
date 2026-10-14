"""API contracts for the bounded PR-7C inbound evidence workflow."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierResponseCreate(BaseModel):
    supplier_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    engagement_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None
    send_command_id: uuid.UUID | None = None
    channel: Literal["EMAIL", "FORM", "MANUAL_IMPORT", "OTHER"] = "EMAIL"
    sender_identity: str | None = Field(default=None, max_length=320)
    recipient_identity: str | None = Field(default=None, max_length=320)
    provider_message_id: str | None = Field(default=None, max_length=240)
    provider_thread_id: str | None = Field(default=None, max_length=240)
    received_at: datetime | None = None
    raw_content: str = Field(min_length=1, max_length=200_000)
    attachment_refs: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    trust_environment: Literal["DETERMINISTIC_TEST", "LIVE_READ_ONLY", "UNKNOWN"] = "UNKNOWN"
    evidence_environment: Literal["DETERMINISTIC_TEST", "LIVE_READ_ONLY", "UNKNOWN"] = "UNKNOWN"
    idempotency_key: str | None = Field(default=None, max_length=220)

    @field_validator("raw_content", "sender_identity", "recipient_identity")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("Inbound response contains a control character.")
        return value

    @field_validator("attachment_refs")
    @classmethod
    def bounded_attachments(cls, value: list[dict[str, object]]) -> list[dict[str, object]]:
        for item in value:
            if len(item) > 12:
                raise ValueError("Attachment metadata is too large.")
            for key, raw_value in item.items():
                if not isinstance(raw_value, str):
                    continue
                lowered_key = str(key).lower()
                if lowered_key in {"path", "filepath", "file_path", "uri", "url"} and (
                    raw_value.startswith(("/", "\\"))
                    or ".." in raw_value.replace("/", "\\").split("\\")
                ):
                    raise ValueError(
                        "Attachment references may not contain absolute or traversing paths."
                    )
                if lowered_key in {"content_hash", "sha256", "hash"} and len(raw_value) > 128:
                    raise ValueError("Attachment content hashes are too large.")
        return value


class SupplierResponseReviewRequest(BaseModel):
    decision: Literal[
        "ACCEPT_EXTRACTION",
        "CORRECT_EXTRACTION",
        "REJECT_EXTRACTION",
        "KEEP_UNDER_REVIEW",
    ]
    extraction_id: uuid.UUID | None = None
    corrections: dict[str, object] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=4000)
    provenance: Literal["HUMAN"] = "HUMAN"
    idempotency_key: str = Field(min_length=3, max_length=220)


class SupplierResponseExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    response_id: uuid.UUID
    version: int
    status: str
    extracted_fields: dict[str, object]
    field_provenance: dict[str, object]
    source_spans: dict[str, object]
    unknown_fields: list[object]
    warnings: list[object]
    extraction_authority: str
    source_raw_hash: str
    created_at: datetime


class SupplierResponseReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    response_id: uuid.UUID
    extraction_id: uuid.UUID
    actor_id: uuid.UUID
    decision: str
    provenance: str
    corrections: dict[str, object]
    reason: str
    created_at: datetime
    idempotency_key: str


class SupplierResponseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    supplier_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    engagement_id: uuid.UUID | None
    draft_id: uuid.UUID | None
    send_command_id: uuid.UUID | None
    channel: str
    sender_identity: str | None
    recipient_identity: str | None
    provider_message_id: str | None
    provider_thread_id: str | None
    received_at: datetime
    raw_content: str
    raw_content_hash: str
    attachment_refs: list[object]
    trust_environment: str
    evidence_environment: str
    correlation_state: str
    correlation_reason: str
    correlation_metadata: dict[str, object]
    classification: str
    response_fingerprint: str
    created_at: datetime
    idempotency_key: str
    extraction: SupplierResponseExtractionResponse | None = None
    reviews: list[SupplierResponseReviewResponse] = Field(default_factory=list)
    promotion: dict[str, object] | None = None
    safe_next_action: str = "Review the extracted supplier claims before any commercial promotion."


class SupplierResponseListResponse(BaseModel):
    responses: list[SupplierResponseResponse]
    total: int
