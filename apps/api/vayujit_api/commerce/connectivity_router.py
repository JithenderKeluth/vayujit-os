"""Read-only Amazon India and Flipkart connectivity certification surface.

The router is intentionally provider-neutral at the API boundary and reuses
the existing marketplace account, connector, order, inventory, settlement,
and reconciliation authorities.  Only the deterministic ``SYNTHETIC`` mode
executes locally.  ``SANDBOX`` and ``LIVE_READ_ONLY`` fail closed until a
separately authorized provider transport and seller account are configured.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.commerce.connector import connector_for
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceImportJob,
    MarketplaceInventory,
    MarketplaceListing,
    MarketplaceOrder,
    MarketplaceSettlement,
)
from vayujit_api.commerce.service import (
    account_or_none,
    create_categories,
    import_fake_order,
    import_fake_settlement,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now

router = APIRouter(prefix="/api/v1/marketplaces", tags=["marketplace-connectivity"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]

Operation = Literal["catalog", "orders", "inventory", "financial"]
Mode = Literal["SYNTHETIC", "SANDBOX", "LIVE_READ_ONLY"]


class ImportRequest(BaseModel):
    operation: Operation
    mode: Mode = "SYNTHETIC"
    idempotency_key: str = Field(min_length=1, max_length=240)


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    marketplace: str
    operation: str
    mode: str
    status: str
    idempotency_key: str
    correlation_id: str
    checkpoint_json: dict[str, object]
    summary_json: dict[str, object]
    provenance_json: dict[str, object]
    pages_fetched: int
    records_seen: int
    records_imported: int
    records_reused: int
    error_code: str | None
    error_message: str | None
    started_at: object | None
    completed_at: object | None
    last_successful_sync: object | None
    stale_after: object | None
    created_at: object
    updated_at: object


def _response(row: MarketplaceImportJob) -> ImportJobResponse:
    return ImportJobResponse.model_validate(row, from_attributes=True)


def _account(db: Session, user: User, account_id: uuid.UUID) -> MarketplaceAccount:
    row = account_or_none(db, user.id, account_id)
    if row is None:
        raise HTTPException(404, "Marketplace account was not found.")
    if row.marketplace not in {"amazon", "flipkart"}:
        raise HTTPException(422, "PR-SOS-08 currently supports Amazon and Flipkart only.")
    return row


def _capability(provider: str) -> dict[str, object]:
    return {
        "provider": provider,
        "regions": ["IN"],
        "transport_modes": ["SYNTHETIC"],
        "supported_operations": ["catalog", "orders", "inventory", "financial"],
        "repo_supported": True,
        "synthetic_fixture": True,
        "official_contract": "UNVERIFIED",
        "sandbox": "NOT_CONFIGURED",
        "live_read_only": "NOT_CONFIGURED",
        "live_write": "DENIED",
        "external_activation_required": True,
    }


@router.get("/connectivity/capabilities")
def connectivity_capabilities() -> dict[str, object]:
    return {
        "providers": [_capability("amazon"), _capability("flipkart")],
        "authority": "MarketplaceAccount + existing provider adapters",
        "default_mode": "SYNTHETIC",
        "external_writes": False,
    }


@router.get("/accounts/{account_id}/connectivity")
def connectivity_status(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    account = _account(db, user, account_id)
    latest = db.scalar(
        select(MarketplaceImportJob)
        .where(
            MarketplaceImportJob.owner_id == user.id,
            MarketplaceImportJob.account_id == account.id,
            MarketplaceImportJob.status == "SUCCEEDED",
        )
        .order_by(MarketplaceImportJob.completed_at.desc())
    )
    if account.encrypted_credentials is None:
        state = "AUTHORIZATION_REQUIRED"
    elif account.validation_status == "expired":
        state = "EXPIRED"
    elif account.validation_status == "invalid":
        state = "DEGRADED"
    else:
        state = "UNVERIFIED"
    return {
        "account_id": str(account.id),
        "marketplace": account.marketplace,
        "environment": account.environment,
        "connection_state": state,
        "permission_state": "UNVERIFIED",
        "credential_status": account.credential_status,
        "validation_status": account.validation_status,
        "transport_mode": "SYNTHETIC",
        "last_successful_sync": latest.completed_at if latest else None,
        "external_writes": False,
        "provider_contract": "UNVERIFIED",
    }


@router.get("/accounts/{account_id}/import-jobs", response_model=list[ImportJobResponse])
def import_jobs(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> list[ImportJobResponse]:
    account = _account(db, user, account_id)
    rows = db.scalars(
        select(MarketplaceImportJob)
        .where(
            MarketplaceImportJob.owner_id == user.id,
            MarketplaceImportJob.account_id == account.id,
        )
        .order_by(MarketplaceImportJob.created_at.desc())
        .limit(100)
    ).all()
    return [_response(row) for row in rows]


def _execute_synthetic(db: Session, account: MarketplaceAccount, job: MarketplaceImportJob) -> None:
    stamp = now()
    connector = connector_for(account.marketplace, seller_id=account.seller_account_id)
    summary: dict[str, object] = {
        "provider": account.marketplace,
        "operation": job.operation,
        "mode": job.mode,
        "transport": "deterministic_fake",
        "external_writes": False,
        "reconciliation": "review_required",
    }
    if job.operation == "catalog":
        categories = create_categories(db, account)
        listing_count = int(
            db.scalar(
                select(func.count(MarketplaceListing.id)).where(
                    MarketplaceListing.owner_id == account.owner_id,
                    MarketplaceListing.account_id == account.id,
                )
            )
            or 0
        )
        job.pages_fetched = 1
        job.records_seen = len(categories) + listing_count
        job.records_imported = len(categories)
        job.records_reused = max(0, listing_count)
        summary.update(
            {
                "categories_observed": len(categories),
                "canonical_listings_observed": listing_count,
                "canonical_authority": "MarketplaceCategory/MarketplaceListing",
            }
        )
    elif job.operation == "orders":
        before = int(
            db.scalar(
                select(func.count(MarketplaceOrder.id)).where(
                    MarketplaceOrder.owner_id == account.owner_id,
                    MarketplaceOrder.account_id == account.id,
                )
            )
            or 0
        )
        order = import_fake_order(db, account)
        after = before + (1 if before == 0 else 0)
        job.pages_fetched = 1
        job.records_seen = 1
        job.records_imported = max(0, after - before)
        job.records_reused = 1 - job.records_imported
        summary.update(
            {
                "remote_order_id": order.remote_order_id,
                "canonical_authority": "MarketplaceOrder/MarketplaceOrderItem",
            }
        )
    elif job.operation == "inventory":
        listings = db.scalars(
            select(MarketplaceListing)
            .where(
                MarketplaceListing.owner_id == account.owner_id,
                MarketplaceListing.account_id == account.id,
            )
            .order_by(MarketplaceListing.created_at)
            .limit(100)
        ).all()
        observations: list[dict[str, object]] = []
        for listing in listings:
            remote_id = listing.remote_listing_id or listing.local_listing_id
            observations.append(
                {
                    "listing_id": str(listing.id),
                    "remote_id": remote_id,
                    "observation": connector.get_inventory(remote_id),
                }
            )
        listing_ids = [row.id for row in listings]
        inventory_rows = 0
        if listing_ids:
            inventory_rows = int(
                db.scalar(
                    select(func.count(MarketplaceInventory.id)).where(
                        MarketplaceInventory.owner_id == account.owner_id,
                        MarketplaceInventory.listing_id.in_(listing_ids),
                    )
                )
                or 0
            )
        job.pages_fetched = 1
        job.records_seen = len(observations)
        job.records_imported = 0
        job.records_reused = inventory_rows
        summary.update(
            {
                "observations": observations,
                "canonical_inventory_rows": inventory_rows,
                "canonical_authority": "MarketplaceInventory/InventoryItem",
                "write_policy": "no canonical quantity overwrite",
            }
        )
    else:
        before = int(
            db.scalar(
                select(func.count(MarketplaceSettlement.id)).where(
                    MarketplaceSettlement.owner_id == account.owner_id,
                    MarketplaceSettlement.account_id == account.id,
                )
            )
            or 0
        )
        settlement = import_fake_settlement(db, account)
        after = before + (1 if before == 0 else 0)
        job.pages_fetched = 1
        job.records_seen = 1
        job.records_imported = max(0, after - before)
        job.records_reused = 1 - job.records_imported
        summary.update(
            {
                "remote_settlement_id": settlement.remote_settlement_id,
                "currency": settlement.currency,
                "canonical_authority": "MarketplaceSettlement/MarketplaceSettlementLine",
                "financial_values": "observed synthetic fixture only",
            }
        )
    job.summary_json = summary
    job.checkpoint_json = {"page": 1, "complete": True}
    job.provenance_json = {
        "provider": account.marketplace,
        "account_id": str(account.id),
        "mode": "SYNTHETIC",
        "source": "deterministic_fake_connector",
        "captured_at": stamp.isoformat(),
        "external_writes": False,
    }


@router.post(
    "/accounts/{account_id}/imports",
    response_model=ImportJobResponse,
    status_code=202,
)
def start_import(
    account_id: uuid.UUID,
    data: ImportRequest,
    db: DatabaseSession,
    user: Owner,
) -> ImportJobResponse:
    account = _account(db, user, account_id)
    # External transports are a separate authorization boundary.  Check the
    # mode before idempotency replay so an external request can never inherit
    # a successful local fixture job that happens to reuse its key.
    if data.mode != "SYNTHETIC":
        raise HTTPException(
            409,
            (
                "External provider authorization is required; SANDBOX and "
                "LIVE_READ_ONLY are not configured."
            ),
            headers={"X-VAYUJIT-External-Write": "denied"},
        )
    existing = db.scalar(
        select(MarketplaceImportJob).where(
            MarketplaceImportJob.owner_id == user.id,
            MarketplaceImportJob.account_id == account.id,
            MarketplaceImportJob.operation == data.operation,
            MarketplaceImportJob.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return _response(existing)
    stamp = now()
    job = MarketplaceImportJob(
        owner_id=user.id,
        account_id=account.id,
        marketplace=account.marketplace,
        operation=data.operation,
        mode="SYNTHETIC",
        status="RUNNING",
        idempotency_key=data.idempotency_key,
        correlation_id=str(uuid.uuid4()),
        started_at=stamp,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(job)
    db.flush()
    try:
        _execute_synthetic(db, account, job)
        job.status = "SUCCEEDED"
        job.completed_at = now()
        job.last_successful_sync = job.completed_at
        job.stale_after = job.completed_at + timedelta(hours=24)
        record_event(
            db,
            actor_id=user.id,
            action="marketplace.import_completed",
            entity_type="marketplace_import_job",
            entity_id=job.id,
            metadata={
                "marketplace": account.marketplace,
                "operation": job.operation,
                "mode": job.mode,
                "records_imported": job.records_imported,
            },
        )
    except Exception as error:  # pragma: no cover - defensive fail-closed path
        job.status = "FAILED"
        job.error_code = "IMPORT_FAILED"
        job.error_message = str(error)[:500]
        job.completed_at = now()
    job.updated_at = now()
    db.commit()
    return _response(job)


@router.get(
    "/accounts/{account_id}/imports/{job_id}",
    response_model=ImportJobResponse,
)
def get_import(
    account_id: uuid.UUID, job_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> ImportJobResponse:
    account = _account(db, user, account_id)
    row = db.scalar(
        select(MarketplaceImportJob).where(
            MarketplaceImportJob.id == job_id,
            MarketplaceImportJob.owner_id == user.id,
            MarketplaceImportJob.account_id == account.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Import job was not found.")
    return _response(row)


@router.post(
    "/accounts/{account_id}/imports/{job_id}/cancel",
    response_model=ImportJobResponse,
)
def cancel_import(
    account_id: uuid.UUID, job_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> ImportJobResponse:
    account = _account(db, user, account_id)
    row = db.scalar(
        select(MarketplaceImportJob).where(
            MarketplaceImportJob.id == job_id,
            MarketplaceImportJob.owner_id == user.id,
            MarketplaceImportJob.account_id == account.id,
        )
    )
    if row is None:
        raise HTTPException(404, "Import job was not found.")
    if row.status not in {"PENDING", "RUNNING"}:
        raise HTTPException(409, "Only pending or running imports can be cancelled.")
    row.status = "CANCELLED"
    row.completed_at = now()
    row.updated_at = now()
    db.commit()
    return _response(row)


@router.get("/accounts/{account_id}/reconciliation")
def reconciliation(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    account = _account(db, user, account_id)
    listing_count = int(
        db.scalar(
            select(func.count(MarketplaceListing.id)).where(
                MarketplaceListing.owner_id == user.id,
                MarketplaceListing.account_id == account.id,
            )
        )
        or 0
    )
    inventory_count = int(
        db.scalar(
            select(func.count(MarketplaceInventory.id)).where(
                MarketplaceInventory.owner_id == user.id,
                MarketplaceInventory.listing_id.in_(
                    select(MarketplaceListing.id).where(
                        MarketplaceListing.owner_id == user.id,
                        MarketplaceListing.account_id == account.id,
                    )
                ),
            )
        )
        or 0
    )
    order_count = int(
        db.scalar(
            select(func.count(MarketplaceOrder.id)).where(
                MarketplaceOrder.owner_id == user.id,
                MarketplaceOrder.account_id == account.id,
            )
        )
        or 0
    )
    settlement_count = int(
        db.scalar(
            select(func.count(MarketplaceSettlement.id)).where(
                MarketplaceSettlement.owner_id == user.id,
                MarketplaceSettlement.account_id == account.id,
            )
        )
        or 0
    )
    jobs = db.scalars(
        select(MarketplaceImportJob)
        .where(
            MarketplaceImportJob.owner_id == user.id, MarketplaceImportJob.account_id == account.id
        )
        .order_by(MarketplaceImportJob.created_at.desc())
        .limit(100)
    ).all()
    latest_by_operation: dict[str, MarketplaceImportJob] = {}
    latest_failed_by_operation: dict[str, MarketplaceImportJob] = {}
    for job in jobs:
        latest_by_operation.setdefault(job.operation, job)
        if job.status in {"FAILED", "PARTIAL"}:
            latest_failed_by_operation.setdefault(job.operation, job)
    stale_operations: list[str] = []
    freshness: dict[str, str] = {}
    imported_counts: dict[str, int] = {}
    exceptions: list[str] = []
    current_time = now()
    for operation in ("catalog", "orders", "inventory", "financial"):
        latest = latest_by_operation.get(operation)
        if (
            latest is None
            or latest.status != "SUCCEEDED"
            or latest.stale_after is None
            or latest.stale_after < current_time
        ):
            stale_operations.append(operation)
        if latest is None:
            freshness[operation] = "NOT_IMPORTED"
            imported_counts[operation] = 0
        elif latest.status != "SUCCEEDED":
            freshness[operation] = latest.status
            imported_counts[operation] = latest.records_imported
        elif latest.stale_after is not None and latest.stale_after < current_time:
            freshness[operation] = "STALE"
            imported_counts[operation] = latest.records_imported
        else:
            freshness[operation] = "FRESH"
            imported_counts[operation] = latest.records_imported
        failed = latest_failed_by_operation.get(operation)
        if failed is not None:
            detail = failed.error_message or "Import requires review."
            exceptions.append(f"{operation}: {detail}")
    next_action = (
        "Review failed or partial import evidence before retrying manually."
        if exceptions
        else (
            "Run the missing or stale synthetic imports, then review reconciliation."
            if stale_operations
            else "Review import evidence and reconcile exceptions manually."
        )
    )
    return {
        "account_id": str(account.id),
        "marketplace": account.marketplace,
        "canonical_counts": {
            "listings": listing_count,
            "inventory": inventory_count,
            "orders": order_count,
            "settlements": settlement_count,
        },
        "latest_imports": {
            operation: _response(job).model_dump(mode="json")
            for operation, job in latest_by_operation.items()
        },
        "last_failed_imports": {
            operation: _response(job).model_dump(mode="json")
            for operation, job in latest_failed_by_operation.items()
        },
        "freshness": freshness,
        "imported_counts": imported_counts,
        "stale_operations": stale_operations,
        "exceptions": exceptions,
        "automatic_mutations": False,
        "next_action": next_action,
    }
