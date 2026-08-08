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
from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event
from vayujit_api.commerce.amazon import (
    AmazonCommerceConnector,
    AmazonMediaPolicy,
    AmazonPricingPolicy,
    AmazonVariantPolicy,
    FakeAmazonSPAPITransport,
    amazon_marketplace,
)
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceDriftRecord,
    MarketplaceFee,
    MarketplaceFulfilment,
    MarketplaceInventory,
    MarketplaceListing,
    MarketplaceMediaMapping,
    MarketplaceOrder,
    MarketplaceOrderItem,
    MarketplacePrice,
    MarketplaceRefund,
    MarketplaceReturn,
    MarketplaceSettlement,
    MarketplaceSettlementLine,
    MarketplaceVariant,
)
from vayujit_api.commerce.service import encrypt_credentials
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/marketplaces/amazon", tags=["amazon"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


class AmazonAccountCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    seller_account_id: str = Field(min_length=1, max_length=160)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    environment: str = Field(default="sandbox", pattern="^(sandbox|production)$")
    credentials: dict[str, str] = Field(default_factory=dict, max_length=12)


class AmazonCredentialReplace(BaseModel):
    credentials: dict[str, str] = Field(default_factory=dict, max_length=12)


class AmazonAccountToggle(BaseModel):
    confirm: bool = False


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


class AmazonMediaItem(BaseModel):
    media_id: uuid.UUID
    position: int = Field(ge=0, le=20)
    alt_text: str = Field(default="", max_length=500)


class AmazonMediaRequest(BaseModel):
    media: list[AmazonMediaItem] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=200)


class AmazonVariantsRequest(BaseModel):
    variants: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)


