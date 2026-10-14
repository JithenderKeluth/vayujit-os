"""Controlled RFQ EMAIL authorization, outbox, and fake-provider delivery."""

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.core.config import get_settings
from vayujit_api.identity.models import User
from vayujit_api.intelligence.email_delivery_models import (
    RfqDeliveryAttempt,
    RfqSendAuthorization,
    RfqSendCommand,
    RfqSendOutbox,
)
from vayujit_api.intelligence.email_delivery_provider import (
    FakeEmailProvider,
    ProviderOutcome,
)
from vayujit_api.intelligence.engagement_models import (
    SupplierEngagement,
    SupplierEngagementDraft,
)
from vayujit_api.intelligence.engagement_service import (
    _decision_context,
    _event,
    _hash,
    _latest_approval,
    _latest_draft,
    _owned,
    now,
)
from vayujit_api.intelligence.supplier_models import Supplier, SupplierContact

_EMAIL = re.compile(r"^[^\s@\r\n]+@[^\s@\r\n]+\.[^\s@\r\n]+$")


def _fake_enabled() -> bool:
    settings = get_settings()
    return (
        settings.environment == "test"
        and settings.email_delivery_enabled
        and settings.email_delivery_provider_mode == "FAKE"
        and not settings.external_mutations_emergency_stop
    )


def _trust_environment(supplier: Supplier, contact: SupplierContact) -> str:
    source = (supplier.source_identity or "").lower()
    provenance = (contact.provenance or "").lower()
    if any(
        token in source or token in provenance for token in ("fixture", "deterministic", "local")
    ):
        return "DETERMINISTIC_TEST"
    return "UNKNOWN"


