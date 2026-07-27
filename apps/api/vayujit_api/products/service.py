import re
import unicodedata
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now
from vayujit_api.products.models import Product, ProductStatus
from vayujit_api.products.schemas import ProductCreate, ProductUpdate


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def make_slug(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")
    if not slug:
        raise HTTPException(422, "Name must contain characters that can form a slug.")
    return slug[:160].rstrip("-")


def owned_brand(db: Session, owner_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    brand = db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == owner_id))
    if brand is None:
        raise HTTPException(404, "Brand not found.")
    return brand


def writable_brand(db: Session, owner_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    brand = owned_brand(db, owner_id, brand_id)
    if brand.status == BrandStatus.ARCHIVED.value:
        raise HTTPException(409, "Archived brands cannot receive products.")
    return brand


def resolve_create_brand(db: Session, owner: User, brand_id: uuid.UUID | None) -> Brand:
    if brand_id is not None:
        return writable_brand(db, owner.id, brand_id)
    brand = db.scalar(
        select(Brand).where(Brand.owner_id == owner.id, Brand.is_active_context.is_(True))
    )
    if brand is None:
        raise HTTPException(409, "Select an active brand before creating a product.")
    return writable_brand(db, owner.id, brand.id)


def owned_product(db: Session, owner_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.owner_id == owner_id)
    )
    if product is None:
        raise HTTPException(404, "Product not found.")
    return product


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            409, "A product with this name, slug, SKU, or barcode already exists."
        ) from error


def create_product(db: Session, owner: User, data: ProductCreate) -> Product:
    brand = resolve_create_brand(db, owner, data.brand_id)
    stamp = now()
    product = Product(
        owner_id=owner.id,
        brand_id=brand.id,
        name=data.name,
        normalized_name=normalize_name(data.name),
        slug=data.slug or make_slug(data.name),
        sku=data.sku,
        product_type=data.product_type,
        status=ProductStatus.DRAFT.value,
        short_description=data.short_description,
        description=data.description,
        category=data.category,
        tags=data.tags,
        price_amount=data.price_amount,
        price_currency=data.price_currency,
        compare_at_price_amount=data.compare_at_price_amount,
        cost_amount=data.cost_amount,
        tax_code=data.tax_code,
        barcode=data.barcode,
        weight_value=data.weight_value,
        weight_unit=data.weight_unit,
        inventory_tracking_enabled=data.inventory_tracking_enabled,
        inventory_quantity=data.inventory_quantity,
        low_stock_threshold=data.low_stock_threshold,
        is_featured=data.is_featured,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(product)
    try:
        db.flush()
        record_event(
            db,
            actor_id=owner.id,
            action="product.created",
            entity_type="product",
            entity_id=product.id,
            metadata={
                "brand_id": str(brand.id),
                "product_type": product.product_type,
                "sku_present": bool(product.sku),
            },
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            409, "A product with this name, slug, SKU, or barcode already exists."
        ) from error
    return product


def validate_combined_values(product: Product) -> None:
    if product.price_amount is not None and product.price_currency is None:
        raise HTTPException(422, "Currency is required when a price is supplied.")
    if product.compare_at_price_amount is not None:
        if product.price_amount is None:
            raise HTTPException(422, "Sale price is required with compare-at price.")
        if product.compare_at_price_amount < product.price_amount:
            raise HTTPException(422, "Compare-at price cannot be lower than sale price.")
    if product.weight_value is not None and product.weight_unit is None:
        raise HTTPException(422, "Weight unit is required when weight is supplied.")


def update_product(db: Session, owner: User, product: Product, data: ProductUpdate) -> Product:
    changes = data.model_dump(exclude_unset=True)
    changed_fields: list[str] = []
    previous_brand = product.brand_id
    required_fields = {
        "brand_id",
        "name",
        "slug",
        "product_type",
        "tags",
        "inventory_tracking_enabled",
        "inventory_quantity",
        "low_stock_threshold",
        "is_featured",
    }
    for key, value in changes.items():
        if key in required_fields and value is None:
            raise HTTPException(422, f"{key.replace('_', ' ').title()} cannot be null.")
        if key == "brand_id":
            writable_brand(db, owner.id, value)
        if key == "name":
            product.name = value
            product.normalized_name = normalize_name(value)
        else:
            setattr(product, key, value)
        changed_fields.append(key)
    validate_combined_values(product)
    if changed_fields:
        product.updated_at = now()
        if product.brand_id != previous_brand:
            record_event(
                db,
                actor_id=owner.id,
                action="product.brand_changed",
                entity_type="product",
                entity_id=product.id,
                metadata={
                    "previous_brand_id": str(previous_brand),
                    "brand_id": str(product.brand_id),
                },
            )
        record_event(
            db,
            actor_id=owner.id,
            action="product.updated",
            entity_type="product",
            entity_id=product.id,
            metadata={"changed_fields": sorted(changed_fields)},
        )
        commit_or_conflict(db)
    return product


def activation_errors(product: Product) -> list[str]:
    missing: list[str] = []
    if not (product.short_description or product.description):
        missing.append("description")
    if product.product_type in {"physical", "digital", "affiliate"}:
        if product.price_amount is None:
            missing.append("price_amount")
        if product.price_currency is None:
            missing.append("price_currency")
    return missing


def activate_product(db: Session, owner: User, product: Product) -> Product:
    if product.status == ProductStatus.ARCHIVED.value:
        raise HTTPException(409, "Restore archived products before activation.")
    writable_brand(db, owner.id, product.brand_id)
    fields = activation_errors(product)
    if fields:
        raise HTTPException(
            409,
            detail={
                "code": "product_not_ready",
                "message": "Product does not meet activation requirements.",
                "fields": fields,
            },
        )
    if product.status != ProductStatus.ACTIVE.value:
        previous = product.status
        product.status = ProductStatus.ACTIVE.value
        product.updated_at = now()
        record_event(
            db,
            actor_id=owner.id,
            action="product.activated",
            entity_type="product",
            entity_id=product.id,
            metadata={"previous_status": previous, "new_status": product.status},
        )
        db.commit()
    return product


def move_to_draft(db: Session, owner: User, product: Product) -> Product:
    if product.status == ProductStatus.ARCHIVED.value:
        raise HTTPException(409, "Restore archived products before moving them to draft.")
    if product.status != ProductStatus.DRAFT.value:
        previous = product.status
        product.status = ProductStatus.DRAFT.value
        product.updated_at = now()
        record_event(
            db,
            actor_id=owner.id,
            action="product.moved_to_draft",
            entity_type="product",
            entity_id=product.id,
            metadata={"previous_status": previous, "new_status": product.status},
        )
        db.commit()
    return product


def archive_product(db: Session, owner: User, product: Product) -> Product:
    if product.status == ProductStatus.ARCHIVED.value:
        return product
    previous = product.status
    product.status = ProductStatus.ARCHIVED.value
    product.archived_at = product.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="product.archived",
        entity_type="product",
        entity_id=product.id,
        metadata={"previous_status": previous, "new_status": product.status},
    )
    db.commit()
    return product


def restore_product(db: Session, owner: User, product: Product) -> Product:
    if product.status != ProductStatus.ARCHIVED.value:
        return product
    writable_brand(db, owner.id, product.brand_id)
    product.status = ProductStatus.DRAFT.value
    product.archived_at = None
    product.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="product.restored",
        entity_type="product",
        entity_id=product.id,
        metadata={"previous_status": "archived", "new_status": product.status},
    )
    db.commit()
    return product
