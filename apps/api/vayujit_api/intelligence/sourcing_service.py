"""Deterministic, local-only sourcing workflow services."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.intelligence.models import IntelligenceOpportunity
from vayujit_api.intelligence.sourcing_models import (
    CostScenario,
    Inspection,
    LandedCostEstimate,
    RequestForQuote,
    RFQDraft,
    RFQSupplier,
    RFQVersion,
    Sample,
    SampleEvaluation,
    SampleRequest,
    SourcingApproval,
    SourcingAssumptionVersion,
    SourcingDecision,
    SourcingRecoveryRecord,
    SourcingRequirement,
    SourcingRequirementVersion,
    SourcingWorkerJob,
    SupplierQuote,
    SupplierQuoteLine,
    SupplierQuoteVersion,
)
from vayujit_api.intelligence.supplier_models import Supplier
from vayujit_api.products.models import Product


def now() -> datetime:
    return datetime.now(UTC)


def dump(row: object) -> dict[str, object]:
    return {k: v for k, v in vars(row).items() if k != "_sa_instance_state"}


def get_owned(db: Session, model: Any, owner_id: uuid.UUID, row_id: uuid.UUID):
    row = db.scalar(select(model).where(model.id == row_id, model.owner_id == owner_id))
    if row is None:
        raise HTTPException(404, "Sourcing record not found.")
    return row


def create_requirement(db, owner, data):
    if (
        data.opportunity_id is not None
        and db.scalar(
            select(IntelligenceOpportunity).where(
                IntelligenceOpportunity.id == data.opportunity_id,
                IntelligenceOpportunity.owner_id == owner.id,
            )
        )
        is None
    ):
        raise HTTPException(404, "Opportunity is not available in the owner scope.")
    if (
        data.product_id is not None
        and db.scalar(
            select(Product).where(Product.id == data.product_id, Product.owner_id == owner.id)
        )
        is None
    ):
        raise HTTPException(404, "Product is not available in the owner scope.")
    existing = db.scalar(
        select(SourcingRequirement).where(
            SourcingRequirement.owner_id == owner.id,
            SourcingRequirement.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    row = SourcingRequirement(
        owner_id=owner.id,
        opportunity_id=data.opportunity_id,
        product_id=data.product_id,
        idempotency_key=data.idempotency_key,
        payload=data.payload,
        created_at=now(),
        updated_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
            db.add(
                SourcingRequirementVersion(
                    owner_id=owner.id,
                    requirement_id=row.id,
                    version=1,
                    payload=data.payload,
                    created_at=now(),
                )
            )
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SourcingRequirement).where(
                SourcingRequirement.owner_id == owner.id,
                SourcingRequirement.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.commit()
    db.refresh(row)
    return row, False


def version_requirement(db, owner, req, payload):
    req.current_version += 1
    req.payload = payload
    req.updated_at = now()
    db.add(
        SourcingRequirementVersion(
            owner_id=owner.id,
            requirement_id=req.id,
            version=req.current_version,
            payload=payload,
            created_at=now(),
        )
    )
    db.commit()
    db.refresh(req)
    return req


def create_rfq(db, owner, data):
    from vayujit_api.intelligence.sourcing_closure import validate_incoterm, validate_shipping_mode

    payload = dict(data.payload)
    for key, validator in (
        ("shipping_mode", validate_shipping_mode),
        ("incoterm", validate_incoterm),
    ):
        if key in payload:
            try:
                payload[key] = validator(str(payload[key]))
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
    req = get_owned(db, SourcingRequirement, owner.id, data.requirement_id)
    if data.requirement_version != req.current_version:
        raise HTTPException(409, "Requirement version is not current; create a new RFQ version.")
    existing = db.scalar(
        select(RequestForQuote).where(
            RequestForQuote.owner_id == owner.id,
            RequestForQuote.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing, True
    row = RequestForQuote(
        owner_id=owner.id,
        requirement_id=req.id,
        requirement_version=data.requirement_version,
        title=data.title,
        version=1,
        status="draft",
        dispatch_status="not_sent",
        payload=payload,
        idempotency_key=data.idempotency_key,
        created_at=now(),
        updated_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
            db.add(RFQDraft(owner_id=owner.id, rfq_id=row.id, content=payload, created_at=now()))
            db.add(
                RFQVersion(
                    owner_id=owner.id,
                    rfq_id=row.id,
                    version=1,
                    payload=payload,
                    created_at=now(),
                )
            )
            for sid in data.supplier_ids:
                supplier = get_owned(db, Supplier, owner.id, sid)
                context = {
                    "supplier_id": str(supplier.id),
                    "verification_state": supplier.verification_state,
                    "captured_at": now().isoformat(),
                }
                db.add(
                    RFQSupplier(
                        owner_id=owner.id,
                        rfq_id=row.id,
                        supplier_id=sid,
                        supplier_context=context,
                        created_at=now(),
                    )
                )
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(RequestForQuote).where(
                RequestForQuote.owner_id == owner.id,
                RequestForQuote.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return existing, True
    db.commit()
    db.refresh(row)
    return row, False


def approve_rfq(db, owner, rfq):
    if rfq.status not in ("draft", "ready_for_review"):
        raise HTTPException(409, "RFQ is not awaiting approval.")
    rfq.status = "approved"
    rfq.dispatch_status = "ready_for_manual_send"
    rfq.approved_at = now()
    rfq.updated_at = now()
    db.commit()
    db.refresh(rfq)
    return rfq


def dispatch_rfq(db, owner, rfq, status):
    if status not in ("not_sent", "ready_for_manual_send", "sent_manually"):
        raise HTTPException(422, "Unsupported local dispatch state.")
    if status != "not_sent" and rfq.status not in (
        "approved",
        "dispatch_pending",
        "dispatched_manually",
    ):
        raise HTTPException(409, "RFQ must be approved before manual dispatch.")
    rfq.dispatch_status = status
    if status == "ready_for_manual_send":
        rfq.status = "dispatch_pending"
    if status == "sent_manually":
        rfq.status = "dispatched_manually"
    rfq.updated_at = now()
    db.commit()
    db.refresh(rfq)
    return rfq


def create_quote(db, owner, data):
    rfq = get_owned(db, RequestForQuote, owner.id, data.rfq_id)
    get_owned(db, Supplier, owner.id, data.supplier_id)
    if not db.scalar(
        select(RFQSupplier).where(
            RFQSupplier.rfq_id == rfq.id, RFQSupplier.supplier_id == data.supplier_id
        )
    ):
        raise HTTPException(409, "Supplier is not selected for this RFQ.")
    if data.unit_price < 0 or data.moq <= 0:
        raise HTTPException(422, "Quote price must be non-negative and MOQ must be positive.")
    if len(data.currency) != 3 or not data.currency.isalpha():
        raise HTTPException(422, "Currency must be a three-letter code.")
    if data.idempotency_key:
        existing = db.scalar(
            select(SupplierQuote).where(
                SupplierQuote.owner_id == owner.id,
                SupplierQuote.idempotency_key == data.idempotency_key,
            )
        )
        if existing:
            return existing

    prior = db.scalar(
        select(func.max(SupplierQuote.version)).where(
            SupplierQuote.owner_id == owner.id,
            SupplierQuote.rfq_id == rfq.id,
            SupplierQuote.supplier_id == data.supplier_id,
        )
    )
    version = int(prior or 0) + 1
    row = SupplierQuote(
        owner_id=owner.id,
        rfq_id=rfq.id,
        supplier_id=data.supplier_id,
        version=version,
        quote_reference=data.quote_reference,
        quote_date=data.quote_date or now(),
        valid_until=data.valid_until,
        currency=data.currency.upper(),
        unit_price=data.unit_price,
        moq=data.moq,
        payload=data.payload,
        evidence_refs=data.evidence_refs,
        idempotency_key=data.idempotency_key,
        created_at=now(),
        status="received",
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SupplierQuote).where(
                SupplierQuote.owner_id == owner.id,
                SupplierQuote.rfq_id == rfq.id,
                SupplierQuote.supplier_id == data.supplier_id,
                SupplierQuote.version == version,
            )
        )
        if existing is not None:
            return existing
        raise
    db.add(
        SupplierQuoteVersion(
            owner_id=owner.id,
            quote_id=row.id,
            version=version,
            snapshot=data.model_dump(mode="json"),
            created_at=now(),
        )
    )
    for line in data.lines:
        kind = line.get("kind")
        amount = line.get("amount", 0)
        line_currency = str(line.get("currency", data.currency.upper()))
        if (
            not isinstance(kind, str)
            or not kind.strip()
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(float(amount))
            or float(amount) < 0
            or len(line_currency) != 3
            or not line_currency.isalpha()
        ):
            raise HTTPException(422, "Quote line is invalid.")
        db.add(
            SupplierQuoteLine(
                owner_id=owner.id,
                quote_id=row.id,
                kind=kind,
                description=str(line.get("description", ""))[:2000],
                amount=float(amount),
                currency=line_currency.upper(),
                created_at=now(),
            )
        )
    rfq.status = "responded"
    db.commit()
    db.refresh(row)
    return row


def compare_quotes(db, owner, rfq_id):
    rows = list(
        db.scalars(
            select(SupplierQuote)
            .where(SupplierQuote.owner_id == owner.id, SupplierQuote.rfq_id == rfq_id)
            .order_by(SupplierQuote.supplier_id, SupplierQuote.version)
        )
    )
    currencies = {r.currency for r in rows}
    return {
        "rfq_id": str(rfq_id),
        "comparable": len(currencies) <= 1,
        "status": "comparable" if len(currencies) <= 1 else "NOT DIRECTLY COMPARABLE",
        "quotes": [dump(r) for r in rows],
    }


def create_sample_request(db, owner, data):
    if data.rfq_id is not None:
        rfq = get_owned(db, RequestForQuote, owner.id, data.rfq_id)
        if not db.scalar(
            select(RFQSupplier).where(
                RFQSupplier.rfq_id == rfq.id, RFQSupplier.supplier_id == data.supplier_id
            )
        ):
            raise HTTPException(409, "Supplier is not selected for this RFQ.")
    get_owned(db, Supplier, owner.id, data.supplier_id)
    row = SampleRequest(
        owner_id=owner.id,
        rfq_id=data.rfq_id,
        supplier_id=data.supplier_id,
        quantity=data.quantity,
        status="requested",
        notes=data.notes,
        created_at=now(),
    )
    db.add(row)
    db.flush()
    sample = Sample(
        owner_id=owner.id,
        request_id=row.id,
        status="requested",
        notes="",
        evidence=[],
        created_at=now(),
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


def update_sample(db, owner, sample, status):
    allowed = {
        "requested",
        "approved",
        "ordered_manually",
        "in_transit",
        "received",
        "under_review",
        "rejected",
        "archived",
    }
    transitions = {
        "requested": {"approved", "archived"},
        "approved": {"ordered_manually", "rejected", "archived"},
        "ordered_manually": {"in_transit", "archived"},
        "in_transit": {"received", "archived"},
        "received": {"under_review", "archived"},
        "under_review": {"approved", "rejected", "archived"},
        "rejected": {"archived"},
        "archived": set(),
    }
    if status not in allowed:
        raise HTTPException(422, "Unsupported sample state.")
    if status != sample.status and status not in transitions.get(sample.status, set()):
        raise HTTPException(409, "Sample state transition is not allowed.")
    sample.status = status
    db.commit()
    db.refresh(sample)
    return sample


def evaluate_sample(db, owner, sample, data):
    if data.decision not in (
        "PASS",
        "PASS_WITH_CONDITIONS",
        "REWORK",
        "FAIL",
        "INSUFFICIENT_EVIDENCE",
    ):
        raise HTTPException(422, "Unsupported sample decision.")
    existing = db.scalar(
        select(SampleEvaluation).where(
            SampleEvaluation.owner_id == owner.id, SampleEvaluation.sample_id == sample.id
        )
    )
    if existing:
        return existing
    row = SampleEvaluation(
        owner_id=owner.id,
        sample_id=sample.id,
        decision=data.decision,
        dimensions=data.dimensions,
        notes=data.notes,
        created_at=now(),
    )
    sample.status = "approved" if data.decision in ("PASS", "PASS_WITH_CONDITIONS") else "rejected"
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SampleEvaluation).where(
                SampleEvaluation.owner_id == owner.id, SampleEvaluation.sample_id == sample.id
            )
        )
        if existing is None:
            raise
        return existing
    db.commit()
    db.refresh(row)
    return row


def calculate_cost(inputs: dict[str, object]) -> tuple[dict[str, float], float]:
    numeric = {
        str(k): float(v) for k, v in inputs.items() if isinstance(v, (int, float)) and float(v) >= 0
    }
    keys = (
        "unit_supplier_price",
        "tooling",
        "branding",
        "packaging",
        "inspection",
        "freight",
        "insurance",
        "duty",
        "tax",
        "brokerage",
        "local_transport",
        "warehouse_inbound",
        "payment_fx_fee",
        "other",
    )
    breakdown = {k: numeric.get(k, 0.0) for k in keys}
    total = sum(breakdown.values())
    return breakdown, total


def create_scenario(db, owner, data):
    for key, value in data.inputs.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise HTTPException(422, f"Scenario input {key} is invalid.")
    if data.requirement_id is not None:
        get_owned(db, SourcingRequirement, owner.id, data.requirement_id)
    if data.quote_id is not None:
        get_owned(db, SupplierQuote, owner.id, data.quote_id)
    breakdown, total = calculate_cost(data.inputs)
    qty = max(int(data.inputs.get("quantity", 1)), 1)
    selling = float(data.inputs.get("selling_price", 0))
    ads = float(data.inputs.get("ads_cac", 0))
    returns = float(data.inputs.get("returns_allowance", 0))
    landed = total / qty
    contribution = (
        selling
        - landed
        - float(data.inputs.get("marketplace_fee", 0))
        - float(data.inputs.get("payment_fee", 0))
        - ads
        - returns
    )
    result = {
        "landed_cost_per_unit": round(landed, 4),
        "total_landed_cost": round(total, 4),
        "breakdown": breakdown,
        "gross_contribution": round(contribution, 4),
        "contribution_margin": round(contribution / selling, 4) if selling else None,
        "maximum_cac": round(
            max(
                selling
                - landed
                - float(data.inputs.get("marketplace_fee", 0))
                - float(data.inputs.get("payment_fee", 0))
                - returns,
                0,
            ),
            4,
        ),
        "break_even_price": round(
            landed
            + float(data.inputs.get("marketplace_fee", 0))
            + float(data.inputs.get("payment_fee", 0))
            + returns,
            4,
        ),
    }
    existing = db.scalars(
        select(CostScenario)
        .where(
            CostScenario.owner_id == owner.id,
            CostScenario.requirement_id == data.requirement_id,
            CostScenario.name == data.name,
        )
        .order_by(CostScenario.version.desc())
    ).first()
    if existing and existing.inputs == data.inputs and existing.quote_id == data.quote_id:
        return existing
    row = CostScenario(
        owner_id=owner.id,
        requirement_id=data.requirement_id,
        quote_id=data.quote_id,
        name=data.name,
        version=int(existing.version) + 1 if existing else 1,
        currency=data.currency.upper(),
        inputs=data.inputs,
        result=result,
        confidence="MEDIUM" if breakdown else "INSUFFICIENT",
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
            if not db.scalar(
                select(LandedCostEstimate).where(LandedCostEstimate.scenario_id == row.id)
            ):
                db.add(
                    LandedCostEstimate(
                        owner_id=owner.id,
                        scenario_id=row.id,
                        per_unit=landed,
                        total=total,
                        breakdown=breakdown,
                        confidence=row.confidence,
                        created_at=now(),
                    )
                )
            db.flush()
    except IntegrityError:
        existing = db.scalars(
            select(CostScenario)
            .where(
                CostScenario.owner_id == owner.id,
                CostScenario.requirement_id == data.requirement_id,
                CostScenario.name == data.name,
                CostScenario.inputs == data.inputs,
            )
            .order_by(CostScenario.version.desc())
        ).first()
        if existing is None:
            raise
        return existing
    db.commit()
    db.refresh(row)
    return row


def create_decision(db, owner, data):
    req = get_owned(db, SourcingRequirement, owner.id, data.requirement_id)
    quote = get_owned(db, SupplierQuote, owner.id, data.quote_id)
    if quote.rfq_id is None:
        raise HTTPException(422, "Quote is not linked to an RFQ.")
    if data.decision not in (
        "shortlist_for_order",
        "request_negotiation",
        "request_new_sample",
        "request_requote",
        "reject",
        "hold",
        "approve_for_future_purchase",
    ):
        raise HTTPException(422, "Unsupported sourcing decision.")
    existing = db.scalar(
        select(SourcingDecision).where(
            SourcingDecision.owner_id == owner.id,
            SourcingDecision.requirement_id == req.id,
            SourcingDecision.quote_id == quote.id,
        )
    )
    if existing:
        return existing
    row = SourcingDecision(
        owner_id=owner.id,
        requirement_id=req.id,
        quote_id=quote.id,
        classification=data.classification,
        decision=data.decision,
        critic=data.critic,
        confirmed=data.confirmed,
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SourcingDecision).where(
                SourcingDecision.owner_id == owner.id,
                SourcingDecision.requirement_id == req.id,
                SourcingDecision.quote_id == quote.id,
            )
        )
        if existing is None:
            raise
        return existing
    db.commit()
    db.refresh(row)
    return row


def approve_decision(db, owner, decision, note):
    if not decision.confirmed:
        raise HTTPException(409, "Decision confirmation is required.")
    existing = db.scalar(
        select(SourcingApproval).where(SourcingApproval.decision_id == decision.id)
    )
    if existing:
        return existing
    row = SourcingApproval(
        owner_id=owner.id, decision_id=decision.id, approved=True, note=note, created_at=now()
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SourcingApproval).where(
                SourcingApproval.owner_id == owner.id,
                SourcingApproval.decision_id == decision.id,
            )
        )
        if existing is None:
            raise
        return existing
    db.commit()
    db.refresh(row)
    return row


def enqueue_worker(db, owner, data):
    existing = db.scalar(
        select(SourcingWorkerJob).where(
            SourcingWorkerJob.owner_id == owner.id,
            SourcingWorkerJob.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing
    row = SourcingWorkerJob(
        owner_id=owner.id,
        task=data.task,
        status="pending",
        idempotency_key=data.idempotency_key,
        payload=data.payload,
        result={},
        created_at=now(),
        updated_at=now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _checkpoint(db: Session, job: SourcingWorkerJob, stage: str, **payload: object) -> None:
    job.checkpoint_stage = stage
    job.checkpoint_payload = {
        **(job.checkpoint_payload or {}),
        **payload,
        "checkpoint_updated_at": now().isoformat(),
    }
    job.updated_at = now()
    db.flush()


def run_worker(
    db: Session,
    owner,
    job,
    *,
    worker_id: str | None = None,
    lease_seconds: int = 60,
    crash_after_stage: str | None = None,
):
    """Run one local sourcing job with durable checkpoints and safe replay."""
    stages = {
        "created": 0,
        "claimed": 1,
        "before_calculation": 2,
        "calculation_complete": 3,
        "scenario_complete": 4,
        "report_complete": 5,
        "finalized": 6,
    }
    if job.status == "completed" and job.checkpoint_stage == "finalized":
        return job
    worker_id = worker_id or f"sourcing-worker:{uuid.uuid4()}"
    timestamp = now()
    if (
        job.status == "running"
        and job.lease_expires_at is not None
        and job.lease_expires_at > timestamp
        and job.lease_owner not in (None, worker_id)
    ):
        return job
    if job.status == "running" and (
        job.lease_expires_at is None or job.lease_expires_at <= timestamp
    ):
        job.status = "pending"
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.last_error = "Worker lease expired; execution resumed safely."
    prior_stage = job.checkpoint_stage or "created"
    job.status = "running"
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.claimed_at = job.claimed_at or timestamp
    job.lease_owner = worker_id
    job.lease_expires_at = timestamp + timedelta(seconds=lease_seconds)
    job.heartbeat_at = timestamp
    if stages.get(prior_stage, 0) < stages["claimed"]:
        _checkpoint(db, job, "claimed", worker_claimed_at=timestamp.isoformat())
    else:
        job.updated_at = now()
        db.flush()
    db.commit()

    requested_crash = crash_after_stage or (job.payload or {}).get("crash_after_stage")
    if requested_crash:
        job.payload = {
            key: value for key, value in (job.payload or {}).items() if key != "crash_after_stage"
        }
        db.commit()
    if requested_crash == "claimed":
        raise RuntimeError("local sourcing worker crash after claim checkpoint")

    if stages.get(job.checkpoint_stage, 0) < stages["before_calculation"]:
        _checkpoint(db, job, "before_calculation", calculation_started_at=now().isoformat())
        db.commit()
    if requested_crash == "before_calculation":
        raise RuntimeError("local sourcing worker crash before calculation")

    if stages.get(job.checkpoint_stage, 0) < stages["calculation_complete"]:
        if job.task == "cost_recalculation":
            from vayujit_api.intelligence.sourcing_closure import landed_cost

            job.result = {
                "status": "completed",
                "deterministic": True,
                "calculation": landed_cost(job.payload),
            }
        elif job.task == "scenario_generation":
            job.result = {"status": "completed", "deterministic": True, "task": job.task}
        elif job.task == "stale_quote_check":
            job.result = {
                "status": "completed",
                "expired_quotes": int(
                    db.scalar(
                        select(func.count())
                        .select_from(SupplierQuote)
                        .where(
                            SupplierQuote.owner_id == owner.id, SupplierQuote.valid_until < now()
                        )
                    )
                    or 0
                ),
            }
        else:
            job.result = {"status": "completed", "task": job.task, "deterministic": True}
        _checkpoint(db, job, "calculation_complete", calculation_completed_at=now().isoformat())
        db.commit()
    if requested_crash == "calculation_complete":
        raise RuntimeError("local sourcing worker crash after calculation checkpoint")

    if stages.get(job.checkpoint_stage, 0) < stages["scenario_complete"]:
        _checkpoint(db, job, "scenario_complete", scenario_completed_at=now().isoformat())
        db.commit()
    if requested_crash == "scenario_complete":
        raise RuntimeError("local sourcing worker crash after scenario checkpoint")

    if stages.get(job.checkpoint_stage, 0) < stages["report_complete"]:
        _checkpoint(db, job, "report_complete", report_completed_at=now().isoformat())
        db.commit()
    if requested_crash == "report_complete":
        raise RuntimeError("local sourcing worker crash after report checkpoint")

    job.status = "completed"
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.last_error = None
    _checkpoint(db, job, "finalized", finalized_at=now().isoformat())
    db.commit()
    db.refresh(job)
    return job


SOURCING_RECOVERY_ACTIONS: dict[str, tuple[str, ...]] = {
    "invalid_requirement": ("review_requirement", "cancel"),
    "invalid_supplier_state": ("review_supplier", "cancel"),
    "quote_expired": ("review_quote", "refresh_assumptions", "cancel"),
    "quote_invalid": ("review_quote", "request_requote", "cancel"),
    "currency_mismatch": ("refresh_assumptions", "review_quote", "cancel"),
    "cost_calculation_failed": ("retry", "reconcile", "cancel"),
    "missing_assumption": ("refresh_assumptions", "retry", "cancel"),
    "sample_failed": ("review_sample", "request_new_sample", "cancel"),
    "inspection_failed": ("review_inspection", "request_new_sample", "cancel"),
    "checkpoint_invalid": ("reconcile", "retry", "cancel"),
}


def recover(db, owner, data):
    failure_code = data.failure_code
    allowed_actions = SOURCING_RECOVERY_ACTIONS.get(failure_code)
    if allowed_actions is None or data.action not in allowed_actions:
        raise HTTPException(
            422, "Recovery action is not executable for this failure classification."
        )
    key = (
        data.idempotency_key or f"{failure_code}:{data.entity_type}:{data.entity_id}:{data.action}"
    )
    prior = db.scalar(
        select(SourcingRecoveryRecord).where(
            SourcingRecoveryRecord.owner_id == owner.id,
            SourcingRecoveryRecord.entity_type == data.entity_type,
            SourcingRecoveryRecord.entity_id == data.entity_id,
            SourcingRecoveryRecord.action == data.action,
            SourcingRecoveryRecord.idempotency_key == key,
        )
    )
    if prior:
        return {
            "id": str(prior.id),
            "status": "recovered",
            "result": "recovered",
            "idempotent_reuse": True,
            "action": prior.action,
            "failure_code": failure_code,
            "safe_message": "Sourcing recovery was already applied safely.",
            "allowed_actions": list(allowed_actions),
            "correlation_id": str(prior.id),
        }
    record = SourcingRecoveryRecord(
        owner_id=owner.id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        action=data.action,
        result="recovered",
        reason=data.reason,
        idempotency_key=key,
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        prior = db.scalar(
            select(SourcingRecoveryRecord).where(
                SourcingRecoveryRecord.owner_id == owner.id,
                SourcingRecoveryRecord.entity_type == data.entity_type,
                SourcingRecoveryRecord.entity_id == data.entity_id,
                SourcingRecoveryRecord.action == data.action,
                SourcingRecoveryRecord.idempotency_key == key,
            )
        )
        if prior is None:
            raise
        record = prior
        reused = True
    else:
        reused = False
    db.commit()
    return {
        "id": str(record.id),
        "status": "recovered",
        "result": "recovered",
        "idempotent_reuse": reused,
        "action": record.action,
        "failure_code": failure_code,
        "safe_message": "Sourcing recovery completed without external actions.",
        "allowed_actions": list(allowed_actions),
        "correlation_id": str(record.id),
    }


def overview(db, owner):
    def count(model, *conds):
        return int(
            db.scalar(
                select(func.count()).select_from(model).where(model.owner_id == owner.id, *conds)
            )
            or 0
        )

    return {
        "active_requirements": count(SourcingRequirement, SourcingRequirement.status == "active"),
        "open_rfqs": count(
            RequestForQuote,
            RequestForQuote.status.in_(
                ("draft", "approved", "dispatch_pending", "dispatched_manually")
            ),
        ),
        "awaiting_quotes": count(
            RequestForQuote, RequestForQuote.status.in_(("approved", "dispatched_manually"))
        ),
        "quotes_expiring": count(SupplierQuote, SupplierQuote.status == "received"),
        "samples": count(Sample),
        "inspections": count(Inspection),
        "decisions_awaiting_review": count(SourcingDecision, SourcingDecision.confirmed.is_(False)),
        "economic_warnings": 0,
        "external_dispatch": "disabled",
        "purchasing": "not_implemented",
    }


MATERIAL_RFQ_FIELDS = {
    "requirement_version",
    "supplier_ids",
    "quantity",
    "packaging",
    "private_label",
    "customization",
    "sample_requirements",
    "certifications",
    "destination",
    "incoterm",
    "lead_time",
    "payment_terms",
}


def revise_rfq(db, owner, rfq, payload):
    if rfq.dispatch_status == "sent_manually" or rfq.status in {
        "dispatched_manually",
        "closed",
        "cancelled",
    }:
        raise HTTPException(409, "Dispatched RFQ versions are immutable.")
    current = dict(rfq.payload or {})
    if "supplier_ids" in payload:
        supplier_ids = [uuid.UUID(str(value)) for value in payload["supplier_ids"]]
        for supplier_id in supplier_ids:
            supplier = get_owned(db, Supplier, owner.id, supplier_id)
            payload.setdefault("supplier_context", {})
            payload["supplier_context"][str(supplier_id)] = {
                "verification_state": supplier.verification_state,
                "captured_at": now().isoformat(),
            }
        payload["supplier_ids"] = [str(value) for value in supplier_ids]
        selected = list(
            db.scalars(
                select(RFQSupplier).where(
                    RFQSupplier.owner_id == owner.id, RFQSupplier.rfq_id == rfq.id
                )
            )
        )
        desired = set(supplier_ids)
        for link in selected:
            if link.supplier_id not in desired:
                db.delete(link)
        existing_ids = {link.supplier_id for link in selected}
        for supplier_id in desired - existing_ids:
            supplier = get_owned(db, Supplier, owner.id, supplier_id)
            db.add(
                RFQSupplier(
                    owner_id=owner.id,
                    rfq_id=rfq.id,
                    supplier_id=supplier_id,
                    supplier_context={
                        "verification_state": supplier.verification_state,
                        "captured_at": now().isoformat(),
                    },
                    created_at=now(),
                )
            )
    merged = {**current, **payload}
    if merged == current:
        return rfq
    version = int(rfq.version) + 1
    rfq.version = version
    rfq.payload = merged
    rfq.updated_at = now()
    draft = db.scalar(
        select(RFQDraft).where(RFQDraft.owner_id == owner.id, RFQDraft.rfq_id == rfq.id)
    )
    if draft is not None:
        draft.content = dict(merged)
    db.add(
        RFQVersion(
            owner_id=owner.id,
            rfq_id=rfq.id,
            version=version,
            payload=dict(merged),
            created_at=now(),
        )
    )
    db.commit()
    db.refresh(rfq)
    return rfq


def create_assumption_version(db, owner, scenario_id, kind, payload):
    if kind not in {"logistics", "duty_tax", "fx"}:
        raise HTTPException(422, "Unsupported sourcing assumption kind.")
    prior = db.scalar(
        select(func.max(SourcingAssumptionVersion.version)).where(
            SourcingAssumptionVersion.owner_id == owner.id,
            SourcingAssumptionVersion.scenario_id == scenario_id,
            SourcingAssumptionVersion.kind == kind,
        )
    )
    row = SourcingAssumptionVersion(
        owner_id=owner.id,
        scenario_id=scenario_id,
        kind=kind,
        version=int(prior or 0) + 1,
        payload=payload,
        created_at=now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
