import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, desc, false, func, or_, select
from sqlalchemy.orm import Session

from vayujit_api.audit.models import AuditEvent
from vayujit_api.brands.models import Brand
from vayujit_api.core.database import get_session
from vayujit_api.identity.models import User
from vayujit_api.identity.router import current_user
from vayujit_api.products.models import Product, ProductStatus
from vayujit_api.products.schemas import (
    ProductAuditSummary,
    ProductCreate,
    ProductDetailsResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from vayujit_api.products.service import (
    activate_product,
    archive_product,
    create_product,
    move_to_draft,
    owned_brand,
    owned_product,
    restore_product,
    update_product,
)

router = APIRouter(prefix="/api/v1/products", tags=["products"])
DatabaseSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


def present(product: Product, brand_name: str) -> ProductResponse:
    values = {
        field: getattr(product, field)
        for field in ProductResponse.model_fields
        if field != "brand_name"
    }
    return ProductResponse.model_validate({**values, "brand_name": brand_name})


def present_owned(db: Session, owner: User, product: Product) -> ProductResponse:
    brand = owned_brand(db, owner.id, product.brand_id)
    return present(product, brand.name)


@router.get("", response_model=ProductListResponse)
def list_products(
    db: DatabaseSession,
    owner: CurrentUser,
    brand_id: uuid.UUID | None = None,
    all_brands: bool = False,
    include_archived: bool = False,
    search: Annotated[str | None, Query(max_length=160)] = None,
    sku: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    product_type: Literal["physical", "digital", "service", "affiliate"] | None = None,
    status: Literal["draft", "active", "archived"] | None = None,
    featured: bool | None = None,
    sort_by: Literal["name", "created_at", "updated_at", "price", "inventory_quantity"] = "name",
    sort_direction: Literal["asc", "desc"] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductListResponse:
    filters = [Product.owner_id == owner.id]
    if brand_id is not None:
        owned_brand(db, owner.id, brand_id)
        filters.append(Product.brand_id == brand_id)
    elif not all_brands:
        active_id = db.scalar(
            select(Brand.id).where(Brand.owner_id == owner.id, Brand.is_active_context.is_(True))
        )
        filters.append(Product.brand_id == active_id if active_id else false())
    if not include_archived:
        filters.append(Product.status != ProductStatus.ARCHIVED.value)
    if status:
        filters.append(Product.status == status)
    if product_type:
        filters.append(Product.product_type == product_type)
    if category:
        filters.append(func.lower(Product.category) == category.casefold())
    if featured is not None:
        filters.append(Product.is_featured.is_(featured))
    if search and search.strip():
        term = f"%{' '.join(search.casefold().split())}%"
        filters.append(
            or_(
                Product.normalized_name.like(term),
                func.lower(Product.sku).like(term),
            )
        )
    if sku and sku.strip():
        filters.append(func.lower(Product.sku).contains(sku.strip().casefold()))
    sort_columns = {
        "name": Product.name,
        "created_at": Product.created_at,
        "updated_at": Product.updated_at,
        "price": Product.price_amount,
        "inventory_quantity": Product.inventory_quantity,
    }
    direction = desc if sort_direction == "desc" else asc
    ordering = direction(sort_columns[sort_by]).nulls_last()
    total = db.scalar(select(func.count(Product.id)).where(*filters)) or 0
    rows = db.execute(
        select(Product, Brand.name)
        .join(Brand, Brand.id == Product.brand_id)
        .where(*filters)
        .order_by(ordering, Product.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProductListResponse(
        items=[present(product, brand_name) for product, brand_name in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=ProductResponse, status_code=201)
def create(data: ProductCreate, db: DatabaseSession, owner: CurrentUser) -> ProductResponse:
    return present_owned(db, owner, create_product(db, owner, data))


@router.get("/{product_id}", response_model=ProductDetailsResponse)
def get_product(
    product_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser
) -> ProductDetailsResponse:
    product = owned_product(db, owner.id, product_id)
    base = present_owned(db, owner, product)
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == "product", AuditEvent.entity_id == product.id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(10)
        )
    )
    return ProductDetailsResponse(
        **base.model_dump(),
        recent_audit_events=[
            ProductAuditSummary(action=event.action, occurred_at=event.occurred_at)
            for event in events
        ],
    )


@router.patch("/{product_id}", response_model=ProductResponse)
def patch_product(
    product_id: uuid.UUID, data: ProductUpdate, db: DatabaseSession, owner: CurrentUser
) -> ProductResponse:
    product = update_product(db, owner, owned_product(db, owner.id, product_id), data)
    return present_owned(db, owner, product)


@router.post("/{product_id}/activate", response_model=ProductResponse)
def activate(product_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> ProductResponse:
    product = activate_product(db, owner, owned_product(db, owner.id, product_id))
    return present_owned(db, owner, product)


@router.post("/{product_id}/move-to-draft", response_model=ProductResponse)
def draft(product_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> ProductResponse:
    product = move_to_draft(db, owner, owned_product(db, owner.id, product_id))
    return present_owned(db, owner, product)


@router.post("/{product_id}/archive", response_model=ProductResponse)
def archive(product_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> ProductResponse:
    product = archive_product(db, owner, owned_product(db, owner.id, product_id))
    return present_owned(db, owner, product)


@router.post("/{product_id}/restore", response_model=ProductResponse)
def restore(product_id: uuid.UUID, db: DatabaseSession, owner: CurrentUser) -> ProductResponse:
    product = restore_product(db, owner, owned_product(db, owner.id, product_id))
    return present_owned(db, owner, product)
