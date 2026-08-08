"""Owner-scoped Marketplace Commerce Core API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vayujit_api.ai.models import GeneratedArtifact
from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand
from vayujit_api.commerce.connector import connector_for
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceCategory,
    MarketplaceInventory,
    MarketplaceListing,
    MarketplaceOrder,
    MarketplaceSettlement,
)
from vayujit_api.commerce.schemas import (
    AccountCreate,
    AccountResponse,
    AnalyticsResponse,
    CategoryResponse,
    ConnectorResult,
    DriftResponse,
    InventoryResponse,
    InventoryUpdate,
    ListingCreate,
    ListingResponse,
    ListingUpdate,
    OrderResponse,
    SettlementResponse,
    capabilities_for,
)
from vayujit_api.commerce.service import (
    account_or_none,
    capabilities,
    create_categories,
    encrypt_credentials,
    idempotent_resource,
    import_fake_order,
    import_fake_settlement,
    remember_idempotency,
    safe_drift,
)
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/marketplaces", tags=["marketplaces"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


def account_response(row: MarketplaceAccount) -> AccountResponse:
    return AccountResponse(
        id=row.id,
        marketplace=row.marketplace,
        display_name=row.display_name,
        seller_account_id=row.seller_account_id,
        environment=row.environment,
        enabled=row.enabled,
        credential_status=row.credential_status,
        validation_status=row.validation_status,
        last_validated_at=row.last_validated_at,
        capabilities=capabilities_for(row.marketplace),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def listing_response(row: MarketplaceListing) -> ListingResponse:
    return ListingResponse.model_validate(row, from_attributes=True)


def ensure_account(db: Session, user: User, account_id: uuid.UUID) -> MarketplaceAccount:
    row = account_or_none(db, user.id, account_id)
    if row is None:
        raise HTTPException(404, "Marketplace account was not found.")
    return row


@router.get("/capabilities")
def marketplace_capabilities() -> dict[str, object]:
    return {key: capabilities(key) for key in ("amazon", "flipkart", "meesho", "shopify")}


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(db: DatabaseSession, user: Owner) -> list[AccountResponse]:
    rows = db.scalars(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == user.id)
        .order_by(MarketplaceAccount.created_at.desc())
    ).all()
    return [account_response(row) for row in rows]


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(data: AccountCreate, db: DatabaseSession, user: Owner) -> AccountResponse:
    stamp = now()
    try:
        encrypted = encrypt_credentials(data.credentials)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    row = MarketplaceAccount(
        owner_id=user.id,
        marketplace=data.marketplace.value,
        display_name=data.display_name.strip(),
        seller_account_id=data.seller_account_id.strip(),
        environment=data.environment,
        enabled=False,
        credential_status="configured" if encrypted else "missing",
        encrypted_credentials=encrypted,
        validation_status="unknown",
        capabilities_json=capabilities(data.marketplace.value),
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    try:
        db.flush()
    except Exception as error:
        db.rollback()
        raise HTTPException(
            409, "A marketplace account with these identifiers already exists."
        ) from error
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.account_created",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"marketplace": row.marketplace, "environment": row.environment},
    )
    db.commit()
    return account_response(row)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> AccountResponse:
    return account_response(ensure_account(db, user, account_id))


@router.post("/accounts/{account_id}/validate", response_model=AccountResponse)
def validate_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> AccountResponse:
    row = ensure_account(db, user, account_id)
    result = connector_for(row.marketplace).validate_account(row.seller_account_id)
    row.validation_status = "valid" if result["valid"] else "invalid"
    row.last_validated_at = now()
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.account_validated",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"marketplace": row.marketplace, "valid": bool(result["valid"])},
    )
    db.commit()
    return account_response(row)


@router.post("/accounts/{account_id}/enable", response_model=AccountResponse)
def enable_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> AccountResponse:
    row = ensure_account(db, user, account_id)
    if row.validation_status != "valid":
        raise HTTPException(409, "Validate the marketplace account before enabling it.")
    row.enabled = True
    row.updated_at = now()
    db.commit()
    return account_response(row)


@router.post("/accounts/{account_id}/disable", response_model=AccountResponse)
def disable_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> AccountResponse:
    row = ensure_account(db, user, account_id)
    row.enabled = False
    row.updated_at = now()
    db.commit()
    return account_response(row)


@router.post("/accounts/{account_id}/remove-credential", response_model=AccountResponse)
def remove_credential(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> AccountResponse:
    row = ensure_account(db, user, account_id)
    row.encrypted_credentials = None
    row.credential_status = "missing"
    row.enabled = False
    row.updated_at = now()
    db.commit()
    return account_response(row)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> None:
    row = ensure_account(db, user, account_id)
    db.delete(row)
    db.commit()


@router.get("/categories", response_model=list[CategoryResponse])
def categories(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> list[CategoryResponse]:
    account = ensure_account(db, user, account_id)
    rows = db.scalars(
        select(MarketplaceCategory)
        .where(
            MarketplaceCategory.owner_id == user.id, MarketplaceCategory.account_id == account.id
        )
        .order_by(MarketplaceCategory.name)
    ).all()
    if not rows:
        rows = create_categories(db, account)
        db.commit()
    return [
        CategoryResponse(
            id=row.id,
            remote_id=row.remote_id,
            name=row.name,
            parent_remote_id=row.parent_remote_id,
            attributes=[],
        )
        for row in rows
    ]


@router.get("/listings", response_model=list[ListingResponse])
def list_listings(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    status: str | None = None,
    product_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(50, ge=1, le=100),
) -> list[ListingResponse]:
    query = select(MarketplaceListing).where(MarketplaceListing.owner_id == user.id)
    if marketplace:
        query = query.where(MarketplaceListing.marketplace == marketplace)
    if status:
        query = query.where(MarketplaceListing.status == status)
    if product_id:
        query = query.where(MarketplaceListing.product_id == product_id)
    if brand_id:
        query = query.where(MarketplaceListing.brand_id == brand_id)
    rows = db.scalars(
        query.order_by(MarketplaceListing.updated_at.desc()).offset(offset).limit(limit)
    ).all()
    return [listing_response(row) for row in rows]


@router.post("/listings", response_model=ListingResponse, status_code=201)
def create_listing(data: ListingCreate, db: DatabaseSession, user: Owner) -> ListingResponse:
    account = ensure_account(db, user, data.account_id)
    brand = db.scalar(select(Brand).where(Brand.id == data.brand_id, Brand.owner_id == user.id))
    product = db.scalar(
        select(Product).where(
            Product.id == data.product_id,
            Product.owner_id == user.id,
            Product.brand_id == data.brand_id,
        )
    )
    if brand is None or product is None:
        raise HTTPException(404, "Brand or Product was not found.")
    artifact = None
    if data.artifact_id:
        artifact = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == data.artifact_id,
                GeneratedArtifact.owner_id == user.id,
                GeneratedArtifact.product_id == data.product_id,
            )
        )
        if artifact is None or artifact.status != "approved":
            raise HTTPException(
                409, "Only an approved content artifact can be attached to a listing."
            )
    previous = idempotent_resource(db, user.id, account.id, "listing:create", data.idempotency_key)
    if previous:
        existing = db.scalar(
            select(MarketplaceListing).where(
                MarketplaceListing.id == previous, MarketplaceListing.owner_id == user.id
            )
        )
        if existing:
            return listing_response(existing)
    stamp = now()
    remote = connector_for(account.marketplace).create_listing(
        title=data.title,
        sku=data.marketplace_sku,
        idempotency_key=data.idempotency_key or str(uuid.uuid4()),
    )
    row = MarketplaceListing(
        owner_id=user.id,
        brand_id=brand.id,
        product_id=product.id,
        account_id=account.id,
        marketplace=account.marketplace,
        local_listing_id=f"local-{uuid.uuid4().hex[:16]}",
        remote_listing_id=str(remote["remote_id"]),
        marketplace_sku=str(remote["remote_sku"]),
        title=data.title.strip(),
        description_source="artifact" if artifact else "product",
        category=data.category,
        status="active",
        publication_state="active",
        external_url=str(remote["url"]),
        raw_safe_status="active",
        remote_created_at=stamp,
        remote_updated_at=stamp,
        last_synchronized_at=stamp,
        drift_state="none",
        content_artifact_id=artifact.id if artifact else None,
        safe_metadata_json={},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    remember_idempotency(
        db,
        owner_id=user.id,
        account_id=account.id,
        operation="listing:create",
        key=data.idempotency_key,
        resource_type="listing",
        resource_id=row.id,
    )
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.listing_created",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"marketplace": row.marketplace, "product_id": str(product.id)},
    )
    db.commit()
    return listing_response(row)


@router.get("/listings/{listing_id}", response_model=ListingResponse)
def get_listing(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> ListingResponse:
    row = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id, MarketplaceListing.owner_id == user.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace listing was not found.")
    return listing_response(row)


@router.patch("/listings/{listing_id}", response_model=ListingResponse)
def update_listing(
    listing_id: uuid.UUID, data: ListingUpdate, db: DatabaseSession, user: Owner
) -> ListingResponse:
    row = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id, MarketplaceListing.owner_id == user.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace listing was not found.")
    previous = idempotent_resource(
        db, user.id, row.account_id, "listing:update", data.idempotency_key
    )
    if previous:
        return listing_response(row)
    remote = connector_for(row.marketplace).update_listing(
        remote_id=row.remote_listing_id or str(row.id), title=data.title, sku=data.marketplace_sku
    )
    if data.title is not None:
        row.title = data.title.strip()
    if data.category is not None:
        row.category = data.category
    if data.marketplace_sku is not None:
        row.marketplace_sku = data.marketplace_sku
    if data.status is not None:
        row.status = data.status
    row.remote_updated_at = now()
    row.last_synchronized_at = now()
    row.updated_at = now()
    db.flush()
    remember_idempotency(
        db,
        owner_id=user.id,
        account_id=row.account_id,
        operation="listing:update",
        key=data.idempotency_key,
        resource_type="listing",
        resource_id=row.id,
    )
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.listing_updated",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"marketplace": row.marketplace, "status": str(remote.get("status", row.status))},
    )
    db.commit()
    return listing_response(row)


@router.post("/listings/{listing_id}/preview")
def preview_listing(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    row = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id, MarketplaceListing.owner_id == user.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace listing was not found.")
    return connector_for(row.marketplace).preview_listing(title=row.title, sku=row.marketplace_sku)


@router.post("/listings/{listing_id}/reconcile", response_model=DriftResponse)
def reconcile_listing(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> DriftResponse:
    row = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id, MarketplaceListing.owner_id == user.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace listing was not found.")
    remote = connector_for(row.marketplace).reconcile_listing(row.remote_listing_id or str(row.id))
    fields = safe_drift(db, row, remote)
    row.last_synchronized_at = now()
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.listing_reconciled",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={
            "marketplace": row.marketplace,
            "drift_fields": [field.field_name for field in fields],
        },
    )
    db.commit()
    return DriftResponse(
        listing_id=row.id,
        drift_state=row.drift_state,
        fields=[{"field": field.field_name, "state": field.state} for field in fields],
    )


@router.post("/listings/{listing_id}/archive", response_model=ListingResponse)
def archive_listing(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> ListingResponse:
    row = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id, MarketplaceListing.owner_id == user.id
        )
    )
    if row is None:
        raise HTTPException(404, "Marketplace listing was not found.")
    row.status = "archived"
    row.publication_state = "archived"
    row.updated_at = now()
    db.commit()
    return listing_response(row)


@router.get("/inventory", response_model=list[InventoryResponse])
def list_inventory(
    db: DatabaseSession,
    user: Owner,
    marketplace: str | None = None,
    low_stock: bool = False,
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(50, ge=1, le=100),
) -> list[InventoryResponse]:
    query = select(MarketplaceInventory).where(MarketplaceInventory.owner_id == user.id)
    if low_stock:
        query = query.where(MarketplaceInventory.available_quantity <= 5)
    rows = db.scalars(
        query.order_by(MarketplaceInventory.updated_at.desc()).offset(offset).limit(limit)
    ).all()
    return [InventoryResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/inventory", response_model=InventoryResponse)
def update_inventory(data: InventoryUpdate, db: DatabaseSession, user: Owner) -> InventoryResponse:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == data.listing_id, MarketplaceListing.owner_id == user.id
        )
    )
    if listing is None:
        raise HTTPException(404, "Marketplace listing was not found.")
    if data.idempotency_key and idempotent_resource(
        db, user.id, listing.account_id, "inventory:update", data.idempotency_key
    ):
        row = db.scalar(
            select(MarketplaceInventory).where(
                MarketplaceInventory.listing_id == listing.id,
                MarketplaceInventory.variant_id == data.variant_id,
            )
        )
        if row:
            return InventoryResponse.model_validate(row, from_attributes=True)
    connector_for(listing.marketplace).update_inventory(
        listing.remote_listing_id or str(listing.id), data.available_quantity
    )
    row = db.scalar(
        select(MarketplaceInventory).where(
            MarketplaceInventory.listing_id == listing.id,
            MarketplaceInventory.variant_id == data.variant_id,
        )
    )
    if row is None:
        row = MarketplaceInventory(
            owner_id=user.id,
            listing_id=listing.id,
            variant_id=data.variant_id,
            product_id=listing.product_id,
            available_quantity=data.available_quantity,
            reserved_quantity=data.reserved_quantity,
            marketplace_reported_quantity=data.available_quantity,
            local_target_quantity=data.available_quantity,
            synchronization_status="synced",
            last_synchronized_at=now(),
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)
    else:
        row.available_quantity = data.available_quantity
        row.reserved_quantity = data.reserved_quantity
        row.marketplace_reported_quantity = data.available_quantity
        row.local_target_quantity = data.available_quantity
        row.synchronization_status = "synced"
        row.last_synchronized_at = now()
        row.updated_at = now()
    db.flush()
    remember_idempotency(
        db,
        owner_id=user.id,
        account_id=listing.account_id,
        operation="inventory:update",
        key=data.idempotency_key,
        resource_type="inventory",
        resource_id=row.id,
    )
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.inventory_updated",
        entity_type="marketplace_inventory",
        entity_id=row.id,
        metadata={"listing_id": str(listing.id)},
    )
    db.commit()
    return InventoryResponse.model_validate(row, from_attributes=True)


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    db: DatabaseSession,
    user: Owner,
    account_id: uuid.UUID | None = None,
    status: str | None = None,
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(50, ge=1, le=100),
) -> list[OrderResponse]:
    query = select(MarketplaceOrder).where(MarketplaceOrder.owner_id == user.id)
    if account_id:
        query = query.where(MarketplaceOrder.account_id == account_id)
    if status:
        query = query.where(MarketplaceOrder.status == status)
    rows = db.scalars(
        query.order_by(MarketplaceOrder.ordered_at.desc()).offset(offset).limit(limit)
    ).all()
    return [
        OrderResponse(
            id=row.id,
            account_id=row.account_id,
            marketplace=row.marketplace,
            remote_order_id=row.remote_order_id,
            status=row.status,
            payment_status=row.payment_status,
            fulfilment_status=row.fulfilment_status,
            totals=row.totals_json,
            ordered_at=row.ordered_at,
            buyer_summary={"display_name": "Masked buyer"},
        )
        for row in rows
    ]


@router.post("/orders/import", response_model=ConnectorResult)
def import_orders(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> ConnectorResult:
    account = ensure_account(db, user, account_id)
    order = import_fake_order(db, account)
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.orders_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata={"count": 1, "marketplace": account.marketplace},
    )
    db.commit()
    return ConnectorResult(status="succeeded", message="Orders imported.", resource_id=order.id)


@router.get("/settlements", response_model=list[SettlementResponse])
def list_settlements(
    db: DatabaseSession,
    user: Owner,
    account_id: uuid.UUID | None = None,
    offset: int = Query(0, ge=0, le=100_000),
    limit: int = Query(50, ge=1, le=100),
) -> list[SettlementResponse]:
    query = select(MarketplaceSettlement).where(MarketplaceSettlement.owner_id == user.id)
    if account_id:
        query = query.where(MarketplaceSettlement.account_id == account_id)
    rows = db.scalars(
        query.order_by(MarketplaceSettlement.period_end.desc()).offset(offset).limit(limit)
    ).all()
    return [SettlementResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/settlements/import", response_model=ConnectorResult)
def import_settlements(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> ConnectorResult:
    account = ensure_account(db, user, account_id)
    settlement = import_fake_settlement(db, account)
    record_event(
        db,
        actor_id=user.id,
        action="marketplace.settlement_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata={"count": 1, "marketplace": account.marketplace},
    )
    db.commit()
    return ConnectorResult(
        status="succeeded", message="Settlement imported.", resource_id=settlement.id
    )


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(db: DatabaseSession, user: Owner) -> AnalyticsResponse:
    settlements = db.scalars(
        select(MarketplaceSettlement).where(MarketplaceSettlement.owner_id == user.id)
    ).all()
    from decimal import Decimal

    gross = sum((row.gross_amount for row in settlements), start=Decimal("0"))
    fees = sum((row.fee_amount for row in settlements), start=Decimal("0"))
    refunds = sum((row.refund_amount for row in settlements), start=Decimal("0"))
    active = (
        db.scalar(
            select(func.count(MarketplaceListing.id)).where(
                MarketplaceListing.owner_id == user.id, MarketplaceListing.status == "active"
            )
        )
        or 0
    )
    low = (
        db.scalar(
            select(func.count(MarketplaceInventory.id)).where(
                MarketplaceInventory.owner_id == user.id,
                MarketplaceInventory.available_quantity <= 5,
            )
        )
        or 0
    )
    orders = (
        db.scalar(
            select(func.count(MarketplaceOrder.id)).where(MarketplaceOrder.owner_id == user.id)
        )
        or 0
    )
    return AnalyticsResponse(
        gross_sales=gross,
        fees=fees,
        refunds=refunds,
        net_contribution=gross - fees - refunds,
        estimated_profit=None,
        profit_status="unavailable",
        order_count=orders,
        active_listing_count=active,
        low_stock_count=low,
        sales_by_marketplace={},
    )
