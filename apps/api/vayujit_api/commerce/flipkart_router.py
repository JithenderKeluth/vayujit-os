"""Owner-scoped Flipkart Commerce API.

The route surface mirrors the Amazon workspace while using the shared
Marketplace Core tables.  The default transport is deterministic and local;
live Flipkart compatibility is deliberately not claimed.
"""

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
from vayujit_api.brands.models import Brand
from vayujit_api.commerce.flipkart import (
    FLIPKART_MARKETPLACE,
    FlipkartCommerceConnector,
    FlipkartPricingPolicy,
    FlipkartVariantPolicy,
)
from vayujit_api.commerce.flipkart_projection import (
    import_financials as project_financials,
)
from vayujit_api.commerce.flipkart_projection import (
    import_order_events,
)
from vayujit_api.commerce.flipkart_projection import (
    profitability as project_profitability,
)
from vayujit_api.commerce.models import (
    MarketplaceAccount,
    MarketplaceCategory,
    MarketplaceInventory,
    MarketplaceListing,
    MarketplaceMediaMapping,
    MarketplaceOrder,
    MarketplacePrice,
    MarketplaceSettlement,
    MarketplaceVariant,
)
from vayujit_api.commerce.service import idempotent_resource, remember_idempotency
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.identity.service import now
from vayujit_api.media.models import MediaAsset
from vayujit_api.products.models import Product

router = APIRouter(prefix="/api/v1/marketplaces/flipkart", tags=["flipkart"])
DatabaseSession = Annotated[Session, Depends(get_session)]
Owner = Annotated[User, Depends(current_user)]


class AccountCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    seller_account_id: str = Field(min_length=1, max_length=160)
    environment: str = Field(default="sandbox", pattern="^(sandbox|production)$")
    credentials: dict[str, str] = Field(default_factory=dict, max_length=12)


class ConfirmRequest(BaseModel):
    confirm: bool = False


class ListingCreate(BaseModel):
    brand_id: uuid.UUID
    product_id: uuid.UUID
    account_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=240)
    marketplace_sku: str = Field(min_length=1, max_length=160)
    artifact_id: uuid.UUID


class PreviewRequest(BaseModel):
    category_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    media: list[dict[str, Any]] = Field(default_factory=list)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    price: dict[str, Any] | None = None


class SubmitRequest(PreviewRequest):
    idempotency_key: str = Field(min_length=1, max_length=200)


class VariantsRequest(BaseModel):
    variants: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)


class MediaRequest(BaseModel):
    media: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=200)


class PriceRequest(BaseModel):
    selling_price: Decimal = Field(ge=0)
    list_price: Decimal | None = Field(default=None, ge=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(min_length=3, max_length=3)
    confirm: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


class InventoryRequest(BaseModel):
    quantity: int = Field(ge=0, le=10_000_000)
    confirm: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


def _account(db: Session, user: User, account_id: uuid.UUID) -> MarketplaceAccount:
    row = db.scalar(
        select(MarketplaceAccount).where(
            MarketplaceAccount.id == account_id,
            MarketplaceAccount.owner_id == user.id,
            MarketplaceAccount.marketplace == "flipkart",
        )
    )
    if row is None:
        raise HTTPException(404, "Flipkart account was not found.")
    return row


def _connector(account: MarketplaceAccount) -> FlipkartCommerceConnector:
    return FlipkartCommerceConnector(seller_id=account.seller_account_id)


def _require_enabled(account: MarketplaceAccount) -> None:
    if not account.enabled:
        raise HTTPException(409, "Flipkart account is disabled; enable it before remote mutations.")


def _account_response(row: MarketplaceAccount) -> dict[str, object]:
    return {
        "id": row.id,
        "marketplace": "flipkart",
        "display_name": row.display_name,
        "seller_account_id": row.seller_account_id,
        "environment": row.environment,
        "enabled": row.enabled,
        "credential_status": row.credential_status,
        "validation_status": row.validation_status,
        "last_validated_at": row.last_validated_at,
        "marketplace_id": FLIPKART_MARKETPLACE.marketplace_id,
        "currency": FLIPKART_MARKETPLACE.currency,
        "locale": FLIPKART_MARKETPLACE.locale,
        "capabilities": [
            "categories",
            "attributes",
            "listing_preview",
            "listing_submit",
            "listing_reconcile",
            "inventory",
            "orders",
            "returns",
            "financials",
        ],
    }


def _listing_response(row: MarketplaceListing) -> dict[str, object]:
    return {
        "id": row.id,
        "brand_id": row.brand_id,
        "product_id": row.product_id,
        "account_id": row.account_id,
        "marketplace": row.marketplace,
        "local_listing_id": row.local_listing_id,
        "remote_listing_id": row.remote_listing_id,
        "marketplace_sku": row.marketplace_sku,
        "title": row.title,
        "category": row.category,
        "status": row.status,
        "publication_state": row.publication_state,
        "drift_state": row.drift_state,
        "content_artifact_id": row.content_artifact_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/marketplaces")
def marketplaces() -> list[dict[str, str]]:
    return [
        {
            "marketplace_id": FLIPKART_MARKETPLACE.marketplace_id,
            "country_code": "IN",
            "currency": "INR",
            "locale": "en-IN",
            "live_validation": "NOT LIVE-VALIDATED",
        }
    ]


@router.get("/accounts")
def list_accounts(db: DatabaseSession, user: Owner) -> list[dict[str, object]]:
    rows = db.scalars(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == user.id, MarketplaceAccount.marketplace == "flipkart")
        .order_by(MarketplaceAccount.created_at.desc())
    ).all()
    return [_account_response(row) for row in rows]


@router.post("/accounts", status_code=201)
def create_account(data: AccountCreate, db: DatabaseSession, user: Owner) -> dict[str, object]:
    from vayujit_api.commerce.service import encrypt_credentials

    try:
        encrypted = encrypt_credentials(data.credentials)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    stamp = now()
    row = MarketplaceAccount(
        owner_id=user.id,
        marketplace="flipkart",
        display_name=data.display_name.strip(),
        seller_account_id=data.seller_account_id.strip(),
        environment=data.environment,
        enabled=False,
        credential_status="configured" if encrypted else "missing",
        encrypted_credentials=encrypted,
        validation_status="unknown",
        capabilities_json={"live_validation": "NOT LIVE-VALIDATED"},
        configuration_json={
            "marketplace_id": FLIPKART_MARKETPLACE.marketplace_id,
            "country_code": "IN",
            "currency": "INR",
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
            409, "A Flipkart account with these identifiers already exists."
        ) from error
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.account_configured",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"marketplace": "flipkart", "environment": row.environment},
    )
    db.commit()
    return _account_response(row)


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
        action="flipkart.account_validated",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={"valid": bool(result["valid"]), "live_validation": "NOT LIVE-VALIDATED"},
    )
    db.commit()
    return _account_response(row)