class AmazonPriceRequest(BaseModel):
    list_price: Decimal | None = Field(default=None, ge=0)
    selling_price: Decimal = Field(ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(min_length=3, max_length=3)
    confirm: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


class AmazonDriftActionRequest(BaseModel):
    confirm: bool = False
    expected_remote_title: str | None = Field(default=None, max_length=500)


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


def _require_enabled(account: MarketplaceAccount) -> None:
    if not account.enabled:
        raise HTTPException(409, "Amazon account is disabled; enable it before remote mutations.")


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
        "last_validated_at": row.last_validated_at,
        "capability_state": {"enabled": row.enabled, "validated": row.validation_status == "valid"},
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


@router.post("/accounts/{account_id}/enable")
def enable_account(
    account_id: uuid.UUID, data: AmazonAccountToggle, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required to enable an Amazon account.")
    row = _account(db, user, account_id)
    row.enabled = True
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.account_enabled",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={},
    )
    db.commit()
    return _safe_account(row)


@router.post("/accounts/{account_id}/disable")
def disable_account(
    account_id: uuid.UUID, data: AmazonAccountToggle, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required to disable an Amazon account.")
    row = _account(db, user, account_id)
    row.enabled = False
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.account_disabled",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={},
    )
    db.commit()
    return _safe_account(row)


@router.post("/accounts/{account_id}/credentials")
def replace_credentials(
    account_id: uuid.UUID, data: AmazonCredentialReplace, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _account(db, user, account_id)
    try:
        encrypted = encrypt_credentials(data.credentials)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    row.encrypted_credentials = encrypted
    row.credential_status = "configured" if encrypted else "missing"
    row.validation_status = "unknown"
    row.last_validated_at = None
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.credentials_replaced",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"configured": bool(encrypted)},
    )
    db.commit()
    return _safe_account(row)


@router.delete("/accounts/{account_id}/credentials")
def remove_credentials(
    account_id: uuid.UUID, data: AmazonAccountToggle, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required to remove Amazon credentials.")
    row = _account(db, user, account_id)
    row.encrypted_credentials = None
    row.credential_status = "missing"
    row.validation_status = "unknown"
    row.last_validated_at = None
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.credentials_removed",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={},
    )
    db.commit()
    return _safe_account(row)


@router.post("/accounts/{account_id}/revalidate")
def revalidate_account(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    return validate_account(account_id, db, user)


@router.get("/accounts")
def list_accounts(db: DatabaseSession, user: Owner) -> list[dict[str, object]]:
    rows = db.scalars(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == user.id, MarketplaceAccount.marketplace == "amazon")
        .order_by(MarketplaceAccount.created_at.desc())
    )
    return [_safe_account(row) for row in rows]


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
    listings = list(
        db.scalars(
            select(MarketplaceListing).where(
                MarketplaceListing.owner_id == user.id,
                MarketplaceListing.account_id == account.id,
                MarketplaceListing.marketplace == "amazon",
            )
        )
    )
    events = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.actor_id == user.id,
                AuditEvent.action.like("amazon.%"),
            )
        )
    )

    def last_event(action: str) -> object:
        matching = [event.occurred_at for event in events if event.action == action]
        return max(matching) if matching else None

    return {
        "configured": account.credential_status == "configured",
        "enabled": account.enabled,
        "validation_status": account.validation_status,
        "validated": account.validation_status == "valid",
        "last_validated_at": account.last_validated_at,
        "transport_validation": bool(result["valid"]),
        "marketplace": _safe_account(account),
        "recent_listing_successes": sum(1 for listing in listings if listing.status == "active"),
        "listing_failures": sum(
            1 for listing in listings if listing.status in {"error", "rejected"}
        ),
        "rejection_count": sum(1 for event in events if "rejected" in event.action),
        "throttle_count": sum(
            1 for event in events if "thrott" in str(event.metadata_json).casefold()
        ),
        "ambiguous_operations": sum(
            1 for event in events if "ambiguous" in str(event.metadata_json).casefold()
        ),
        "last_inventory_read": last_event("amazon.inventory_read"),
        "last_inventory_update": last_event("amazon.inventory_updated"),
        "last_order_import": last_event("amazon.orders_imported"),
        "last_settlement_import": last_event("amazon.financial_events_imported"),
        "median_connector_latency_ms": None,
        "recent_retry_count": sum(
            1 for event in events if "retry" in str(event.metadata_json).casefold()
        ),
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
    _require_enabled(account)
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
        select(MarketplaceInventory).where(
            MarketplaceInventory.owner_id == user.id,
            MarketplaceInventory.listing_id == listing.id,
            MarketplaceInventory.variant_id.is_(None),
        )
    )
    if quantity is None and row is None:
        status = "unavailable"
    else:
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
        status = row.synchronization_status
    record_event(
        db,
        actor_id=user.id,
        action="amazon.inventory_read",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"available": quantity is not None},
    )
    db.commit()
    return {
        "listing_id": listing.id,
        "quantity": quantity,
        "synchronization_status": status,
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
    _require_enabled(account)
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


@router.get("/listings/{listing_id}/readiness")
def listing_readiness(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
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
    product = db.scalar(
        select(Product).where(Product.id == listing.product_id, Product.owner_id == user.id)
    )
    artifact = None
    if listing.content_artifact_id is not None:
        artifact = db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == listing.content_artifact_id,
                GeneratedArtifact.owner_id == user.id,
                GeneratedArtifact.product_id == listing.product_id,
            )
        )
    variants = list(
        db.scalars(
            select(MarketplaceVariant).where(
                MarketplaceVariant.owner_id == user.id,
                MarketplaceVariant.listing_id == listing.id,
            )
        )
    )
    media = list(
        db.scalars(
            select(MarketplaceMediaMapping).where(
                MarketplaceMediaMapping.owner_id == user.id,
                MarketplaceMediaMapping.listing_id == listing.id,
            )
        )
    )
    prices = list(
        db.scalars(
            select(MarketplacePrice).where(
                MarketplacePrice.owner_id == user.id,
                MarketplacePrice.listing_id == listing.id,
                MarketplacePrice.variant_id.is_(None),
            )
        )
    )
    blocking: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    informational: list[dict[str, object]] = []

    def block(code: str, message: str, field: str | None = None) -> None:
        item: dict[str, object] = {"code": code, "message": message}
        if field:
            item["field"] = field
        blocking.append(item)

    if not account.enabled:
        block("account_disabled", "Enable the Amazon account before submission.", "account")
    if account.credential_status != "configured":
        block("credential_missing", "A stored Amazon credential is required.", "credential")
    if account.validation_status != "valid":
        block("account_not_validated", "Validate the Amazon account before submission.", "account")
    if product is None or product.status != "active":
        block("product_not_active", "The mapped Product must be active.", "product")
    if artifact is None or artifact.status != "approved":
        block(
            "approval_required", "The exact mapped Artifact version must be approved.", "artifact"
        )
    if not listing.category:
        block("product_type_missing", "Select an Amazon product type.", "product_type")
    if not listing.marketplace_sku:
        block("seller_sku_missing", "Seller SKU is required.", "seller_sku")
    if not variants:
        block("variants_missing", "At least one valid variant is required.", "variants")
    else:
        variant_payload = [
            {
                "stable_variant_key": row.stable_variant_key,
                "sku": row.sku,
                "variation_theme": row.options_json.get("variation_theme"),
                "price": str(row.price_amount) if row.price_amount is not None else None,
            }
            for row in variants
        ]
        for issue in AmazonVariantPolicy.validate(variant_payload):
            block(str(issue.code), issue.message, issue.field)
    if not media:
        block("media_missing", "At least one mapped main image is required.", "media")
    else:
        media_payload = []
        for mapping in media:
            asset = db.scalar(
                select(MediaAsset).where(
                    MediaAsset.id == mapping.media_id, MediaAsset.owner_id == user.id
                )
            )
            if asset is None:
                block("media_unavailable", "A mapped Media Asset is no longer available.", "media")
                continue
            media_payload.append(
                {
                    "position": mapping.position,
                    "mime_type": asset.mime_type,
                    "width": asset.width,
                    "height": asset.height,
                    "size_bytes": asset.size_bytes,
                    "checksum_sha256": asset.checksum_sha256,
                }
            )
        for issue in AmazonMediaPolicy.validate(media_payload):
            block(str(issue.code), issue.message, issue.field)
    if not prices:
        block("price_missing", "A selling price is required.", "price")
    if listing.drift_state not in {"none", "remote_kept"}:
        block(
            "drift_review_required", "Reconcile and review remote drift before submission.", "drift"
        )
    if listing.status in {"rejected", "error"}:
        warnings.append(
            {
                "code": "previous_failure",
                "message": "The listing has a previous remote failure; review before retrying.",
            }
        )
    informational.append(
        {
            "code": "inventory_policy",
            "message": "Inventory changes are explicit and are not continuously synchronized.",
        }
    )
    return {
        "ready": not blocking,
        "blocking": blocking,
        "warnings": warnings,
        "informational": informational,
        "artifact_version": artifact.version_number if artifact is not None else None,
        "product_type": listing.category,
        "account_id": account.id,
        "listing_id": listing.id,
    }