def _contact_snapshot(contact: SupplierContact) -> dict[str, object]:
    return {
        "id": str(contact.id),
        "name": contact.name,
        "role": contact.role,
        "email": contact.email,
        "preferred_method": contact.preferred_method,
        "provenance": contact.provenance,
        "verification_status": contact.verification_status,
        "communication_status": contact.communication_status,
        "trust_environment": (
            "DETERMINISTIC_TEST"
            if "fixture" in (contact.provenance or "").lower()
            or "deterministic" in (contact.provenance or "").lower()
            else "UNKNOWN"
        ),
        "observed_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


def _supplier_snapshot(supplier: Supplier) -> dict[str, object]:
    return {
        "id": str(supplier.id),
        "display_name": supplier.display_name,
        "website": supplier.website,
        "normalized_domain": supplier.normalized_domain,
        "verification_state": supplier.verification_state,
        "source_identity": supplier.source_identity,
        "trust_environment": (
            "DETERMINISTIC_TEST"
            if "fixture" in (supplier.source_identity or "").lower()
            or "deterministic" in (supplier.source_identity or "").lower()
            else "UNKNOWN"
        ),
    }


def _payload(draft: SupplierEngagementDraft, contact: SupplierContact) -> dict[str, object]:
    return {
        "to": contact.email,
        "subject": draft.subject,
        "message_body": draft.message_body,
        "channel": "EMAIL",
        "cc": [],
        "bcc": [],
    }


def _eligibility(db: Session, owner: User, engagement: SupplierEngagement) -> dict[str, Any]:
    draft = _latest_draft(db, owner, engagement.id)
    approval = _latest_approval(db, owner, engagement.id)
    supplier = db.get(Supplier, engagement.supplier_id)
    contact = db.get(SupplierContact, engagement.contact_id) if engagement.contact_id else None
    reasons: list[dict[str, str]] = []
    decision = None
    if supplier is None:
        reasons.append({"code": "SUPPLIER_NOT_FOUND", "message": "Supplier scope is unavailable."})
    if (
        contact is None
        or contact.owner_id != owner.id
        or contact.supplier_id != engagement.supplier_id
        or contact.archived
    ):
        reasons.append(
            {
                "code": "EMAIL_CONTACT_REQUIRED",
                "message": "An active email contact belonging to this supplier is required.",
            }
        )
    elif not contact.email or not _EMAIL.match(contact.email):
        reasons.append(
            {
                "code": "EMAIL_CONTACT_INVALID",
                "message": "The reviewed contact does not contain a safe email address.",
            }
        )
    if draft is None:
        reasons.append({"code": "DRAFT_REQUIRED", "message": "A current RFQ draft is required."})
    if (
        approval is None
        or approval.state != "APPROVED_FOR_SEND"
        or draft is None
        or approval.draft_id != draft.id
    ):
        reasons.append(
            {
                "code": "CURRENT_APPROVAL_REQUIRED",
                "message": "The exact current draft must have HUMAN approval.",
            }
        )
    if engagement.status == "CANCELLED":
        reasons.append(
            {"code": "ENGAGEMENT_CANCELLED", "message": "Cancelled engagements cannot send."}
        )
    try:
        decision = _decision_context(
            db,
            owner,
            engagement.opportunity_id,
            engagement.supplier_id,
            engagement.decision_target,
            engagement.human_decision_id,
        )
    except HTTPException:
        decision = None
    if decision is None or decision.decision != "PROCEED":
        reasons.append(
            {"code": "HUMAN_PROCEED_REQUIRED", "message": "A current HUMAN PROCEED is required."}
        )
    if supplier is not None and supplier.verification_state in {"suspended", "blocked"}:
        reasons.append(
            {"code": "SUPPLIER_BLOCKED", "message": "Supplier verification blocks delivery."}
        )
    settings = get_settings()
    trust = _trust_environment(supplier, contact) if supplier and contact else "UNKNOWN"
    fake_allowed = _fake_enabled() and trust == "DETERMINISTIC_TEST"
    live_allowed = (
        settings.environment in {"staging", "production"}
        and settings.email_delivery_enabled
        and settings.email_delivery_provider_mode == "LIVE"
        and settings.live_email_delivery_enabled
        and not settings.external_mutations_emergency_stop
        and trust != "DETERMINISTIC_TEST"
    )
    if trust == "DETERMINISTIC_TEST" and not fake_allowed:
        reasons.append(
            {
                "code": "DETERMINISTIC_PROVIDER_BLOCKED",
                "message": "Deterministic test evidence can never reach a real provider.",
            }
        )
    if contact is not None and contact.email and contact.verification_status != "verified":
        reasons.append(
            {
                "code": "CONTACT_NOT_VERIFIED",
                "message": (
                    "Email syntax is not recipient verification; live delivery requires "
                    "a verified contact."
                ),
            }
        )
    if not fake_allowed and not live_allowed:
        reasons.append(
            {
                "code": "EMAIL_PROVIDER_NOT_CONFIGURED",
                "message": "No permitted email delivery provider is configured.",
            }
        )
    payload = _payload(draft, contact) if draft and contact else {}
    fingerprint = _hash(payload)
    blocking_codes = {
        reason["code"]
        for reason in reasons
        if not (fake_allowed and reason["code"] == "CONTACT_NOT_VERIFIED")
    }
    return {
        "draft": draft,
        "approval": approval,
        "supplier": supplier,
        "contact": contact,
        "decision": decision,
        "payload": payload,
        "payload_fingerprint": fingerprint,
        "trust_environment": trust,
        "reasons": reasons,
        "can_authorize_send": not blocking_codes,
        "fake_allowed": fake_allowed,
        "live_allowed": live_allowed,
    }


def _auth_dict(row: RfqSendAuthorization | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "engagement_id": str(row.engagement_id),
        "draft_id": str(row.draft_id),
        "draft_version": row.draft_version,
        "approval_id": str(row.approval_id),
        "human_decision_id": str(row.human_decision_id),
        "channel": row.channel,
        "recipient": row.recipient,
        "status": row.status,
        "provenance": row.provenance,
        "idempotency_key": row.idempotency_key,
        "payload_fingerprint": row.payload_fingerprint,
        "context_fingerprint": row.context_fingerprint,
        "created_at": row.created_at.isoformat(),
    }


def _command_dict(db: Session, row: RfqSendCommand | None) -> dict[str, object] | None:
    if row is None:
        return None
    attempts = list(
        db.scalars(
            select(RfqDeliveryAttempt)
            .where(RfqDeliveryAttempt.command_id == row.id)
            .order_by(RfqDeliveryAttempt.attempt_number)
        )
    )
    return {
        "id": str(row.id),
        "logical_message_id": str(row.logical_message_id),
        "authorization_id": str(row.authorization_id),
        "engagement_id": str(row.engagement_id),
        "channel": row.channel,
        "recipient": row.recipient,
        "provider": row.provider,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "provider_reference": row.provider_reference,
        "last_error": row.last_error,
        "idempotency_key": row.idempotency_key,
        "payload_fingerprint": row.payload_fingerprint,
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "outcome": a.outcome,
                "provider": a.provider,
                "provider_reference": a.provider_reference,
                "error_category": a.error_category,
                "retryable": a.retryable,
                "payload_fingerprint": a.payload_fingerprint,
                "started_at": a.started_at.isoformat(),
                "completed_at": a.completed_at.isoformat(),
            }
            for a in attempts
        ],
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _outbox_dict(row: RfqSendOutbox | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "command_id": str(row.command_id),
        "state": row.state,
        "attempt_count": row.attempt_count,
        "available_at": row.available_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _latest_auth(db: Session, owner: User, engagement_id: uuid.UUID) -> RfqSendAuthorization | None:
    return db.scalars(
        select(RfqSendAuthorization)
        .where(
            RfqSendAuthorization.owner_id == owner.id,
            RfqSendAuthorization.engagement_id == engagement_id,
        )
        .order_by(RfqSendAuthorization.created_at.desc())
    ).first()


def _latest_command(db: Session, owner: User, engagement_id: uuid.UUID) -> RfqSendCommand | None:
    return db.scalars(
        select(RfqSendCommand)
        .where(RfqSendCommand.owner_id == owner.id, RfqSendCommand.engagement_id == engagement_id)
        .order_by(RfqSendCommand.created_at.desc())
    ).first()


def send_eligibility(db: Session, owner: User, engagement_id: uuid.UUID) -> dict[str, object]:
    engagement = _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    ctx = _eligibility(db, owner, engagement)
    auth = _latest_auth(db, owner, engagement.id)
    command = _latest_command(db, owner, engagement.id)
    return {
        "engagement_id": str(engagement.id),
        "channel": "EMAIL",
        "can_authorize_send": ctx["can_authorize_send"],
        "fake_provider_allowed": ctx["fake_allowed"],
        "live_provider_allowed": ctx["live_allowed"],
        "live_eligible": ctx["live_allowed"],
        "trust_environment": ctx["trust_environment"],
        "blocking_reasons": ctx["reasons"],
        "preview": {
            "supplier": ctx["supplier"].display_name if ctx["supplier"] else None,
            "recipient": ctx["contact"].email if ctx["contact"] else None,
            "subject": ctx["draft"].subject if ctx["draft"] else None,
            "quantity": (
                (ctx["draft"].structured_request or {}).get("requested_quantity")
                if ctx["draft"]
                else None
            ),
            "requested_fields": (
                (ctx["draft"].structured_request or {}).get("requested_fields", [])
                if ctx["draft"]
                else []
            ),
            "message": ctx["draft"].message_body if ctx["draft"] else None,
            "warnings": ctx["draft"].warnings if ctx["draft"] else [],
            "unknowns": ctx["draft"].unknowns if ctx["draft"] else [],
            "limitations": ctx["draft"].limitations if ctx["draft"] else [],
        },
        "send_authorization": _auth_dict(auth),
        "send_command": _command_dict(db, command),
        "safe_next_action": (
            "Review the exact recipient and message, then explicitly authorize Send RFQ."
            if ctx["can_authorize_send"]
            else "Resolve the blocking evidence and approval requirements before sending."
        ),
    }


def authorize_send(
    db: Session, owner: User, engagement_id: uuid.UUID, data: Any
) -> dict[str, object]:
    if data.provenance != "HUMAN" or not data.confirm or data.channel != "EMAIL":
        raise HTTPException(
            403,
            {
                "code": "HUMAN_SEND_AUTH_REQUIRED",
                "message": "Only an explicit HUMAN EMAIL authorization can proceed.",
            },
        )
    existing = db.scalar(
        select(RfqSendAuthorization).where(
            RfqSendAuthorization.owner_id == owner.id,
            RfqSendAuthorization.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        if existing.engagement_id != engagement_id:
            raise HTTPException(
                409, "The authorization idempotency key belongs to another engagement."
            )
        return {
            "authorization": _auth_dict(existing),
            "eligibility": send_eligibility(db, owner, engagement_id),
        }
    engagement = _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    ctx = _eligibility(db, owner, engagement)
    if not ctx["can_authorize_send"]:
        raise HTTPException(
            409,
            {
                "code": "SEND_NOT_ELIGIBLE",
                "message": "RFQ send authorization is blocked.",
                "blocking_reasons": ctx["reasons"],
            },
        )
    draft = ctx["draft"]
    if draft.version != data.draft_version:
        raise HTTPException(
            409,
            {"code": "STALE_DRAFT", "message": "The requested draft version is no longer current."},
        )
    auth = RfqSendAuthorization(
        owner_id=owner.id,
        actor_id=owner.id,
        goal_id=engagement.goal_id,
        opportunity_id=engagement.opportunity_id,
        supplier_id=engagement.supplier_id,
        contact_id=ctx["contact"].id,
        engagement_id=engagement.id,
        draft_id=draft.id,
        draft_version=draft.version,
        approval_id=ctx["approval"].id,
        human_decision_id=ctx["decision"].id,
        channel="EMAIL",
        recipient=ctx["contact"].email,
        subject_fingerprint=_hash(draft.subject),
        payload_fingerprint=ctx["payload_fingerprint"],
        context_fingerprint=_hash(
            {
                "engagement": str(engagement.id),
                "draft": str(draft.id),
                "approval": str(ctx["approval"].id),
                "decision": str(ctx["decision"].id),
                "recipient": ctx["contact"].email,
            }
        ),
        status="AUTHORIZED",
        provenance="HUMAN",
        idempotency_key=data.idempotency_key,
        supplier_snapshot=_supplier_snapshot(ctx["supplier"]),
        contact_snapshot=_contact_snapshot(ctx["contact"]),
        confirmation_snapshot={
            "subject": draft.subject,
            "message_body": draft.message_body,
            "structured_request": draft.structured_request,
            "warnings": draft.warnings,
            "unknowns": draft.unknowns,
            "limitations": draft.limitations,
        },
        created_at=now(),
    )
    db.add(auth)
    _event(
        db,
        owner,
        engagement,
        "rfq_send_authorized",
        draft_version=draft.version,
        provenance="HUMAN",
        actor_id=owner.id,
        payload={
            "authorization_id": str(auth.id),
            "channel": "EMAIL",
            "recipient": ctx["contact"].email,
            "payload_fingerprint": ctx["payload_fingerprint"],
        },
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(RfqSendAuthorization).where(
                RfqSendAuthorization.owner_id == owner.id,
                RfqSendAuthorization.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        auth = existing
    return {
        "authorization": _auth_dict(auth),
        "eligibility": send_eligibility(db, owner, engagement_id),
    }


def _blocked_command(
    db: Session, owner: User, auth: RfqSendAuthorization, reason: str, payload: dict[str, object]
) -> RfqSendCommand:
    timestamp = now()
    command = RfqSendCommand(
        owner_id=owner.id,
        authorization_id=auth.id,
        engagement_id=auth.engagement_id,
        draft_id=auth.draft_id,
        channel=auth.channel,
        recipient=auth.recipient,
        provider="none",
        payload_fingerprint=auth.payload_fingerprint,
        payload_snapshot=payload,
        status="BLOCKED",
        attempt_count=0,
        last_error=reason,
        idempotency_key=auth.idempotency_key,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(command)
    db.flush()
    db.add(
        RfqSendOutbox(
            owner_id=owner.id,
            command_id=command.id,
            state="BLOCKED",
            attempt_count=0,
            available_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    return command


def _process(
    db: Session, owner: User, command: RfqSendCommand, outcome: ProviderOutcome | None = None
) -> RfqSendCommand:
    auth = db.get(RfqSendAuthorization, command.authorization_id)
    engagement = db.get(SupplierEngagement, command.engagement_id)
    if auth is None or engagement is None:
        command.status = "BLOCKED"
        command.last_error = "AUTHORIZATION_OR_ENGAGEMENT_MISSING"
        db.commit()
        return command
    ctx = _eligibility(db, owner, engagement)
    outbox = db.scalar(select(RfqSendOutbox).where(RfqSendOutbox.command_id == command.id))
    if command.status in {"PROVIDER_ACCEPTED", "FAILED_FINAL", "UNKNOWN_OUTCOME", "BLOCKED"}:
        return command
    if (
        not ctx["can_authorize_send"]
        or ctx["draft"].id != auth.draft_id
        or ctx["draft"].version != auth.draft_version
        or ctx["payload_fingerprint"] != auth.payload_fingerprint
        or ctx["contact"].email != auth.recipient
    ):
        command.status = "BLOCKED"
        command.last_error = "STALE_SEND_AUTHORIZATION"
        if outbox:
            outbox.state = "BLOCKED"
            outbox.updated_at = now()
        _event(
            db,
            owner,
            engagement,
            "rfq_send_blocked",
            draft_version=auth.draft_version,
            payload={"command_id": str(command.id), "reason": command.last_error},
        )
        db.commit()
        return command
    if not ctx["fake_allowed"] and not ctx["live_allowed"]:
        command.status = "BLOCKED"
        command.last_error = "EMAIL_PROVIDER_NOT_CONFIGURED"
        if outbox:
            outbox.state = "BLOCKED"
        _event(
            db,
            owner,
            engagement,
            "rfq_send_blocked",
            draft_version=auth.draft_version,
            payload={"command_id": str(command.id), "reason": command.last_error},
        )
        db.commit()
        return command
    # This bounded implementation has no live adapter.  A production/live
    # configuration therefore fails closed rather than accidentally sending.
    if not ctx["fake_allowed"]:
        command.status = "BLOCKED"
        command.last_error = "LIVE_EMAIL_ADAPTER_NOT_ENABLED"
        if outbox:
            outbox.state = "BLOCKED"
        db.commit()
        return command
    command.status = "PROCESSING"
    if outbox:
        outbox.state = "PROCESSING"
    db.commit()
    attempt_number = command.attempt_count + 1
    started = now()
    result = FakeEmailProvider.send(
        recipient=command.recipient,
        subject=str(command.payload_snapshot.get("subject", "")),
        message_body=str(command.payload_snapshot.get("message_body", "")),
        logical_message_id=command.logical_message_id,
        payload_fingerprint=command.payload_fingerprint,
        outcome=outcome or "ACCEPTED",
    )
    completed = now()
    attempt = RfqDeliveryAttempt(
        owner_id=owner.id,
        command_id=command.id,
        attempt_number=attempt_number,
        provider=result.provider,
        provider_reference=result.provider_reference,
        outcome=result.outcome,
        error_category=result.error_category,
        retryable=result.retryable,
        payload_fingerprint=command.payload_fingerprint,
        receipt_metadata=result.receipt_metadata or {},
        started_at=started,
        completed_at=completed,
    )
    db.add(attempt)
    command.attempt_count = attempt_number
    command.provider_reference = result.provider_reference
    command.last_error = result.error_category
    if result.outcome == "ACCEPTED":
        command.status = "PROVIDER_ACCEPTED"
        _event(
            db,
            owner,
            engagement,
            "rfq_provider_accepted",
            draft_version=auth.draft_version,
            payload={
                "command_id": str(command.id),
                "provider": result.provider,
                "provider_reference": result.provider_reference,
            },
        )
    elif result.outcome == "RETRYABLE_FAILURE":
        command.status = "FAILED_RETRYABLE"
        _event(
            db,
            owner,
            engagement,
            "rfq_delivery_failed",
            draft_version=auth.draft_version,
            payload={
                "command_id": str(command.id),
                "error_category": result.error_category,
                "retryable": True,
            },
        )
    elif result.outcome == "FINAL_FAILURE":
        command.status = "FAILED_FINAL"
        _event(
            db,
            owner,
            engagement,
            "rfq_delivery_failed",
            draft_version=auth.draft_version,
            payload={
                "command_id": str(command.id),
                "error_category": result.error_category,
                "retryable": False,
            },
        )
    else:
        command.status = "UNKNOWN_OUTCOME"
        _event(
            db,
            owner,
            engagement,
            "rfq_delivery_failed",
            draft_version=auth.draft_version,
            payload={
                "command_id": str(command.id),
                "error_category": result.error_category,
                "unknown_outcome": True,
            },
        )
    command.updated_at = completed
    if outbox:
        outbox.state = command.status
        outbox.attempt_count = command.attempt_count
        outbox.updated_at = completed
    db.commit()
    return command


def send_rfq(db: Session, owner: User, engagement_id: uuid.UUID, data: Any) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit send confirmation is required.")
    try:
        auth_id = uuid.UUID(data.authorization_id)
    except ValueError as exc:
        raise HTTPException(422, "Invalid send authorization id.") from exc
    auth = db.scalar(
        select(RfqSendAuthorization).where(
            RfqSendAuthorization.id == auth_id,
            RfqSendAuthorization.owner_id == owner.id,
            RfqSendAuthorization.engagement_id == engagement_id,
        )
    )
    if auth is None:
        raise HTTPException(404, "Send authorization not found.")
    command = db.scalar(
        select(RfqSendCommand).where(
            RfqSendCommand.owner_id == owner.id,
            RfqSendCommand.authorization_id == auth.id,
        )
    )
    if command is None:
        command = db.scalar(
            select(RfqSendCommand).where(
                RfqSendCommand.owner_id == owner.id,
                RfqSendCommand.idempotency_key == data.idempotency_key,
            )
        )
        if command is not None and command.authorization_id != auth.id:
            raise HTTPException(409, "The send idempotency key belongs to another authorization.")
    if command is None:
        command = RfqSendCommand(
            owner_id=owner.id,
            authorization_id=auth.id,
            engagement_id=auth.engagement_id,
            draft_id=auth.draft_id,
            channel=auth.channel,
            recipient=auth.recipient,
            provider="fake",
            payload_fingerprint=auth.payload_fingerprint,
            payload_snapshot=auth.confirmation_snapshot,
            status="PENDING",
            attempt_count=0,
            idempotency_key=data.idempotency_key,
            created_at=now(),
            updated_at=now(),
        )
        db.add(command)
        db.flush()
        db.add(
            RfqSendOutbox(
                owner_id=owner.id,
                command_id=command.id,
                state="PENDING",
                attempt_count=0,
                available_at=now(),
                created_at=now(),
                updated_at=now(),
            )
        )
        db.commit()
    command = _process(db, owner, command, data.provider_outcome)
    return {
        "command": _command_dict(db, command),
        "outbox": _outbox_dict(
            db.scalar(select(RfqSendOutbox).where(RfqSendOutbox.command_id == command.id))
        ),
        "send_eligibility": send_eligibility(db, owner, engagement_id),
    }


def retry_rfq(db: Session, owner: User, engagement_id: uuid.UUID, data: Any) -> dict[str, object]:
    command = _latest_command(db, owner, engagement_id)
    if command is None:
        raise HTTPException(404, "No RFQ send command exists.")
    if command.status != "FAILED_RETRYABLE":
        raise HTTPException(
            409,
            {
                "code": "RETRY_NOT_ALLOWED",
                "message": (
                    "Only retryable failures may be retried; unknown outcomes require "
                    "reconciliation."
                ),
            },
        )
    if command.attempt_count >= get_settings().email_delivery_max_attempts:
        raise HTTPException(409, "The bounded RFQ retry limit has been reached.")
    db.commit()
    command = _process(db, owner, command, data.provider_outcome)
    return {
        "command": _command_dict(db, command),
        "outbox": _outbox_dict(
            db.scalar(select(RfqSendOutbox).where(RfqSendOutbox.command_id == command.id))
        ),
    }


def process_outbox(
    db: Session, owner: User, command_id: uuid.UUID, outcome: ProviderOutcome | None = None
) -> dict[str, object]:
    command = _owned(db, RfqSendCommand, owner.id, command_id, "Send command not found.")
    command = _process(db, owner, command, outcome)
    return {
        "command": _command_dict(db, command),
        "outbox": _outbox_dict(
            db.scalar(select(RfqSendOutbox).where(RfqSendOutbox.command_id == command.id))
        ),
    }


def delivery_projection(db: Session, owner: User, engagement_id: uuid.UUID) -> dict[str, object]:
    return {
        "send_eligibility": send_eligibility(db, owner, engagement_id),
        "send_authorization": _auth_dict(_latest_auth(db, owner, engagement_id)),
        "send_command": _command_dict(db, _latest_command(db, owner, engagement_id)),
    }
