import re
import unicodedata
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vayujit_api.audit.service import record_event
from vayujit_api.brands.models import Brand, BrandStatus
from vayujit_api.brands.schemas import BrandCreate, BrandUpdate
from vayujit_api.identity.models import User
from vayujit_api.identity.service import now


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def make_slug(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")
    if not slug:
        raise HTTPException(422, "Name must contain characters that can form a slug.")
    return slug[:120].rstrip("-")


def owned_brand(db: Session, owner_id: uuid.UUID, brand_id: uuid.UUID) -> Brand:
    brand = db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == owner_id))
    if brand is None:
        raise HTTPException(404, "Brand not found.")
    return brand


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "A brand with this name or slug already exists.") from error


def lock_owner(db: Session, owner_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:owner_id, 0))"),
        {"owner_id": str(owner_id)},
    )


def create_brand(db: Session, owner: User, data: BrandCreate) -> Brand:
    stamp = now()
    lock_owner(db, owner.id)
    first = (db.scalar(select(func.count(Brand.id)).where(Brand.owner_id == owner.id)) or 0) == 0
    brand = Brand(
        owner_id=owner.id,
        name=data.name,
        normalized_name=normalize_name(data.name),
        slug=data.slug or make_slug(data.name),
        description=data.description,
        tagline=data.tagline,
        website_url=str(data.website_url) if data.website_url else None,
        primary_color=data.primary_color.upper() if data.primary_color else None,
        secondary_color=data.secondary_color.upper() if data.secondary_color else None,
        status=BrandStatus.ACTIVE.value,
        is_active_context=first,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(brand)
    try:
        db.flush()
        record_event(
            db,
            actor_id=owner.id,
            action="brand.created",
            entity_type="brand",
            entity_id=brand.id,
            metadata={"name": brand.name, "slug": brand.slug, "became_active": first},
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "A brand with this name or slug already exists.") from error
    return brand


def update_brand(db: Session, owner: User, brand: Brand, data: BrandUpdate) -> Brand:
    changes = data.model_dump(exclude_unset=True)
    changed_fields: list[str] = []
    for key, value in changes.items():
        if key in {"name", "slug"} and value is None:
            raise HTTPException(422, f"{key.replace('_', ' ').title()} cannot be null.")
        if key == "name":
            brand.name = value
            brand.normalized_name = normalize_name(value)
        elif key == "website_url":
            brand.website_url = str(value) if value else None
        elif key in {"primary_color", "secondary_color"}:
            setattr(brand, key, value.upper() if value else None)
        else:
            setattr(brand, key, value)
        changed_fields.append(key)
    if changed_fields:
        brand.updated_at = now()
        record_event(
            db,
            actor_id=owner.id,
            action="brand.updated",
            entity_type="brand",
            entity_id=brand.id,
            metadata={"changed_fields": sorted(changed_fields)},
        )
        commit_or_conflict(db)
    return brand


def archive_brand(db: Session, owner: User, brand: Brand) -> Brand:
    lock_owner(db, owner.id)
    db.refresh(brand)
    if brand.status == BrandStatus.ARCHIVED.value:
        return brand
    was_active = brand.is_active_context
    brand.status = BrandStatus.ARCHIVED.value
    brand.is_active_context = False
    brand.archived_at = brand.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="brand.archived",
        entity_type="brand",
        entity_id=brand.id,
        metadata={"cleared_active_context": was_active},
    )
    db.commit()
    return brand


def restore_brand(db: Session, owner: User, brand: Brand) -> Brand:
    if brand.status == BrandStatus.ACTIVE.value:
        return brand
    brand.status = BrandStatus.ACTIVE.value
    brand.archived_at = None
    brand.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="brand.restored",
        entity_type="brand",
        entity_id=brand.id,
    )
    db.commit()
    return brand


def activate_brand(db: Session, owner: User, brand: Brand) -> Brand:
    lock_owner(db, owner.id)
    db.refresh(brand)
    if brand.status == BrandStatus.ARCHIVED.value:
        raise HTTPException(409, "Archived brands cannot be activated.")
    db.execute(
        update(Brand)
        .where(Brand.owner_id == owner.id, Brand.id != brand.id)
        .values(is_active_context=False)
    )
    brand.is_active_context = True
    brand.updated_at = now()
    record_event(
        db,
        actor_id=owner.id,
        action="brand.active_changed",
        entity_type="brand",
        entity_id=brand.id,
        metadata={"active_brand_id": str(brand.id)},
    )
    db.commit()
    db.refresh(brand)
    return brand
