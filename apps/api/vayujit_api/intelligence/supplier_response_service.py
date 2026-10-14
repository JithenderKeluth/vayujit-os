"""PR-7C deterministic supplier-response capture, review, and promotion."""

# Compact parser maps/regular expressions are intentionally kept readable.
# ruff: noqa: E501

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.identity.models import User
from vayujit_api.intelligence.commercial_readiness_schemas import CommercialReadinessCreate
from vayujit_api.intelligence.commercial_readiness_service import project_readiness
from vayujit_api.intelligence.email_delivery_models import (
    RfqSendAuthorization,
    RfqSendCommand,
)
from vayujit_api.intelligence.engagement_models import (
    SupplierEngagement,
    SupplierEngagementDraft,
    SupplierEngagementEvent,
)
from vayujit_api.intelligence.product_opportunity_models import ProductOpportunity
from vayujit_api.intelligence.supplier_models import (
    Supplier,
    SupplierCommercialTerm,
    SupplierEvidence,
    SupplierProduct,
    SupplierSource,
)
from vayujit_api.intelligence.supplier_response_models import (
    SupplierInboundResponse,
    SupplierResponseExtraction,
    SupplierResponsePromotion,
    SupplierResponseReview,
)
from vayujit_api.intelligence.supplier_response_schemas import (
    SupplierResponseCreate,
    SupplierResponseReviewRequest,
)