@router.post("/accounts/{account_id}/revalidate")
def revalidate_account(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    return validate_account(account_id, db, user)


@router.post("/accounts/{account_id}/enable")
def enable_account(
    account_id: uuid.UUID, data: ConfirmRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _account(db, user, account_id)
    if row.validation_status != "valid":
        raise HTTPException(409, "Validate the Flipkart account before enabling it.")
    row.enabled = True
    row.updated_at = now()
    db.commit()
    return _account_response(row)


@router.post("/accounts/{account_id}/disable")
def disable_account(
    account_id: uuid.UUID, data: ConfirmRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _account(db, user, account_id)
    row.enabled = False
    row.updated_at = now()
    db.commit()
    return _account_response(row)


@router.put("/accounts/{account_id}/credential")
def replace_credential(
    account_id: uuid.UUID, data: dict[str, str], db: DatabaseSession, user: Owner
) -> dict[str, object]:
    from vayujit_api.commerce.service import encrypt_credentials

    row = _account(db, user, account_id)
    try:
        row.encrypted_credentials = encrypt_credentials(data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    row.credential_status = "configured" if row.encrypted_credentials else "missing"
    row.updated_at = now()
    db.commit()
    return _account_response(row)


@router.delete("/accounts/{account_id}/credential")
def remove_credential(
    account_id: uuid.UUID, data: ConfirmRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _account(db, user, account_id)
    row.encrypted_credentials = None
    row.credential_status = "missing"
    row.enabled = False
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.account_credential_removed",
        entity_type="marketplace_account",
        entity_id=row.id,
        metadata={},
    )
    db.commit()
    return _account_response(row)


@router.get("/accounts/{account_id}/categories")
def categories(
    account_id: uuid.UUID,
    db: DatabaseSession,
    user: Owner,
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[dict[str, Any]]:
    row = _account(db, user, account_id)
    values = _connector(row).discover_categories(search=search, offset=offset, limit=limit)
    for item in values:
        category_id = str(item["id"])
        existing = db.scalar(
            select(MarketplaceCategory).where(
                MarketplaceCategory.owner_id == user.id,
                MarketplaceCategory.account_id == row.id,
                MarketplaceCategory.remote_id == category_id,
            )
        )
        if existing is None:
            stamp = now()
            db.add(
                MarketplaceCategory(
                    owner_id=user.id,
                    account_id=row.id,
                    marketplace="flipkart",
                    remote_id=category_id,
                    name=str(item["name"]),
                    parent_remote_id=item.get("parent_id"),
                    attributes_json={},
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
    db.commit()
    return values


@router.get("/accounts/{account_id}/categories/{category_id}/attributes")
def category_attributes(
    account_id: uuid.UUID, category_id: str, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _account(db, user, account_id)
    return {
        "category_id": category_id,
        "attributes": _connector(row).category_attributes(category_id),
        "source": "deterministic-fake",
        "live_validation": "NOT LIVE-VALIDATED",
    }


@router.get("/accounts/{account_id}/diagnostics")
def diagnostics(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    row = _account(db, user, account_id)
    return {
        "configured": row.credential_status == "configured",
        "enabled": row.enabled,
        "validated": row.validation_status == "valid",
        "seller_account_id": row.seller_account_id,
        "live_validation": "NOT LIVE-VALIDATED",
        "recent_retry_count": 0,
        "ambiguous_operations": 0,
        "throttled_operations": 0,
    }


@router.get("/listings")
def list_listings(
    db: DatabaseSession, user: Owner, status: str | None = None
) -> list[dict[str, object]]:
    query = select(MarketplaceListing).where(
        MarketplaceListing.owner_id == user.id, MarketplaceListing.marketplace == "flipkart"
    )
    if status:
        query = query.where(MarketplaceListing.status == status)
    return [
        _listing_response(row)
        for row in db.scalars(query.order_by(MarketplaceListing.updated_at.desc())).all()
    ]


@router.post("/listings", status_code=201)
def create_listing(data: ListingCreate, db: DatabaseSession, user: Owner) -> dict[str, object]:
    account = _account(db, user, data.account_id)
    brand = db.scalar(select(Brand).where(Brand.id == data.brand_id, Brand.owner_id == user.id))
    product = db.scalar(
        select(Product).where(
            Product.id == data.product_id,
            Product.owner_id == user.id,
            Product.brand_id == data.brand_id,
        )
    )
    artifact = db.scalar(
        select(GeneratedArtifact).where(
            GeneratedArtifact.id == data.artifact_id,
            GeneratedArtifact.owner_id == user.id,
            GeneratedArtifact.product_id == data.product_id,
        )
    )
    if brand is None or product is None:
        raise HTTPException(404, "Brand or Product was not found.")
    if artifact is None or artifact.status != "approved":
        raise HTTPException(
            409, "Only an approved content artifact can be attached to a Flipkart listing."
        )
    stamp = now()
    row = MarketplaceListing(
        owner_id=user.id,
        brand_id=brand.id,
        product_id=product.id,
        account_id=account.id,
        marketplace="flipkart",
        local_listing_id=f"local-{uuid.uuid4().hex[:16]}",
        remote_listing_id=None,
        marketplace_sku=data.marketplace_sku,
        title=data.title.strip(),
        description_source="artifact",
        category=data.category,
        status="draft",
        publication_state="draft",
        external_url=None,
        raw_safe_status=None,
        remote_created_at=None,
        remote_updated_at=None,
        last_synchronized_at=None,
        drift_state="none",
        content_artifact_id=artifact.id,
        content_artifact_version=artifact.version_number,
        safe_metadata_json={},
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    db.flush()
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.listing_created",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"product_id": str(product.id)},
    )
    db.commit()
    return _listing_response(row)


def _listing(db: Session, user: User, listing_id: uuid.UUID) -> MarketplaceListing:
    row = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "flipkart",
        )
    )
    if row is None:
        raise HTTPException(404, "Flipkart listing was not found.")
    return row


def _readiness(
    db: Session, user: User, listing: MarketplaceListing, data: PreviewRequest | None = None
) -> dict[str, object]:
    account = _account(db, user, listing.account_id)
    product = db.scalar(
        select(Product).where(Product.id == listing.product_id, Product.owner_id == user.id)
    )
    artifact = (
        db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == listing.content_artifact_id,
                GeneratedArtifact.owner_id == user.id,
                GeneratedArtifact.product_id == listing.product_id,
            )
        )
        if listing.content_artifact_id
        else None
    )
    variants = list(
        db.scalars(
            select(MarketplaceVariant).where(
                MarketplaceVariant.owner_id == user.id, MarketplaceVariant.listing_id == listing.id
            )
        ).all()
    )
    media_rows = list(
        db.scalars(
            select(MarketplaceMediaMapping).where(
                MarketplaceMediaMapping.owner_id == user.id,
                MarketplaceMediaMapping.listing_id == listing.id,
            )
        ).all()
    )
    prices = list(
        db.scalars(
            select(MarketplacePrice).where(
                MarketplacePrice.owner_id == user.id,
                MarketplacePrice.listing_id == listing.id,
                MarketplacePrice.variant_id.is_(None),
            )
        ).all()
    )
    blocking: list[dict[str, object]] = []

    def block(code: str, message: str, field: str) -> None:
        blocking.append({"code": code, "message": message, "field": field})

    if not account.enabled:
        block("account_disabled", "Enable the Flipkart account before submission.", "account")
    if account.credential_status != "configured":
        block("credential_missing", "A stored Flipkart credential is required.", "credential")
    if account.validation_status != "valid":
        block(
            "account_not_validated", "Validate the Flipkart account before submission.", "account"
        )
    if product is None or product.status != "active":
        block("product_not_active", "The mapped Product must be active.", "product")
    if artifact is None or artifact.status != "approved":
        block(
            "approval_required", "The exact mapped Artifact version must be approved.", "artifact"
        )
    if not listing.category:
        block("category_missing", "Select a Flipkart category.", "category")
    if not listing.marketplace_sku:
        block("seller_sku_missing", "Seller SKU is required.", "seller_sku")
    variant_payload = [
        {
            "stable_variant_key": value.stable_variant_key,
            "sku": value.sku,
            "price": str(value.price_amount) if value.price_amount is not None else None,
        }
        for value in variants
    ]
    for issue in FlipkartVariantPolicy.validate(variant_payload):
        block(str(issue.code), issue.message, issue.field or "variants")
    if not media_rows:
        block("media_missing", "At least one mapped main image is required.", "media")
    if not prices:
        block("price_missing", "A selling price is required.", "price")
    return {
        "ready": not blocking,
        "blocking": blocking,
        "warnings": [],
        "informational": [
            {
                "code": "inventory_policy",
                "message": "Inventory changes are explicit and are not continuously synchronized.",
            }
        ],
        "artifact_version": artifact.version_number if artifact else None,
        "listing_id": listing.id,
        "account_id": account.id,
        "live_validation": "NOT LIVE-VALIDATED",
    }


@router.get("/listings/{listing_id}/readiness")
def readiness(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    return _readiness(db, user, _listing(db, user, listing_id))


@router.post("/listings/{listing_id}/preview")
def preview(
    listing_id: uuid.UUID, data: PreviewRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _listing(db, user, listing_id)
    account = _account(db, user, row.account_id)
    artifact = (
        db.scalar(
            select(GeneratedArtifact).where(
                GeneratedArtifact.id == row.content_artifact_id,
                GeneratedArtifact.owner_id == user.id,
                GeneratedArtifact.status == "approved",
            )
        )
        if row.content_artifact_id
        else None
    )
    result = _connector(account).preview(
        title=row.title,
        sku=row.marketplace_sku,
        category_id=data.category_id or row.category,
        attributes=data.attributes,
        approved=artifact is not None,
        media=data.media,
        variants=data.variants,
        price=data.price,
    )
    result["readiness"] = _readiness(db, user, row, data)
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.listing_previewed",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"ready": bool(result["readiness"]["ready"])},
    )
    db.commit()
    return result


@router.post("/listings/{listing_id}/submit")
def submit(
    listing_id: uuid.UUID, data: SubmitRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _listing(db, user, listing_id)
    account = _account(db, user, row.account_id)
    _require_enabled(account)
    ready = _readiness(db, user, row, data)
    if not ready["ready"]:
        raise HTTPException(409, "Flipkart listing is not ready for submission.")
    previous = idempotent_resource(db, user.id, account.id, "listing_submit", data.idempotency_key)
    if previous == row.id and row.remote_listing_id:
        return {
            "status": row.raw_safe_status or row.status,
            "remote_listing_id": row.remote_listing_id,
            "remote_status": row.raw_safe_status,
            "retryable": False,
            "ambiguous": False,
            "idempotent_reuse": True,
            "issues": [],
        }
    result = _connector(account).submit(
        sku=row.marketplace_sku or "",
        payload={
            "title": row.title,
            "category": row.category,
            "attributes": data.attributes,
            "artifact_version": ready["artifact_version"],
        },
        idempotency_key=data.idempotency_key,
    )
    if result.status == "throttled":
        raise HTTPException(429, "Flipkart throttled the listing submission; retry safely.")
    if result.remote_id:
        row.remote_listing_id = result.remote_id
    row.status = (
        "submitting" if result.status in {"accepted", "succeeded", "unknown"} else "rejected"
    )
    row.publication_state = "processing" if row.status == "submitting" else "rejected"
    row.raw_safe_status = result.remote_status or result.status
    row.updated_at = now()
    db.flush()
    remember_idempotency(
        db,
        owner_id=user.id,
        account_id=account.id,
        operation="listing_submit",
        key=data.idempotency_key,
        resource_type="marketplace_listing",
        resource_id=row.id,
    )
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.listing_submitted",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"status": result.status},
    )
    db.commit()
    return {
        "status": result.status,
        "remote_listing_id": result.remote_id,
        "remote_status": result.remote_status,
        "retryable": result.retryable,
        "ambiguous": result.ambiguous,
        "idempotent_reuse": False,
        "issues": [
            {"code": issue.code, "message": issue.message, "retryable": issue.retryable}
            for issue in result.issues
        ],
    }


@router.post("/listings/{listing_id}/reconcile")
def reconcile(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    row = _listing(db, user, listing_id)
    if not row.remote_listing_id:
        raise HTTPException(404, "Flipkart listing remote identifier was not found.")
    result = _connector(_account(db, user, row.account_id)).reconcile_listing(row.remote_listing_id)
    status = (
        "active"
        if result["status"] == "ACTIVE"
        else "submitting" if result["status"] == "PROCESSING" else "error"
    )
    row.status = status
    row.publication_state = status
    row.raw_safe_status = str(result["status"])
    row.last_synchronized_at = now()
    row.updated_at = now()
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.listing_reconciled",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"status": status},
    )
    db.commit()
    return {"status": status, "remote_listing_id": row.remote_listing_id}


@router.get("/listings/{listing_id}/variants")
def list_variants(
    listing_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    row = _listing(db, user, listing_id)
    return [
        {
            "stable_variant_key": value.stable_variant_key,
            "sku": value.sku,
            "variation_theme": value.options_json.get("variation_theme"),
            "options": value.options_json,
            "price": str(value.price_amount) if value.price_amount is not None else None,
            "barcode": value.barcode,
        }
        for value in db.scalars(
            select(MarketplaceVariant).where(
                MarketplaceVariant.owner_id == user.id, MarketplaceVariant.listing_id == row.id
            )
        ).all()
    ]


@router.put("/listings/{listing_id}/variants")
def save_variants(
    listing_id: uuid.UUID, data: VariantsRequest, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    row = _listing(db, user, listing_id)
    issues = FlipkartVariantPolicy.validate(data.variants)
    if issues:
        raise HTTPException(422, issues[0].message)
    for old in db.scalars(
        select(MarketplaceVariant).where(
            MarketplaceVariant.owner_id == user.id, MarketplaceVariant.listing_id == row.id
        )
    ).all():
        db.delete(old)
    stamp = now()
    for item in data.variants:
        db.add(
            MarketplaceVariant(
                owner_id=user.id,
                listing_id=row.id,
                product_id=row.product_id,
                stable_variant_key=str(item["stable_variant_key"]),
                sku=str(item.get("sku") or ""),
                price_amount=Decimal(str(item["price"])),
                compare_at_amount=(
                    Decimal(str(item["compare_at_price"]))
                    if item.get("compare_at_price") is not None
                    else None
                ),
                currency=FLIPKART_MARKETPLACE.currency,
                barcode=item.get("barcode"),
                options_json=dict(
                    item.get("options") or {"variation_theme": item.get("variation_theme")}
                ),
                remote_variant_id=None,
                remote_sku=None,
                listing_state="draft",
                created_at=stamp,
                updated_at=stamp,
            )
        )
    db.commit()
    return list_variants(listing_id, db, user)


@router.get("/listings/{listing_id}/media")
def list_media(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> list[dict[str, object]]:
    row = _listing(db, user, listing_id)
    return [
        {
            "media_id": value.media_id,
            "position": value.position,
            "alt_text": value.alt_text,
            "status": value.status,
        }
        for value in db.scalars(
            select(MarketplaceMediaMapping)
            .where(
                MarketplaceMediaMapping.owner_id == user.id,
                MarketplaceMediaMapping.listing_id == row.id,
            )
            .order_by(MarketplaceMediaMapping.position)
        ).all()
    ]


@router.put("/listings/{listing_id}/media")
def save_media(
    listing_id: uuid.UUID, data: MediaRequest, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    row = _listing(db, user, listing_id)
    for item in data.media:
        asset = db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == item.get("media_id"), MediaAsset.owner_id == user.id
            )
        )
        if asset is None:
            raise HTTPException(404, "Media Asset was not found.")
    for old in db.scalars(
        select(MarketplaceMediaMapping).where(
            MarketplaceMediaMapping.owner_id == user.id,
            MarketplaceMediaMapping.listing_id == row.id,
        )
    ).all():
        db.delete(old)
    stamp = now()
    for item in data.media:
        db.add(
            MarketplaceMediaMapping(
                owner_id=user.id,
                listing_id=row.id,
                media_id=uuid.UUID(str(item["media_id"])),
                position=int(item.get("position", 0)),
                alt_text=str(item.get("alt_text", "")),
                remote_media_id=None,
                remote_url=None,
                status="pending",
                created_at=stamp,
                updated_at=stamp,
            )
        )
    db.commit()
    return list_media(listing_id, db, user)


@router.put("/listings/{listing_id}/pricing")
def save_price(
    listing_id: uuid.UUID, data: PriceRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _listing(db, user, listing_id)
    account = _account(db, user, row.account_id)
    _require_enabled(account)
    if not data.confirm:
        raise HTTPException(409, "Confirm the Flipkart price update.")
    issues = FlipkartPricingPolicy.validate(
        {
            "selling_price": data.selling_price,
            "list_price": data.list_price,
            "currency": data.currency,
        },
        FLIPKART_MARKETPLACE.currency,
    )
    if issues:
        raise HTTPException(422, issues[0].message)
    if not row.remote_listing_id:
        raise HTTPException(409, "Submit the listing before changing its Flipkart price.")
    previous = idempotent_resource(db, user.id, account.id, "price_update", data.idempotency_key)
    if previous == row.id:
        current = db.scalar(
            select(MarketplacePrice).where(
                MarketplacePrice.owner_id == user.id,
                MarketplacePrice.listing_id == row.id,
                MarketplacePrice.variant_id.is_(None),
            )
        )
        if current is not None:
            return {
                "amount": str(current.amount),
                "mrp_amount": str(current.mrp_amount) if current.mrp_amount is not None else None,
                "currency": current.currency,
                "idempotent_reuse": True,
            }
    remote = _connector(account).update_price(
        remote_id=row.remote_listing_id,
        payload={
            "selling_price": str(data.selling_price),
            "list_price": str(data.list_price) if data.list_price is not None else None,
            "sale_price": str(data.sale_price) if data.sale_price is not None else None,
            "currency": data.currency,
        },
        idempotency_key=data.idempotency_key,
    )
    operation_status = str(remote.get("operation_status", "succeeded"))
    if operation_status == "throttled":
        raise HTTPException(429, "Flipkart throttled the price update; retry safely.")
    if operation_status in {"unknown", "rejected"}:
        raise HTTPException(409, "Flipkart price update requires reconciliation.")
    old = db.scalar(
        select(MarketplacePrice).where(
            MarketplacePrice.owner_id == user.id,
            MarketplacePrice.listing_id == row.id,
            MarketplacePrice.variant_id.is_(None),
        )
    )
    stamp = now()
    if old is None:
        old = MarketplacePrice(
            owner_id=user.id,
            listing_id=row.id,
            variant_id=None,
            currency=data.currency,
            amount=data.selling_price,
            mrp_amount=data.list_price,
            sale_amount=data.sale_price,
            cost_amount=None,
            minimum_amount=None,
            maximum_amount=None,
            effective_from=stamp,
            effective_to=None,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(old)
    else:
        old.currency = data.currency
        old.amount = data.selling_price
        old.mrp_amount = data.list_price
        old.sale_amount = data.sale_price
        old.updated_at = stamp
    db.flush()
    remember_idempotency(
        db,
        owner_id=user.id,
        account_id=account.id,
        operation="price_update",
        key=data.idempotency_key,
        resource_type="marketplace_listing",
        resource_id=row.id,
    )
    db.commit()
    return {
        "amount": str(old.amount),
        "mrp_amount": str(old.mrp_amount) if old.mrp_amount is not None else None,
        "currency": old.currency,
        "idempotent_reuse": False,
    }


@router.get("/listings/{listing_id}/inventory")
def listing_inventory(
    listing_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    row = _listing(db, user, listing_id)
    return [
        {
            "id": value.id,
            "variant_id": value.variant_id,
            "available_quantity": value.available_quantity,
            "marketplace_reported_quantity": value.marketplace_reported_quantity,
            "local_target_quantity": value.local_target_quantity,
            "synchronization_status": value.synchronization_status,
        }
        for value in db.scalars(
            select(MarketplaceInventory).where(
                MarketplaceInventory.owner_id == user.id, MarketplaceInventory.listing_id == row.id
            )
        ).all()
    ]


@router.post("/listings/{listing_id}/inventory")
def update_inventory(
    listing_id: uuid.UUID, data: InventoryRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    row = _listing(db, user, listing_id)
    account = _account(db, user, row.account_id)
    _require_enabled(account)
    if not data.confirm:
        raise HTTPException(409, "Confirm the Flipkart inventory update.")
    previous = idempotent_resource(
        db, user.id, account.id, "inventory_update", data.idempotency_key
    )
    if previous == row.id:
        item = db.scalar(
            select(MarketplaceInventory).where(
                MarketplaceInventory.owner_id == user.id,
                MarketplaceInventory.listing_id == row.id,
                MarketplaceInventory.variant_id.is_(None),
            )
        )
        if item is not None:
            return {
                "status": "succeeded",
                "quantity": item.available_quantity,
                "idempotent_reuse": True,
            }
    sku = row.marketplace_sku or ""
    remote = _connector(account).update_inventory(sku, data.quantity, data.idempotency_key)
    operation_status = str(remote.get("operation_status", "succeeded"))
    if operation_status == "throttled":
        raise HTTPException(429, "Flipkart throttled the inventory update; retry safely.")
    if operation_status in {"unknown", "rejected"}:
        raise HTTPException(409, "Flipkart inventory update requires reconciliation.")
    stamp = now()
    item = db.scalar(
        select(MarketplaceInventory).where(
            MarketplaceInventory.owner_id == user.id,
            MarketplaceInventory.listing_id == row.id,
            MarketplaceInventory.variant_id.is_(None),
        )
    )
    if item is None:
        item = MarketplaceInventory(
            owner_id=user.id,
            listing_id=row.id,
            variant_id=None,
            product_id=row.product_id,
            available_quantity=data.quantity,
            reserved_quantity=0,
            marketplace_reported_quantity=int(remote.get("quantity", data.quantity)),
            local_target_quantity=data.quantity,
            synchronization_status="succeeded",
            last_synchronized_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(item)
    else:
        item.available_quantity = data.quantity
        item.local_target_quantity = data.quantity
        item.marketplace_reported_quantity = int(remote.get("quantity", data.quantity))
        item.synchronization_status = "succeeded"
        item.last_synchronized_at = stamp
        item.updated_at = stamp
    db.flush()
    remember_idempotency(
        db,
        owner_id=user.id,
        account_id=account.id,
        operation="inventory_update",
        key=data.idempotency_key,
        resource_type="marketplace_listing",
        resource_id=row.id,
    )
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.inventory_updated",
        entity_type="marketplace_listing",
        entity_id=row.id,
        metadata={"quantity": data.quantity},
    )
    db.commit()
    return {"status": "succeeded", "quantity": data.quantity, "idempotent_reuse": False}


@router.post("/accounts/{account_id}/orders/import")
def import_orders(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    counts = import_order_events(db, account, _connector(account))
    db.commit()
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.orders_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata=cast(dict[str, object], counts),
    )
    db.commit()
    return counts


@router.get("/accounts/{account_id}/returns")
def import_returns(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    account = _account(db, user, account_id)
    counts = import_order_events(db, account, _connector(account))
    db.commit()
    return {"imported": counts["returns"], "records": _connector(account).get_returns()}


@router.get("/accounts/{account_id}/returns/records")
def list_returns(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    from vayujit_api.commerce.models import MarketplaceRefund, MarketplaceReturn

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
                "refund_amount": str(row.refund_amount or 0),
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


@router.post("/accounts/{account_id}/cancellations/import")
def import_cancellations(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    counts = import_order_events(db, account, _connector(account))
    db.commit()
    return {"imported": counts["cancellations"]}


@router.post("/accounts/{account_id}/returns/import")
def import_returns_records(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> dict[str, int]:
    account = _account(db, user, account_id)
    counts = import_order_events(db, account, _connector(account))
    db.commit()
    return {"imported": counts["returns"]}


@router.post("/accounts/{account_id}/refunds/import")
def import_refunds(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    counts = import_order_events(db, account, _connector(account))
    db.commit()
    return {"imported": counts["refunds"]}


@router.post("/accounts/{account_id}/financial-events/import")
def import_financials(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, int]:
    account = _account(db, user, account_id)
    counts = project_financials(db, account, _connector(account))
    db.commit()
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.settlements_imported",
        entity_type="marketplace_account",
        entity_id=account.id,
        metadata=cast(dict[str, object], counts),
    )
    db.commit()
    return counts


@router.get("/accounts/{account_id}/settlements")
def list_settlements(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    from vayujit_api.commerce.models import MarketplaceSettlementLine

    rows = list(
        db.scalars(
            select(MarketplaceSettlement)
            .where(
                MarketplaceSettlement.owner_id == user.id,
                MarketplaceSettlement.account_id == account.id,
            )
            .order_by(MarketplaceSettlement.period_end.desc())
        )
    )
    return [
        {
            "id": row.id,
            "settlement_id": row.remote_settlement_id,
            "account_id": row.account_id,
            "marketplace": row.marketplace,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "status": row.status,
            "currency": row.currency,
            "gross_sales": str(row.gross_amount),
            "refunds": str(row.refund_amount),
            "fees": str(row.fee_amount),
            "tax_withholding": str(row.tax_withholding_amount),
            "adjustments": str(row.other_adjustment_amount),
            "net": str(row.net_amount),
            "imported_at": row.imported_at,
            "lines": [
                {
                    "category": line.line_type,
                    "order_id": line.order_id,
                    "amount": str(line.amount),
                    "currency": line.currency,
                    "description": line.description,
                }
                for line in db.scalars(
                    select(MarketplaceSettlementLine)
                    .where(MarketplaceSettlementLine.settlement_id == row.id)
                    .order_by(MarketplaceSettlementLine.created_at)
                )
            ],
        }
        for row in rows
    ]


@router.get("/accounts/{account_id}/profitability")
def get_profitability(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    account = _account(db, user, account_id)
    return project_profitability(db, account)


@router.get("/accounts/{account_id}/orders")
def list_orders(account_id: uuid.UUID, db: DatabaseSession, user: Owner) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    from vayujit_api.commerce.models import (
        MarketplaceCancellation,
        MarketplaceFulfilment,
        MarketplaceOrderItem,
        MarketplaceRefund,
        MarketplaceReturn,
    )

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
                select(MarketplaceOrderItem).where(MarketplaceOrderItem.order_id == order.id)
            )
        )
        fulfilments = list(
            db.scalars(
                select(MarketplaceFulfilment).where(MarketplaceFulfilment.order_id == order.id)
            )
        )
        cancellations = list(
            db.scalars(
                select(MarketplaceCancellation).where(MarketplaceCancellation.order_id == order.id)
            )
        )
        returns = list(
            db.scalars(select(MarketplaceReturn).where(MarketplaceReturn.order_id == order.id))
        )
        refunds = list(
            db.scalars(select(MarketplaceRefund).where(MarketplaceRefund.order_id == order.id))
        )
        result.append(
            {
                "id": order.id,
                "flipkart_order_id": order.remote_order_id,
                "status": order.status,
                "raw_status": order.remote_raw_status,
                "payment_status": order.payment_status,
                "fulfilment_status": order.fulfilment_status,
                "totals": order.totals_json,
                "ordered_at": order.ordered_at,
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
                        "remote_fulfilment_id": row.remote_fulfilment_id,
                    }
                    for row in fulfilments
                ],
                "cancellations": [
                    {"reference": row.marketplace_reference, "status": row.status}
                    for row in cancellations
                ],
                "returns": [
                    {"reference": row.marketplace_reference, "status": row.status}
                    for row in returns
                ],
                "refunds": [
                    {
                        "reference": row.marketplace_reference,
                        "amount": str(row.amount),
                        "currency": row.currency,
                    }
                    for row in refunds
                ],
            }
        )
    return result


@router.get("/accounts/{account_id}/fulfilments")
def list_fulfilments(
    account_id: uuid.UUID, db: DatabaseSession, user: Owner
) -> list[dict[str, object]]:
    account = _account(db, user, account_id)
    from vayujit_api.commerce.models import MarketplaceFulfilment

    rows = db.scalars(
        select(MarketplaceFulfilment)
        .join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceFulfilment.order_id)
        .where(MarketplaceFulfilment.owner_id == user.id, MarketplaceOrder.account_id == account.id)
        .order_by(MarketplaceFulfilment.updated_at.desc())
    )
    return [
        {
            "id": row.id,
            "order_id": row.order_id,
            "remote_fulfilment_id": row.remote_fulfilment_id,
            "status": row.status,
            "carrier": row.carrier,
            "tracking_reference": row.tracking_reference,
            "shipped_at": row.shipped_at,
            "delivered_at": row.delivered_at,
        }
        for row in rows
    ]


def _flipkart_drift(listing_id: uuid.UUID, db: Session, user: User) -> dict[str, object]:
    from vayujit_api.commerce.models import MarketplaceDriftRecord

    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "flipkart",
        )
    )
    if listing is None:
        raise HTTPException(404, "Flipkart listing was not found.")
    if not listing.remote_listing_id:
        return {
            "listing_id": listing.id,
            "drift_state": "none",
            "classification": "local_only",
            "fields": [],
        }
    account = _account(db, user, listing.account_id)
    remote = _connector(account).get_listing(listing.remote_listing_id)
    remote_status = str(remote.get("status", "unknown")).casefold()
    pairs: dict[str, tuple[object, object]] = {
        "status": (listing.status, remote_status),
        "seller_sku": (listing.marketplace_sku, remote.get("sku")),
        "title": (listing.title, remote.get("title")),
        "category": (listing.category, remote.get("category")),
        "inventory": (None, remote.get("quantity")),
    }
    fields: list[dict[str, object]] = []
    for name, (local_value, remote_value) in pairs.items():
        if local_value == remote_value:
            continue
        classification = (
            "missing_remote"
            if remote_value is None
            else ("remote_only" if local_value is None else "modified")
        )
        fields.append(
            {
                "path": name,
                "local": local_value,
                "remote": remote_value,
                "classification": classification,
            }
        )
        existing = db.scalar(
            select(MarketplaceDriftRecord).where(
                MarketplaceDriftRecord.owner_id == user.id,
                MarketplaceDriftRecord.listing_id == listing.id,
                MarketplaceDriftRecord.field_name == name,
                MarketplaceDriftRecord.state == "detected",
            )
        )
        if existing is None:
            db.add(
                MarketplaceDriftRecord(
                    owner_id=user.id,
                    listing_id=listing.id,
                    field_name=name,
                    local_value_json=local_value,
                    remote_value_json=remote_value,
                    state="detected",
                    created_at=now(),
                    updated_at=now(),
                )
            )
    listing.drift_state = "detected" if fields else "none"
    listing.last_synchronized_at = now()
    listing.updated_at = now()
    db.commit()
    return {
        "listing_id": listing.id,
        "drift_state": listing.drift_state,
        "classification": (
            "unchanged"
            if not fields
            else ("missing_remote" if remote_status == "unknown" else "modified")
        ),
        "fields": fields,
    }


@router.get("/listings/{listing_id}/drift")
def drift(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    return _flipkart_drift(listing_id, db, user)


@router.post("/listings/{listing_id}/drift/review")
def review_drift(listing_id: uuid.UUID, db: DatabaseSession, user: Owner) -> dict[str, object]:
    result = _flipkart_drift(listing_id, db, user)
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.drift_reviewed",
        entity_type="marketplace_listing",
        entity_id=listing_id,
        metadata={"field_count": len(cast(list[object], result["fields"]))},
    )
    db.commit()
    return result


@router.post("/listings/{listing_id}/drift/keep-remote")
def keep_remote_drift(
    listing_id: uuid.UUID, data: ConfirmRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(
            400, "Explicit confirmation is required to keep remote Flipkart changes."
        )
    result = _flipkart_drift(listing_id, db, user)
    from vayujit_api.commerce.models import MarketplaceDriftRecord

    rows = list(
        db.scalars(
            select(MarketplaceDriftRecord).where(
                MarketplaceDriftRecord.owner_id == user.id,
                MarketplaceDriftRecord.listing_id == listing_id,
                MarketplaceDriftRecord.state == "detected",
            )
        )
    )
    for row in rows:
        row.state = "resolved_keep_remote"
        row.resolved_at = now()
        row.updated_at = now()
    listing = db.get(MarketplaceListing, listing_id)
    if listing is not None:
        listing.drift_state = "remote_kept"
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.drift_kept_remote",
        entity_type="marketplace_listing",
        entity_id=listing_id,
        metadata={"field_count": len(rows)},
    )
    db.commit()
    return {"status": "succeeded", "action": "keep_remote", "fields": result["fields"]}


@router.post("/listings/{listing_id}/drift/overwrite")
def overwrite_drift(
    listing_id: uuid.UUID, data: ConfirmRequest, db: DatabaseSession, user: Owner
) -> dict[str, object]:
    if not data.confirm:
        raise HTTPException(400, "Explicit confirmation is required for Flipkart drift overwrite.")
    listing = db.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.owner_id == user.id,
            MarketplaceListing.marketplace == "flipkart",
        )
    )
    if listing is None or not listing.remote_listing_id:
        raise HTTPException(404, "Flipkart listing remote identifier was not found.")
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
    account = _account(db, user, listing.account_id)
    _require_enabled(account)
    result = _connector(account).update_listing(
        remote_id=listing.remote_listing_id, title=listing.title, sku=listing.marketplace_sku
    )
    if not result.get("status"):
        raise HTTPException(502, "Flipkart overwrite did not complete safely.")
    listing.drift_state = "none"
    record_event(
        db,
        actor_id=user.id,
        action="flipkart.drift_overwritten",
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
    return _flipkart_drift(listing_id, db, user)
