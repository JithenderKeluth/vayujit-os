"""Repository/service operations for the owner-scoped 8E.1 foundation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.identity.models import User
from vayujit_api.intelligence.cross_marketplace_models import CrossMarketplaceSupplier
from vayujit_api.intelligence.portfolio_models import (
    SupplierPortfolioAssessmentVersion,
    SupplierPortfolioContext,
    SupplierPortfolioInputSnapshot,
    SupplierPortfolioMembership,
)
from vayujit_api.intelligence.portfolio_schemas import (
    AssessmentCreate,
    PortfolioCreate,
    PortfolioMemberCreate,
    PortfolioPatch,
)


def now() -> datetime:
    return datetime.now(UTC)


def portfolio_or_404(db: Session, owner: User, portfolio_id: uuid.UUID) -> SupplierPortfolioContext:
    row = db.scalar(
        select(SupplierPortfolioContext).where(
            SupplierPortfolioContext.id == portfolio_id,
            SupplierPortfolioContext.owner_id == owner.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Supplier portfolio not found.")
    return row


def _portfolio_payload(row: SupplierPortfolioContext) -> dict[str, object]:
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "scope_type": row.scope_type,
        "scope_reference": row.scope_reference,
        "status": row.status,
        "current_assessment_version_id": (
            str(row.current_assessment_version_id)
            if row.current_assessment_version_id is not None
            else None
        ),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def create_portfolio(
    db: Session, owner: User, data: PortfolioCreate
) -> tuple[dict[str, object], bool]:
    existing = db.scalar(
        select(SupplierPortfolioContext).where(
            SupplierPortfolioContext.owner_id == owner.id,
            SupplierPortfolioContext.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return _portfolio_payload(existing), True
    stamp = now()
    row = SupplierPortfolioContext(
        owner_id=owner.id,
        name=data.name.strip(),
        description=data.description.strip(),
        scope_type=data.scope_type,
        scope_reference=data.scope_reference,
        status="active",
        idempotency_key=data.idempotency_key,
        created_at=stamp,
        updated_at=stamp,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SupplierPortfolioContext).where(
                SupplierPortfolioContext.owner_id == owner.id,
                SupplierPortfolioContext.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return _portfolio_payload(existing), True
    db.commit()
    db.refresh(row)
    return _portfolio_payload(row), False


def list_portfolios(db: Session, owner: User) -> list[dict[str, object]]:
    rows = db.scalars(
        select(SupplierPortfolioContext)
        .where(SupplierPortfolioContext.owner_id == owner.id)
        .order_by(SupplierPortfolioContext.created_at, SupplierPortfolioContext.id)
    )
    return [_portfolio_payload(row) for row in rows]


def portfolio_detail(row: SupplierPortfolioContext) -> dict[str, object]:
    return _portfolio_payload(row)


def update_portfolio(
    db: Session, owner: User, row: SupplierPortfolioContext, data: PortfolioPatch
) -> dict[str, object]:
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None or key == "scope_reference":
            setattr(row, key, value)
    row.updated_at = now()
    db.commit()
    db.refresh(row)
    return _portfolio_payload(row)


def _member_payload(row: SupplierPortfolioMembership) -> dict[str, object]:
    return {
        "id": str(row.id),
        "portfolio_id": str(row.portfolio_id),
        "supplier_id": str(row.supplier_id),
        "version": row.version,
        "associated_products": row.associated_products,
        "associated_opportunities": row.associated_opportunities,
        "shortlist_lineage_id": str(row.shortlist_lineage_id) if row.shortlist_lineage_id else None,
        "due_diligence_lineage_id": (
            str(row.due_diligence_lineage_id) if row.due_diligence_lineage_id else None
        ),
        "sourcing_scenario_lineage_id": (
            str(row.sourcing_scenario_lineage_id) if row.sourcing_scenario_lineage_id else None
        ),
        "allocation_percent": (
            str(row.allocation_percent) if row.allocation_percent is not None else None
        ),
        "evidence_freshness": row.evidence_freshness,
        "confidence": str(row.confidence) if row.confidence is not None else None,
        "risk": row.risk,
        "country_region": row.country_region,
        "capabilities": row.capabilities,
        "alternate_source_status": row.alternate_source_status,
    }


def add_member(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, data: PortfolioMemberCreate
) -> dict[str, object]:
    supplier = db.scalar(
        select(CrossMarketplaceSupplier).where(
            CrossMarketplaceSupplier.id == data.supplier_id,
            CrossMarketplaceSupplier.owner_id == owner.id,
        )
    )
    if supplier is None:
        raise HTTPException(404, "Supplier is not available in the owner scope.")
    row = SupplierPortfolioMembership(
        owner_id=owner.id,
        portfolio_id=portfolio.id,
        supplier_id=supplier.id,
        version=data.version,
        associated_products=[str(value) for value in data.associated_products],
        associated_opportunities=[str(value) for value in data.associated_opportunities],
        shortlist_lineage_id=data.shortlist_lineage_id,
        due_diligence_lineage_id=data.due_diligence_lineage_id,
        sourcing_scenario_lineage_id=data.sourcing_scenario_lineage_id,
        allocation_percent=data.allocation_percent,
        evidence_freshness=data.evidence_freshness,
        confidence=data.confidence,
        risk=data.risk,
        country_region=data.country_region,
        capabilities=data.capabilities,
        alternate_source_status=data.alternate_source_status,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as error:
        raise HTTPException(409, "Portfolio membership version already exists.") from error
    db.commit()
    db.refresh(row)
    return _member_payload(row)


def list_members(
    db: Session, owner: User, portfolio: SupplierPortfolioContext
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(SupplierPortfolioMembership)
        .where(
            SupplierPortfolioMembership.owner_id == owner.id,
            SupplierPortfolioMembership.portfolio_id == portfolio.id,
        )
        .order_by(SupplierPortfolioMembership.version, SupplierPortfolioMembership.created_at)
    )
    return [_member_payload(row) for row in rows]


def _assessment_payload(row: SupplierPortfolioAssessmentVersion) -> dict[str, object]:
    return {
        "id": str(row.id),
        "portfolio_id": str(row.portfolio_id),
        "version": row.version,
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "input_snapshot": row.input_snapshot,
        "created_at": row.created_at.isoformat(),
    }


def create_assessment(
    db: Session, owner: User, portfolio: SupplierPortfolioContext, data: AssessmentCreate
) -> tuple[dict[str, object], bool]:
    existing = db.scalar(
        select(SupplierPortfolioAssessmentVersion).where(
            SupplierPortfolioAssessmentVersion.owner_id == owner.id,
            SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id,
            SupplierPortfolioAssessmentVersion.idempotency_key == data.idempotency_key,
        )
    )
    if existing:
        return _assessment_payload(existing), True
    memberships = list_members(db, owner, portfolio)
    snapshot: dict[str, Any] = {
        "portfolio": _portfolio_payload(portfolio),
        "memberships": memberships,
        "provided": data.input_snapshot,
    }
    latest = db.scalar(
        select(SupplierPortfolioAssessmentVersion.version)
        .where(SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id)
        .order_by(SupplierPortfolioAssessmentVersion.version.desc())
        .limit(1)
    )
    row = SupplierPortfolioAssessmentVersion(
        owner_id=owner.id,
        portfolio_id=portfolio.id,
        version=(latest or 0) + 1,
        idempotency_key=data.idempotency_key,
        status="created",
        input_snapshot=snapshot,
        created_at=now(),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
            db.add(
                SupplierPortfolioInputSnapshot(
                    owner_id=owner.id,
                    portfolio_id=portfolio.id,
                    assessment_version_id=row.id,
                    snapshot=snapshot,
                    created_at=now(),
                )
            )
            portfolio.current_assessment_version_id = row.id
            portfolio.updated_at = now()
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(SupplierPortfolioAssessmentVersion).where(
                SupplierPortfolioAssessmentVersion.owner_id == owner.id,
                SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id,
                SupplierPortfolioAssessmentVersion.idempotency_key == data.idempotency_key,
            )
        )
        if existing is None:
            raise
        return _assessment_payload(existing), True
    db.commit()
    db.refresh(row)
    return _assessment_payload(row), False


def current_assessment(
    db: Session, owner: User, portfolio: SupplierPortfolioContext
) -> dict[str, object] | None:
    if portfolio.current_assessment_version_id is None:
        return None
    row = db.scalar(
        select(SupplierPortfolioAssessmentVersion).where(
            SupplierPortfolioAssessmentVersion.id == portfolio.current_assessment_version_id,
            SupplierPortfolioAssessmentVersion.owner_id == owner.id,
            SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id,
        )
    )
    return _assessment_payload(row) if row else None


def assessment_history(
    db: Session, owner: User, portfolio: SupplierPortfolioContext
) -> list[dict[str, object]]:
    rows = db.scalars(
        select(SupplierPortfolioAssessmentVersion)
        .where(
            SupplierPortfolioAssessmentVersion.owner_id == owner.id,
            SupplierPortfolioAssessmentVersion.portfolio_id == portfolio.id,
        )
        .order_by(SupplierPortfolioAssessmentVersion.version)
    )
    return [_assessment_payload(row) for row in rows]
