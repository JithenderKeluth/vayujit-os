from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.sourcing_closure import (
    capital_requirement,
    cash_timeline,
    concentration,
    evaluate_rules,
    landed_cost,
    negotiation_delta,
    safe_report,
    score_candidate,
    sensitivity,
    sourcing_decision,
    validate_duty_tax,
    validate_fx,
    validate_incoterm,
    validate_logistics,
    validate_shipping_mode,
)
from vayujit_api.intelligence.sourcing_closure import (
    critic as build_critic,
)
from vayujit_api.intelligence.sourcing_models import (
    CostScenario,
    DutyTaxAssumption,
    FXAssumption,
    Inspection,
    InspectionFinding,
    LogisticsEstimate,
    NegotiationRound,
    RequestForQuote,
    RFQVersion,
    Sample,
    SourcingCalendarItem,
    SourcingDecision,
    SourcingRequirement,
    SourcingRuleEvaluation,
    SourcingScoreEvaluation,
    SourcingWorkerJob,
    SupplierQuote,
)
from vayujit_api.intelligence.sourcing_schemas import (
    ApprovalCreate,
    AssumptionCreate,
    CalendarCreate,
    DecisionCreate,
    DispatchRequest,
    FindingCreate,
    InspectionCreate,
    NegotiationCreate,
    QuoteCreate,
    RecoveryCreate,
    RequirementCreate,
    RequirementVersionCreate,
    RFQCreate,
    RFQRevisionCreate,
    RuleEvaluate,
    SampleEvaluate,
    SampleRequestCreate,
    SampleStatusUpdate,
    ScenarioCreate,
    ScoreEvaluate,
    WorkerCreate,
)
from vayujit_api.intelligence.sourcing_service import (
    approve_decision,
    approve_rfq,
    compare_quotes,
    create_assumption_version,
    create_decision,
    create_quote,
    create_requirement,
    create_sample_request,
    create_scenario,
    dispatch_rfq,
    dump,
    enqueue_worker,
    evaluate_sample,
    get_owned,
    recover,
    revise_rfq,
    run_worker,
    update_sample,
    version_requirement,
)
from vayujit_api.intelligence.sourcing_service import (
    overview as sourcing_overview,
)

router = APIRouter(prefix="/api/v1/intelligence/sourcing", tags=["intelligence-sourcing"])
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


@router.get("/overview")
def overview(db: DB, owner: Owner):
    return sourcing_overview(db, owner)


@router.post("/requirements", status_code=201)
def requirements_create(data: RequirementCreate, db: DB, owner: Owner):
    row, reused = create_requirement(db, owner, data)
    return {"requirement": row, "idempotent_reuse": reused}


@router.get("/requirements")
def requirements_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(
                select(SourcingRequirement)
                .where(SourcingRequirement.owner_id == owner.id)
                .order_by(SourcingRequirement.created_at.desc())
            )
        )
    }


@router.get("/requirements/{requirement_id}")
def requirements_detail(requirement_id: uuid.UUID, db: DB, owner: Owner):
    return get_owned(db, SourcingRequirement, owner.id, requirement_id)


@router.post("/requirements/{requirement_id}/versions")
def requirements_version(
    requirement_id: uuid.UUID, data: RequirementVersionCreate, db: DB, owner: Owner
):
    return version_requirement(
        db, owner, get_owned(db, SourcingRequirement, owner.id, requirement_id), data.payload
    )


@router.post("/rfqs", status_code=201)
def rfq_create(data: RFQCreate, db: DB, owner: Owner):
    row, reused = __import__(
        "vayujit_api.intelligence.sourcing_service", fromlist=["create_rfq"]
    ).create_rfq(db, owner, data)
    return {"rfq": row, "idempotent_reuse": reused}


@router.get("/rfqs")
def rfq_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(
                select(RequestForQuote)
                .where(RequestForQuote.owner_id == owner.id)
                .order_by(RequestForQuote.created_at.desc())
            )
        )
    }


