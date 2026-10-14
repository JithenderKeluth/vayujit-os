"""Controlled, local-only supplier engagement workflow for PR-7A.

This module deliberately stops at a durable, human-reviewed future-send state.
It never calls a mailer, HTTP contact form, provider adapter, outbox, or RFQ
dispatch boundary.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplierLink
from vayujit_api.intelligence.decision_recommendation_models import HumanDecision
from vayujit_api.intelligence.decision_recommendation_service import latest_human_decision
from vayujit_api.intelligence.engagement_models import (
    ENGAGEMENT_INTENTS,
    SupplierEngagement,
    SupplierEngagementApproval,
    SupplierEngagementDraft,
    SupplierEngagementEvent,
)
from vayujit_api.intelligence.engagement_schemas import (
    ApprovalRequest,
    CancelRequest,
    DraftRevision,
    EngagementCreate,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import Supplier, SupplierContact

TEMPLATE_VERSION = "rfq-neutral-v1"
EXTERNAL_WRITES: list[object] = []
SEND_STATUS = "NOT_EXECUTED"


def now() -> datetime:
    return datetime.now(UTC)


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _owned(db: Session, model: Any, owner_id: uuid.UUID, row_id: uuid.UUID, message: str) -> Any:
    row = db.scalar(select(model).where(model.id == row_id, model.owner_id == owner_id))
    if row is None:
        raise HTTPException(404, message)
    return row


def _event(
    db: Session,
    owner: User,
    engagement: SupplierEngagement,
    event_type: str,
    *,
    draft_version: int = 0,
    provenance: str = "SYSTEM",
    payload: dict[str, object] | None = None,
    actor_id: uuid.UUID | None = None,
) -> SupplierEngagementEvent:
    event = SupplierEngagementEvent(
        owner_id=owner.id,
        engagement_id=engagement.id,
        supplier_id=engagement.supplier_id,
        actor_id=actor_id,
        event_type=event_type,
        draft_version=draft_version,
        provenance=provenance,
        payload=payload or {},
        created_at=now(),
    )
    db.add(event)
    return event


def _supplier_snapshot(supplier: Supplier) -> dict[str, object]:
    return {
        "id": str(supplier.id),
        "display_name": supplier.display_name,
        "legal_name": supplier.legal_name,
        "website": supplier.website,
        "normalized_domain": supplier.normalized_domain,
        "country": supplier.country,
        "region": supplier.region,
        "verification_state": supplier.verification_state,
        "source_identity": supplier.source_identity,
        "communication_status": supplier.communication_status,
        "trust_environment": (
            "DETERMINISTIC_TEST"
            if supplier.source_identity.lower()
            in {"fixture", "local_fixture", "deterministic_test"}
            else "UNKNOWN"
        ),
    }


def _contact_snapshot(contact: SupplierContact | None) -> dict[str, object]:
    if contact is None:
        return {}
    channels = {
        "EMAIL": contact.email,
        "PHONE": contact.phone,
        "WHATSAPP": contact.whatsapp,
    }
    return {
        "id": str(contact.id),
        "name": contact.name,
        "role": contact.role,
        "channels": {key: value for key, value in channels.items() if value},
        "preferred_method": contact.preferred_method,
        "provenance": contact.provenance,
        "verification_status": contact.verification_status,
        "communication_status": contact.communication_status,
        "observed_at": contact.updated_at.isoformat() if contact.updated_at else None,
        "trust_environment": (
            "DETERMINISTIC_TEST"
            if "deterministic" in contact.provenance.lower()
            or "fixture" in contact.provenance.lower()
            else "UNKNOWN"
        ),
        "syntax_valid": bool(contact.email or contact.phone or contact.whatsapp),
        "verified": contact.verification_status == "verified",
    }


def _product_snapshot(opportunity: ProductOpportunity) -> dict[str, object]:
    return {
        "id": str(opportunity.id),
        "name": opportunity.name,
        "description": opportunity.description,
        "product_concept": opportunity.product_concept,
        "category": opportunity.category,
        "subcategory": opportunity.subcategory,
        "target_marketplace": opportunity.target_marketplace,
        "target_region": opportunity.target_region,
        "brand_strategy": opportunity.brand_strategy,
        "research_state": opportunity.research_state,
        "evidence_state": opportunity.evidence_state,
    }


def _contact_for(
    db: Session, owner: User, supplier_id: uuid.UUID, contact_id: uuid.UUID | None
) -> SupplierContact | None:
    if contact_id is None:
        return None
    contact = db.scalar(
        select(SupplierContact).where(
            SupplierContact.id == contact_id,
            SupplierContact.owner_id == owner.id,
            SupplierContact.supplier_id == supplier_id,
            SupplierContact.archived.is_(False),
        )
    )
    if contact is None:
        raise HTTPException(404, "Supplier contact is not available in the supplier scope.")
    return contact


def _decision_context(
    db: Session,
    owner: User,
    opportunity_id: uuid.UUID,
    supplier_id: uuid.UUID,
    target: str,
    requested_id: uuid.UUID | None,
) -> HumanDecision | None:
    canonical_ids = list(
        db.scalars(
            select(CrossMarketplaceSupplierLink.canonical_supplier_id).where(
                CrossMarketplaceSupplierLink.owner_id == owner.id,
                CrossMarketplaceSupplierLink.supplier_id == supplier_id,
            )
        )
    )
    decision = None
    for canonical_id in canonical_ids:
        decision = latest_human_decision(db, owner, opportunity_id, target, canonical_id)
        if decision is not None:
            break
    if decision is None:
        decision = latest_human_decision(db, owner, opportunity_id, target, supplier_id)
    if requested_id is not None and (decision is None or decision.id != requested_id):
        raise HTTPException(
            409,
            {
                "code": "STALE_DECISION_CONTEXT",
                "message": (
                    "The supplied HUMAN decision is no longer the current supplier-scoped decision."
                ),
            },
        )
    if decision is None:
        return None
    return decision


def _blocking_reasons(
    decision: Any,
    supplier: Supplier,
    contact: SupplierContact | None,
) -> list[dict[str, object]]:
    reasons: list[dict[str, object]] = []
    if decision is None:
        reasons.append(
            {
                "code": "HUMAN_PROCEED_REQUIRED",
                "message": "An explicit current HUMAN PROCEED is required.",
            }
        )
    elif decision.decision != "PROCEED":
        reasons.append(
            {
                "code": f"HUMAN_{decision.decision}",
                "message": (
                    f"Current HUMAN decision is {decision.decision}; "
                    "supplier engagement remains blocked."
                ),
            }
        )
    if contact is None:
        reasons.append(
            {
                "code": "CONTACT_REQUIRED",
                "message": "A canonical supplier contact is required before drafting.",
            }
        )
    elif not (contact.email or contact.phone or contact.whatsapp):
        reasons.append(
            {
                "code": "CONTACT_EVIDENCE_REQUIRED",
                "message": "The selected contact has no usable channel.",
            }
        )
    if supplier.verification_state in {"suspended", "blocked"}:
        reasons.append(
            {
                "code": "SUPPLIER_BLOCKED",
                "message": "Supplier verification state blocks engagement drafting.",
            }
        )
    return reasons


def _structured_request(
    opportunity: ProductOpportunity,
    requested_quantity: int,
    destination_region: str,
    requested_fields: list[str],
) -> dict[str, object]:
    allowed = {
        "unit_price",
        "moq",
        "lead_time",
        "incoterm",
        "payment_terms",
        "packaging",
        "certifications",
        "validity_period",
    }
    fields = list(dict.fromkeys(item.strip().lower() for item in requested_fields if item.strip()))
    unknown_fields = [item for item in fields if item not in allowed]
    return {
        "product_identity": {
            "name": opportunity.name,
            "product_concept": opportunity.product_concept,
            "category": opportunity.category,
            "subcategory": opportunity.subcategory,
            "sku_or_model": None,
        },
        "requested_quantity": requested_quantity,
        "destination_region": destination_region or opportunity.target_region or None,
        "requested_fields": [item for item in fields if item in allowed]
        or ["unit_price", "moq", "lead_time", "incoterm", "payment_terms"],
        "unknown_requested_fields": unknown_fields,
        "assumptions": [],
        "supplier_terms": {
            "unit_price": None,
            "moq": None,
            "lead_time": None,
            "incoterm": None,
            "payment_terms": None,
        },
    }


def _message(
    opportunity: ProductOpportunity,
    supplier: Supplier,
    request: dict[str, Any],
    contact: SupplierContact,
) -> tuple[str, str]:
    subject = f"Request for quote: {opportunity.name}"
    requested = ", ".join(str(item) for item in request["requested_fields"])
    destination = request.get("destination_region") or "the target market"
    body = (
        f"Hello {contact.name},\n\n"
        f"I am evaluating {opportunity.name} for "
        f"{opportunity.target_marketplace or 'an online marketplace'} "
        f"in {destination}. Please share your current information for the requested quantity of "
        f"{request['requested_quantity']} units.\n\n"
        f"Please provide, if available: {requested}. Product identity: {opportunity.name}. "
        "Please treat this as an information request only; it is not an order "
        "or payment commitment."
    )
    return subject, body


def _draft_warnings(
    supplier: Supplier, contact: SupplierContact
) -> tuple[list[object], list[object], list[object]]:
    warnings: list[object] = []
    unknowns: list[object] = [
        {"field": "supplier_price", "reason": "No supplier quote has been received."},
        {"field": "supplier_moq", "reason": "MOQ is requested, not assumed."},
        {"field": "lead_time", "reason": "Lead time is requested, not assumed."},
    ]
    limitations: list[object] = [
        "External writes are disabled in PR-7A.",
        "Approval means approved for a future controlled send, not contacted or sent.",
    ]
    if supplier.verification_state not in {"verified", "high_confidence"}:
        warnings.append(
            {
                "code": "SUPPLIER_UNVERIFIED",
                "message": "Supplier verification is not live/verified.",
            }
        )
    if contact.verification_status != "verified":
        warnings.append(
            {
                "code": "CONTACT_UNVERIFIED",
                "message": "Contact provenance is retained but not verified.",
            }
        )
    if "deterministic" in contact.provenance.lower() or "fixture" in contact.provenance.lower():
        warnings.append(
            {
                "code": "DETERMINISTIC_TEST_CONTACT",
                "message": "Contact is deterministic test evidence.",
            }
        )
    return warnings, unknowns, limitations


def _approval_dict(row: SupplierEngagementApproval | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "state": row.state,
        "draft_id": str(row.draft_id),
        "supplier_id": str(row.supplier_id),
        "human_decision_id": str(row.human_decision_id) if row.human_decision_id else None,
        "actor_id": str(row.actor_id),
        "provenance": row.provenance,
        "context_fingerprint": row.context_fingerprint,
        "idempotency_key": row.idempotency_key,
        "supersedes_approval_id": (
            str(row.supersedes_approval_id) if row.supersedes_approval_id else None
        ),
        "reason": row.reason,
        "created_at": row.created_at.isoformat(),
        "external_writes": list(row.external_writes or []),
    }


def _draft_dict(row: SupplierEngagementDraft | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "engagement_id": str(row.engagement_id),
        "opportunity_id": str(row.opportunity_id),
        "supplier_id": str(row.supplier_id),
        "contact_id": str(row.contact_id) if row.contact_id else None,
        "human_decision_id": str(row.human_decision_id) if row.human_decision_id else None,
        "recommendation_id": str(row.recommendation_id) if row.recommendation_id else None,
        "synthesis_id": str(row.synthesis_id) if row.synthesis_id else None,
        "version": row.version,
        "status": row.status,
        "supplier": row.supplier_snapshot,
        "contact": row.contact_snapshot,
        "product": row.product_snapshot,
        "structured_request": row.structured_request,
        "subject": row.subject,
        "message_body": row.message_body,
        "template_version": row.template_version,
        "idempotency_key": row.idempotency_key,
        "warnings": row.warnings,
        "unknowns": row.unknowns,
        "limitations": row.limitations,
        "provenance": row.provenance,
        "input_fingerprint": row.input_fingerprint,
        "supersedes_draft_id": str(row.supersedes_draft_id) if row.supersedes_draft_id else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _latest_draft(
    db: Session, owner: User, engagement_id: uuid.UUID
) -> SupplierEngagementDraft | None:
    return db.scalars(
        select(SupplierEngagementDraft)
        .where(
            SupplierEngagementDraft.owner_id == owner.id,
            SupplierEngagementDraft.engagement_id == engagement_id,
        )
        .order_by(SupplierEngagementDraft.version.desc())
    ).first()


def _latest_approval(
    db: Session, owner: User, engagement_id: uuid.UUID
) -> SupplierEngagementApproval | None:
    return db.scalars(
        select(SupplierEngagementApproval)
        .where(
            SupplierEngagementApproval.owner_id == owner.id,
            SupplierEngagementApproval.engagement_id == engagement_id,
        )
        .order_by(SupplierEngagementApproval.created_at.desc())
    ).first()


def _effective_status(
    engagement: SupplierEngagement,
    draft: SupplierEngagementDraft | None,
    approval: SupplierEngagementApproval | None,
) -> str:
    if engagement.status == "CANCELLED" or (draft and draft.status == "CANCELLED"):
        return "CANCELLED"
    if (
        approval
        and approval.state == "APPROVED_FOR_SEND"
        and draft
        and draft.id == approval.draft_id
    ):
        return "APPROVED_FOR_SEND"
    if draft is not None:
        return draft.status
    return engagement.status


def serialize_engagement(
    db: Session, owner: User, engagement: SupplierEngagement
) -> dict[str, object]:
    # Import lazily to keep the PR-7A foundation usable on installations that
    # have not yet upgraded the PR-7B migration.
    try:
        from vayujit_api.intelligence.email_delivery_service import delivery_projection

        delivery = delivery_projection(db, owner, engagement.id)
    except Exception:
        # The legacy PR-7A projection remains readable while an older database
        # is being upgraded; no send is ever implied by this fallback.
        delivery = {
            "send_eligibility": None,
            "send_authorization": None,
            "send_command": None,
        }
    draft = _latest_draft(db, owner, engagement.id)
    approval = _latest_approval(db, owner, engagement.id)
    decision_current = True
    if engagement.human_decision_id is not None:
        try:
            current_decision = _decision_context(
                db,
                owner,
                engagement.opportunity_id,
                engagement.supplier_id,
                engagement.decision_target,
                engagement.human_decision_id,
            )
            decision_current = bool(
                current_decision is not None and current_decision.decision == "PROCEED"
            )
        except HTTPException:
            decision_current = False
    blocking_reasons = list(engagement.blocking_reasons or [])
    if not decision_current and not any(
        item.get("code") == "HUMAN_DECISION_SUPERSEDED"
        for item in blocking_reasons
        if isinstance(item, dict)
    ):
        blocking_reasons.append(
            {
                "code": "HUMAN_DECISION_SUPERSEDED",
                "message": (
                    "The prior HUMAN PROCEED is no longer current; fresh review is required."
                ),
            }
        )
    status = _effective_status(engagement, draft, approval)
    if not decision_current and status == "APPROVED_FOR_SEND":
        status = "NEEDS_REVIEW" if draft is not None else "BLOCKED"
    delivery_status = SEND_STATUS
    send_command = delivery.get("send_command")
    if isinstance(send_command, dict):
        delivery_status = str(cast(dict[str, object], send_command).get("status") or SEND_STATUS)
    return {
        "id": str(engagement.id),
        "owner_id": str(engagement.owner_id),
        "goal_id": str(engagement.goal_id) if engagement.goal_id else None,
        "opportunity_id": str(engagement.opportunity_id),
        "supplier_id": str(engagement.supplier_id),
        "contact_id": str(engagement.contact_id) if engagement.contact_id else None,
        "human_decision_id": (
            str(engagement.human_decision_id) if engagement.human_decision_id else None
        ),
        "recommendation_id": (
            str(engagement.recommendation_id) if engagement.recommendation_id else None
        ),
        "synthesis_id": str(engagement.synthesis_id) if engagement.synthesis_id else None,
        "decision_target": engagement.decision_target,
        "engagement_type": engagement.engagement_type,
        "engagement_version": engagement.engagement_version,
        "current_draft_version": engagement.current_draft_version,
        "status": status,
        "blocking_reasons": blocking_reasons,
        "idempotency_key": engagement.idempotency_key,
        "input_fingerprint": engagement.input_fingerprint,
        "external_writes": list(EXTERNAL_WRITES),
        "can_send": False,
        "send_status": delivery_status,
        "current_draft": _draft_dict(draft),
        "latest_approval": _approval_dict(approval),
        "safe_next_action": (
            "Review the draft and explicitly approve for a future send."
            if draft and not approval and decision_current
            else "Keep this engagement internal; no send is executed by PR-7A."
        ),
        **delivery,
        "created_at": engagement.created_at.isoformat(),
        "updated_at": engagement.updated_at.isoformat(),
    }


def _ensure_current_proceed(
    db: Session,
    owner: User,
    engagement: SupplierEngagement,
    *,
    decision_id: uuid.UUID | None = None,
) -> HumanDecision:
    decision = _decision_context(
        db,
        owner,
        engagement.opportunity_id,
        engagement.supplier_id,
        engagement.decision_target,
        decision_id,
    )
    if decision is None or decision.decision != "PROCEED":
        raise HTTPException(
            409,
            {
                "code": "ENGAGEMENT_BLOCKED",
                "message": "A current HUMAN PROCEED is required; engagement is blocked.",
            },
        )
    return decision


def create_engagement(db: Session, owner: User, data: EngagementCreate) -> dict[str, object]:
    existing = db.scalar(
        select(SupplierEngagement).where(
            SupplierEngagement.owner_id == owner.id,
            SupplierEngagement.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return serialize_engagement(db, owner, existing)
    if data.engagement_type not in ENGAGEMENT_INTENTS:
        raise HTTPException(422, "Unsupported engagement intent.")
    opportunity = _owned(
        db, ProductOpportunity, owner.id, data.opportunity_id, "Product opportunity not found."
    )
    supplier = _owned(db, Supplier, owner.id, data.supplier_id, "Supplier not found.")
    contact = _contact_for(db, owner, supplier.id, data.contact_id)
    decision = _decision_context(
        db, owner, opportunity.id, supplier.id, data.decision_target, data.human_decision_id
    )
    # Supplier engagement is only unlocked by a supplier-scoped current PROCEED.
    if decision is not None and decision.decision_target != data.decision_target:
        raise HTTPException(409, "Human decision target does not match the engagement target.")
    blocking = _blocking_reasons(decision, supplier, contact)
    fingerprint = _hash(
        {
            "opportunity_id": str(opportunity.id),
            "supplier_id": str(supplier.id),
            "contact_id": str(contact.id) if contact else None,
            "decision_id": str(decision.id) if decision else None,
            "intent": data.engagement_type,
            "quantity": data.requested_quantity,
            "destination": data.destination_region,
            "requested_fields": data.requested_fields,
        }
    )
    row = SupplierEngagement(
        owner_id=owner.id,
        goal_id=decision.goal_id if decision else None,
        opportunity_id=opportunity.id,
        supplier_id=supplier.id,
        contact_id=contact.id if contact else None,
        human_decision_id=decision.id if decision else None,
        recommendation_id=decision.recommendation_id if decision else None,
        synthesis_id=decision.synthesis_id if decision else None,
        decision_target=data.decision_target,
        engagement_type=data.engagement_type,
        engagement_version=1,
        current_draft_version=0,
        status="BLOCKED" if blocking else "NEEDS_REVIEW",
        blocking_reasons=blocking,
        idempotency_key=data.idempotency_key,
        input_fingerprint=fingerprint,
        external_writes=[],
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(SupplierEngagement).where(
                SupplierEngagement.owner_id == owner.id,
                SupplierEngagement.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return serialize_engagement(db, owner, existing)
    _event(db, owner, row, "engagement_created", payload={"blocking_reasons": blocking})
    if not blocking and contact is not None and decision is not None:
        _create_draft(
            db,
            owner,
            row,
            opportunity,
            supplier,
            contact,
            decision,
            requested_quantity=data.requested_quantity,
            destination_region=data.destination_region,
            requested_fields=data.requested_fields,
            idempotency_key=f"{data.idempotency_key}:draft",
            status="NEEDS_REVIEW",
            provenance="SYSTEM_DRAFT",
        )
    db.commit()
    db.refresh(row)
    return serialize_engagement(db, owner, row)


def _create_draft(
    db: Session,
    owner: User,
    engagement: SupplierEngagement,
    opportunity: ProductOpportunity,
    supplier: Supplier,
    contact: SupplierContact,
    decision: Any,
    *,
    requested_quantity: int,
    destination_region: str,
    requested_fields: list[str],
    idempotency_key: str,
    status: str,
    provenance: str,
    subject: str | None = None,
    message_body: str | None = None,
    supersedes: SupplierEngagementDraft | None = None,
) -> SupplierEngagementDraft:
    request = _structured_request(
        opportunity, requested_quantity, destination_region, requested_fields
    )
    generated_subject, generated_body = _message(opportunity, supplier, request, contact)
    warnings, unknowns, limitations = _draft_warnings(supplier, contact)
    final_subject = subject or generated_subject
    final_body = message_body or generated_body
    draft_fingerprint = _hash(
        {
            "engagement": str(engagement.id),
            "supplier": str(supplier.id),
            "contact": str(contact.id),
            "decision": str(decision.id),
            "request": request,
            "subject": final_subject,
            "body": final_body,
            "template": TEMPLATE_VERSION,
        }
    )
    prior = supersedes or _latest_draft(db, owner, engagement.id)
    version = (prior.version + 1) if prior else 1
    row = SupplierEngagementDraft(
        owner_id=owner.id,
        engagement_id=engagement.id,
        opportunity_id=opportunity.id,
        supplier_id=supplier.id,
        contact_id=contact.id,
        human_decision_id=decision.id,
        recommendation_id=decision.recommendation_id,
        synthesis_id=decision.synthesis_id,
        version=version,
        status=status,
        supplier_snapshot=_supplier_snapshot(supplier),
        contact_snapshot=_contact_snapshot(contact),
        product_snapshot=_product_snapshot(opportunity),
        structured_request=request,
        subject=final_subject,
        message_body=final_body,
        template_version=TEMPLATE_VERSION,
        warnings=warnings,
        unknowns=unknowns,
        limitations=limitations,
        provenance=provenance,
        idempotency_key=idempotency_key,
        input_fingerprint=draft_fingerprint,
        supersedes_draft_id=prior.id if prior else None,
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    db.flush()
    engagement.current_draft_version = version
    engagement.contact_id = contact.id
    engagement.status = status
    engagement.engagement_version += 1 if prior else 0
    engagement.updated_at = now()
    _event(
        db,
        owner,
        engagement,
        "engagement_draft_created" if prior is None else "engagement_draft_edited",
        draft_version=version,
        provenance=provenance,
        payload={"draft_id": str(row.id), "template_version": TEMPLATE_VERSION},
        actor_id=owner.id if provenance == "HUMAN" else None,
    )
    return row


def create_revision(
    db: Session, owner: User, engagement_id: uuid.UUID, data: DraftRevision
) -> dict[str, object]:
    engagement = _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    replay = db.scalar(
        select(SupplierEngagementDraft).where(
            SupplierEngagementDraft.owner_id == owner.id,
            SupplierEngagementDraft.engagement_id == engagement.id,
            SupplierEngagementDraft.idempotency_key == data.idempotency_key,
        )
    )
    if replay is not None:
        return serialize_engagement(db, owner, engagement)
    decision = _ensure_current_proceed(
        db, owner, engagement, decision_id=engagement.human_decision_id
    )
    supplier = _owned(db, Supplier, owner.id, engagement.supplier_id, "Supplier not found.")
    opportunity = _owned(
        db,
        ProductOpportunity,
        owner.id,
        engagement.opportunity_id,
        "Product opportunity not found.",
    )
    contact_id = data.contact_id or engagement.contact_id
    contact = _contact_for(db, owner, supplier.id, contact_id)
    if contact is None:
        raise HTTPException(409, "A canonical supplier contact is required before editing a draft.")
    prior = _latest_draft(db, owner, engagement.id)
    if prior is None:
        raise HTTPException(409, "Create an engagement draft before revising it.")
    _invalidate_latest_approval(
        db, owner, engagement, prior, "Material draft change requires fresh review."
    )
    _create_draft(
        db,
        owner,
        engagement,
        opportunity,
        supplier,
        contact,
        decision,
        requested_quantity=data.requested_quantity,
        destination_region=data.destination_region,
        requested_fields=data.requested_fields,
        idempotency_key=data.idempotency_key,
        status="NEEDS_REVIEW",
        provenance="HUMAN",
        subject=data.subject,
        message_body=data.message_body,
        supersedes=prior,
    )
    db.commit()
    return serialize_engagement(db, owner, engagement)


def _invalidate_latest_approval(
    db: Session,
    owner: User,
    engagement: SupplierEngagement,
    draft: SupplierEngagementDraft,
    reason: str,
) -> SupplierEngagementApproval | None:
    prior = _latest_approval(db, owner, engagement.id)
    if prior is None or prior.state != "APPROVED_FOR_SEND":
        return prior
    invalidation = SupplierEngagementApproval(
        owner_id=owner.id,
        engagement_id=engagement.id,
        draft_id=draft.id,
        supplier_id=engagement.supplier_id,
        human_decision_id=engagement.human_decision_id,
        state="INVALIDATED",
        actor_id=owner.id,
        provenance="SYSTEM",
        context_fingerprint=draft.input_fingerprint,
        idempotency_key=f"invalidate:{prior.id}:{draft.input_fingerprint}",
        supersedes_approval_id=prior.id,
        reason=reason,
        created_at=now(),
        external_writes=[],
    )
    db.add(invalidation)
    engagement.status = "NEEDS_REVIEW"
    _event(
        db,
        owner,
        engagement,
        "engagement_approval_invalidated",
        draft_version=draft.version,
        payload={"approval_id": str(prior.id), "reason": reason},
    )
    return invalidation


def approve_engagement(
    db: Session, owner: User, engagement_id: uuid.UUID, data: ApprovalRequest
) -> dict[str, object]:
    if data.provenance != "HUMAN":
        raise HTTPException(403, "Only an authenticated HUMAN may approve a future send.")
    engagement = _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    decision = _ensure_current_proceed(
        db, owner, engagement, decision_id=engagement.human_decision_id
    )
    draft = _latest_draft(db, owner, engagement.id)
    if draft is None or draft.status == "CANCELLED":
        raise HTTPException(409, "A reviewable draft is required before approval.")
    existing = db.scalar(
        select(SupplierEngagementApproval).where(
            SupplierEngagementApproval.owner_id == owner.id,
            SupplierEngagementApproval.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        if existing.engagement_id != engagement.id or existing.draft_id != draft.id:
            raise HTTPException(409, "Approval idempotency key is already bound to another draft.")
        return serialize_engagement(db, owner, engagement)
    approval = SupplierEngagementApproval(
        owner_id=owner.id,
        engagement_id=engagement.id,
        draft_id=draft.id,
        supplier_id=engagement.supplier_id,
        human_decision_id=decision.id,
        state="APPROVED_FOR_SEND",
        actor_id=owner.id,
        provenance="HUMAN",
        context_fingerprint=draft.input_fingerprint,
        idempotency_key=data.idempotency_key,
        supersedes_approval_id=None,
        reason=data.reason,
        created_at=now(),
        external_writes=[],
    )
    db.add(approval)
    draft.status = "NEEDS_REVIEW"
    engagement.status = "APPROVED_FOR_SEND"
    engagement.updated_at = now()
    _event(
        db,
        owner,
        engagement,
        "engagement_draft_approved",
        draft_version=draft.version,
        provenance="HUMAN",
        payload={"approval_id": str(approval.id), "state": "APPROVED_FOR_SEND"},
        actor_id=owner.id,
    )
    db.commit()
    return serialize_engagement(db, owner, engagement)


def cancel_engagement(
    db: Session, owner: User, engagement_id: uuid.UUID, data: CancelRequest
) -> dict[str, object]:
    if data.provenance != "HUMAN":
        raise HTTPException(403, "Only an authenticated HUMAN may cancel an engagement.")
    engagement = _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    existing_event = db.scalar(
        select(SupplierEngagementEvent).where(
            SupplierEngagementEvent.owner_id == owner.id,
            SupplierEngagementEvent.engagement_id == engagement.id,
            SupplierEngagementEvent.event_type == "engagement_cancelled",
            SupplierEngagementEvent.payload["idempotency_key"].as_string() == data.idempotency_key,
        )
    )
    if existing_event is not None:
        return serialize_engagement(db, owner, engagement)
    draft = _latest_draft(db, owner, engagement.id)
    if draft is not None:
        _invalidate_latest_approval(
            db, owner, engagement, draft, "Engagement was cancelled by the human reviewer."
        )
        draft.status = "CANCELLED"
    engagement.status = "CANCELLED"
    engagement.updated_at = now()
    _event(
        db,
        owner,
        engagement,
        "engagement_cancelled",
        draft_version=draft.version if draft else 0,
        provenance="HUMAN",
        payload={"reason": data.reason, "idempotency_key": data.idempotency_key},
        actor_id=owner.id,
    )
    db.commit()
    return serialize_engagement(db, owner, engagement)


def engagement_history(
    db: Session, owner: User, engagement_id: uuid.UUID
) -> list[dict[str, object]]:
    _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    rows = db.scalars(
        select(SupplierEngagementEvent)
        .where(
            SupplierEngagementEvent.owner_id == owner.id,
            SupplierEngagementEvent.engagement_id == engagement_id,
        )
        .order_by(SupplierEngagementEvent.created_at.asc())
    )
    return [
        {
            "id": str(row.id),
            "event_type": row.event_type,
            "draft_version": row.draft_version,
            "provenance": row.provenance,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "payload": row.payload,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def send_readiness(db: Session, owner: User, engagement_id: uuid.UUID) -> dict[str, object]:
    engagement = _owned(db, SupplierEngagement, owner.id, engagement_id, "Engagement not found.")
    detail = serialize_engagement(db, owner, engagement)
    return {
        "engagement_id": str(engagement.id),
        "status": detail["status"],
        "can_send": False,
        "send_status": SEND_STATUS,
        "provider_calls": 0,
        "external_writes": [],
        "reason": "PR-7A stops before the send boundary; no provider or outbox is invoked.",
        "blocking_reasons": detail["blocking_reasons"],
    }


def latest_engagement_for_opportunity(
    db: Session, owner: User, opportunity_id: uuid.UUID
) -> dict[str, object] | None:
    """Project the latest owner-scoped engagement without creating or mutating it."""
    row = db.scalar(
        select(SupplierEngagement)
        .where(
            SupplierEngagement.owner_id == owner.id,
            SupplierEngagement.opportunity_id == opportunity_id,
        )
        .order_by(SupplierEngagement.updated_at.desc(), SupplierEngagement.created_at.desc())
    )
    return serialize_engagement(db, owner, row) if row is not None else None
