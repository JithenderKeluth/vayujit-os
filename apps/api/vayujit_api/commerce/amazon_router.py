"""Owner-scoped Amazon Marketplace API using the transport-injected adapter."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
)
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceFee,
    MarketplaceInventory,
    MarketplaceListing,
    MarketplaceOrder,
)
from vayujit_api.commerce.service import encrypt_credentials
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now

router = APIRouter(prefix="/api/v1/marketplaces/amazon", tags=["amazon"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


class AmazonAccountCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    seller_account_id: str = Field(min_length=1, max_length=160)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    environment: str = Field(default="sandbox", pattern="^(sandbox|production)$")
    credentials: dict[str, str] = Field(default_factory=dict, max_length=12)


class AmazonSubmitRequest(BaseModel):
    product_type: str = Field(min_length=1, max_length=100)
    attributes: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)


class AmazonPreviewRequest(BaseModel):
    product_type: str | None = Field(default=None, max_length=100)
    attributes: dict[str, Any] = Field(default_factory=dict)
    media_count: int = Field(default=0, ge=0, le=100)


class AmazonInventoryUpdateRequest(BaseModel):
    quantity: int = Field(ge=0, le=10_000_000)
    confirm: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


def _account(db: Session, user: User, account_id: uuid.UUID) -> MarketplaceAccount:
    row = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id,
            MarketplaceAccount.owner_id == user.id,
            MarketplaceAccount.marketplace == "amazon",
        )
    )
    if row is None:
        raise HTTPException(404, "Amazon account was not found.")
    return row


def _connector(account: MarketplaceAccount) -> AmazonCommerceConnector:
    config = account.configuration_json or {}
    country_code = str(config.get("country_code", "IN"))
    return AmazonCommerceConnector(
        seller_id=account.seller_account_id,
        marketplace=amazon_marketplace(country_code),
        transport=FakeAmazonSPAPITransport(),
    )


def _safe_account(row: MarketplaceAccount) -> dict[str, object]:
    config = row.configuration_json or {}
    marketplace = amazon_marketplace(str(config.get("country_code", "IN")))
    return {
        "id": row.id,
        "marketplace": "amazon",
        "display_name": row.display_name,
        "seller_account_id": row.seller_account_id,
        "environment": row.environment,
        "enabled": row.enabled,
        "credential_status": row.credential_status,
        "validation_status": row.validation_status,
        "country_code": marketplace.country_code,
        "marketplace_id": marketplace.marketplace_id,
        "currency": marketplace.currency,
        "locale": marketplace.locale,
        "endpoint_region": marketplace.endpoint_region,
        "capabilities": [
            "listing_preview",
            "listing_submit",
            "listing_reconcile",
            "inventory_read",
            "inventory_update",
            "orders_import",
            "financial_events_import",
        ],
    }


@router.get("/marketplaces")
def marketplaces() -> list[dict[str, str]]:
    return [
        {
            "country_code": item.country_code,
            "marketplace_id": item.marketplace_id,
            "currency": item.currency,
            "locale": item.locale,
            "endpoint_region": item.endpoint_region,
        }
        for item in _connector(
            MarketplaceAccount(
                seller_account_id="fake",
                configuration_json={"country_code": "IN"},
            )
        ).discover_marketplaces()
    ]


@router.post("/accounts", status_code=201)
def create_account(
    data: AmazonAccountCreate, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    try:
        marketplace = amazon_marketplace(data.country_code)
        encrypted = encrypt_credentials(data.credentials)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    stamp = now()
    row = MarketplaceAccount(
        owner_id=user.id,
        marketplace="amazon",
        display_name=data.display_name.strip(),
        seller_account_id=data.seller_account_id.strip(),
        environment=data.environment,
        enabled=False,
        credential_status="configured" if encrypted else "missing",
        encrypted_credentials=encrypted,
        validation_status="unknown",
        capabilities_json={
            "operations": [
                "listing_preview",
                "listing_submit",
                "listing_reconcile",
                "inventory_read",
                "inventory_update",
                "orders_import",
                "financial_events_import",
            ]
        },
        configuration_json={
            "country_code": marketplace.country_code,
            "marketplace_id": marketplace.marketplace_id,
            "currency": marketplace.currency,
            "locale": marketplace.locale,
            "endpoint_region": marketplace.endpoint_region,
            "endpoint_host": marketplace.endpoint_host,
            "credential_precedence": [
                "encrypted_account",
                "deployment_environment",
                "unconfigured",
            ],
        },
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    try:
        db.flush()
    except Exception as error:
        db.rollback()
        raise HTTPException(
            409, "An Amazon account with these identifiers already exists."
        ) from error
    record_event(
        db,
        actor_id=user.id,
        action="amazon.account_configured",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"country_code": marketplace.country_code, "environment": row.environment},
    )
    db.commit()
    return _safe_account(row)


@router.get("/accounts/{account_id}")
def get_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    return _safe_account(_account(db, user, account_id))


@router.post("/accounts/{account_id}/validate")
def validate_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    row = _account(db, user, account_id)
    result = _connector(row).validate_account(row.seller_account_id)
    row.validation_status = "valid" if result["valid"] else "invalid"
    row.last_validated_at = now()
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.account_validated",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"valid": bool(result["valid"])},
    )
    db.commit()
    return _safe_account(row)


@router.get("/accounts/{account_id}/product-types")
def product_types(
    account_id: uuid.UUID,
    db: DatabaseSession,
    user: Owner,
    search: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    account = _account(db, user, account_id)
    return _connector(account).discover_product_types(search=search, offset=offset, limit=limit)


@router.get("/accounts/{account_id}/product-types/{product_type}/attributes")
def product_type_attributes(
    account_id: uuid.UUID,
    product_type: str,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    account = _account(db, user, account_id)
    supported = {item["id"] for item in _connector(account).discover_product_types()}
    if product_type not in supported:
        raise HTTPException(404, "Amazon product type was not found.")
    attributes = [
        {"key": "item_name", "label": "Item name", "type": "string", "required": True},
        {"key": "brand", "label": "Brand", "type": "string", "required": True},
        {"key": "manufacturer", "label": "Manufacturer", "type": "string", "required": True},
        {"key": "bullet_point", "label": "Bullet point", "type": "string", "required": False},
    ]
    return {
        "product_type": product_type,
        "marketplace_id": _connector(account).marketplace.marketplace_id,
        "attributes": attributes,
    }


@router.get("/accounts/{account_id}/diagnostics")
def diagnostics(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    account = _account(db, user, account_id)
    result = _connector(account).validate_account(account.seller_account_id)
    return {
        "configured": account.credential_status == "configured",
        "validation_status": account.validation_status,
        "transport_validation": bool(result["valid"]),
        "marketplace": _safe_account(account),
        "recent_throttles": 0,
        "recent_ambiguous_results": 0,
        "real_amazon_validation": "not_performed",
    }


@router.post("/listings/{listing_id}/preview")
def preview_listing(
    listing_id: uuid.UUID,
    data: AmazonPreviewRequest,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    account = _account(db, user, listing.account_id)
    approved = False
    if listing.content_artifact_id:
        approved = (
            db.scalar(
                select(GeneratedArtifact.id).where(
                    GeneratedArtifact.id == listing.content_artifact_id,
                    GeneratedArtifact.owner_id == user.id,
                    GeneratedArtifact.product_id == listing.product_id,
                    GeneratedArtifact.status == "approved",
                )
            )
            is not None
        )
    result = _connector(account).preview(
        title=listing.title,
        sku=listing.marketplace_sku,
        product_type=data.product_type,
        attributes=data.attributes,
        approved=approved,
        media_count=data.media_count,
    )
    record_event(
        db,
        actor_id=user.id,
        action="amazon.listing_previewed",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"ready": bool(result["ready"])},
    )
    db.commit()
    return result


@router.post("/listings/{listing_id}/submit")
def submit_listing(
    listing_id: uuid.UUID,
    data: AmazonSubmitRequest,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    account = _account(db, user, listing.account_id)
    if listing.content_artifact_id is None:
        raise HTTPException(
            409, "An approved Amazon content Artifact is required before submission."
        )
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == listing.content_artifact_id,
            GeneratedArtifact.owner_id == user.id,
            GeneratedArtifact.product_id == listing.product_id,
        )
    )
    if artifact is None or artifact.status != "approved":
        raise HTTPException(
            409, "An approved Amazon content Artifact is required before submission."
        )
    result = _connector(account).submit(
        sku=listing.marketplace_sku or f"VJ-{listing.id.hex[:10]}",
        payload={
            "title": listing.title,
            "product_type": data.product_type,
            "attributes": data.attributes,
            "artifact_version": artifact.version_number,
        },
        idempotency_key=data.idempotency_key,
    )
    if result.status in {"accepted", "succeeded"}:
        listing.remote_listing_id = result.remote_id
        listing.status = "submitting"
        listing.publication_state = "processing"
        listing.raw_safe_status = result.remote_status
    elif result.status == "rejected":
        listing.status = "rejected"
        listing.publication_state = "rejected"
    else:
        listing.status = "error"
        listing.publication_state = "error"
    listing.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.listing_submitted",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"status": result.status, "remote_status": result.remote_status},
    )
    db.commit()
    return {
        "status": result.status,
        "remote_listing_id": result.remote_id,
        "remote_status": result.remote_status,
        "retryable": result.retryable,
        "ambiguous": result.ambiguous,
        "issues": [
            {"code": issue.code, "message": issue.message, "retryable": issue.retryable}
            for issue in result.issues
        ],
    }


@router.post("/listings/{listing_id}/reconcile")
def reconcile_listing(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None or not listing.remote_listing_id:
        raise HTTPException(404, "Amazon listing remote identifier was not found.")
    account = _account(db, user, listing.account_id)
    result = _connector(account).reconcile_listing(listing.remote_listing_id)
    status = {"ACTIVE": "active", "PROCESSING": "submitting", "REJECTED": "rejected"}.get(
        cast(str, result.get("status", "unknown")), "error"
    )
    listing.status = status
    listing.publication_state = status
    listing.raw_safe_status = str(result.get("status", "unknown"))
    listing.last_synchronized_at = now()
    listing.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.listing_reconciled",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"status": status},
    )
    db.commit()
    return {"status": status, "remote_listing_id": listing.remote_listing_id}


@router.get("/listings/{listing_id}/inventory")
def inventory(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    account = _account(db, user, listing.account_id)
    result = _connector(account).get_inventory(listing.marketplace_sku or "")
    quantity_value = result.get("quantity")
    quantity = int(quantity_value) if isinstance(quantity_value, (int, str)) else None
    row = db.scalar(
        select(MarketplaceInventory).where(MarketplaceInventory.listing_id == listing.id)
    )
    if row is None:
        row = MarketplaceInventory(
            owner_id=user.id,
            listing_id=listing.id,
            variant_id=None,
            product_id=listing.product_id,
            available_quantity=quantity or 0,
            reserved_quantity=0,
            marketplace_reported_quantity=quantity,
            local_target_quantity=None,
            synchronization_status="synced" if quantity is not None else "unavailable",
            last_synchronized_at=now(),
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
    else:
        row.marketplace_reported_quantity = quantity
        row.synchronization_status = "synced" if quantity is not None else "unavailable"
        row.last_synchronized_at = now()
        row.updated_at = now()
    db.commit()
    return {
        "listing_id": listing.id,
        "quantity": quantity,
        "synchronization_status": row.synchronization_status,
    }


@router.post("/listings/{listing_id}/inventory")
def update_inventory(
    listing_id: uuid.UUID,
    data: AmazonInventoryUpdateRequest,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required for Amazon inventory updates.")
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    account = _account(db, user, listing.account_id)
    result = _connector(account).update_inventory(listing.marketplace_sku or "", data.quantity)
    record_event(
        db,
        actor_id=user.id,
        action="amazon.inventory_updated",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"quantity": data.quantity},
    )
    db.commit()
    return {"status": "succeeded", "quantity": result.get("quantity")}


@router.post("/accounts/{account_id}/orders/import")
def import_orders(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    imported = 0
    for item in _connector(account).get_orders():
        existing = db.scalar(
            select(MarketplaceOrder).where(
                MarketplaceOrder.account_id == account.id,
                MarketplaceOrder.remote_order_id == str(item["order_id"]),
            )
        )
        if existing is None:
            db.add(
                MarketplaceOrder(
                    owner_id=user.id,
                    account_id=account.id,
                    marketplace="amazon",
                    remote_order_id=str(item["order_id"]),
                    status="confirmed",
                    payment_status="paid",
                    fulfilment_status="unfulfilled",
                    buyer_snapshot_json={"display_name": "Masked buyer"},
                    totals_json={"total": str(item["total"]), "currency": str(item["currency"])},
                    ordered_at=now(),
                    remote_raw_status=str(item["status"]),
                    created_at=now(),
                    updated_at=now(),
                )
            )
            imported += 1
    record_event(
        db,
        actor_id=user.id,
        action="amazon.orders_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata={"count": imported},
    )
    db.commit()
    return {"imported": imported}


@router.post("/accounts/{account_id}/financial-events/import")
def import_financial_events(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> dict[str, int]:
    account = _account(db, user, account_id)
    imported = 0
    for item in _connector(account).get_fees():
        db.add(
            MarketplaceFee(
                owner_id=user.id,
                account_id=account.id,
                order_id=None,
                settlement_id=None,
                fee_type="commission",
                amount=Decimal(str(item["amount"])),
                currency=str(item["currency"]),
                description="Amazon commission",
                occurred_at=now(),
                created_at=now(),
                updated_at=now(),
            )
        )
        imported += 1
    record_event(
        db,
        actor_id=user.id,
        action="amazon.financial_events_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata={"count": imported},
    )
    db.commit()
    return {"imported": imported}