@router.get("/rfqs/{rfq_id}")
def rfq_detail(rfq_id: uuid.UUID, db: DB, owner: Owner):
    return get_owned(db, RequestForQuote, owner.id, rfq_id)


@router.post("/rfqs/{rfq_id}/approve")
def rfq_approve(rfq_id: uuid.UUID, db: DB, owner: Owner):
    return approve_rfq(db, owner, get_owned(db, RequestForQuote, owner.id, rfq_id))


@router.post("/rfqs/{rfq_id}/dispatch")
def rfq_dispatch(rfq_id: uuid.UUID, data: DispatchRequest, db: DB, owner: Owner):
    return dispatch_rfq(db, owner, get_owned(db, RequestForQuote, owner.id, rfq_id), data.status)


@router.post("/quotes", status_code=201)
def quote_create(data: QuoteCreate, db: DB, owner: Owner):
    return create_quote(db, owner, data)


@router.get("/quotes")
def quote_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(
                select(SupplierQuote)
                .where(SupplierQuote.owner_id == owner.id)
                .order_by(SupplierQuote.created_at.desc())
            )
        )
    }


@router.get("/quotes/{quote_id}")
def quote_detail(quote_id: uuid.UUID, db: DB, owner: Owner):
    return get_owned(db, SupplierQuote, owner.id, quote_id)


@router.get("/rfqs/{rfq_id}/compare")
def quote_compare(rfq_id: uuid.UUID, db: DB, owner: Owner):
    return compare_quotes(db, owner, rfq_id)


@router.get("/quotes/compare/{rfq_id}")
def quote_compare_alias(rfq_id: uuid.UUID, db: DB, owner: Owner):
    return compare_quotes(db, owner, rfq_id)


@router.post("/samples", status_code=201)
def sample_create(data: SampleRequestCreate, db: DB, owner: Owner):
    return create_sample_request(db, owner, data)


@router.get("/samples")
def sample_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(
                select(Sample).where(Sample.owner_id == owner.id).order_by(Sample.created_at.desc())
            )
        )
    }


@router.get("/samples/{sample_id}")
def sample_detail(sample_id: uuid.UUID, db: DB, owner: Owner):
    return get_owned(db, Sample, owner.id, sample_id)


@router.post("/samples/{sample_id}/status")
def sample_status(sample_id: uuid.UUID, data: SampleStatusUpdate, db: DB, owner: Owner):
    return update_sample(db, owner, get_owned(db, Sample, owner.id, sample_id), data.status)


@router.post("/samples/{sample_id}/evaluate")
def sample_evaluate(sample_id: uuid.UUID, data: SampleEvaluate, db: DB, owner: Owner):
    return evaluate_sample(db, owner, get_owned(db, Sample, owner.id, sample_id), data)