UNKNOWN = "UNKNOWN"
_CURRENCY_RE = re.compile(
    r"(?P<symbol>\u20b9|\$|\u20ac|\u00a3|INR|USD|EUR|GBP|CNY|RMB|AED|JPY)", re.I
)
_AMOUNT_RE = re.compile(r"(?P<amount>\d{1,12}(?:,\d{3})*(?:\.\d{1,4})?)")
_INCOTERM_RE = re.compile(r"\b(EXW|FOB|CIF|CFR|DAP|DDP|FCA|CPT|CIP)\b", re.I)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, Decimal, datetime)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _currency(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.upper()
    return {
        "₹": "INR",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "RMB": "CNY",
    }.get(normalized, normalized)


def _amount(value: str) -> float | None:
    try:
        return float(Decimal(value.replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def _unknown_fields(fields: dict[str, object]) -> list[str]:
    result: list[str] = []
    for key, value in fields.items():
        if value is None or value == UNKNOWN or value == [] or value == {}:
            result.append(key)
    return result


def _parse_fields(raw: str) -> tuple[dict[str, object], dict[str, str]]:
    """Parse only explicitly supported claims; no country/market inference."""

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    spans: dict[str, str] = {}
    fields: dict[str, object] = {
        "supplier_product_description": UNKNOWN,
        "supplier_sku_model": UNKNOWN,
        "unit_price": None,
        "currency": UNKNOWN,
        "price_basis": UNKNOWN,
        "moq": None,
        "moq_unit": UNKNOWN,
        "quantity_tiers": [],
        "lead_time": UNKNOWN,
        "lead_time_days": None,
        "lead_time_unit": UNKNOWN,
        "incoterm": UNKNOWN,
        "origin": UNKNOWN,
        "destination": UNKNOWN,
        "freight_inclusion": UNKNOWN,
        "tax_inclusion": UNKNOWN,
        "duty_inclusion": UNKNOWN,
        "insurance_inclusion": UNKNOWN,
        "packaging": UNKNOWN,
        "carton_quantity": None,
        "payment_terms": UNKNOWN,
        "quote_validity": UNKNOWN,
        "certification_claims": [],
        "production_capacity_claim": UNKNOWN,
        "notes": UNKNOWN,
    }

    for line in lines:
        match = re.search(r"(?:product(?: description)?|item)\s*[:=-]\s*(.+)", line, re.I)
        if match:
            fields["supplier_product_description"] = match.group(1).strip()
            spans["supplier_product_description"] = line
        match = re.search(r"(?:sku|model|mpn|product code)\s*[:#=-]\s*([\w./-]+)", line, re.I)
        if match:
            fields["supplier_sku_model"] = match.group(1)
            spans["supplier_sku_model"] = line

    price_line: str | None = None
    for line in lines:
        if re.search(r"(?:unit\s*)?price|rate|quote", line, re.I) and _AMOUNT_RE.search(line):
            price_line = line
            break
    if price_line is None:
        explicit_currency = _CURRENCY_RE.search(raw)
        if explicit_currency and _AMOUNT_RE.search(raw):
            price_line = explicit_currency.group(0) + " " + _AMOUNT_RE.search(raw).group(0)  # type: ignore[union-attr]
    if price_line:
        amount_match = _AMOUNT_RE.search(price_line)
        currency_match = _CURRENCY_RE.search(price_line)
        if amount_match:
            fields["unit_price"] = _amount(amount_match.group("amount"))
            spans["unit_price"] = price_line
        if currency_match:
            fields["currency"] = _currency(currency_match.group("symbol")) or UNKNOWN
            spans["currency"] = price_line
        basis = re.search(r"per\s+(unit|piece|pc|carton|order|kg|set)\b", price_line, re.I)
        if basis:
            fields["price_basis"] = {
                "piece": "PER_UNIT",
                "pc": "PER_UNIT",
                "unit": "PER_UNIT",
                "carton": "PER_CARTON",
                "order": "PER_ORDER",
                "kg": "PER_KG",
                "set": "PER_SET",
            }[basis.group(1).lower()]
            spans["price_basis"] = price_line

    tier_rows: list[dict[str, object]] = []
    for match in re.finditer(
        r"(?P<qty>\d{1,9})\s*(?P<unit>units?|pcs?|pieces?)\s*(?:=|at|for)\s*(?P<currency>₹|\$|€|£|INR|USD|EUR|GBP|CNY|RMB)?\s*(?P<amount>\d+(?:\.\d+)?)",
        raw,
        re.I,
    ):
        tier_rows.append(
            {
                "quantity": int(match.group("qty")),
                "unit": match.group("unit").lower(),
                "amount": _amount(match.group("amount")),
                "currency": _currency(match.group("currency")),
                "source_claim": match.group(0),
            }
        )
    if tier_rows:
        fields["quantity_tiers"] = tier_rows
        spans["quantity_tiers"] = "; ".join(str(item["source_claim"]) for item in tier_rows)

    moq_match = re.search(
        r"(?:MOQ|min(?:imum)?\s*order(?:\s*quantity)?)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)?",
        raw,
        re.I,
    )
    if moq_match:
        fields["moq"] = _amount(moq_match.group(1))
        fields["moq_unit"] = (moq_match.group(2) or "UNKNOWN").lower()
        spans["moq"] = moq_match.group(0)
        spans["moq_unit"] = moq_match.group(0)

    lead_match = re.search(
        r"(?:lead(?:\s*time)?|dispatch)\s*[:=-]?\s*(about\s+)?(\d+(?:-\d+)?)\s*(days?|weeks?|months?)",
        raw,
        re.I,
    )
    if lead_match:
        raw_lead = lead_match.group(0)
        fields["lead_time"] = raw_lead
        fields["lead_time_unit"] = lead_match.group(3).lower()
        if lead_match.group(3).lower().startswith("day") and "-" not in lead_match.group(2):
            fields["lead_time_days"] = int(lead_match.group(2))
        elif lead_match.group(3).lower().startswith("week") and "-" not in lead_match.group(2):
            fields["lead_time_days"] = int(lead_match.group(2)) * 7
        spans["lead_time"] = raw_lead

    incoterm = _INCOTERM_RE.search(raw)
    if incoterm:
        fields["incoterm"] = incoterm.group(1).upper()
        spans["incoterm"] = incoterm.group(0)
    for key, pattern in {
        "origin": r"origin\s*[:=-]\s*([^\n,;]+)",
        "destination": r"destination\s*[:=-]\s*([^\n,;]+)",
        "packaging": r"packaging\s*[:=-]\s*([^\n]+)",
        "freight_inclusion": r"(shipping|freight)\s+(included|excluded|not included)",
        "tax_inclusion": r"tax(?:es)?\s+(included|excluded|not included)",
        "duty_inclusion": r"duty\s+(included|excluded|not included)",
        "insurance_inclusion": r"insurance\s+(included|excluded|not included)",
        "payment_terms": r"payment(?:\s+terms?)?\s*[:=-]\s*([^\n]+)",
        "quote_validity": r"(?:quote|quotation)\s+valid(?:ity)?\s*[:=-]?\s*([^\n]+)",
        "production_capacity_claim": r"capacity\s*[:=-]\s*([^\n]+)",
    }.items():
        match = re.search(pattern, raw, re.I)
        if match:
            value = match.group(match.lastindex or 1).strip()
            fields[key] = value.upper() if key.endswith("_inclusion") else value
            spans[key] = match.group(0)

    carton_match = re.search(r"(?:carton|case)\s*(?:quantity|pack)?\s*[:=-]?\s*(\d+)", raw, re.I)
    if carton_match:
        fields["carton_quantity"] = int(carton_match.group(1))
        spans["carton_quantity"] = carton_match.group(0)
    certifications = re.findall(
        r"(?:ISO\s*\d{3,6}|CE|BIS|GOTS|FSC)\s*(?:certified|certificate)?", raw, re.I
    )
    if certifications:
        fields["certification_claims"] = list(
            dict.fromkeys(item.strip() for item in certifications)
        )
        spans["certification_claims"] = "; ".join(certifications)

    if fields["supplier_product_description"] == UNKNOWN and lines:
        first = lines[0]
        if not re.match(r"(?:price|MOQ|lead|quote|hello|hi|dear)\b", first, re.I):
            fields["notes"] = first
    return fields, spans


def _classify(raw: str) -> str:
    lower = raw.lower()
    if any(
        term in lower for term in ("cannot supply", "unable to quote", "decline", "not available")
    ):
        return "DECLINED"
    if any(
        term in lower
        for term in ("please clarify", "need more information", "what quantity", "which model")
    ):
        return "REQUEST_FOR_CLARIFICATION"
    quote_cue = bool(
        re.search(r"\b(?:quote|quotation|unit\s*price|moq|lead\s*time|incoterm)\b", lower)
    )
    explicit_money = bool(_CURRENCY_RE.search(raw) and _AMOUNT_RE.search(raw))
    if quote_cue and (explicit_money or re.search(r"\bmoq\b|lead\s*time", lower)):
        return "QUOTE"
    if re.fullmatch(r"[\s\d.,\u20b9$\u20ac\u00a3:+-]+", raw):
        return "UNKNOWN"
    if raw.strip():
        return "GENERAL_RESPONSE"
    return "UNKNOWN"


def _correlation(
    db: Session, owner: User, data: SupplierResponseCreate
) -> tuple[dict[str, uuid.UUID | None], str, str, dict[str, object]]:
    supplier_id = data.supplier_id
    opportunity_id = data.opportunity_id
    engagement_id = data.engagement_id
    draft_id = data.draft_id
    metadata: dict[str, object] = {}

    def scoped(model: Any, value: uuid.UUID | None, label: str) -> Any | None:
        if value is None:
            return None
        row = db.scalar(select(model).where(model.id == value, model.owner_id == owner.id))
        if row is None:
            raise HTTPException(404, f"{label} is not available in the owner scope.")
        return row

    scoped(Supplier, supplier_id, "Supplier")
    scoped(ProductOpportunity, opportunity_id, "Product opportunity")
    command = None
    expected_supplier: uuid.UUID | None = None
    expected_opportunity: uuid.UUID | None = None
    expected_engagement: uuid.UUID | None = None
    expected_draft: uuid.UUID | None = None
    if data.send_command_id is not None:
        command = db.scalar(
            select(RfqSendCommand).where(
                RfqSendCommand.id == data.send_command_id,
                RfqSendCommand.owner_id == owner.id,
            )
        )
        if command is None:
            raise HTTPException(404, "RFQ send command is not available in the owner scope.")
        authorization = db.scalar(
            select(RfqSendAuthorization).where(
                RfqSendAuthorization.id == command.authorization_id,
                RfqSendAuthorization.owner_id == owner.id,
            )
        )
        if authorization is None:
            raise HTTPException(404, "RFQ authorization is not available in the owner scope.")
        expected_supplier = authorization.supplier_id
        expected_opportunity = authorization.opportunity_id
        expected_engagement = command.engagement_id
        expected_draft = command.draft_id
        metadata.update(
            {
                "expected_supplier_id": str(expected_supplier),
                "expected_opportunity_id": str(expected_opportunity),
                "expected_engagement_id": str(expected_engagement),
                "expected_draft_id": str(expected_draft),
                "strong_reference": "send_command",
            }
        )
    elif data.engagement_id is not None:
        engagement = db.scalar(
            select(SupplierEngagement).where(
                SupplierEngagement.id == data.engagement_id,
                SupplierEngagement.owner_id == owner.id,
            )
        )
        if engagement is None:
            raise HTTPException(404, "Supplier engagement is not available in the owner scope.")
        expected_supplier = engagement.supplier_id
        expected_opportunity = engagement.opportunity_id
        expected_engagement = engagement.id
        current_draft = None
        if engagement.current_draft_version:
            current_draft = db.scalar(
                select(SupplierEngagementDraft).where(
                    SupplierEngagementDraft.engagement_id == engagement.id,
                    SupplierEngagementDraft.owner_id == owner.id,
                    SupplierEngagementDraft.version == engagement.current_draft_version,
                )
            )
        expected_draft = current_draft.id if current_draft is not None else None
        metadata.update(
            {
                "expected_supplier_id": str(expected_supplier),
                "expected_opportunity_id": str(expected_opportunity),
                "strong_reference": "engagement",
            }
        )

    if expected_supplier is not None:
        supplier_id = supplier_id or expected_supplier
        opportunity_id = opportunity_id or expected_opportunity
        engagement_id = engagement_id or expected_engagement
        draft_id = draft_id or expected_draft
        mismatches = []
        if data.supplier_id is not None and data.supplier_id != expected_supplier:
            mismatches.append("supplier")
        if data.opportunity_id is not None and data.opportunity_id != expected_opportunity:
            mismatches.append("opportunity")
        if data.engagement_id is not None and data.engagement_id != expected_engagement:
            mismatches.append("engagement")
        if data.draft_id is not None and data.draft_id != expected_draft:
            mismatches.append("draft")
        if mismatches:
            metadata["mismatched_scopes"] = mismatches
            return (
                {
                    "supplier_id": supplier_id,
                    "opportunity_id": opportunity_id,
                    "engagement_id": engagement_id,
                    "draft_id": draft_id,
                },
                "UNMATCHED",
                "Inbound response scope does not match the referenced RFQ authority.",
                metadata,
            )
        return (
            {
                "supplier_id": supplier_id,
                "opportunity_id": opportunity_id,
                "engagement_id": engagement_id,
                "draft_id": draft_id,
            },
            "CORRELATED",
            "Strong RFQ/engagement reference matched the owner-scoped supplier and opportunity.",
            metadata,
        )

    if supplier_id is not None or opportunity_id is not None:
        return (
            {
                "supplier_id": supplier_id,
                "opportunity_id": opportunity_id,
                "engagement_id": engagement_id,
                "draft_id": draft_id,
            },
            "AMBIGUOUS",
            "Supplier or product was supplied without a strong RFQ/engagement reference.",
            metadata,
        )
    return (
        {"supplier_id": None, "opportunity_id": None, "engagement_id": None, "draft_id": None},
        "UNMATCHED",
        "No owner-scoped supplier/RFQ correlation reference was supplied.",
        metadata,
    )


def _field_provenance(
    fields: dict[str, object], spans: dict[str, str], response_id: uuid.UUID
) -> dict[str, object]:
    return {
        key: {
            "provenance": (
                "SOURCE_PROVIDED_CLAIM" if value not in (None, UNKNOWN, [], {}) else UNKNOWN
            ),
            "response_id": str(response_id),
            "source_span": spans.get(key),
            "trust": "SUPPLIER_CLAIM" if value not in (None, UNKNOWN, [], {}) else UNKNOWN,
        }
        for key, value in fields.items()
    }


def _serialize_extraction(row: SupplierResponseExtraction) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "response_id": str(row.response_id),
        "version": row.version,
        "status": row.status,
        "extracted_fields": _json(row.extracted_fields),
        "field_provenance": _json(row.field_provenance),
        "source_spans": _json(row.source_spans),
        "unknown_fields": _json(row.unknown_fields),
        "warnings": _json(row.warnings),
        "extraction_authority": row.extraction_authority,
        "source_raw_hash": row.source_raw_hash,
        "created_at": row.created_at,
    }


def _serialize_review(row: SupplierResponseReview) -> dict[str, object]:
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "response_id": str(row.response_id),
        "extraction_id": str(row.extraction_id),
        "actor_id": str(row.actor_id),
        "decision": row.decision,
        "provenance": row.provenance,
        "corrections": _json(row.corrections),
        "reason": row.reason,
        "created_at": row.created_at,
        "idempotency_key": row.idempotency_key,
    }


def serialize_response(db: Session, owner: User, row: SupplierInboundResponse) -> dict[str, object]:
    extraction = db.scalar(
        select(SupplierResponseExtraction)
        .where(
            SupplierResponseExtraction.owner_id == owner.id,
            SupplierResponseExtraction.response_id == row.id,
        )
        .order_by(SupplierResponseExtraction.version.desc())
    )
    reviews = list(
        db.scalars(
            select(SupplierResponseReview)
            .where(
                SupplierResponseReview.owner_id == owner.id,
                SupplierResponseReview.response_id == row.id,
            )
            .order_by(SupplierResponseReview.created_at)
        )
    )
    promotion = db.scalar(
        select(SupplierResponsePromotion).where(
            SupplierResponsePromotion.owner_id == owner.id,
            SupplierResponsePromotion.response_id == row.id,
        )
    )
    return {
        "id": str(row.id),
        "owner_id": str(row.owner_id),
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "opportunity_id": str(row.opportunity_id) if row.opportunity_id else None,
        "engagement_id": str(row.engagement_id) if row.engagement_id else None,
        "draft_id": str(row.draft_id) if row.draft_id else None,
        "send_command_id": str(row.send_command_id) if row.send_command_id else None,
        "channel": row.channel,
        "sender_identity": row.sender_identity,
        "recipient_identity": row.recipient_identity,
        "provider_message_id": row.provider_message_id,
        "provider_thread_id": row.provider_thread_id,
        "received_at": row.received_at,
        "raw_content": row.raw_content,
        "raw_content_hash": row.raw_content_hash,
        "attachment_refs": row.attachment_refs,
        "trust_environment": row.trust_environment,
        "evidence_environment": row.evidence_environment,
        "correlation_state": row.correlation_state,
        "correlation_reason": row.correlation_reason,
        "correlation_metadata": row.correlation_metadata,
        "classification": row.classification,
        "response_fingerprint": row.response_fingerprint,
        "created_at": row.created_at,
        "idempotency_key": row.idempotency_key,
        "extraction": _serialize_extraction(extraction) if extraction else None,
        "reviews": [_serialize_review(item) for item in reviews],
        "promotion": (
            {
                "id": str(promotion.id),
                "status": promotion.status,
                "provenance": promotion.provenance,
                "supplier_evidence_id": (
                    str(promotion.supplier_evidence_id) if promotion.supplier_evidence_id else None
                ),
                "supplier_product_id": (
                    str(promotion.supplier_product_id) if promotion.supplier_product_id else None
                ),
                "commercial_term_id": (
                    str(promotion.commercial_term_id) if promotion.commercial_term_id else None
                ),
                "readiness_snapshot_id": (
                    str(promotion.readiness_snapshot_id)
                    if promotion.readiness_snapshot_id
                    else None
                ),
                "contradictions": _json(promotion.contradictions),
                **_json(promotion.lineage),
                "created_at": promotion.created_at,
            }
            if promotion
            else None
        ),
        "safe_next_action": (
            "Inspect the raw response and extraction before HUMAN review."
            if extraction is None
            else (
                "Promote accepted claims through PR-5A readiness."
                if promotion is None
                and reviews
                and reviews[-1].decision in {"ACCEPT_EXTRACTION", "CORRECT_EXTRACTION"}
                else "No automatic commercial or supplier action is permitted."
            )
        ),
    }


def create_response(
    db: Session, owner: User, data: SupplierResponseCreate
) -> tuple[dict[str, object], bool]:
    received_at = data.received_at or _now()
    raw_hash = _hash(data.raw_content)
    fingerprint_payload = "|".join(
        [
            str(data.provider_message_id or ""),
            str(data.provider_thread_id or ""),
            str(data.send_command_id or ""),
            str(data.engagement_id or ""),
            data.channel,
            data.sender_identity or "",
            raw_hash,
        ]
    )
    fingerprint = _hash(fingerprint_payload)
    if data.idempotency_key:
        existing = db.scalar(
            select(SupplierInboundResponse).where(
                SupplierInboundResponse.owner_id == owner.id,
                SupplierInboundResponse.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            if existing.raw_content_hash != raw_hash:
                raise HTTPException(
                    409, "Idempotency key is already bound to different raw evidence."
                )
            return serialize_response(db, owner, existing), True
    existing = db.scalar(
        select(SupplierInboundResponse).where(
            SupplierInboundResponse.owner_id == owner.id,
            SupplierInboundResponse.response_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return serialize_response(db, owner, existing), True

    scopes, correlation_state, correlation_reason, correlation_metadata = _correlation(
        db, owner, data
    )
    classification = _classify(data.raw_content)
    row = SupplierInboundResponse(
        owner_id=owner.id,
        **scopes,
        send_command_id=data.send_command_id,
        channel=data.channel,
        sender_identity=data.sender_identity,
        recipient_identity=data.recipient_identity,
        provider_message_id=data.provider_message_id,
        provider_thread_id=data.provider_thread_id,
        received_at=received_at,
        raw_content=data.raw_content,
        raw_content_hash=raw_hash,
        attachment_refs=data.attachment_refs,
        trust_environment=data.trust_environment,
        evidence_environment=data.evidence_environment,
        correlation_state=correlation_state,
        correlation_reason=correlation_reason,
        correlation_metadata=correlation_metadata,
        classification=classification,
        response_fingerprint=fingerprint,
        created_at=_now(),
        idempotency_key=data.idempotency_key or f"pr7c-response:{fingerprint}",
    )
    db.add(row)
    db.flush()
    fields, spans = _parse_fields(data.raw_content)
    populated = len([item for item in fields.values() if item not in (None, UNKNOWN, [], {})])
    extraction_status = (
        "EXTRACTED"
        if classification == "QUOTE" and populated >= 2
        else "PARTIAL" if classification == "QUOTE" else "NEEDS_REVIEW"
    )
    extraction = SupplierResponseExtraction(
        owner_id=owner.id,
        response_id=row.id,
        version=1,
        status=extraction_status,
        extracted_fields=fields,
        field_provenance=_field_provenance(fields, spans, row.id),
        source_spans=spans,
        unknown_fields=_unknown_fields(fields),
        warnings=(
            ["Currency was not explicitly supplied; no currency was inferred."]
            if fields.get("unit_price") is not None and fields.get("currency") == UNKNOWN
            else []
        ),
        extraction_authority="DETERMINISTIC_PARSER",
        source_raw_hash=raw_hash,
        created_at=_now(),
    )
    db.add(extraction)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.supplier_response_recorded",
        entity_type="supplier_inbound_response",
        entity_id=row.id,
        metadata={
            "correlation_state": correlation_state,
            "classification": classification,
            "evidence_environment": data.evidence_environment,
        },
        idempotency_key=f"pr7c:response:{fingerprint}",
    )
    db.commit()
    db.refresh(row)
    return serialize_response(db, owner, row), False


def get_response(db: Session, owner: User, response_id: uuid.UUID) -> dict[str, object]:
    row = db.scalar(
        select(SupplierInboundResponse).where(
            SupplierInboundResponse.id == response_id,
            SupplierInboundResponse.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Supplier response not found.")
    return serialize_response(db, owner, row)


def list_responses(
    db: Session, owner: User, *, opportunity_id: uuid.UUID | None = None
) -> dict[str, object]:
    query = select(SupplierInboundResponse).where(SupplierInboundResponse.owner_id == owner.id)
    if opportunity_id is not None:
        query = query.where(SupplierInboundResponse.opportunity_id == opportunity_id)
    rows = list(db.scalars(query.order_by(SupplierInboundResponse.created_at.desc())))
    return {"responses": [serialize_response(db, owner, row) for row in rows], "total": len(rows)}


def review_response(
    db: Session, owner: User, response_id: uuid.UUID, data: SupplierResponseReviewRequest
) -> dict[str, object]:
    if data.provenance != "HUMAN":
        raise HTTPException(403, "Only HUMAN provenance may review supplier response evidence.")
    existing = db.scalar(
        select(SupplierResponseReview).where(
            SupplierResponseReview.owner_id == owner.id,
            SupplierResponseReview.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return get_response(db, owner, existing.response_id)
    response = db.scalar(
        select(SupplierInboundResponse).where(
            SupplierInboundResponse.id == response_id,
            SupplierInboundResponse.owner_id == owner.id,
        )
    )
    if response is None:
        raise HTTPException(404, "Supplier response not found.")
    extraction = db.scalar(
        select(SupplierResponseExtraction)
        .where(
            SupplierResponseExtraction.owner_id == owner.id,
            SupplierResponseExtraction.response_id == response.id,
            *([SupplierResponseExtraction.id == data.extraction_id] if data.extraction_id else []),
        )
        .order_by(SupplierResponseExtraction.version.desc())
    )
    if extraction is None:
        raise HTTPException(404, "Supplier response extraction not found.")
    invalid = set(data.corrections) - set(extraction.extracted_fields)
    if invalid:
        raise HTTPException(422, f"Unsupported correction fields: {sorted(invalid)}")
    if data.decision != "CORRECT_EXTRACTION" and data.corrections:
        raise HTTPException(422, "Corrections require CORRECT_EXTRACTION.")
    row = SupplierResponseReview(
        owner_id=owner.id,
        response_id=response.id,
        extraction_id=extraction.id,
        actor_id=owner.id,
        decision=data.decision,
        provenance="HUMAN",
        corrections=_json(data.corrections),
        reason=data.reason,
        created_at=_now(),
        idempotency_key=data.idempotency_key,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=owner.id,
        action="intelligence.supplier_response_reviewed",
        entity_type="supplier_response_review",
        entity_id=row.id,
        metadata={
            "response_id": str(response.id),
            "decision": row.decision,
            "provenance": row.provenance,
        },
        idempotency_key=f"pr7c:review:{row.id}",
    )
    db.commit()
    return get_response(db, owner, response.id)


def _promoted_value(fields: dict[str, object], corrections: dict[str, object], key: str) -> object:
    return corrections[key] if key in corrections else fields.get(key, UNKNOWN)


def promote_response(db: Session, owner: User, response_id: uuid.UUID) -> dict[str, object]:
    response = db.scalar(
        select(SupplierInboundResponse).where(
            SupplierInboundResponse.id == response_id,
            SupplierInboundResponse.owner_id == owner.id,
        )
    )
    if response is None:
        raise HTTPException(404, "Supplier response not found.")
    latest_review = db.scalar(
        select(SupplierResponseReview)
        .where(
            SupplierResponseReview.owner_id == owner.id,
            SupplierResponseReview.response_id == response.id,
        )
        .order_by(SupplierResponseReview.created_at.desc())
    )
    if latest_review is None or latest_review.provenance != "HUMAN":
        raise HTTPException(409, "Explicit HUMAN extraction review is required before promotion.")
    existing = db.scalar(
        select(SupplierResponsePromotion).where(
            SupplierResponsePromotion.owner_id == owner.id,
            SupplierResponsePromotion.review_id == latest_review.id,
        )
    )
    if existing is not None:
        return get_response(db, owner, response.id)
    if latest_review.decision in {"REJECT_EXTRACTION", "KEEP_UNDER_REVIEW"}:
        raise HTTPException(409, "This response review does not permit commercial promotion.")
    if response.classification != "QUOTE":
        raise HTTPException(
            409,
            "Only an explicitly classified supplier quote can promote commercial claims.",
        )
    if (
        response.correlation_state != "CORRELATED"
        or response.supplier_id is None
        or response.opportunity_id is None
    ):
        raise HTTPException(
            409, "Only a strongly correlated response can promote commercial claims."
        )
    extraction = db.get(SupplierResponseExtraction, latest_review.extraction_id)
    if (
        extraction is None
        or extraction.owner_id != owner.id
        or extraction.response_id != response.id
    ):
        raise HTTPException(409, "The reviewed extraction is no longer available.")
    supplier = db.scalar(
        select(Supplier).where(Supplier.id == response.supplier_id, Supplier.owner_id == owner.id)
    )
    opportunity = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == response.opportunity_id,
            ProductOpportunity.owner_id == owner.id,
        )
    )
    if supplier is None or opportunity is None:
        raise HTTPException(404, "Response commercial context is unavailable in the owner scope.")

    fields = dict(extraction.extracted_fields or {})
    corrections = dict(latest_review.corrections or {})
    accepted = {key: _promoted_value(fields, corrections, key) for key in fields}
    source_external_id = f"pr7c-response:{response.id}"
    source = db.scalar(
        select(SupplierSource).where(
            SupplierSource.supplier_id == supplier.id,
            SupplierSource.source_type == "internal_supplier_record",
            SupplierSource.external_id == source_external_id,
        )
    )
    if source is None:
        source = SupplierSource(
            owner_id=owner.id,
            supplier_id=supplier.id,
            source_type="internal_supplier_record",
            access_mode="manual_entry",
            external_id=source_external_id,
            reference=f"PR-7C inbound response {response.id}",
            source_url=None,
            status=response.evidence_environment,
            metadata_json={"response_id": str(response.id), "channel": response.channel},
            observed_at=response.received_at,
            created_at=_now(),
        )
        db.add(source)
        db.flush()

    evidence_key = f"pr7c:evidence:{response.id}:{latest_review.id}"
    evidence = db.scalar(
        select(SupplierEvidence).where(
            SupplierEvidence.owner_id == owner.id,
            SupplierEvidence.idempotency_key == evidence_key,
        )
    )
    if evidence is None:
        evidence = SupplierEvidence(
            owner_id=owner.id,
            supplier_id=supplier.id,
            source_id=source.id,
            evidence_kind="self_reported",
            reference=f"PR-7C response {response.id} / review {latest_review.id}",
            source_url=None,
            normalized_value={
                "response_id": str(response.id),
                "engagement_id": str(response.engagement_id) if response.engagement_id else None,
                "send_command_id": (
                    str(response.send_command_id) if response.send_command_id else None
                ),
                "extraction_id": str(extraction.id),
                "review_id": str(latest_review.id),
                "fields": _json(accepted),
                "field_provenance": extraction.field_provenance,
                "claim_semantics": "SOURCE_PROVIDED_CLAIM",
                "trust_environment": response.trust_environment,
                "evidence_environment": response.evidence_environment,
            },
            excerpt=response.raw_content[:4000],
            content_hash=response.raw_content_hash,
            observed_at=response.received_at,
            retrieved_at=_now(),
            freshness_status="fresh",
            verification_status="unverified",
            archived=False,
            updated_at=_now(),
            idempotency_key=evidence_key,
        )
        db.add(evidence)
        db.flush()

    previous_promotion = db.scalar(
        select(SupplierResponsePromotion)
        .join(
            SupplierInboundResponse,
            SupplierResponsePromotion.response_id == SupplierInboundResponse.id,
        )
        .where(
            SupplierResponsePromotion.owner_id == owner.id,
            SupplierInboundResponse.owner_id == owner.id,
            SupplierInboundResponse.supplier_id == supplier.id,
            SupplierInboundResponse.opportunity_id == opportunity.id,
            SupplierInboundResponse.engagement_id == response.engagement_id,
            SupplierResponsePromotion.supplier_product_id.is_not(None),
        )
        .order_by(SupplierResponsePromotion.created_at)
    )
    product = (
        db.get(SupplierProduct, previous_promotion.supplier_product_id)
        if previous_promotion
        else None
    )
    if product is None:
        product = SupplierProduct(
            owner_id=owner.id,
            supplier_id=supplier.id,
            source_id=source.id,
            source_reference=source_external_id,
            title=str(accepted.get("supplier_product_description") or opportunity.name),
            category=opportunity.category or UNKNOWN,
            specifications={
                "sku_model": accepted.get("supplier_sku_model"),
                "price_basis": accepted.get("price_basis"),
                "quantity_tiers": accepted.get("quantity_tiers"),
                "origin": accepted.get("origin"),
                "destination": accepted.get("destination"),
                "freight_inclusion": accepted.get("freight_inclusion"),
                "tax_inclusion": accepted.get("tax_inclusion"),
                "duty_inclusion": accepted.get("duty_inclusion"),
                "insurance_inclusion": accepted.get("insurance_inclusion"),
                "certification_claims": accepted.get("certification_claims"),
                "production_capacity_claim": accepted.get("production_capacity_claim"),
                "response_id": str(response.id),
            },
            observed_price=(
                accepted.get("unit_price")
                if isinstance(accepted.get("unit_price"), (int, float))
                else None
            ),
            currency=(
                accepted.get("currency")
                if accepted.get("currency") not in (None, UNKNOWN)
                else None
            ),
            price_kind="observed_quote",
            moq=accepted.get("moq") if isinstance(accepted.get("moq"), (int, float)) else None,
            moq_unit=(
                accepted.get("moq_unit")
                if accepted.get("moq_unit") not in (None, UNKNOWN)
                else None
            ),
            sample_available=None,
            sample_moq=None,
            sample_lead_days=None,
            production_lead_days=(
                accepted.get("lead_time_days")
                if isinstance(accepted.get("lead_time_days"), int)
                else None
            ),
            dispatch_lead_days=None,
            shipping_lead_days=None,
            private_label=False,
            customization=False,
            packaging=(
                accepted.get("packaging")
                if accepted.get("packaging") not in (None, UNKNOWN)
                else None
            ),
            evidence_ids=[str(evidence.id)],
            observed_at=response.received_at,
            freshness_status="fresh",
            created_at=_now(),
        )
        db.add(product)
        db.flush()
    elif str(evidence.id) not in [str(item) for item in (product.evidence_ids or [])]:
        product.evidence_ids = [*(product.evidence_ids or []), str(evidence.id)]

    old_terms = list(
        db.scalars(
            select(SupplierCommercialTerm)
            .where(SupplierCommercialTerm.supplier_product_id == product.id)
            .order_by(SupplierCommercialTerm.version.desc())
        )
    )
    version = (old_terms[0].version + 1) if old_terms else 1
    for old in old_terms:
        old.is_current = False
    term = SupplierCommercialTerm(
        owner_id=owner.id,
        supplier_id=supplier.id,
        supplier_product_id=product.id,
        version=version,
        unit_price=(
            accepted.get("unit_price")
            if isinstance(accepted.get("unit_price"), (int, float))
            else None
        ),
        currency=(
            accepted.get("currency") if accepted.get("currency") not in (None, UNKNOWN) else None
        ),
        price_tiers=(
            accepted.get("quantity_tiers")
            if isinstance(accepted.get("quantity_tiers"), list)
            else []
        ),
        moq=accepted.get("moq") if isinstance(accepted.get("moq"), (int, float)) else None,
        sample_price=None,
        tooling_fee=None,
        packaging_fee=None,
        branding_fee=None,
        payment_terms=(
            accepted.get("payment_terms")
            if accepted.get("payment_terms") not in (None, UNKNOWN)
            else None
        ),
        deposit_percent=None,
        balance_percent=None,
        incoterm=(
            accepted.get("incoterm") if accepted.get("incoterm") not in (None, UNKNOWN) else None
        ),
        valid_until=None,
        lead_time_days=(
            accepted.get("lead_time_days")
            if isinstance(accepted.get("lead_time_days"), int)
            else None
        ),
        sample_lead_days=None,
        production_lead_days=(
            accepted.get("lead_time_days")
            if isinstance(accepted.get("lead_time_days"), int)
            else None
        ),
        dispatch_lead_days=None,
        is_current=True,
        source_evidence_ids=[str(evidence.id)],
        observed_at=response.received_at,
        created_at=_now(),
    )
    db.add(term)
    db.flush()

    contradictions: list[dict[str, object]] = []
    for old in old_terms:
        for field in ("unit_price", "currency", "moq", "lead_time_days", "incoterm"):
            old_value = getattr(old, field)
            new_value = getattr(term, field)
            if old_value is not None and new_value is not None and str(old_value) != str(new_value):
                contradictions.append(
                    {
                        "field": field,
                        "previous": str(old_value),
                        "new": str(new_value),
                        "state": "UNRESOLVED",
                        "source": "PR-7C_RESPONSE",
                    }
                )

    promotion = SupplierResponsePromotion(
        owner_id=owner.id,
        response_id=response.id,
        extraction_id=extraction.id,
        review_id=latest_review.id,
        supplier_evidence_id=evidence.id,
        supplier_product_id=product.id,
        commercial_term_id=term.id,
        status="PROMOTED",
        provenance="SOURCE_PROVIDED_CLAIM",
        contradictions=contradictions,
        lineage={
            "supplier_id": str(supplier.id),
            "opportunity_id": str(opportunity.id),
            "engagement_id": str(response.engagement_id) if response.engagement_id else None,
            "send_command_id": str(response.send_command_id) if response.send_command_id else None,
            "response_id": str(response.id),
            "raw_content_hash": response.raw_content_hash,
            "extraction_id": str(extraction.id),
            "review_id": str(latest_review.id),
            "claim_semantics": "SOURCE_PROVIDED_CLAIM",
            "supplier_verification_unchanged": supplier.verification_state,
        },
        created_at=_now(),
    )
    db.add(promotion)
    if response.engagement_id:
        db.add(
            SupplierEngagementEvent(
                owner_id=owner.id,
                engagement_id=response.engagement_id,
                supplier_id=supplier.id,
                actor_id=owner.id,
                event_type="SUPPLIER_RESPONSE_RECORDED",
                draft_version=0,
                provenance="HUMAN_REVIEWED_EVIDENCE",
                payload={
                    "response_id": str(response.id),
                    "classification": response.classification,
                },
                created_at=_now(),
            )
        )
    db.flush()
    assessment_id = opportunity.current_assessment_id
    if assessment_id is not None:
        try:
            readiness, _ = project_readiness(
                db,
                owner,
                opportunity.id,
                assessment_id,
                CommercialReadinessCreate(
                    idempotency_key=f"pr7c-readiness:{response.id}:{latest_review.id}",
                    supplier_id=supplier.id,
                    scenario_key="source-evidence",
                ),
            )
            promotion.readiness_snapshot_id = readiness.id
        except HTTPException:
            # Promotion remains durable even when an assessment context is not yet
            # complete.  The safe next action is to project readiness later.
            pass
    db.commit()
    return get_response(db, owner, response.id)