@router.get("/listings/{listing_id}/variants")
def list_variants(
    listing_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    rows = db.scalars(
        select(MarketplaceVariant)
        .where(MarketplaceVariant.owner_id == user.id, MarketplaceVariant.listing_id == listing.id)
        .order_by(MarketplaceVariant.created_at)
    )
    return [
        {
            "id": row.id,
            "stable_variant_key": row.stable_variant_key,
            "sku": row.sku,
            "barcode": row.barcode,
            "options": row.options_json,
            "price": str(row.price_amount) if row.price_amount is not None else None,
            "compare_at_price": (
                str(row.compare_at_amount) if row.compare_at_amount is not None else None
            ),
            "currency": row.currency,
            "remote_variant_id": row.remote_variant_id,
            "remote_sku": row.remote_sku,
            "listing_state": row.listing_state,
        }
        for row in rows
    ]


@router.get("/listings/{listing_id}/media")
def list_media(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> list[dict[str, object]]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    rows = list(
        db.scalars(
            select(MarketplaceMediaMapping)
            .where(
                MarketplaceMediaMapping.owner_id == user.id,
                MarketplaceMediaMapping.listing_id == listing.id,
            )
            .order_by(MarketplaceMediaMapping.position)
        )
    )
    result: list[dict[str, object]] = []
    for row in rows:
        asset = db.scalar(
            select(MediaAsset).where(MediaAsset.id == row.media_id, MediaAsset.owner_id == user.id)
        )
        result.append(
            {
                "id": row.id,
                "media_id": row.media_id,
                "position": row.position,
                "alt_text": row.alt_text,
                "remote_media_id": row.remote_media_id,
                "status": row.status,
                "checksum_sha256": asset.checksum_sha256 if asset else None,
                "mime_type": asset.mime_type if asset else None,
                "width": asset.width if asset else None,
                "height": asset.height if asset else None,
                "size_bytes": asset.size_bytes if asset else None,
            }
        )
    return result


@router.get("/accounts/{account_id}/orders")
def list_orders(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    orders = list(
        db.scalars(
            select(MarketplaceOrder)
            .where(MarketplaceOrder.owner_id == user.id, MarketplaceOrder.account_id == account.id)
            .order_by(MarketplaceOrder.ordered_at.desc())
        )
    )
    result: list[dict[str, object]] = []
    for order in orders:
        items = list(
            db.scalars(
                select(MarketplaceOrderItem).where(
                    MarketplaceOrderItem.owner_id == user.id,
                    MarketplaceOrderItem.order_id == order.id,
                )
            )
        )
        fulfilments = list(
            db.scalars(
                select(MarketplaceFulfilment).where(
                    MarketplaceFulfilment.owner_id == user.id,
                    MarketplaceFulfilment.order_id == order.id,
                )
            )
        )
        result.append(
            {
                "id": order.id,
                "amazon_order_id": order.remote_order_id,
                "purchase_date": order.ordered_at,
                "update_date": order.updated_at,
                "status": order.status,
                "raw_status": order.remote_raw_status,
                "payment_status": order.payment_status,
                "fulfilment_status": order.fulfilment_status,
                "totals": order.totals_json,
                "tax": str(order.tax_amount or 0),
                "shipping": str(order.shipping_amount or 0),
                "discount": str(order.discount_amount or 0),
                "items": [
                    {
                        "sku": item.marketplace_sku,
                        "title": item.title_snapshot,
                        "quantity": item.quantity,
                        "unit_price": str(item.unit_price),
                        "total": str(item.total_price),
                        "product_id": item.product_id,
                        "variant_id": item.variant_id,
                    }
                    for item in items
                ],
                "fulfilments": [
                    {
                        "status": row.status,
                        "carrier": row.carrier,
                        "tracking_reference": row.tracking_reference,
                        "shipped_at": row.shipped_at,
                        "delivered_at": row.delivered_at,
                    }
                    for row in fulfilments
                ],
            }
        )
    return result


@router.get("/accounts/{account_id}/settlements")
def list_settlements(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    settlements = list(
        db.scalars(
            select(MarketplaceSettlement)
            .where(
                MarketplaceSettlement.owner_id == user.id,
                MarketplaceSettlement.account_id == account.id,
            )
            .order_by(MarketplaceSettlement.period_end.desc())
        )
    )
    result: list[dict[str, object]] = []
    for settlement in settlements:
        lines = list(
            db.scalars(
                select(MarketplaceSettlementLine)
                .where(
                    MarketplaceSettlementLine.owner_id == user.id,
                    MarketplaceSettlementLine.settlement_id == settlement.id,
                )
                .order_by(MarketplaceSettlementLine.created_at)
            )
        )
        result.append(
            {
                "id": settlement.id,
                "settlement_id": settlement.remote_settlement_id,
                "account_id": account.id,
                "marketplace": settlement.marketplace,
                "period_start": settlement.period_start,
                "period_end": settlement.period_end,
                "status": settlement.status,
                "currency": settlement.currency,
                "gross_sales": str(settlement.gross_amount),
                "refunds": str(settlement.refund_amount),
                "fees": str(settlement.fee_amount),
                "tax_withholding": str(settlement.tax_withholding_amount),
                "adjustments": str(settlement.other_adjustment_amount),
                "net": str(settlement.net_amount),
                "imported_at": settlement.imported_at,
                "lines": [
                    {
                        "category": line.line_type,
                        "order_id": line.order_id,
                        "amount": str(line.amount),
                        "currency": line.currency,
                        "description": line.description,
                    }
                    for line in lines
                ],
            }
        )
    return result


@router.post("/accounts/{account_id}/orders/import")
def import_orders(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    imported = 0
    for item in _connector(account).get_orders():
        remote_id = str(item["remote_id"])
        existing = db.scalar(
            select(MarketplaceOrder).where(
                MarketplaceOrder.account_id == account.id,
                MarketplaceOrder.remote_order_id == remote_id,
            )
        )
        if existing is not None:
            continue
        raw_status = str(item.get("raw_status", item.get("status", "Unshipped")))
        status = {
            "pending": "pending",
            "unshipped": "confirmed",
            "partiallyshipped": "processing",
            "shipped": "shipped",
            "delivered": "delivered",
            "canceled": "cancelled",
            "cancelled": "cancelled",
        }.get(raw_status.casefold().replace(" ", ""), "confirmed")
        channel = str(item.get("fulfilment_channel", "MFN")).upper()
        fulfilment_status = {
            "AFN": "amazon_fulfilled",
            "FBA": "amazon_fulfilled",
            "MFN": "merchant_fulfilled",
        }.get(channel, "unfulfilled")
        currency = str(item.get("currency", _connector(account).marketplace.currency))
        total = Decimal(str(item.get("total", "0")))
        quantity_value = item.get("quantity", 1)
        quantity = int(quantity_value) if isinstance(quantity_value, (int, str)) else 1
        unit_price = Decimal(str(item.get("unit_price", total)))
        order = MarketplaceOrder(
            owner_id=account.owner_id,
            account_id=account.id,
            marketplace="amazon",
            remote_order_id=remote_id,
            status=status,
            payment_status=str(item.get("payment_status", "paid")),
            fulfilment_status=fulfilment_status,
            buyer_snapshot_json={"display_name": "Masked buyer"},
            totals_json={
                "item_subtotal": str(item.get("item_subtotal", total)),
                "currency": currency,
                "asin": item.get("asin"),
                "last_update": item.get("last_update"),
            },
            tax_amount=Decimal(str(item.get("tax", "0"))),
            shipping_amount=Decimal(str(item.get("shipping", "0"))),
            discount_amount=Decimal(str(item.get("discount", "0"))),
            ordered_at=now(),
            remote_raw_status=raw_status,
            created_at=now(),
            updated_at=now(),
        )
        db.add(order)
        db.flush()
        db.add(
            MarketplaceOrderItem(
                owner_id=account.owner_id,
                order_id=order.id,
                product_id=None,
                variant_id=None,
                marketplace_sku=str(item.get("seller_sku")) if item.get("seller_sku") else None,
                title_snapshot=str(item.get("title", "Amazon order item")),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total,
                created_at=now(),
                updated_at=now(),
            )
        )
        db.add(
            MarketplaceFulfilment(
                owner_id=account.owner_id,
                order_id=order.id,
                remote_fulfilment_id=(
                    str(item.get("fulfilment_id")) if item.get("fulfilment_id") else None
                ),
                status=fulfilment_status,
                carrier=str(item.get("carrier")) if item.get("carrier") else None,
                tracking_reference=(
                    str(item.get("tracking_reference")) if item.get("tracking_reference") else None
                ),
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
    connector = _connector(account)
    stamp = now()
    settlements_imported = 0
    lines_imported = 0
    settlements = connector.get_settlements()
    for settlement_data in settlements:
        remote_id = str(settlement_data["remote_id"])
        settlement = db.scalar(
            select(MarketplaceSettlement).where(
                MarketplaceSettlement.owner_id == user.id,
                MarketplaceSettlement.account_id == account.id,
                MarketplaceSettlement.remote_settlement_id == remote_id,
            )
        )
        if settlement is None:
            gross = Decimal(str(settlement_data.get("gross", "0")))
            fees = Decimal(str(settlement_data.get("fees", "0")))
            refund = Decimal(str(settlement_data.get("refunds", "0")))
            withholding = Decimal(str(settlement_data.get("withholding", "0")))
            net = Decimal(str(settlement_data.get("net", gross - fees - refund - withholding)))
            settlement = MarketplaceSettlement(
                owner_id=user.id,
                account_id=account.id,
                marketplace="amazon",
                remote_settlement_id=remote_id,
                period_start=stamp,
                period_end=stamp,
                gross_amount=gross,
                fee_amount=fees,
                refund_amount=refund,
                tax_withholding_amount=withholding,
                net_amount=net,
                currency=connector.marketplace.currency,
                status="settled",
                other_adjustment_amount=Decimal("0"),
                remote_generated_at=stamp,
                imported_at=stamp,
                created_at=stamp,
                updated_at=stamp,
            )
            db.add(settlement)
            db.flush()
            db.add(
                MarketplaceSettlementLine(
                    owner_id=account.owner_id,
                    settlement_id=settlement.id,
                    order_id=None,
                    line_type="sales",
                    amount=gross,
                    currency=connector.marketplace.currency,
                    description="Amazon settlement gross sales",
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            db.add(
                MarketplaceSettlementLine(
                    owner_id=account.owner_id,
                    settlement_id=settlement.id,
                    order_id=None,
                    line_type="net",
                    amount=net,
                    currency=connector.marketplace.currency,
                    description="Amazon settlement net",
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            settlements_imported += 1
    settlement_id = settlement.id if settlement is not None else None
    for item in connector.get_fees():
        raw_type = str(item.get("type", "other")).casefold()
        category = {
            "commission": "commission",
            "referral": "commission",
            "referral_commission": "commission",
            "fulfilment": "fulfilment",
            "fulfillment": "fulfilment",
            "shipping": "shipping",
            "storage": "storage",
            "closing": "other",
            "refund": "refund",
            "refund_fee": "refund",
            "promotion": "other",
            "advertising": "advertising",
            "tax": "tax",
            "withholding": "withholding",
            "chargeback": "other",
            "adjustment": "other",
        }.get(raw_type, "other")
        amount = Decimal(str(item.get("amount", "0")))
        existing_fee = db.scalar(
            select(MarketplaceFee).where(
                MarketplaceFee.account_id == account.id,
                MarketplaceFee.fee_type == category,
                MarketplaceFee.amount == amount,
            )
        )
        if existing_fee is None:
            db.add(
                MarketplaceFee(
                    owner_id=user.id,
                    account_id=account.id,
                    order_id=None,
                    settlement_id=settlement_id,
                    fee_type=category,
                    amount=amount,
                    currency=str(item.get("currency", connector.marketplace.currency)),
                    description=f"Amazon financial event: {raw_type[:80]}",
                    occurred_at=stamp,
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            if settlement_id is not None:
                db.add(
                    MarketplaceSettlementLine(
                        owner_id=account.owner_id,
                        settlement_id=settlement_id,
                        order_id=None,
                        line_type=raw_type[:40],
                        amount=amount,
                        currency=str(item.get("currency", connector.marketplace.currency)),
                        description="Amazon normalized financial event",
                        created_at=stamp,
                        updated_at=stamp,
                    )
                )
            lines_imported += 1
    record_event(
        db,
        actor_id=user.id,
        action="amazon.financial_events_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata={"lines": lines_imported, "settlements": settlements_imported},
    )
    db.commit()
    return {"imported": lines_imported, "settlements": settlements_imported}


@router.post("/listings/{listing_id}/media")
def submit_media(
    listing_id: uuid.UUID,
    data: AmazonMediaRequest,
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
    if listing is None or not listing.remote_listing_id:
        raise HTTPException(409, "Submit the Amazon listing before adding remote media.")
    media_rows = list(
        db.scalars(
            select(MediaAsset).where(
                MediaAsset.owner_id == user.id,
                MediaAsset.id.in_([item.media_id for item in data.media]),
                MediaAsset.status == "ready",
            )
        )
    )
    by_id = {row.id: row for row in media_rows}
    if len(by_id) != len(data.media):
        raise HTTPException(422, "Every Amazon media asset must be owner-scoped and ready.")
    payload = [
        {
            "media_id": str(item.media_id),
            "position": item.position,
            "alt_text": item.alt_text,
            "mime_type": by_id[item.media_id].mime_type,
            "width": by_id[item.media_id].width,
            "height": by_id[item.media_id].height,
            "size_bytes": by_id[item.media_id].size_bytes,
            "checksum_sha256": by_id[item.media_id].checksum_sha256,
        }
        for item in data.media
        if item.media_id in by_id
    ]
    issues = AmazonMediaPolicy.validate(payload)
    if issues:
        raise HTTPException(
            422, {"code": "amazon_media_not_ready", "issues": [issue.message for issue in issues]}
        )
    account = _account(
        db,
        user,
        listing.account_id,
    )
    _require_enabled(account)
    result = _connector(account).submit_media(
        listing.remote_listing_id, payload, data.idempotency_key
    )
    if result.status != "succeeded":
        raise HTTPException(
            502,
            {
                "code": "amazon_media_failed",
                "message": "Amazon media submission did not complete safely.",
            },
        )
    for item in data.media:
        mapping = db.scalar(
            select(MarketplaceMediaMapping).where(
                MarketplaceMediaMapping.owner_id == user.id,
                MarketplaceMediaMapping.listing_id == listing.id,
                MarketplaceMediaMapping.media_id == item.media_id,
            )
        )
        if mapping is None:
            mapping = MarketplaceMediaMapping(
                owner_id=user.id,
                listing_id=listing.id,
                media_id=item.media_id,
                position=item.position,
                alt_text=item.alt_text,
                remote_media_id=f"{listing.remote_listing_id}:media:{item.position}",
                remote_url=None,
                status="accepted",
                created_at=now(),
                updated_at=now(),
            )
            db.add(mapping)
        else:
            mapping.position = item.position
            mapping.alt_text = item.alt_text
            mapping.status = "accepted"
            mapping.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.media_submitted",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"count": len(payload)},
    )
    db.commit()
    return {"status": "succeeded", "count": len(payload)}


@router.post("/listings/{listing_id}/variants")
def submit_variants(
    listing_id: uuid.UUID,
    data: AmazonVariantsRequest,
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
    if listing is None or not listing.remote_listing_id:
        raise HTTPException(409, "Submit the Amazon listing before adding variants.")
    issues = AmazonVariantPolicy.validate(data.variants)
    if issues:
        raise HTTPException(
            422,
            {"code": "amazon_variants_not_ready", "issues": [issue.message for issue in issues]},
        )
    account = _account(db, user, listing.account_id)
    _require_enabled(account)
    result = _connector(account).submit_variants(
        listing.remote_listing_id, data.variants, data.idempotency_key
    )
    if result.status != "succeeded":
        raise HTTPException(
            409,
            {
                "code": "amazon_variants_rejected",
                "message": "Amazon variant submission was rejected safely.",
            },
        )
    for item in data.variants:
        key = str(item["stable_variant_key"])
        variant = db.scalar(
            select(MarketplaceVariant).where(
                MarketplaceVariant.owner_id == user.id,
                MarketplaceVariant.listing_id == listing.id,
                MarketplaceVariant.stable_variant_key == key,
            )
        )
        if variant is None:
            variant = MarketplaceVariant(
                owner_id=user.id,
                listing_id=listing.id,
                product_id=listing.product_id,
                stable_variant_key=key,
                sku=str(item.get("sku") or ""),
                price_amount=item.get("price"),
                compare_at_amount=item.get("compare_at_price"),
                currency=str(item.get("currency") or "INR"),
                barcode=item.get("barcode"),
                options_json=dict(item.get("options") or {}),
                remote_variant_id=f"{listing.remote_listing_id}:{key}",
                remote_sku=str(item.get("sku") or ""),
                listing_state="active",
                created_at=now(),
                updated_at=now(),
            )
            db.add(variant)
        else:
            variant.options_json = dict(item.get("options") or {})
            variant.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.variants_submitted",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"count": len(data.variants)},
    )
    db.commit()
    return {"status": "succeeded", "count": len(data.variants)}


@router.post("/listings/{listing_id}/pricing")
def update_pricing(
    listing_id: uuid.UUID,
    data: AmazonPriceRequest,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required for Amazon price updates.")
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None or not listing.remote_listing_id:
        raise HTTPException(404, "Amazon listing was not found.")
    account = _account(db, user, listing.account_id)
    _require_enabled(account)
    price_payload = {
        "list_price": str(data.list_price) if data.list_price is not None else None,
        "selling_price": str(data.selling_price),
        "sale_price": str(data.sale_price) if data.sale_price is not None else None,
        "currency": data.currency.upper(),
    }
    issues = AmazonPricingPolicy.validate(price_payload, _connector(account).marketplace.currency)
    if issues:
        raise HTTPException(
            422, {"code": "amazon_price_not_ready", "issues": [issue.message for issue in issues]}
        )
    result = _connector(account).update_price(
        listing.remote_listing_id, price_payload, data.idempotency_key
    )
    if result.status != "succeeded":
        raise HTTPException(
            409,
            {
                "code": "amazon_price_failed",
                "message": "Amazon price update did not complete safely.",
            },
        )
    db.add(
        MarketplacePrice(
            owner_id=user.id,
            listing_id=listing.id,
            variant_id=None,
            currency=data.currency.upper(),
            amount=data.selling_price,
            mrp_amount=data.list_price,
            sale_amount=data.sale_price,
            cost_amount=None,
            minimum_amount=None,
            maximum_amount=None,
            effective_from=now(),
            effective_to=None,
        )
    )
    record_event(
        db,
        actor_id=user.id,
        action="amazon.price_updated",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"currency": data.currency.upper()},
    )
    db.commit()
    return {"status": "succeeded", "price": price_payload}


@router.get("/accounts/{account_id}/returns")
def import_returns(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    imported = 0
    for item in _connector(account).get_returns():
        order = db.scalar(
            select(MarketplaceOrder).where(
                MarketplaceOrder.account_id == account.id,
                MarketplaceOrder.remote_order_id == str(item["order_id"]),
            )
        )
        if order is None:
            continue
        existing = db.scalar(
            select(MarketplaceReturn).where(
                MarketplaceReturn.order_id == order.id,
                MarketplaceReturn.marketplace_reference == str(item["return_id"]),
            )
        )
        if existing is None:
            db.add(
                MarketplaceReturn(
                    owner_id=user.id,
                    order_id=order.id,
                    reason=str(item["reason"]),
                    quantity=int(item["quantity"]),
                    requested_at=now(),
                    status=str(item["status"]),
                    marketplace_reference=str(item["return_id"]),
                    refund_amount=Decimal(str(item["refund_amount"])),
                    safe_notes="Imported from deterministic Amazon boundary.",
                    created_at=now(),
                    updated_at=now(),
                )
            )
            db.add(
                MarketplaceRefund(
                    owner_id=user.id,
                    order_id=order.id,
                    amount=Decimal(str(item["refund_amount"])),
                    currency=str(_connector(account).marketplace.currency),
                    reason="Amazon return refund",
                    status="reported",
                    marketplace_reference=str(item["return_id"]),
                    created_at=now(),
                    updated_at=now(),
                )
            )
            imported += 1
    record_event(
        db,
        actor_id=user.id,
        action="amazon.returns_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata={"count": imported},
    )
    db.commit()
    return {"imported": imported}


@router.get("/accounts/{account_id}/returns/records")
def list_returns(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    rows = list(
        db.scalars(
            select(MarketplaceReturn)
            .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceReturn.order_id)
            .where(
                MarketplaceReturn.owner_id == user.id,
                MarketplaceOrder.account_id == account.id,
            )
            .order_by(MarketplaceReturn.requested_at.desc())
        )
    )
    result: list[dict[str, object]] = []
    for row in rows:
        refunds = list(
            db.scalars(
                select(MarketplaceRefund).where(
                    MarketplaceRefund.owner_id == user.id,
                    MarketplaceRefund.order_id == row.order_id,
                    MarketplaceRefund.marketplace_reference == row.marketplace_reference,
                )
            )
        )
        result.append(
            {
                "id": row.id,
                "order_id": row.order_id,
                "reference": row.marketplace_reference,
                "status": row.status,
                "reason": row.reason,
                "quantity": row.quantity,
                "requested_at": row.requested_at,
                "refund_amount": str(row.refund_amount),
                "safe_notes": row.safe_notes,
                "refunds": [
                    {
                        "amount": str(refund.amount),
                        "currency": refund.currency,
                        "status": refund.status,
                        "reason": refund.reason,
                    }
                    for refund in refunds
                ],
            }
        )
    return result


@router.get("/accounts/{account_id}/profitability")
def profitability(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    account = _account(db, user, account_id)
    orders = list(
        db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.account_id == account.id))
    )
    fees = list(db.scalars(select(MarketplaceFee).where(MarketplaceFee.account_id == account.id)))
    refunds = list(
        db.scalars(
            select(MarketplaceRefund)
            .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceRefund.order_id)
            .where(MarketplaceOrder.account_id == account.id)
        )
    )
    gross = sum(
        (
            Decimal(
                str(order.totals_json.get("item_subtotal", order.totals_json.get("total", "0")))
            )
            for order in orders
        ),
        Decimal("0"),
    )
    refund_total = sum((refund.amount for refund in refunds), Decimal("0"))
    fee_total = sum((fee.amount for fee in fees), Decimal("0"))
    missing: list[str] = []
    if not orders:
        missing.append("orders")
    if not fees:
        missing.append("marketplace_fees")
    missing.append("cogs")
    return {
        "gross_sales": gross,
        "refunds": refund_total,
        "fees": fee_total,
        "cogs": None,
        "contribution": gross - refund_total - fee_total,
        "estimated_profit": None,
        "profit_status": "unavailable",
        "missing_inputs": missing,
        "accounting_semantics": (
            "Contribution excludes unavailable COGS; settlement net is not profit."
        ),
    }


@router.get("/listings/{listing_id}/drift")
def drift(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None:
        raise HTTPException(404, "Amazon listing was not found.")
    if not listing.remote_listing_id:
        return {
            "listing_id": listing.id,
            "drift_state": "none",
            "classification": "local_only",
            "fields": [
                {
                    "path": "listing",
                    "local": listing.id,
                    "remote": None,
                    "classification": "local_only",
                }
            ],
        }
    account = _account(db, user, listing.account_id)
    remote = _connector(account).get_listing(listing.remote_listing_id)
    remote_missing = (
        not remote.get("sku") and str(remote.get("status", "unknown")).casefold() == "unknown"
    )
    variants = list(
        db.scalars(
            select(MarketplaceVariant)
            .where(
                MarketplaceVariant.owner_id == user.id, MarketplaceVariant.listing_id == listing.id
            )
            .order_by(MarketplaceVariant.stable_variant_key)
        )
    )
    mappings = list(
        db.scalars(
            select(MarketplaceMediaMapping)
            .where(
                MarketplaceMediaMapping.owner_id == user.id,
                MarketplaceMediaMapping.listing_id == listing.id,
            )
            .order_by(MarketplaceMediaMapping.position)
        )
    )
    price = db.scalar(
        select(MarketplacePrice)
        .where(
            MarketplacePrice.owner_id == user.id,
            MarketplacePrice.listing_id == listing.id,
            MarketplacePrice.variant_id.is_(None),
        )
        .order_by(MarketplacePrice.effective_from.desc())
    )
    inventory_row = db.scalar(
        select(MarketplaceInventory).where(
            MarketplaceInventory.owner_id == user.id,
            MarketplaceInventory.listing_id == listing.id,
            MarketplaceInventory.variant_id.is_(None),
        )
    )
    local_values: dict[str, object] = {
        "status": listing.raw_safe_status or listing.status,
        "seller_sku": listing.marketplace_sku,
        "asin": listing.catalog_identifier,
        "title": listing.title,
        "product_type": listing.category,
        "attributes": (listing.safe_metadata_json or {}).get("attributes"),
        "bullet_content_fingerprint": (listing.safe_metadata_json or {}).get(
            "bullet_content_fingerprint"
        ),
        "variants": [
            {
                "key": row.stable_variant_key,
                "sku": row.sku,
                "options": row.options_json,
                "price": str(row.price_amount) if row.price_amount is not None else None,
            }
            for row in variants
        ],
        "media": [
            {"media_id": row.media_id, "position": row.position, "status": row.status}
            for row in mappings
        ],
        "price": str(price.amount) if price is not None else None,
        "inventory_quantity": (
            inventory_row.marketplace_reported_quantity if inventory_row is not None else None
        ),
    }
    remote_values: dict[str, object] = {
        "status": None if remote_missing else remote.get("status"),
        "seller_sku": None if remote_missing else remote.get("sku"),
        "asin": None if remote_missing else remote.get("asin"),
        "title": None if remote_missing else remote.get("title"),
        "product_type": None if remote_missing else remote.get("product_type"),
        "attributes": None if remote_missing else remote.get("attributes"),
        "bullet_content_fingerprint": (
            None if remote_missing else remote.get("bullet_content_fingerprint")
        ),
        "variants": None if remote_missing else remote.get("variants"),
        "media": None if remote_missing else remote.get("media"),
        "price": (
            None
            if remote_missing
            else cast(dict[str, object], remote.get("price") or {}).get("selling_price")
        ),
        "inventory_quantity": None if remote_missing else remote.get("quantity"),
    }
    fields: list[dict[str, object]] = []
    for path, local_value in local_values.items():
        remote_value = remote_values.get(path)
        if local_value == remote_value:
            continue
        if remote_value is None and local_value is not None:
            classification = "missing_remote"
        elif local_value is None and remote_value is not None:
            classification = "remote_only"
        else:
            classification = "modified"
        field = {
            "path": path,
            "local": local_value,
            "remote": remote_value,
            "classification": classification,
        }
        fields.append(field)
        existing = db.scalar(
            select(MarketplaceDriftRecord).where(
                MarketplaceDriftRecord.owner_id == user.id,
                MarketplaceDriftRecord.listing_id == listing.id,
                MarketplaceDriftRecord.field_name == path,
                MarketplaceDriftRecord.state == "detected",
            )
        )
        if existing is None:
            db.add(
                MarketplaceDriftRecord(
                    owner_id=user.id,
                    listing_id=listing.id,
                    field_name=path,
                    local_value_json=local_value,
                    remote_value_json=remote_value,
                    state="detected",
                    created_at=now(),
                    updated_at=now(),
                )
            )
    listing.drift_state = "detected" if fields else "none"
    listing.updated_at = now()
    db.commit()
    classification = (
        "unchanged" if not fields else ("missing_remote" if remote_missing else "modified")
    )
    return {
        "listing_id": listing.id,
        "drift_state": listing.drift_state,
        "classification": classification,
        "fields": fields,
    }


@router.post("/listings/{listing_id}/drift/review")
def review_drift(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    result = drift(listing_id, db, user)
    record_event(
        db,
        actor_id=user.id,
        action="amazon.drift_reviewed",
        entity_type="marketplace_listing",
        entity_id=listing_id,
        metadata={"field_count": len(cast(list[object], result.get("fields", [])))},
    )
    db.commit()
    return result


@router.post("/listings/{listing_id}/drift/keep-remote")
def keep_remote_drift(
    listing_id: uuid.UUID,
    data: AmazonDriftActionRequest,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required to keep remote Amazon changes.")
    result = drift(listing_id, db, user)
    records = list(
        db.scalars(
            select(MarketplaceDriftRecord).where(
                MarketplaceDriftRecord.owner_id == user.id,
                MarketplaceDriftRecord.listing_id == listing_id,
                MarketplaceDriftRecord.state == "detected",
            )
        )
    )
    for record in records:
        record.state = "resolved_keep_remote"
        record.resolved_at = now()
        record.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="amazon.drift_kept_remote",
        entity_type="marketplace_listing",
        entity_id=listing_id,
        metadata={"field_count": len(records)},
    )
    db.commit()
    return {"status": "succeeded", "action": "keep_remote", "fields": result.get("fields", [])}


@router.post("/listings/{listing_id}/drift/overwrite")
def overwrite_drift(
    listing_id: uuid.UUID,
    data: AmazonDriftActionRequest,
    db: DatabaseSession,
    user: Owner,
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required for Amazon drift overwrite.")
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "amazon",
        )
    )
    if listing is None or not listing.remote_listing_id:
        raise HTTPException(404, "Amazon listing remote identifier was not found.")
    if data.expected_remote_title is None:
        raise HTTPException(409, "Fresh reconciliation is required before Amazon overwrite.")
    account = _account(db, user, listing.account_id)
    _require_enabled(account)
    remote = _connector(account).get_listing(listing.remote_listing_id)
    if remote.get("title") != data.expected_remote_title:
        raise HTTPException(409, "Remote Amazon listing changed; reconcile again before overwrite.")
    if listing.content_artifact_id is None:
        raise HTTPException(409, "An approved Artifact is required before overwrite.")
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == listing.content_artifact_id,
            GeneratedArtifact.owner_id == user.id,
            GeneratedArtifact.product_id == listing.product_id,
            GeneratedArtifact.status == "approved",
        )
    )
    if artifact is None:
        raise HTTPException(409, "An approved Artifact is required before overwrite.")
    result = _connector(account).update_listing(
        remote_id=listing.remote_listing_id,
        title=listing.title,
        sku=listing.marketplace_sku or "",
    )
    if not result.get("status"):
        raise HTTPException(502, "Amazon overwrite did not complete safely.")
    record_event(
        db,
        actor_id=user.id,
        action="amazon.drift_overwritten",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        metadata={"artifact_version": artifact.version_number},
    )
    db.commit()
    return {
        "status": "succeeded",
        "action": "overwrite",
        "artifact_version": artifact.version_number,
    }


@router.post("/listings/{listing_id}/refresh")
def refresh_remote(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    return drift(listing_id, db, user)