@router.post("/inspections", status_code=201)
def inspection_create(data: InspectionCreate, db: DB, owner: Owner):
    if data.sample_id is not None:
        get_owned(db, Sample, owner.id, data.sample_id)
    row = Inspection(
        owner_id=owner.id,
        sample_id=data.sample_id,
        inspection_type=data.inspection_type,
        status="open",
        notes=data.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/inspections")
def inspection_list(db: DB, owner: Owner):
    return {"items": list(db.scalars(select(Inspection).where(Inspection.owner_id == owner.id)))}


@router.post("/inspections/{inspection_id}/findings", status_code=201)
def finding_create(inspection_id: uuid.UUID, data: FindingCreate, db: DB, owner: Owner):
    get_owned(db, Inspection, owner.id, inspection_id)
    row = InspectionFinding(owner_id=owner.id, inspection_id=inspection_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/negotiations", status_code=201)
def negotiation_create(data: NegotiationCreate, db: DB, owner: Owner):
    get_owned(db, SupplierQuote, owner.id, data.quote_id)
    prior = db.scalar(
        select(NegotiationRound.round_number)
        .where(NegotiationRound.owner_id == owner.id, NegotiationRound.quote_id == data.quote_id)
        .order_by(NegotiationRound.round_number.desc())
    )
    row = NegotiationRound(owner_id=owner.id, **data.model_dump(), round_number=int(prior or 0) + 1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/scenarios", status_code=201)
def scenario_create(data: ScenarioCreate, db: DB, owner: Owner):
    return create_scenario(db, owner, data)


@router.get("/scenarios")
def scenario_list(db: DB, owner: Owner):
    from vayujit_api.intelligence.sourcing_models import CostScenario

    return {
        "items": list(db.scalars(select(CostScenario).where(CostScenario.owner_id == owner.id)))
    }


@router.get("/scenarios/{scenario_id}")
def scenario_detail(scenario_id: uuid.UUID, db: DB, owner: Owner):
    from vayujit_api.intelligence.sourcing_models import CostScenario

    return get_owned(db, CostScenario, owner.id, scenario_id)


@router.post("/costs/calculate")
def cost_calculate(data: ScenarioCreate, db: DB, owner: Owner):
    return create_scenario(db, owner, data)


@router.post("/scenarios/compare")
def scenario_compare(data: dict[str, object], db: DB, owner: Owner):
    from vayujit_api.intelligence.sourcing_models import CostScenario

    raw_ids = data.get("scenario_ids", [])
    if not isinstance(raw_ids, list):
        return {"scenarios": []}
    ids = [uuid.UUID(str(i)) for i in raw_ids]
    rows = [get_owned(db, CostScenario, owner.id, i) for i in ids]
    return {"scenarios": rows}


@router.post("/decisions", status_code=201)
def decision_create(data: DecisionCreate, db: DB, owner: Owner):
    return create_decision(db, owner, data)


@router.get("/decisions")
def decision_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(select(SourcingDecision).where(SourcingDecision.owner_id == owner.id))
        )
    }


@router.get("/decisions/{decision_id}")
def decision_detail(decision_id: uuid.UUID, db: DB, owner: Owner):
    return get_owned(db, SourcingDecision, owner.id, decision_id)


@router.post("/decisions/{decision_id}/approve")
def decision_approve(decision_id: uuid.UUID, data: ApprovalCreate, db: DB, owner: Owner):
    return approve_decision(
        db, owner, get_owned(db, SourcingDecision, owner.id, decision_id), data.note
    )


@router.post("/worker/jobs", status_code=201)
def worker_enqueue(data: WorkerCreate, db: DB, owner: Owner):
    return enqueue_worker(db, owner, data)


@router.post("/worker/jobs/{job_id}/run")
def worker_run(job_id: uuid.UUID, db: DB, owner: Owner):
    return run_worker(db, owner, get_owned(db, SourcingWorkerJob, owner.id, job_id))


@router.get("/operations")
def operations(db: DB, owner: Owner):
    return {
        "worker": "registered",
        "queue": int(
            db.query(SourcingWorkerJob)
            .filter(SourcingWorkerJob.owner_id == owner.id, SourcingWorkerJob.status == "pending")
            .count()
        ),
        "external_dispatch": "disabled",
        "purchasing": "not_implemented",
        "live_freight": "not_configured",
        "live_fx": "not_configured",
        "live_duty_tax": "not_configured",
    }


@router.post("/recovery")
def recovery(data: RecoveryCreate, db: DB, owner: Owner):
    return recover(db, owner, data)


@router.get("/history")
def history(db: DB, owner: Owner):
    from vayujit_api.intelligence.sourcing_models import SourcingRecoveryRecord

    return {
        "items": list(
            db.scalars(
                select(SourcingRecoveryRecord)
                .where(SourcingRecoveryRecord.owner_id == owner.id)
                .order_by(SourcingRecoveryRecord.created_at.desc())
            )
        )
    }


@router.get("/report")
def report(db: DB, owner: Owner):
    return {
        "format": "json",
        "Requirement": sourcing_overview(db, owner),
        "RFQ": "local_manual_only",
        "Supplier": "owner_scoped",
        "Quote": "manual_local",
        "Economics": "deterministic_assumptions_only",
        "Decision": "human_approval_required",
        "Evidence": "metadata_references_only",
    }


@router.post("/rfqs/{rfq_id}/versions")
def rfq_revision(rfq_id: uuid.UUID, data: RFQRevisionCreate, db: DB, owner: Owner):
    rfq = get_owned(db, RequestForQuote, owner.id, rfq_id)
    payload = {
        **data.payload,
        **data.model_dump(mode="json", exclude={"payload"}, exclude_none=True),
    }
    try:
        if "shipping_mode" in payload:
            validate_shipping_mode(str(payload["shipping_mode"]))
        if "incoterm" in payload:
            validate_incoterm(str(payload["incoterm"]))
        return revise_rfq(db, owner, rfq, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/rfqs/{rfq_id}/versions")
def rfq_versions(rfq_id: uuid.UUID, db: DB, owner: Owner):
    get_owned(db, RequestForQuote, owner.id, rfq_id)
    return {
        "items": list(
            db.scalars(
                select(RFQVersion)
                .where(RFQVersion.owner_id == owner.id, RFQVersion.rfq_id == rfq_id)
                .order_by(RFQVersion.version)
            )
        )
    }


def _scenario_owned(db: Session, owner: User, scenario_id: uuid.UUID) -> CostScenario:
    return get_owned(db, CostScenario, owner.id, scenario_id)


@router.post("/scenarios/{scenario_id}/logistics")
def logistics_create(scenario_id: uuid.UUID, data: AssumptionCreate, db: DB, owner: Owner):
    if data.scenario_id != scenario_id:
        raise HTTPException(409, "Scenario reference does not match path.")
    _scenario_owned(db, owner, scenario_id)
    try:
        payload = validate_logistics(data.payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = db.scalar(
        select(LogisticsEstimate).where(
            LogisticsEstimate.owner_id == owner.id, LogisticsEstimate.scenario_id == scenario_id
        )
    )
    if row is None:
        row = LogisticsEstimate(
            owner_id=owner.id,
            scenario_id=scenario_id,
            payload=payload,
            classification=payload["classification"],
        )
        db.add(row)
    else:
        row.payload = payload
        row.classification = payload["classification"]
    db.commit()
    db.refresh(row)
    create_assumption_version(db, owner, scenario_id, "logistics", payload)
    return row


@router.get("/scenarios/{scenario_id}/logistics")
def logistics_detail(scenario_id: uuid.UUID, db: DB, owner: Owner):
    _scenario_owned(db, owner, scenario_id)
    return db.scalar(
        select(LogisticsEstimate).where(
            LogisticsEstimate.owner_id == owner.id, LogisticsEstimate.scenario_id == scenario_id
        )
    ) or {"status": "not_configured"}


@router.post("/scenarios/{scenario_id}/duty-tax")
def duty_tax_create(scenario_id: uuid.UUID, data: AssumptionCreate, db: DB, owner: Owner):
    if data.scenario_id != scenario_id:
        raise HTTPException(409, "Scenario reference does not match path.")
    _scenario_owned(db, owner, scenario_id)
    try:
        payload = validate_duty_tax(data.payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = db.scalar(
        select(DutyTaxAssumption).where(
            DutyTaxAssumption.owner_id == owner.id, DutyTaxAssumption.scenario_id == scenario_id
        )
    )
    if row is None:
        row = DutyTaxAssumption(
            owner_id=owner.id,
            scenario_id=scenario_id,
            payload=payload,
            classification=payload["classification"],
        )
        db.add(row)
    else:
        row.payload = payload
        row.classification = payload["classification"]
    db.commit()
    db.refresh(row)
    create_assumption_version(db, owner, scenario_id, "duty_tax", payload)
    return row


@router.get("/scenarios/{scenario_id}/duty-tax")
def duty_tax_detail(scenario_id: uuid.UUID, db: DB, owner: Owner):
    _scenario_owned(db, owner, scenario_id)
    return db.scalar(
        select(DutyTaxAssumption).where(
            DutyTaxAssumption.owner_id == owner.id, DutyTaxAssumption.scenario_id == scenario_id
        )
    ) or {"status": "not_configured"}


@router.post("/scenarios/{scenario_id}/fx")
def fx_create(scenario_id: uuid.UUID, data: AssumptionCreate, db: DB, owner: Owner):
    if data.scenario_id != scenario_id:
        raise HTTPException(409, "Scenario reference does not match path.")
    _scenario_owned(db, owner, scenario_id)
    try:
        payload = validate_fx(data.payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row = db.scalar(
        select(FXAssumption).where(
            FXAssumption.owner_id == owner.id, FXAssumption.scenario_id == scenario_id
        )
    )
    values = {
        "from_currency": payload["from_currency"],
        "to_currency": payload["to_currency"],
        "rate": payload["rate"],
        "classification": payload["classification"],
        "reference": payload["source_reference"],
        "observed_at": payload.get("observed_at"),
        "valid_until": payload.get("valid_until"),
    }
    if row is None:
        row = FXAssumption(owner_id=owner.id, scenario_id=scenario_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    create_assumption_version(db, owner, scenario_id, "fx", payload)
    return row


def _assumption_versions(db: Session, owner: User, scenario_id: uuid.UUID, kind: str):
    _scenario_owned(db, owner, scenario_id)
    from vayujit_api.intelligence.sourcing_models import SourcingAssumptionVersion

    return {
        "items": list(
            db.scalars(
                select(SourcingAssumptionVersion)
                .where(
                    SourcingAssumptionVersion.owner_id == owner.id,
                    SourcingAssumptionVersion.scenario_id == scenario_id,
                    SourcingAssumptionVersion.kind == kind,
                )
                .order_by(SourcingAssumptionVersion.version)
            )
        )
    }


@router.get("/scenarios/{scenario_id}/assumptions/{kind}")
def assumption_versions(scenario_id: uuid.UUID, kind: str, db: DB, owner: Owner):
    if kind not in {"logistics", "duty_tax", "fx"}:
        raise HTTPException(422, "Unsupported sourcing assumption kind.")
    return _assumption_versions(db, owner, scenario_id, kind)


@router.get("/scenarios/{scenario_id}/fx")
def fx_detail(scenario_id: uuid.UUID, db: DB, owner: Owner):
    _scenario_owned(db, owner, scenario_id)
    return db.scalar(
        select(FXAssumption).where(
            FXAssumption.owner_id == owner.id, FXAssumption.scenario_id == scenario_id
        )
    ) or {"status": "not_configured"}


@router.post("/economics/landed-cost")
def landed_cost_calculate(data: dict[str, object]):
    try:
        return landed_cost(data, currency=str(data.get("currency", "INR")))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/economics/capital")
def capital_calculate(data: dict[str, object]):
    try:
        return capital_requirement(data, currency=str(data.get("currency", "INR")))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/economics/cash-timeline")
def cash_timeline_calculate(data: dict[str, object]):
    try:
        return {"items": cash_timeline(data, currency=str(data.get("currency", "INR")))}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/economics/sensitivity")
def sensitivity_calculate(data: dict[str, object]):
    try:
        return {"items": sensitivity(data)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/scores/evaluate")
def score_evaluate(data: ScoreEvaluate, db: DB, owner: Owner):
    get_owned(db, SourcingRequirement, owner.id, data.requirement_id)
    get_owned(db, SupplierQuote, owner.id, data.quote_id)
    try:
        result = score_candidate(data.inputs, data.weights, model_version=data.model_version)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = db.scalar(
        select(SourcingScoreEvaluation).where(
            SourcingScoreEvaluation.owner_id == owner.id,
            SourcingScoreEvaluation.requirement_id == data.requirement_id,
            SourcingScoreEvaluation.quote_id == data.quote_id,
            SourcingScoreEvaluation.model_version == data.model_version,
        )
    )
    if existing is not None:
        return {"evaluation": existing, "result": result, "idempotent_reuse": True}
    row = SourcingScoreEvaluation(
        owner_id=owner.id,
        requirement_id=data.requirement_id,
        quote_id=data.quote_id,
        model_version=data.model_version,
        weights=result["weights"],
        dimensions=result["dimensions"],
        score=result["score"],
        confidence=result["confidence"],
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SourcingScoreEvaluation).where(
                SourcingScoreEvaluation.owner_id == owner.id,
                SourcingScoreEvaluation.requirement_id == data.requirement_id,
                SourcingScoreEvaluation.quote_id == data.quote_id,
                SourcingScoreEvaluation.model_version == data.model_version,
            )
        )
        if existing is None:
            raise
        return {"evaluation": existing, "result": result, "idempotent_reuse": True}
    db.commit()
    db.refresh(row)
    return {"evaluation": row, "result": result, "idempotent_reuse": False}


@router.get("/scores")
def score_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(
                select(SourcingScoreEvaluation)
                .where(SourcingScoreEvaluation.owner_id == owner.id)
                .order_by(SourcingScoreEvaluation.created_at)
            )
        )
    }


@router.post("/critic")
def critic_evaluate(data: dict[str, object]):
    return {"findings": build_critic(data)}


@router.post("/rules/evaluate")
def rules_evaluate(data: RuleEvaluate, db: DB, owner: Owner):
    get_owned(db, SourcingRequirement, owner.id, data.requirement_id)
    result = evaluate_rules(data.inputs, data.rules)
    row = SourcingRuleEvaluation(
        owner_id=owner.id, requirement_id=data.requirement_id, payload=result
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"evaluation": row, "result": result}


@router.post("/decision-engine")
def decision_engine(data: dict[str, object]):
    findings = cast(list[Mapping[str, Any]], build_critic(data))
    score_raw = data.get("score")
    score = float(score_raw) if isinstance(score_raw, (int, float)) else None
    supplier_raw = data.get("supplier_count")
    supplier_count = int(supplier_raw) if isinstance(supplier_raw, (int, float)) else None
    return {
        "classification": sourcing_decision(
            score,
            hard_block=bool(data.get("hard_block")),
            critic_findings=findings,
            confidence=str(data.get("confidence", "INSUFFICIENT")),
        ),
        "critic": findings,
        "concentration": concentration(supplier_count, bool(data.get("evidence_sufficient", True))),
    }


@router.post("/concentration")
def concentration_evaluate(data: dict[str, object]):
    supplier_raw = data.get("supplier_count")
    supplier_count = int(supplier_raw) if isinstance(supplier_raw, (int, float)) else None
    return {
        "classification": concentration(supplier_count, bool(data.get("evidence_sufficient", True)))
    }


@router.post("/negotiations/delta")
def negotiation_delta_calculate(data: dict[str, object]):
    previous = data.get("previous")
    current = data.get("current")
    return negotiation_delta(
        previous if isinstance(previous, Mapping) else {},
        current if isinstance(current, Mapping) else {},
    )


@router.post("/calendar", status_code=201)
def calendar_create(data: CalendarCreate, db: DB, owner: Owner):
    existing = db.scalar(
        select(SourcingCalendarItem).where(
            SourcingCalendarItem.owner_id == owner.id,
            SourcingCalendarItem.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return existing
    row = SourcingCalendarItem(owner_id=owner.id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/calendar")
def calendar_list(db: DB, owner: Owner):
    return {
        "items": list(
            db.scalars(
                select(SourcingCalendarItem)
                .where(SourcingCalendarItem.owner_id == owner.id)
                .order_by(SourcingCalendarItem.due_at)
            )
        )
    }


@router.get("/product-channel/{product_id}")
def sourcing_product_channel(product_id: uuid.UUID, db: DB, owner: Owner):
    from vayujit_api.products.models import Product

    get_owned(db, Product, owner.id, product_id)
    requirement = db.scalar(
        select(SourcingRequirement)
        .where(
            SourcingRequirement.owner_id == owner.id, SourcingRequirement.product_id == product_id
        )
        .order_by(SourcingRequirement.created_at.desc())
    )
    rfqs = (
        list(
            db.scalars(
                select(RequestForQuote).where(
                    RequestForQuote.owner_id == owner.id,
                    RequestForQuote.requirement_id == requirement.id,
                )
            )
        )
        if requirement
        else []
    )
    return {
        "product_id": str(product_id),
        "research_status": "available",
        "supplier_status": "available" if requirement else "not_started",
        "rfq_status": rfqs[-1].status if rfqs else "not_started",
        "quote_status": "available" if rfqs else "not_started",
        "sample_status": "available" if rfqs else "not_started",
        "inspection_status": "available" if rfqs else "not_started",
        "economics_status": "available" if rfqs else "not_started",
        "sourcing_decision": "review_required",
    }


@router.get("/history/unified")
def unified_history(db: DB, owner: Owner):
    tables = (
        ("requirement", SourcingRequirement),
        ("rfq", RequestForQuote),
        ("quote", SupplierQuote),
        ("negotiation", NegotiationRound),
        ("score", SourcingScoreEvaluation),
        ("sample", Sample),
        ("inspection", Inspection),
        ("scenario", CostScenario),
        ("decision", SourcingDecision),
        (
            "recovery",
            __import__(
                "vayujit_api.intelligence.sourcing_models", fromlist=["SourcingRecoveryRecord"]
            ).SourcingRecoveryRecord,
        ),
    )
    items = []
    for kind, model in tables:
        for row in db.scalars(select(model).where(model.owner_id == owner.id)):
            item = dump(row)
            item["kind"] = kind
            items.append(item)
    items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"items": items}


@router.get("/report/{format}")
def sourcing_report(format: str, db: DB, owner: Owner):
    payload = {
        "requirement": sourcing_overview(db, owner),
        "rfq": "local_manual_only",
        "supplier": "owner_scoped",
        "quote": "manual_local",
        "economics": "deterministic_assumptions_only",
        "decision": "human_approval_required",
        "evidence": "metadata_references_only",
        "assumptions": "explicit_and_local",
    }
    try:
        return safe_report(payload, format)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/storage/inventory")
def storage_inventory():
    return {
        "tables": [
            "intelligence_sourcing_requirements",
            "intelligence_sourcing_requirement_versions",
            "intelligence_rfqs",
            "intelligence_rfq_versions",
            "intelligence_rfq_suppliers",
            "intelligence_rfq_drafts",
            "intelligence_supplier_quotes",
            "intelligence_supplier_quote_lines",
            "intelligence_supplier_quote_versions",
            "intelligence_sample_requests",
            "intelligence_samples",
            "intelligence_sample_evaluations",
            "intelligence_inspections",
            "intelligence_inspection_findings",
            "intelligence_negotiation_rounds",
            "intelligence_cost_scenarios",
            "intelligence_landed_cost_estimates",
            "intelligence_logistics_estimates",
            "intelligence_duty_tax_assumptions",
            "intelligence_fx_assumptions",
            "intelligence_sourcing_assumption_versions",
            "intelligence_sourcing_score_evaluations",
            "intelligence_sourcing_rule_evaluations",
            "intelligence_sourcing_decisions",
            "intelligence_sourcing_approvals",
            "intelligence_sourcing_worker_jobs",
            "intelligence_sourcing_recovery_records",
            "intelligence_sourcing_calendar_items",
        ]
    }
