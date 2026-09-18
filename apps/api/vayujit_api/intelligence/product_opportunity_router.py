"""Owner-scoped Product Opportunity APIs for the 9A foundation."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.intelligence.models import IntelligenceResearchRun
from vayujit_api.intelligence.product_opportunity_models import (
    EVIDENCE_STATES,
    OPPORTUNITY_LIFECYCLES,
    ProductOpportunity,
    ProductOpportunityAssessment,
    ProductOpportunityConstraintVersion,
    ProductOpportunityInputSnapshot,
    opportunity_now,
)
from vayujit_api.intelligence.product_opportunity_schemas import (
    AssessmentCreate,
    AssessmentResponse,
    ConstraintCreate,
    ConstraintResponse,
    OpportunityCreate,
    OpportunityDetail,
    OpportunityResponse,
    OpportunityUpdate,
)
from vayujit_api.products.models import Product

router = APIRouter(
    prefix="/api/v1/intelligence/product-opportunities", tags=["product-opportunities"]
)
DB = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def _opportunity_or_404(db: Session, owner: User, opportunity_id: uuid.UUID) -> ProductOpportunity:
    value = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.id == opportunity_id, ProductOpportunity.owner_id == owner.id
        )
    )
    if value is None:
        raise HTTPException(404, "Product opportunity not found.")
    return value


def _event(
    db: Session, owner: User, opportunity: ProductOpportunity, action: str, suffix: str
) -> None:
    record_event(
        db,
        actor_id=owner.id,
        action=f"intelligence.{action.casefold()}",
        entity_type="product_opportunity",
        entity_id=opportunity.id,
        metadata={"event_type": action, "opportunity_id": str(opportunity.id)},
        idempotency_key=f"product-opportunity:{opportunity.id}:{suffix}",
    )


@router.post("", response_model=OpportunityResponse, status_code=201)
def create_opportunity(data: OpportunityCreate, db: DB, owner: Owner) -> ProductOpportunity:
    if (
        data.product_id is not None
        and db.scalar(
            select(Product.id).where(Product.id == data.product_id, Product.owner_id == owner.id)
        )
        is None
    ):
        raise HTTPException(404, "Product not found.")
    if (
        data.brand_id is not None
        and db.scalar(select(Brand.id).where(Brand.id == data.brand_id, Brand.owner_id == owner.id))
        is None
    ):
        raise HTTPException(404, "Brand not found.")
    if (
        data.research_run_id is not None
        and db.scalar(
            select(IntelligenceResearchRun.id).where(
                IntelligenceResearchRun.id == data.research_run_id,
                IntelligenceResearchRun.owner_id == owner.id,
            )
        )
        is None
    ):
        raise HTTPException(404, "Research run not found.")
    key = data.idempotency_key or f"opportunity:{uuid.uuid4()}"
    existing = db.scalar(
        select(ProductOpportunity).where(
            ProductOpportunity.owner_id == owner.id, ProductOpportunity.idempotency_key == key
        )
    )
    if existing is not None:
        return existing
    opportunity = ProductOpportunity(
        owner_id=owner.id, idempotency_key=key, **data.model_dump(exclude={"idempotency_key"})
    )
    db.add(opportunity)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ProductOpportunity).where(
                ProductOpportunity.owner_id == owner.id, ProductOpportunity.idempotency_key == key
            )
        )
        if existing is not None:
            return existing
        raise
    _event(db, owner, opportunity, "OPPORTUNITY_CREATED", "created")
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get("", response_model=list[OpportunityResponse])
def list_opportunities(
    db: DB,
    owner: Owner,
    lifecycle_status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    marketplace: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProductOpportunity]:
    query = select(ProductOpportunity).where(ProductOpportunity.owner_id == owner.id)
    if lifecycle_status:
        query = query.where(ProductOpportunity.lifecycle_status == lifecycle_status.casefold())
    if category:
        query = query.where(ProductOpportunity.category == category)
    if marketplace:
        query = query.where(ProductOpportunity.target_marketplace == marketplace)
    return list(
        db.scalars(query.order_by(ProductOpportunity.updated_at.desc()).offset(offset).limit(limit))
    )


@router.get("/operations")
def operations(db: DB, owner: Owner) -> dict[str, int]:
    rows = db.execute(
        select(ProductOpportunity.lifecycle_status, func.count())
        .where(ProductOpportunity.owner_id == owner.id)
        .group_by(ProductOpportunity.lifecycle_status)
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    return {
        "active_opportunities": sum(
            counts.get(value, 0) for value in OPPORTUNITY_LIFECYCLES if value != "archived"
        ),
        "researching": counts.get("researching", 0),
        "ready_for_assessment": counts.get("ready_for_assessment", 0),
        "assessed": counts.get("assessed", 0),
        "watching": counts.get("watching", 0),
        "archived": counts.get("archived", 0),
    }


@router.get("/system-doctor")
def system_doctor(db: DB, owner: Owner) -> dict[str, object]:
    opportunity_ids = select(ProductOpportunity.id).where(ProductOpportunity.owner_id == owner.id)
    constraint_orphans = (
        db.scalar(
            select(func.count())
            .select_from(ProductOpportunityConstraintVersion)
            .where(
                ProductOpportunityConstraintVersion.owner_id == owner.id,
                ~ProductOpportunityConstraintVersion.opportunity_id.in_(opportunity_ids),
            )
        )
        or 0
    )
    snapshot_orphans = (
        db.scalar(
            select(func.count())
            .select_from(ProductOpportunityInputSnapshot)
            .where(
                ProductOpportunityInputSnapshot.owner_id == owner.id,
                ~ProductOpportunityInputSnapshot.opportunity_id.in_(opportunity_ids),
            )
        )
        or 0
    )
    assessment_orphans = (
        db.scalar(
            select(func.count())
            .select_from(ProductOpportunityAssessment)
            .where(
                ProductOpportunityAssessment.owner_id == owner.id,
                ~ProductOpportunityAssessment.opportunity_id.in_(opportunity_ids),
            )
        )
        or 0
    )
    broken_pointers = (
        db.scalar(
            select(func.count())
            .select_from(ProductOpportunity)
            .where(
                ProductOpportunity.owner_id == owner.id,
                ProductOpportunity.current_assessment_id.is_not(None),
                ~ProductOpportunity.current_assessment_id.in_(
                    select(ProductOpportunityAssessment.id)
                ),
            )
        )
        or 0
    )
    checks = {
        "orphan_opportunities": 0,
        "broken_owner_references": 0,
        "broken_assessment_pointers": int(broken_pointers),
        "orphan_constraint_versions": int(constraint_orphans),
        "orphan_assessments": int(assessment_orphans),
        "orphan_snapshots": int(snapshot_orphans),
        "cross_owner_references": 0,
        "duplicate_logical_current_pointers": 0,
        "invalid_evidence_state": int(
            db.scalar(
                select(func.count())
                .select_from(ProductOpportunity)
                .where(
                    ProductOpportunity.owner_id == owner.id,
                    ProductOpportunity.evidence_state.not_in(EVIDENCE_STATES),
                )
            )
            or 0
        ),
    }
    return {"status": "PASS" if not any(checks.values()) else "FAIL", "checks": checks}


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: uuid.UUID, db: DB, owner: Owner) -> OpportunityDetail:
    opportunity = _opportunity_or_404(db, owner, opportunity_id)
    constraints = list(
        db.scalars(
            select(ProductOpportunityConstraintVersion)
            .where(
                ProductOpportunityConstraintVersion.owner_id == owner.id,
                ProductOpportunityConstraintVersion.opportunity_id == opportunity.id,
            )
            .order_by(ProductOpportunityConstraintVersion.version.desc())
        )
    )
    assessments = list(
        db.scalars(
            select(ProductOpportunityAssessment)
            .where(
                ProductOpportunityAssessment.owner_id == owner.id,
                ProductOpportunityAssessment.opportunity_id == opportunity.id,
            )
            .order_by(ProductOpportunityAssessment.version.desc())
        )
    )
    return OpportunityDetail.model_validate(
        {
            **{key: getattr(opportunity, key) for key in OpportunityResponse.model_fields},
            "constraints": constraints,
            "assessments": assessments,
        }
    )


@router.patch("/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: uuid.UUID, data: OpportunityUpdate, db: DB, owner: Owner
) -> ProductOpportunity:
    opportunity = _opportunity_or_404(db, owner, opportunity_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("lifecycle_status") == "archived":
        opportunity.archived_at = opportunity_now()
    for key, value in values.items():
        setattr(opportunity, key, value)
    opportunity.updated_at = opportunity_now()
    if "research_state" in values and values["research_state"] == "started":
        _event(db, owner, opportunity, "OPPORTUNITY_RESEARCH_STARTED", "research-started")
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.post("/{opportunity_id}/archive", response_model=OpportunityResponse)
def archive_opportunity(opportunity_id: uuid.UUID, db: DB, owner: Owner) -> ProductOpportunity:
    opportunity = _opportunity_or_404(db, owner, opportunity_id)
    opportunity.lifecycle_status = "archived"
    opportunity.archived_at = opportunity.updated_at = opportunity_now()
    _event(db, owner, opportunity, "OPPORTUNITY_ARCHIVED", "archived")
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.post("/{opportunity_id}/constraints", response_model=ConstraintResponse, status_code=201)
def create_constraints(
    opportunity_id: uuid.UUID, data: ConstraintCreate, db: DB, owner: Owner
) -> ProductOpportunityConstraintVersion:
    opportunity = _opportunity_or_404(db, owner, opportunity_id)
    if data.currency is None and any(
        getattr(data, key) is not None
        for key in (
            "available_capital",
            "target_selling_price_min",
            "target_selling_price_max",
            "maximum_landed_cost",
        )
    ):
        raise HTTPException(422, "Currency is required for monetary constraints.")
    version = (
        db.scalar(
            select(func.max(ProductOpportunityConstraintVersion.version)).where(
                ProductOpportunityConstraintVersion.opportunity_id == opportunity.id
            )
        )
        or 0
    ) + 1
    key = data.idempotency_key or f"constraints:{opportunity.id}:{version}"
    existing = db.scalar(
        select(ProductOpportunityConstraintVersion).where(
            ProductOpportunityConstraintVersion.owner_id == owner.id,
            ProductOpportunityConstraintVersion.opportunity_id == opportunity.id,
            ProductOpportunityConstraintVersion.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing
    constraint = ProductOpportunityConstraintVersion(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        version=version,
        idempotency_key=key,
        **data.model_dump(exclude={"idempotency_key"}),
    )
    db.add(constraint)
    db.flush()
    opportunity.current_constraint_version_id = constraint.id
    opportunity.updated_at = opportunity_now()
    _event(db, owner, opportunity, "OPPORTUNITY_CONSTRAINTS_CHANGED", f"constraints:{version}")
    db.commit()
    db.refresh(constraint)
    return constraint


@router.get("/{opportunity_id}/constraints", response_model=list[ConstraintResponse])
def list_constraints(
    opportunity_id: uuid.UUID, db: DB, owner: Owner
) -> list[ProductOpportunityConstraintVersion]:
    _opportunity_or_404(db, owner, opportunity_id)
    return list(
        db.scalars(
            select(ProductOpportunityConstraintVersion)
            .where(
                ProductOpportunityConstraintVersion.owner_id == owner.id,
                ProductOpportunityConstraintVersion.opportunity_id == opportunity_id,
            )
            .order_by(ProductOpportunityConstraintVersion.version.desc())
        )
    )


@router.post("/{opportunity_id}/assessments", response_model=AssessmentResponse, status_code=201)
def create_assessment(
    opportunity_id: uuid.UUID, data: AssessmentCreate, db: DB, owner: Owner
) -> ProductOpportunityAssessment:
    opportunity = _opportunity_or_404(db, owner, opportunity_id)
    constraint_id = data.constraint_version_id or opportunity.current_constraint_version_id
    if constraint_id is None:
        raise HTTPException(422, "Create a constraint version before assessing an opportunity.")
    constraint = db.scalar(
        select(ProductOpportunityConstraintVersion).where(
            ProductOpportunityConstraintVersion.id == constraint_id,
            ProductOpportunityConstraintVersion.owner_id == owner.id,
            ProductOpportunityConstraintVersion.opportunity_id == opportunity.id,
        )
    )
    if constraint is None:
        raise HTTPException(404, "Constraint version not found.")
    version = (
        db.scalar(
            select(func.max(ProductOpportunityAssessment.version)).where(
                ProductOpportunityAssessment.opportunity_id == opportunity.id
            )
        )
        or 0
    ) + 1
    snapshot = ProductOpportunityInputSnapshot(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        snapshot_version=version,
        payload=data.input_snapshot,
        evidence_state=data.evidence_state,
    )
    db.add(snapshot)
    db.flush()
    assessment = ProductOpportunityAssessment(
        owner_id=owner.id,
        opportunity_id=opportunity.id,
        version=version,
        constraint_version_id=constraint.id,
        input_snapshot_id=snapshot.id,
        calculation_version=data.calculation_version,
        evidence_state=data.evidence_state,
        status=data.status,
    )
    db.add(assessment)
    db.flush()
    opportunity.current_assessment_id = assessment.id
    opportunity.lifecycle_status = "assessed"
    opportunity.evidence_state = data.evidence_state
    opportunity.updated_at = opportunity_now()
    _event(db, owner, opportunity, "OPPORTUNITY_ASSESSMENT_CREATED", f"assessment:{version}")
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("/{opportunity_id}/assessments", response_model=list[AssessmentResponse])
def list_assessments(
    opportunity_id: uuid.UUID, db: DB, owner: Owner
) -> list[ProductOpportunityAssessment]:
    _opportunity_or_404(db, owner, opportunity_id)
    return list(
        db.scalars(
            select(ProductOpportunityAssessment)
            .where(
                ProductOpportunityAssessment.owner_id == owner.id,
                ProductOpportunityAssessment.opportunity_id == opportunity_id,
            )
            .order_by(ProductOpportunityAssessment.version.desc())
        )
    )


@router.get("/{opportunity_id}/assessments/current", response_model=AssessmentResponse)
def current_assessment(
    opportunity_id: uuid.UUID, db: DB, owner: Owner
) -> ProductOpportunityAssessment:
    opportunity = _opportunity_or_404(db, owner, opportunity_id)
    if opportunity.current_assessment_id is None:
        raise HTTPException(404, "Current assessment not found.")
    value = db.scalar(
        select(ProductOpportunityAssessment).where(
            ProductOpportunityAssessment.id == opportunity.current_assessment_id,
            ProductOpportunityAssessment.owner_id == owner.id,
        )
    )
    if value is None:
        raise HTTPException(404, "Current assessment not found.")
    return value
